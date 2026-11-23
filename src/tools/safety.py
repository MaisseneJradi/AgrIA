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
      "contexte": {"days_to_harvest": 7, "market": "export", "organic": "n"},   # optional
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
  8. a product whose registered dose is not written, as such, on the same line as the product in the text
  9. a substance or a word of chemical control (fongicide, cuivre, azoxystrobine, spray...) outside the lines of the
     registered products and fertilizers of the answer: advice and quoted sheets never carry a treatment (phyto step 2)
  10. "contexte".days_to_harvest known: a product whose DAR (shown, else every known DAR of its uses) is longer
  11. "contexte".market = export: a product with a substance not approved, or of unknown status, in the EU
  12. "contexte".organic = y: a product with a substance not allowed in organic farming (bio_ue)
  (rules 10-12, phyto step 3: the context filters of ranking.py, checked again on the final answer)
  13. "contexte".last_treatment_group known: a product sharing a FRAC / IRAC group with it (low-risk groups M, BM, P,
      U, UN left out) while another registered product of a known, different group fits the case (phyto step 4)
  14. a practical dose ("Dose pratique : 48 g pour un pulvérisateur de 16 L ; 1,5 kg pour vos 0,5 ha") whose
      quantities differ from the official dose converted by dose_calc, written for a dose that cannot be converted,
      without the sprayer volume or the area it is for, or written outside the lines of a product (phyto step 5)
