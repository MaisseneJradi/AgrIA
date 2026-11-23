"""AgrIA API: the seven agents behind one HTTP endpoint, and the web app served on the same address.

Run:   python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
Open:  http://localhost:8000          the app (phone: http://<IP of the computer>:8000 on the same Wi-Fi)
       http://localhost:8000/docs     interactive documentation, to try /diagnose with a photo

  POST /identify      form-data: photo -> the crop seen on a leaf photo (Identification agent): proposed crop,
                      confidence, top 3; the app pre-fills its crop field with it, the farmer confirms or corrects
  GET  /cultures      the 14 crops of AgrIA (code, French, Arabic) for the crop field
  POST /diagnose      form-data: photo (image, optional), message, gouvernorat, culture, langue (fr | ar), mois,
                      and the optional context of the plot: days_to_harvest (0-365), market (local | export),
                      organic (oui | non), greenhouse (oui | non), stage (early | spread), last_treatment_group, area (ha)
                      -> the answer of the agents: issue, texte, langue, diagnostic, produits, engrais,
                         avertissements, questions, questions_contexte (context fields to ask the farmer for, at most
                         3, only when the answer would change), contexte, sources, verification, trace, duree_s
  GET  /gouvernorats  the 24 governorates (French and Arabic names) for the app
  GET  /health        models loaded, device

  POST /feedback      form-data: journal_id, correct (oui | non), vraie_reponse, garder_photo (oui | non, default
                      non: the tester's consent to keep the photo for the Tunisian test set) -> stored with the analysis

Privacy: the photo is written to a temporary file for the models and deleted right after; nothing is stored.
Test mode only (AGRIA_JOURNAL=1, never for real users without their consent): every analysis is kept in
data/journal/<id>.jpg + <id>.json (inputs, what each model saw, top 3, answer) with the tester's feedback, to find
why the models fail on real photos and to build the Tunisian test set. data/ is outside Git.
One analysis at a time (a lock): the 4 GB GPU holds the models of one request.
"""
import datetime
import json
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from src.agent import paths  # noqa: F401
from src.agent.agents.identification import recognise
from src.agent.graph import build, diagnose
from src.agent.redaction import GOV_AR

CROPS = [("tomato", "Tomate", "طماطم"), ("olive", "Olivier", "زيتون"), ("citrus", "Agrumes", "قوارص"),
         ("pepper", "Poivron / piment", "فلفل"), ("potato", "Pomme de terre", "بطاطا"), ("grape", "Vigne", "عنب"),
         ("datepalm", "Palmier dattier", "نخيل التمر"), ("wheat", "Blé", "قمح"), ("corn", "Maïs", "ذرة"),
         ("apple", "Pommier", "تفاح"), ("peach", "Pêcher", "خوخ"), ("cherry", "Cerisier", "كرز"),
         ("strawberry", "Fraisier", "فراولة"), ("squash", "Courge", "قرع")]

APP_DIR = Path(__file__).resolve().parents[1] / "app"
JOURNAL_DIR = Path(__file__).resolve().parents[2] / "data" / "journal"


def journal_on():
    return os.environ.get("AGRIA_JOURNAL") == "1"
MAX_BYTES = 10 * 2**20
FORMATS = {"JPEG", "PNG", "WEBP"}
_lock = threading.Lock()

app = FastAPI(title="AgrIA", version="1.0",
              description="Diagnostic des plantes pour les agriculteurs tunisiens : six agents, réponses en français "
                          "ou en arabe, uniquement des produits homologués en Tunisie.")


@app.on_event("startup")
def warm_up():
    """Load the graph and the four models once, so the first farmer does not wait for them."""
    build()
    import predict  # src/vision
    for task in ("routing", "diseases", "deficiency", "fruits", "leaf", "crop"):
        if (Path(predict.ROOT) / "models" / task / "model.pt").exists():
            predict._get(task)


@app.get("/health")
def health():
    import predict
    return {"statut": "ok", "modeles": sorted(predict._CACHE), "device": str(predict._DEVICE)}


@app.get("/gouvernorats")
def gouvernorats():
    return [{"fr": fr, "ar": ar} for fr, ar in sorted(GOV_AR.items())]


@app.get("/cultures")
def cultures():
    return [{"code": c, "fr": fr, "ar": ar} for c, fr, ar in CROPS]


def _save_photo(photo):
    """Uploaded photo -> temporary file path (checked: size, format, readable). The caller deletes it."""
    data = photo.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "photo trop lourde (10 Mo au plus)")
    with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with Image.open(path) as im:
            if im.format not in FORMATS:
                raise HTTPException(415, "format accepté : JPEG, PNG ou WEBP")
            im.verify()
    except (UnidentifiedImageError, OSError):
        os.unlink(path)
        raise HTTPException(415, "ce fichier n'est pas une image lisible")
    except HTTPException:
        os.unlink(path)
        raise
    return path


