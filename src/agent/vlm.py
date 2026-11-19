"""Vision-language model (VLM) of NVIDIA build: an OBSERVER, one of the opinions combined by the agents.

In one call it tells what it sees on a leaf photo: the crop (one of the 14 crops of AgrIA or "other") and the kind of
problem (healthy, disease, pest, deficiency), each with a confidence, and a few words on the symptoms. It never names a
disease, a product or a dose: those come from the trained models and the official lists.
Why: the trained models learnt partly the photo style of each source (results_vision.md, section 12); a large VLM
recognises a leaf by its shape and a deficiency by its colour pattern whatever the background.

Configuration (nothing is sent without it):
  AGRIA_VLM=nvidia            turn the observer on (the photo, reduced to 512 px, is sent to NVIDIA)
  NVIDIA_API_KEY=nvapi-...    key of build.nvidia.com, in the environment or in D:\\AgrIA\\.env (ignored by Git)
  AGRIA_VLM_MODEL=...         model name (default DEFAULT_MODEL); python src/agent/vlm.py --models lists them
Endpoint: https://integrate.api.nvidia.com/v1/chat/completions (OpenAI-compatible), image as a base64 data URL.
Answers are cached by photo content (data/processed/vlm_cache.jsonl): a photo is never sent twice for one model.
Any failure (no key, network, quota, unreadable answer) returns None: the agents then combine the trained models only.
"""
import base64
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"  # reasoning model: needs room to think (max_tokens)
CACHE = ROOT / "data" / "processed" / "vlm_cache.jsonl"
PROMPT_VERSION = 2
CROPS = {"tomato": "tomato", "olive": "olive tree", "citrus": "citrus (orange, lemon, mandarin)", "pepper": "pepper",
         "potato": "potato", "grape": "grapevine", "datepalm": "date palm", "wheat": "wheat", "corn": "maize",
         "apple": "apple tree", "peach": "peach tree", "cherry": "cherry tree", "strawberry": "strawberry",
         "squash": "squash / zucchini"}
PROBLEMS = ("healthy", "disease", "pest", "deficiency")
PROMPT = (
    "You are an agronomist. Look at the leaf (or leaves) in this photo.\n"
    "1. Which plant is it? Judge by the leaf shape, margin, venation and texture, not by the background or the "
    "spots. Choose one of: " + "; ".join(f"{k} = {v}" for k, v in CROPS.items()) + "; or other.\n"
    "2. What kind of problem does the leaf show? healthy = no symptom; disease = spots, lesions with a border, "
    "mould, powder, rust pustules, rot, galls, mosaic or curling from a virus; pest = insect damage, mines, holes, "
    "mites, scales; deficiency = yellowing or discoloration without spots or lesions (uniform, between the veins, "
    "along the margins, purple tint).\n"
    "Answer ONLY with a JSON object: {\"crop\": \"...\", \"crop_confidence\": 0 to 1, \"problem\": \"healthy\" or "
    "\"disease\" or \"pest\" or \"deficiency\", \"problem_confidence\": 0 to 1, \"symptoms\": \"a few words\"}.")
_lock = threading.Lock()


def _key():
    key = os.environ.get("NVIDIA_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("NVIDIA_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    return key or None


def enabled():
    return os.environ.get("AGRIA_VLM") == "nvidia" and _key() is not None


def _image_data_url(photo, side=512):
    with Image.open(photo) as im:
        im = im.convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def _conf(v):
    try:
        return round(min(max(float(v), 0.0), 1.0), 3)
    except (TypeError, ValueError):
        return 0.0


def _parse(text):
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    crop = str(d.get("crop", "")).strip().lower()
    problem = str(d.get("problem", "")).strip().lower()
    return {"culture": crop if crop in CROPS else "autre_plante", "conf_culture": _conf(d.get("crop_confidence")),
            "probleme": problem if problem in PROBLEMS else None, "conf_probleme": _conf(d.get("problem_confidence")),
            "symptomes": str(d.get("symptoms", ""))[:200]}


def _cache_key(photo, model):
    with open(photo, "rb") as f:
        return f"{hashlib.md5(f.read()).hexdigest()}|{model}|v{PROMPT_VERSION}"


def _cache_get(key):
    if not CACHE.exists():
        return None
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["key"] == key:
            return r["answer"]
    return None


def _cache_put(key, answer):
    with _lock:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "answer": answer}, ensure_ascii=False) + "\n")


def observe(photo, model=None, timeout=120):
    """{"culture", "conf_culture", "probleme", "conf_probleme", "symptomes", "modele"} or None."""
    key = _key()
    if not key:
        observe.last_error = "NVIDIA_API_KEY absente"
        return None
    model = model or os.environ.get("AGRIA_VLM_MODEL", DEFAULT_MODEL)
    ck = _cache_key(photo, model)
    cached = _cache_get(ck)
    if cached:
        return cached
    body = {"model": model, "max_tokens": 3000, "temperature": 0.0,  # reasoning models think before the JSON
            "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                      {"type": "image_url", "image_url": {"url": _image_data_url(photo)}}]}]}
    try:
        for attempt in range(4):  # free tier: "429 Too Many Requests" -> wait and retry
            r = requests.post(f"{URL}/chat/completions", json=body, timeout=timeout,
                              headers={"Authorization": f"Bearer {key}", "Accept": "application/json"})
            if r.status_code != 429:
                break
            time.sleep(10 * (attempt + 1))
        r.raise_for_status()
        out = _parse(r.json()["choices"][0]["message"]["content"])
    except Exception as e:  # network, quota, model not available to this key...
        observe.last_error = f"{type(e).__name__}: {str(e)[:150]}"
        return None
    if out is None:
        observe.last_error = "réponse illisible"
        return None
    out["modele"] = model
    _cache_put(ck, out)
    return out


observe.last_error = None


def list_models():
    r = requests.get(f"{URL}/models", headers={"Authorization": f"Bearer {_key()}"}, timeout=30)
    r.raise_for_status()
    return sorted(m["id"] for m in r.json().get("data", []))


if __name__ == "__main__":
    if not _key():
        sys.exit("NVIDIA_API_KEY absente : la définir dans l'environnement ou dans D:\\AgrIA\\.env")
    if "--models" in sys.argv:
        names = list_models()
        print("\n".join(n for n in names if any(w in n for w in ("vision", "vl", "multimodal", "gemma", "phi", "kimi",
                                                                   "llama-4", "nemotron-nano"))))
    else:
        print(observe(sys.argv[1]), observe.last_error or "")
