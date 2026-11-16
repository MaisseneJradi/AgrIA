"""Last check of every answer before the farmer sees it. Rules, no LLM: an answer that breaks one is blocked.

  check_answer({
      "task": "diseases",                  # diseases | deficiency | fruits
      "classe": "tomato__late_blight",     # class given by the model
      "culture": "tomate",                 # crop of the farmer, if known
      "fiable": True,                      # `reliable` of predict()
      "hypothese": False,                  # the answer presents the diagnosis as a hypothesis to confirm
      "produits": [{"nom": "CIMOXATE C WG", "dose": "3 kg/ha (300 g/hl)", "dar_jours": 3}],
      "engrais": [{"nom": "Sequestrene 138 FE"}],
      "texte": "the text shown to the farmer",
  })
  -> {"valide": False, "raisons": [...blocking...], "avertissements": [...to mention...], "produits_verifies": [...]}

Blocking rules
  1. a pesticide that is not registered for this class (and this crop, when known), in "produits" or named in the text
  2. a dose different from the registered dose of that product
  3. a DAR (days before harvest) that differs from the list, or any DAR when the list gives none (never estimated)
  4. a product or a fertilizer for a healthy plant
  5. a product while the diagnosis is not reliable (fiable False): ask confirmation questions first
  6. a deficiency on a crop never seen for it in training, not presented as a hypothesis (H2)
  7. a fertilizer that is not in the catalogue of that deficiency
Warnings (the answer must mention them): restriction, provisional authorisation, relation vecteur or proche,
DAR not given by the list, model confusions of fertilizers.py.
"""
import re
from functools import lru_cache

from common import fold, query
from fertilizers import get_fertilizers
from treatments import get_treatments


def _squash(text):
    return re.sub(r"[\s.,;()]+", "", fold(text))


@lru_cache(maxsize=1)
def _known_products():
    """All pesticide names known (Tunisian list + agrishop shop), as (folded name, display name, pattern)."""
    names = {r["nom_commercial"] for r in query("SELECT DISTINCT nom_commercial FROM pesticides_produits")}
    names |= {r["nom"] for r in query("SELECT DISTINCT nom FROM pesticides_agrishop")}
    out = []
    for n in sorted({str(x).strip() for x in names if x and str(x) != "nan"}, key=len, reverse=True):
        base = re.sub(r"\s+(sc|ec|wg|wp|sl|ew|od|se|cs|fs|wdg|sg|sp|gr|me|ul|dc)$", "", n.strip(), flags=re.I)
        if len(base) < 4:
            continue
        one_word = " " not in base
        # one ordinary word ("Impact", "Flint") counts only written with its capital, as a product name
        pat = re.compile(r"(?<![\w])" + re.escape(base if one_word else fold(base)) + r"(?![\w])",
                         0 if one_word else re.I)
        out.append((fold(base), n, pat, one_word))
    return out


def _named_in_text(text):
    found, folded = [], fold(text)
    for key, name, pat, one_word in _known_products():
        hay = text if one_word else folded
        if pat.search(hay) and not any(key in fold(f) for f in found):
            found.append(name)
    return found


def _same_product(a, b):
    fa, fb = fold(a), fold(b)
    return fa == fb or fa.startswith(fb + " ") or fb.startswith(fa + " ")


def check_answer(answer):
    reasons, warnings, checked = [], [], []
    cls = answer.get("classe") or ""
    crop = answer.get("culture")
    produits = answer.get("produits") or []
    engrais = answer.get("engrais") or []
    text = answer.get("texte") or ""
    healthy = cls == "healthy" or cls.endswith("__healthy")

    if healthy and (produits or engrais):
        reasons.append("plante saine : aucun produit ni engrais ne doit être conseillé")
    if answer.get("fiable") is False and (produits or engrais):
        reasons.append("diagnostic non fiable : poser les questions de confirmation avant de conseiller un produit")

    allowed = []
    if answer.get("task") in ("diseases", "fruits") and not healthy:
        try:
            allowed = get_treatments(cls, crop)
        except ValueError as e:
            reasons.append(str(e))

    def registered(name):
        return [u for u in allowed if _same_product(u["produit"], name)]

    for p in produits:
        usages = registered(p.get("nom", ""))
        if not usages:
            reasons.append(f"« {p.get('nom')} » n'est pas homologué pour {cls}" + (f" sur {crop}" if crop else ""))
            continue
        if p.get("dose") and not any(_squash(p["dose"]) == _squash(u["dose"]) for u in usages):
            reasons.append(f"dose de « {p['nom']} » différente de l'homologation ({usages[0]['dose']})")
        if "dar_jours" in p and p["dar_jours"] is not None:
            dars = {u["dar_jours"] for u in usages}
            if dars == {None}:
                reasons.append(f"délai avant récolte de « {p['nom']} » inventé : la liste n'en donne pas")
            elif p["dar_jours"] not in dars:
                reasons.append(f"délai avant récolte de « {p['nom']} » faux (liste : {sorted(d for d in dars if d is not None)})")
        u = usages[0]
        if u["dar_jours"] is None:
            warnings.append(f"« {u['produit']} » : {u['dar_message']}")
        if u["restriction"]:
            warnings.append(f"« {u['produit']} » : {u['restriction']}")
        if u["autorisation_provisoire"]:
            warnings.append(f"« {u['produit']} » : autorisation provisoire de vente")
        if u["relation"] in ("vecteur", "proche"):
            warnings.append(f"« {u['produit']} » : {u['relation_sens']}")
        checked.append({"nom": u["produit"], "product_id": u["product_id"], "relation": u["relation"]})

    for name in _named_in_text(text):
        if not registered(name) and not any(_same_product(name, e.get("nom", "")) for e in engrais):
            reasons.append(f"le texte cite « {name} », non homologué pour {cls}" + (f" sur {crop}" if crop else ""))

    if answer.get("task") == "deficiency" and not healthy:
        try:
            fert = get_fertilizers(cls, crop)
        except ValueError as e:
            reasons.append(str(e))
            fert = None
        if fert:
            if fert["fiabilite"] == "hypothese" and not answer.get("hypothese"):
                reasons.append(f"{cls} n'a jamais été vue sur cette culture : la présenter comme hypothèse à confirmer")
            if fert.get("avertissement_modele"):
                warnings.append(fert["avertissement_modele"])
            catalogue = [r["nom"] for r in query("SELECT nom FROM carence_engrais WHERE unified_class = ?", (cls,))]
            for e in engrais:
                if not any(_same_product(e.get("nom", ""), c) for c in catalogue):
                    reasons.append(f"engrais « {e.get('nom')} » absent du catalogue de {cls}")

    return {"valide": not reasons, "raisons": reasons, "avertissements": list(dict.fromkeys(warnings)),
            "produits_verifies": checked}
