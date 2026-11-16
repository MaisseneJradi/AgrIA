"""Fertilizers for a deficiency seen by the model, with how much the diagnosis can be trusted on that crop and soil.

  get_fertilizers("Fe_deficiency", crop="olivier", governorate="Kairouan")
  -> {"carence": "Fe_deficiency", "nutriment": "Fe", "fiabilite": "hypothese", "culture_vue": False,
      "message": "...", "questions_confirmation": [...], "sol": {"pH": 8.1, "regle": "phh2o_pH >= 7.8",
      "favorable_a_la_carence": True, ...}, "produits": [{"nom": ..., "teneur_pct": ..., "doses": [...]}, ...]}

fiabilite: "fiable" (deficiency seen on many crops), "limite" (few crops), "mono_culture" (one crop), or
"hypothese" when the crop of the farmer was never seen with this deficiency in training (results_vision.md, H2):
then the agent presents it as a hypothesis, asks the confirmation questions and checks the soil before any product.
Products: agriclic and agrishop shops; "preuve" = composition (content read in the composition) or nom (deduced from
the name only). Products with less than 1 % of the nutrient (biostimulants with traces) last; then for Fe on a
calcareous soil (pH >= 7.8) chelates EDDHA first, the only ones that stay available at that pH; then composition
before name, then the highest content.
avertissement_modele: known confusions of the deficiency model measured in step 2 (results_vision.md, H2).
"""
import json
import operator
import re

from common import governorate as gov_name
from common import query
from lexicon import crop_code

SOIL_COLUMNS = {"phh2o_pH": "pH", "sand_%": "sable_pct", "clay_%": "argile_pct", "soc_g/kg": "carbone_g_kg"}
OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt}
SEEN_OK = "conseil possible, en rappelant que la photo ne remplace pas une analyse de sol ou de feuille"
MODEL_WARNINGS = {
    ("Zn_deficiency", "pepper"): "en test, 48 poivrons sains sur 123 ont été classés carence en zinc : confirmer par "
                                 "les questions avant tout engrais (results_vision.md, H2)",
    ("Mn_deficiency", None): "hors palmier dattier, le modèle ne reconnaît la carence en manganèse que dans 58 % des "
                             "cas (results_vision.md, H2)",
}


def _class(deficiency):
    d = deficiency.strip()
    if d.lower() in ("healthy", "sain"):
        return "healthy"
    d = d if d.endswith("_deficiency") else f"{d}_deficiency"
    return d[0].upper() + d[1:]


def _soil(governorate, rule):
    name = gov_name(governorate)
    row = query("SELECT * FROM sols WHERE gouvernorat = ?", (name,))[0]
    soil = {"gouvernorat": name, "texture": row["texture"],
            **{v: row[k] for k, v in SOIL_COLUMNS.items()},
            "risque_chlorose_ferrique": bool(row["risque_chlorose_ferrique"]),
            "source": "SoilGrids 0-30 cm, médiane autour du chef-lieu (context/sols.csv)",
            "regle": rule, "favorable_a_la_carence": None}
    m = re.fullmatch(r"\s*(\S+)\s*(>=|<=|>|<)\s*([\d.]+)\s*", rule or "")
    if m and m.group(1) in row and row[m.group(1)] is not None:
        soil["favorable_a_la_carence"] = OPS[m.group(2)](float(row[m.group(1)]), float(m.group(3)))
    return soil


def _doses(source, pid, usages_text):
    if source == "agriclic":
        rows = query("SELECT contexte, culture, dose FROM engrais_usages WHERE id = ?", (int(pid),))
        out = [" · ".join(str(x) for x in (r["contexte"], r["culture"], r["dose"]) if x and str(x) != "nan")
               for r in rows]
        if out:
            return out
    return [usages_text[:300]] if usages_text and str(usages_text) != "nan" else []


def get_fertilizers(deficiency, crop=None, governorate=None, max_products=5):
    cls = _class(deficiency)
    if cls == "healthy":
        return {"carence": "healthy", "nutriment": None, "fiabilite": None, "culture_vue": None,
                "message": "aucune carence détectée : pas d'engrais correcteur à conseiller", "produits": [],
                "questions_confirmation": [], "sol": None}
    found = query("SELECT regle FROM regles_carences WHERE unified_class = ?", (cls,))
    if not found:
        raise ValueError(f"carence inconnue : {deficiency!r}")
    rule = json.loads(found[0]["regle"])
    code = crop_code(crop) if crop else None
    if crop and code is None:
        raise ValueError(f"culture inconnue : {crop!r}")
    seen = None if code is None else code in rule["cultures_vues"]
    soil = _soil(governorate, rule.get("regle_sol")) if governorate else None

    rows = query("SELECT c.*, e.usages FROM carence_engrais c LEFT JOIN engrais_catalogue e "
                 "ON e.source = c.source AND CAST(e.id_source AS TEXT) = CAST(c.id AS TEXT) "
                 "WHERE c.unified_class = ?", (cls,))
    rows = [r for r in rows if str(r["actif"]) not in ("0", "False")]
    eddha_first = cls == "Fe_deficiency" and soil is not None and (soil["pH"] or 0) >= 7.8

    def key(r):
        trace = r["teneur_pct"] is not None and r["teneur_pct"] < 1
        return (trace, eddha_first and r["chelate"] != "EDDHA", r["preuve"] != "composition", -(r["teneur_pct"] or 0))

    products, names = [], set()
    for r in sorted(rows, key=key):
        if r["nom"].lower() in names:
            continue
        names.add(r["nom"].lower())
        products.append({"nom": r["nom"], "nutriment": r["nutriment"], "teneur_pct": r["teneur_pct"],
                         "chelate": r["chelate"], "npk": r["npk"], "prix_tnd": r["prix_tnd"], "url": r["url"],
                         "source": r["source"], "preuve": r["preuve"],
                         "doses": _doses(r["source"], r["id"], r["usages"])})
        if len(products) >= max_products:
            break
    return {
        "carence": cls, "nutriment": cls.split("_")[0],
        "fiabilite": "hypothese" if seen is False else rule["niveau"],
        "culture_vue": seen, "cultures_vues": rule["cultures_vues"],
        "message": rule["si_culture_non_vue"] if seen is False else SEEN_OK,
        "questions_confirmation": rule["questions_confirmation"],
        "conditions_favorables": rule["conditions_favorables"],
        "avertissement_modele": MODEL_WARNINGS.get((cls, code)) or
                                (MODEL_WARNINGS.get((cls, None)) if code != "datepalm" else None),
        "sol": soil, "produits": products,
    }


if __name__ == "__main__":
    import sys
    args = sys.argv[1:] + [None] * 3
    print(json.dumps(get_fertilizers(args[0], args[1], args[2]), ensure_ascii=False, indent=1))
