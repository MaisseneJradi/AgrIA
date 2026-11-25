"""Phyto plan, step 11: cut the 76 knowledge sheets into sections (symptomes, lutte, prevention, biologie, description,
repartition), by rules, for the retrieval of src/tools/rag.py.

    python src/preparation/build_sections.py
    -> data/processed/knowledge/sections.jsonl   one row per sheet and section: fiche, section, titre, texte, langue,
                                                 source, licence, regle (the rule that chose the section)

The sheets (build_knowledge_base.py) keep the article split of their source: description, symptomes, biologie, lutte,
repartition, with the source's own headings inside ("Symptoms", "Prophylaxie", "Management"...). Rules, in order:
  1. a heading line names the section of the paragraphs under it (HEADINGS), until the next heading;
  2. in a control text (field or heading), a SENTENCE that speaks of prevention more than of chemical control -> prevention;
  3. a paragraph of 'description' or 'biologie' with at least 2 distinct symptom words and more of them than
     biology words -> symptomes;
  4. otherwise the field it comes from.
Reference lists ("== References ==") and lists of host names are dropped. No text is written: paragraphs are quoted.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "processed" / "knowledge" / "fiches.jsonl"
OUT = ROOT / "data" / "processed" / "knowledge" / "sections.jsonl"
FIELDS = ("description", "symptomes", "biologie", "lutte", "repartition")
SECTIONS = ("description", "symptomes", "biologie", "lutte", "prevention", "repartition")

# heading (folded, without accents) -> section; None = drop what follows (references)
HEADINGS = [
    (r"^==\s*references?\s*==$|^references?$|^bibliograph|^liens externes|^notes et references", None),
    (r"prevention|prophylax|precaution", "prevention"),
    (r"lutte|management|treatment|control|traitement|fongicide|methodes? de|moyens? de", "lutte"),
    (r"symptom|degats|damage|signs|on note", "symptomes"),
    (r"repartition|distribution|geographic", "repartition"),
    (r"cycle|biolog|ecolog|epidemiolog|developpement|life|propagation|conditions favorables|hotes?|hosts?"
     r"|plantes?.hotes?|reproduction", "biologie"),
]
PREVENTION = (r"prevent|prophyla|rotation|assolement|resistant|tolerant|semences? saines?|plants? sains?|"
              r"healthy (?:seed|plant|transplant)|certified|certifie|sanitation|hygien|desinfect|eviter|avoid|"
              r"destruction des|detrui|remove|elimin|arrach|brul|burn|residus|debris|aeration|ventilat|drainage|"
              r"espacement|spacing|densite|weed|desherb|mauvaises herbes|taille|prun|filet|net|piege|trap|"
              r"irrigation|arrosage|watering|humidite|humidity")
CHEMICAL = (r"fongicide|fungicide|insecticide|acaricide|bactericide|pesticide|pulveris|spray|traitement chimique|"
            r"chemical|cuivre|copper|soufre|sulfur|bouillie|matiere active|active ingredient|produit|product|"
            r"\bdose|g/l|kg/ha|l/ha")
SYMPTOMS = (r"sympt|tache|spot|lesion|fletri|wilt|jauni|yellow|chloros|necros|desseche|dried|pourri|rot\b|rots\b|"
            r"deform|curl|enroul|galle|\bgall|chancre|canker|mosai|mottl|marbr|poudre blanche|powder|feutr|"
            r"degats|damage|galerie|mine\b|mines\b|defoliat|chute des feuilles|leaf drop|brunisse|brown|noirc|"
            r"blackened|exsud|ooz|gomme|gum")
BIOLOGY = (r"spore|cycle|hiver|overwinter|mycel|conidi|oeuf|egg|larv|nymph|adult|generation|temperature|"
           r"transmi|vecteur|vector|propag|dissemin|inocul|survi")


def fold(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def is_heading(line):
    s = line.strip()
    return bool(s) and len(s) < 70 and not re.search(r"[.!?;]$", s) and len(s.split()) <= 9


def heading_section(line):
    f = fold(line).rstrip(":").strip()
    for rx, sec in HEADINGS:
        if re.search(rx, f):
            return sec, True
    return None, False


def hits(rx, text):
    return len(set(m.group(0) for m in re.finditer(rx, fold(text))))


def sentences(text):
    return [x for x in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ýa-z0-9«(])", text) if x.strip()]


def classify(field, under, para):
    """[(section, rule, text)] of a paragraph: control texts are cut sentence by sentence (a sentence that speaks of
    prevention more than of chemical control is prevention); the other paragraphs keep one section."""
    sec = under or field
    if sec == "lutte":
        return [("prevention", "phrase : mots de prévention > mots de lutte chimique", s)
                if hits(PREVENTION, s) > hits(CHEMICAL, s) else ("lutte", "titre" if under else "champ de la fiche", s)
                for s in sentences(para)]
    if under:
        return [(under, "titre", para)]
    if field in ("description", "biologie"):
        sy, b = hits(SYMPTOMS, para), hits(BIOLOGY, para)
        if sy >= 2 and sy > b:
            return [("symptomes", "paragraphe : mots de symptômes", para)]
    return [(field, "champ de la fiche", para)]


def split_sheet(sheet):
    out = []
    for field in FIELDS:
        text = sheet.get(field) or ""
        if not text.strip() or text.strip() == "None":
            continue
        under, title, dropped = None, "", False
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if is_heading(line):
                sec, known = heading_section(line)
                if known:
                    under, title, dropped = sec, line, sec is None
                    continue
                if dropped or len(line) < 40:  # list items (hosts), unknown headings: kept with the next paragraph
                    continue
            if dropped:
                continue
            for sec, rule, piece in classify(field, under, line):
                out.append({"fiche": sheet["id"], "nom": sheet["nom"], "section": sec, "titre": title,
                            "texte": piece, "regle": rule})
    # one section per sheet and kind, its pieces in the order of the sheet
    merged = {}
    for p in out:
        m = merged.setdefault(p["section"], {**p, "titre": [], "texte": [], "regle": []})
        m["texte"].append(p["texte"])
        for k in ("titre", "regle"):
            if p[k] and p[k] not in m[k]:
                m[k].append(p[k])
    return [{**m, "texte": " ".join(m["texte"]), "titre": " | ".join(m["titre"]), "regle": " | ".join(m["regle"])}
            for sec in SECTIONS for m in [merged.get(sec)] if m]


def main():
    sheets = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    rows = []
    for s in sheets:
        for p in split_sheet(s):
            p.update({"langue": s.get("langue_texte"), "source": s.get("source_texte"),
                      "licence": s.get("licence_texte"), "cultures": s.get("cultures"),
                      "nom_scientifique": s.get("nom_scientifique"), "classes": s.get("classes_modele") or []})
            rows.append(p)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    per = Counter(r["section"] for r in rows)
    sheets_with = {sec: len({r["fiche"] for r in rows if r["section"] == sec}) for sec in SECTIONS}
    print(f"{len(sheets)} fiches -> {len(rows)} sections -> {OUT.relative_to(ROOT)}")
    for sec in SECTIONS:
        print(f"  {sec:12s} {per[sec]:4d} blocs, {sheets_with[sec]:3d} fiches")
    print("  règles :", dict(Counter(x for r in rows for x in r["regle"].split(" | "))))
    empty = [s["id"] for s in sheets if not any(r["fiche"] == s["id"] for r in rows)]
    print("  fiches sans texte :", empty)


if __name__ == "__main__":
    sys.exit(main())
