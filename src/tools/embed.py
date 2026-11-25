"""Local multilingual sentence vectors for the retrieval of the knowledge sheets (phyto plan, step 11).

  encode(["comment lutter contre le mildiou"], "e5-small", kind="query") -> np.ndarray (n, d), L2-normalised
  available("bge-m3") -> True when the model is in the local Hugging Face cache

Two models, read from the local cache only (local_files_only: nothing is downloaded while AgrIA answers):
  e5-small  intfloat/multilingual-e5-small  (118 M parameters, mean pooling, "query: " / "passage: " prefixes)
  bge-m3    BAAI/bge-m3                     (568 M parameters, CLS pooling)
Device: AGRIA_RAG_DEVICE (default "cpu": the GPU stays for the vision models; "cuda" when free).
"""
import os

os.environ.setdefault("USE_TF", "0")  # transformers must not load TensorFlow (slow start)
from functools import lru_cache

import numpy as np

MODELS = {"e5-small": {"repo": "intfloat/multilingual-e5-small", "pool": "mean", "query": "query: ",
                       "passage": "passage: ", "max_len": 512},
          "bge-m3": {"repo": "BAAI/bge-m3", "pool": "cls", "query": "", "passage": "", "max_len": 1024}}


def device():
    want = os.environ.get("AGRIA_RAG_DEVICE", "cpu")
    if want == "cuda":
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    return "cpu"


def available(name):
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(MODELS[name]["repo"], local_files_only=True)
        return True
    except Exception:
        return False


@lru_cache(maxsize=2)
def _load(name):
    import torch
    from transformers import AutoModel, AutoTokenizer
    m = MODELS[name]
    tok = AutoTokenizer.from_pretrained(m["repo"], local_files_only=True)
    model = AutoModel.from_pretrained(m["repo"], local_files_only=True).to(device()).eval()
    torch.set_grad_enabled(False)
    return tok, model


def encode(texts, name="e5-small", kind="passage", batch=16):
    import torch
    m = MODELS[name]
    tok, model = _load(name)
    out = []
    for i in range(0, len(texts), batch):
        chunk = [m[kind] + t for t in texts[i:i + batch]]
        enc = tok(chunk, padding=True, truncation=True, max_length=m["max_len"], return_tensors="pt").to(model.device)
        with torch.no_grad():
            h = model(**enc).last_hidden_state
        if m["pool"] == "cls":
            v = h[:, 0]
        else:
            mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
            v = (h * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        v = torch.nn.functional.normalize(v, dim=-1)
        out.append(v.float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 1), dtype=np.float32)