Warnings (the answer must mention them): restriction, provisional authorisation, relation vecteur or proche,
DAR not given by the list, model confusions of fertilizers.py.
"""
import re
from functools import lru_cache

from common import fold, query
import ranking
from dose_calc import TANK_L, area_text, practical_dose
from dose_calc import check as check_dose
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


# words of chemical control, in French and English (the sheets are in both languages)
CONTROL_WORDS = r"fongicides?|fungicides?|insecticides?|acaricides?|bactericides?|nematicides?|herbicides?|pesticides?|" \
                r"bouillies?|sprays?|sprayed|spraying|soufre|sulfur|sulphur|streptomycine?|antibiotiques?|" \
                r"traite[rz]|pulveris(?:ez|er|ation|ations)"  # 'il faut traiter...': a treatment without a product
# tokens of the substance table that are not substances (organisms, salts, nutrients, generic chemistry words)
NOT_CHEMICAL = {"acetate", "acetates", "adjuvant", "alkylphenolexy", "aluminium", "ammonium", "appliquee",
                "armigera", "armigeranucleopolyhe", "benzoate", "butylglycol", "cannelle", "capsicum", "chlorure",
                "cinnamomum", "compounds", "derivves", "diethyl", "diethyle", "dodecatrienyl", "ectomyeloisceratoniae",
                "essence", "essentielle", "ethylene", "ethylhexyl", "extrai", "extrait", "extract", "formate",
                "formerly", "garlic", "garlicextract", "glutinosa", "helicoverpa", "hydrochloride", "hydrogen",
                "hydrogene", "hydrolysat", "hydrolysed", "hydrolysees", "hydroxide", "hydroxyde", "lepidopteran",
                "littoralis", "littoralisnucleopolyhed", "magnesium", "margosa", "melaleuca", "melaleucaalternifolia",
                "alternifolia", "methyle", "methylheptyl", "minerale", "natural", "orange", "oxychloride",
                "oxychlorure", "paraffinique", "phosphide", "phosphure", "phytoprotecteur", "plante", "potassium",
                "proteines", "proteins", "sodium", "sulfate", "sulphate", "nonanol", "nonanone", "lambada",
                "isothiocyanate", "acides", "active", "dattes", "drovirus", "rovirus", "pyrale", "pythium", "sexuelle",
                "souche", "souches", "spores", "straight", "strain", "strains", "spodoptera", "vegetaux", "verticilium",
                "unsaturated", "tribasic", "tribasique", "tricalcique", "tetraborate", "solaten", "safener", "surfer",
                "renouee", "sakhaline", "swinglea", "trimethylamine", "trimethylaminehcl",
                "trimethylaminehydrochloride", "kurstakisouche", "bassianastrain", "asperellumstrain"}


@lru_cache(maxsize=1)
def _chemical_pattern():
    words = set()
    for r in query("SELECT substance_tn, eu_name FROM substances"):
        for n in (r["substance_tn"], r["eu_name"]):
            words |= {w for w in re.findall(r"[a-z]{6,}", fold(n)) if w not in NOT_CHEMICAL}
    words |= {"cuivre", "copper", "cuivrique", "cuivriques"}
    return re.compile(r"(?<![a-z])(?:" + CONTROL_WORDS + "|" + "|".join(sorted(map(re.escape, words), key=len,
                                                                             reverse=True)) + r")(?![a-z])")


def chemical_terms(text):
    """Substances and words of chemical control written in a text ('cuivre', 'fongicide', 'azoxystrobine'...)."""
    return list(dict.fromkeys(m.group(0) for m in _chemical_pattern().finditer(fold(text))))


def _named_in_text(text):
    found, folded = [], fold(text)
    for key, name, pat, one_word in _known_products():
        hay = text if one_word else folded
        if pat.search(hay) and not any(key in fold(f) for f in found):
            found.append(name)
    return found


PRACTICAL_MARKERS = ("Dose pratique", "الكمية العملية")  # first words of the practical-dose line (redaction.py)


def practical_line_of(p, text):
    """The practical-dose line written under the line of product p (indented lines that follow it), or None."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if p.get("nom") and p["nom"] in line and (p.get("dose") or "") in line:
            for nxt in lines[i + 1:]:
                if not nxt.startswith("  "):
                    break
                if any(m in nxt for m in PRACTICAL_MARKERS):
                    return nxt
            return None
    return None


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

    # rule 13: same FRAC / IRAC group as the last treatment while a product of another known group fits the case
    ctx = answer.get("contexte") or {}
    last = ranking.last_groups(ctx.get("last_treatment_group"))
    alternative = False
    if last and allowed:
        main = [u for u in allowed if u["relation"] != "proche"] or allowed
        dars = {}
        for u in main:
            if u["dar_jours"] is not None:
                dars.setdefault(u["produit"], []).append(u["dar_jours"])
        alternative = any(ranking.moa_groups(u) and not ranking.shared_groups(ranking.moa_groups(u), last)
                          for u in main if not ranking.set_aside(u, ctx, dars.get(u["produit"], ())))

    attached = set()  # practical-dose lines that belong to a product of the answer
    for p in produits:
        usages = registered(p.get("nom", ""))
        if not usages:
            reasons.append(f"« {p.get('nom')} » n'est pas homologué pour {cls}" + (f" sur {crop}" if crop else ""))
            continue
        if p.get("dose") and not any(_squash(p["dose"]) == _squash(u["dose"]) for u in usages):
            reasons.append(f"dose de « {p['nom']} » différente de l'homologation ({usages[0]['dose']})")
        elif p.get("dose") and text and not any(p["nom"] in line and p["dose"] in line for line in text.splitlines()):
            reasons.append(f"dose de « {p['nom']} » absente, modifiée ou séparée du produit dans le texte "
                           f"({p['dose']})")
        if "dar_jours" in p and p["dar_jours"] is not None:
            dars = {u["dar_jours"] for u in usages}
            if dars == {None}:
                reasons.append(f"délai avant récolte de « {p['nom']} » inventé : la liste n'en donne pas")
            elif p["dar_jours"] not in dars:
                reasons.append(f"délai avant récolte de « {p['nom']} » faux (liste : {sorted(d for d in dars if d is not None)})")
        # rule 14: the practical dose written under the product = the official dose converted (dose_calc)
        line = practical_line_of(p, text)
        if line is not None:
            attached.add(line)
            official = next((u["dose"] for u in usages if _squash(u["dose"]) == _squash(p.get("dose") or "")),
                            usages[0]["dose"])
            expected = practical_dose(official, ctx.get("area"))
            if expected is None:
                reasons.append(f"« {p['nom']} » : dose pratique écrite alors que la dose officielle ({official}) ne se "
                               "convertit pas")
            else:
                for err in check_dose(line, expected):
                    reasons.append(f"« {p['nom']} » : dose pratique fausse ({err})")
                if expected.get("pulverisateur") and f"{TANK_L} L" not in line:
                    reasons.append(f"« {p['nom']} » : la dose pratique ne dit pas le volume du pulvérisateur")
                if expected.get("surface") and area_text(ctx["area"]) not in line:
                    reasons.append(f"« {p['nom']} » : la dose pratique ne dit pas la surface")
        same = ranking.shared_groups(ranking.moa_groups(usages[0]), last) if last else set()
        if same and alternative:
            reasons.append(f"« {p['nom']} » : même groupe ({' + '.join(sorted(same))}) que le dernier traitement alors "
                           "qu'un produit d'un autre groupe est homologué pour ce cas")
        # rules 10-12: the situation of the farmer (contexte), when it is known
        dth = ctx.get("days_to_harvest")
        if dth is not None:
            shown = p.get("dar_jours")
            known = [x["dar_jours"] for x in usages if x["dar_jours"] is not None]
            if (shown is not None and shown > dth) or (shown is None and known and min(known) > dth):
                reasons.append(f"« {p['nom']} » : délai avant récolte plus long que les {dth} jours avant la récolte")
        if ctx.get("market") == "export" and not all(x.get("ue_approuve") for x in usages):
            reasons.append(f"« {p['nom']} » : substance non approuvée (ou inconnue) dans l'UE pour un marché export")
        if ctx.get("organic") == "y" and not all(x.get("bio_ue") for x in usages):
            reasons.append(f"« {p['nom']} » : substance non autorisée en agriculture biologique")
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

    stray = [x for x in text.splitlines() if any(m in x for m in PRACTICAL_MARKERS) and x not in attached]
    if stray:
        reasons.append("dose pratique écrite hors de la ligne d'un produit retenu")

    for name in _named_in_text(text):
        if not registered(name) and not any(_same_product(name, e.get("nom", "")) for e in engrais):
            reasons.append(f"le texte cite « {name} », non homologué pour {cls}" + (f" sur {crop}" if crop else ""))

    # rule 9: chemistry only on the lines of the registered products (or fertilizers) of the answer
    names = [n for n in [p.get("nom") for p in produits] + [e.get("nom") for e in engrais] if n]
    free = "\n".join(line for line in text.splitlines() if not any(n in line for n in names))
    chem = chemical_terms(free)
    if chem:
        reasons.append("lutte chimique hors des produits homologués retenus : " + ", ".join(chem))

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
