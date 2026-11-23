"""Tunisian field test set from the app's test mode (step 9 of the improvement plan).

The app (AGRIA_JOURNAL=1) keeps each analysis in data/journal/<id>.jpg + .json; the tester answers "is it correct?",
gives the right answer, and ticks "AgrIA may keep this photo" (avis.garder_photo). Only ticked photos ever leave the
journal.

1. export   writes data/field_tn/review_<date>.csv: one row per kept photo with the tester's feedback (path, crop,
            governorate, month, what the model said, the right answer in the tester's words) and two empty columns
            to fill by hand: `label` (class code of the task, e.g. tomato__septoria_leaf_spot) and `valide` (oui).
            Photos already frozen are not exported again.
2. freeze   reads a reviewed CSV and copies the rows with valide = oui and a known `label` to
            data/field_tn/images/<task>/<label>/<id>.jpg, appending them to data/field_tn/manifest.csv with their md5.
            Rows already in the manifest are never changed or removed (a frozen test set), and a photo whose md5 is
            already frozen is refused.
3. verify   checks that every frozen photo is still there with the same md5 (exit 1 otherwise).

These photos are a TEST set only: load_split(task, "field_tn") reads them and src/evaluation/leakage.py checks that
no training image is one of them. Never train on them.

Usage:
  python src/preparation/field_tn.py export
  python src/preparation/field_tn.py freeze data/field_tn/review_2026-11-22.csv
  python src/preparation/field_tn.py verify
  python src/vision/evaluate.py --task diseases --splits field_tn
"""
import argparse
import csv
import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "data" / "journal"
OUT = ROOT / "data" / "field_tn"
MANIFEST_COLS = ["id", "task", "label", "crop", "file", "md5", "gouvernorat", "mois", "added"]
REVIEW_COLS = ["id", "photo", "culture_saisie", "gouvernorat", "mois", "date", "modele_tache", "modele_classe",
               "modele_confiance", "correct", "vraie_reponse", "label", "valide"]


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def read_manifest(out=OUT):
    f = out / "manifest.csv"
    if not f.exists():
        return []
    with open(f, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def kept_records(journal=JOURNAL):
    """Journal analyses with a photo, a feedback and the tester's consent to keep the photo."""
    for f in sorted(journal.glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        avis = rec.get("avis") or {}
        photo = f.with_suffix(".jpg")
        if avis.get("garder_photo") is True and photo.exists():
            yield rec, photo


def export(journal=JOURNAL, out=OUT, today=None):
    frozen = {r["id"] for r in read_manifest(out)}
    rows = []
    for rec, photo in kept_records(journal):
        if rec["id"] in frozen:
            continue
        e, d, a = rec.get("entree") or {}, rec.get("diagnostic") or {}, rec["avis"]
        rows.append({"id": rec["id"], "photo": str(photo), "culture_saisie": e.get("culture") or "",
                     "gouvernorat": e.get("gouvernorat") or "", "mois": e.get("mois") or "",
                     "date": a.get("date") or "", "modele_tache": d.get("task") or "",
                     "modele_classe": d.get("classe") or "", "modele_confiance": d.get("confiance") or "",
                     "correct": "oui" if a.get("correct") else "non", "vraie_reponse": a.get("vraie_reponse") or "",
                     "label": (d.get("classe") or "") if a.get("correct") else "", "valide": ""})
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"review_{today or datetime.date.today().isoformat()}.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, REVIEW_COLS)
        w.writeheader()
        w.writerows(rows)
    return path, len(rows)


def task_classes():
    out = {}
    for task in ("diseases", "deficiency", "fruits", "leaf", "crop"):
        f = ROOT / "models" / task / "labels.json"
        if f.exists():
            out[task] = set(json.loads(f.read_text(encoding="utf-8")))
    return out


def task_of(label, classes):
    """The task whose classes hold `label` (diseases first: the main disease model)."""
    for task in ("diseases", "deficiency", "fruits", "crop"):
        if label in classes.get(task, ()):
            return task
    return None


def freeze(review_csv, out=OUT, classes=None, today=None):
    classes = classes if classes is not None else task_classes()
    old = read_manifest(out)
    ids, hashes = {r["id"] for r in old}, {r["md5"] for r in old}
    with open(review_csv, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    added, refused = [], []
    for r in rows:
        if r.get("valide", "").strip().lower() != "oui":
            continue
        label = r.get("label", "").strip()
        task = task_of(label, classes)
        if task is None:
            refused.append((r["id"], f"classe inconnue {label!r}"))
            continue
        if r["id"] in ids:
            refused.append((r["id"], "déjà gelée"))
            continue
        h = md5(r["photo"])
        if h in hashes:
            refused.append((r["id"], "même photo déjà gelée"))
            continue
        rel = Path("images") / task / label / f"{r['id']}.jpg"
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(r["photo"], out / rel)
        added.append({"id": r["id"], "task": task, "label": label, "crop": label.split("__")[0],
                      "file": rel.as_posix(), "md5": h, "gouvernorat": r.get("gouvernorat", ""),
                      "mois": r.get("mois", ""), "added": today or datetime.date.today().isoformat()})
        ids.add(r["id"])
        hashes.add(h)
    if added:
        f = out / "manifest.csv"
        new = not f.exists()
        with open(f, "a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, MANIFEST_COLS)
            if new:
                w.writeheader()
            w.writerows(added)
    return added, refused


def verify(out=OUT):
    """Frozen photos missing or changed since they were frozen."""
    bad = []
    for r in read_manifest(out):
        p = out / r["file"]
        if not p.exists():
            bad.append((r["id"], "absente"))
        elif md5(p) != r["md5"]:
            bad.append((r["id"], "modifiée"))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export")
    fz = sub.add_parser("freeze")
    fz.add_argument("review_csv")
    sub.add_parser("verify")
    a = ap.parse_args()
    if a.cmd == "export":
        path, n = export()
        print(f"{n} photos gardées avec accord à relire : {path}")
        print("Remplir `label` (code de classe) et `valide` (oui), puis : python src/preparation/field_tn.py freeze "
              + str(path.relative_to(ROOT)).replace("\\", "/"))
    elif a.cmd == "freeze":
        added, refused = freeze(a.review_csv)
        print(f"{len(added)} photos ajoutées au jeu de test tunisien gelé ({OUT / 'manifest.csv'})")
        for i, why in refused:
            print(f"  refusée {i} : {why}")
    else:
        bad = verify()
        n = len(read_manifest())
        print(f"{n} photos gelées, {len(bad)} problèmes")
        for i, why in bad:
            print(f"  {i} : {why}")
        sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