@app.post("/identify")
def identify(photo: UploadFile = File(...)):
    path = _save_photo(photo)
    try:
        with _lock:
            r = recognise(path)
    finally:
        os.unlink(path)
    names = {c: (fr, ar) for c, fr, ar in CROPS}
    out = {"feuille": r["feuille"], "photo_plante": r["photo_plante"], "routage": r["routage"]["class"]}
    if "predite" in r:
        fr, ar = names.get(r["predite"], ("Autre plante", "نبتة أخرى"))
        out.update(culture=r["predite"], fr=fr, ar=ar, confiance=r["confiance"], sure=r["sure"],
                   autre_plante=r["autre_plante"], avis=r["avis"], accord=r["accord"], n_avis=r["n_avis"],
                   vlm=(r["opinions"] or {}).get("vlm"), source_culture=r["source_culture"],
                   desaccord_vlm=r["desaccord_vlm"],
                   top3=[{"code": c, "fr": names.get(c, ("Autre plante", ""))[0], "confiance": round(q, 4)}
                         for c, q in r["top3"]])
    return out


CHOICES = {"market": ("local", "export"), "organic": ("oui", "non"), "greenhouse": ("oui", "non"),
           "stage": ("early", "spread")}


def _context(days_to_harvest, market, organic, greenhouse, stage, last_treatment_group, area):
    """Optional context of the plot, checked; empty fields are left out (the agents ask when it matters)."""
    ctx = {"market": market, "organic": organic, "greenhouse": greenhouse, "stage": stage}
    for k, v in ctx.items():
        if v not in (None, "") and v not in CHOICES[k]:
            raise HTTPException(422, f"{k} : {' ou '.join(CHOICES[k])}")
    if days_to_harvest is not None and not 0 <= days_to_harvest <= 365:
        raise HTTPException(422, "days_to_harvest : de 0 à 365 jours")
    if area is not None and not 0 < area <= 10000:
        raise HTTPException(422, "area : surface en hectares, supérieure à 0")
    ctx.update(days_to_harvest=days_to_harvest, area=area,
               last_treatment_group=(last_treatment_group or "").strip()[:80] or None)
    return {k: v for k, v in ctx.items() if v not in (None, "")}


@app.post("/diagnose")
def diagnose_endpoint(photo: UploadFile = File(None), message: str = Form(""), gouvernorat: str = Form(None),
                      culture: str = Form(None), langue: str = Form(None), mois: int = Form(None),
                      days_to_harvest: int = Form(None), market: str = Form(None), organic: str = Form(None),
                      greenhouse: str = Form(None), stage: str = Form(None), last_treatment_group: str = Form(None),
                      area: float = Form(None)):
    if langue not in (None, "", "fr", "ar"):
        raise HTTPException(422, "langue : 'fr' ou 'ar'")
    if mois is not None and not 1 <= mois <= 12:
        raise HTTPException(422, "mois : de 1 à 12")
    contexte = _context(days_to_harvest, market, organic, greenhouse, stage, last_treatment_group, area)
    path = _save_photo(photo) if photo is not None and photo.filename else None
    try:
        with _lock:
            answer = diagnose(path, message or "", gouvernorat or None, culture or None, langue or None, mois,
                              contexte)
        if journal_on():
            answer["journal_id"] = keep_in_journal(path, answer, {
                "message": message, "gouvernorat": gouvernorat, "culture": culture, "langue": langue, "mois": mois,
                "contexte": contexte, "fichier": photo.filename if photo is not None else None})
        return answer
    finally:
        if path:
            os.unlink(path)


def keep_in_journal(path, answer, inputs):
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    jid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    if path:
        with Image.open(path) as im:
            im.convert("RGB").save(JOURNAL_DIR / f"{jid}.jpg", quality=92)
    record = {"id": jid, "entree": inputs, "issue": answer["issue"], "diagnostic": answer["diagnostic"],
              "produits": [p["nom"] for p in answer["produits"]], "texte": answer["texte"], "avis": None}
    (JOURNAL_DIR / f"{jid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return jid


@app.post("/feedback")
def feedback(journal_id: str = Form(...), correct: str = Form(...), vraie_reponse: str = Form(""),
             garder_photo: str = Form("non")):
    if not journal_on():
        raise HTTPException(404, "journal désactivé")
    if not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", journal_id):
        raise HTTPException(422, "journal_id invalide")
    f = JOURNAL_DIR / f"{journal_id}.json"
    if not f.exists():
        raise HTTPException(404, "analyse inconnue")
    record = json.loads(f.read_text(encoding="utf-8"))
    record["avis"] = {"correct": correct == "oui", "vraie_reponse": vraie_reponse.strip() or None,
                      "garder_photo": garder_photo == "oui",
                      "date": datetime.datetime.now().isoformat(timespec="seconds")}
    f.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"statut": "enregistré"}


@app.get("/")
def index():
    return FileResponse(APP_DIR / "index.html")


app.mount("/", StaticFiles(directory=APP_DIR), name="app")
