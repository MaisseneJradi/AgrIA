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
  15. a product whose WHO hazard class is known (validated docs/substance_hazard.csv): class not written under it, or
      a different class written
  16. a product highly toxic to bees (validated docs/bee_hazard.csv) without its bee warning (no application during
      flowering)
  17. a pesticide without the line of protective equipment
  18. a rain (24 h) or wind (> 15 km/h, 12 h) warning of the forecast ("meteo" of the answer) not written, or written
      with another number (rules 15-18: phyto step 6)
  19. an answer about registered products (or saying none fits) without the date of the official list loaded
      ("liste DGSVCIA du 22/05/2024"), or with another date (phyto step 7)
  20. an MRL written in the text that differs from its table (EU for an export market, Codex for a local one;
      phyto step 7)
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
from hazard import bee_toxic, who_class
from lexicon import crop_code
from mrl import applicable_mrl
from mrl import check_line as check_mrl_line
from treatments import LIST_DATE, get_treatments


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
# step 6 (redaction.py): protective equipment line, weather lines, bee warning, WHO class written in the reasons
PPE_MARKERS = ("Protection :", "الوقاية:")
WEATHER_MARKERS = ("Météo :", "الطقس:")
RAIN_WORDS, WIND_WORDS, BEE_WORDS = ("pluie", "أمطار"), ("vent", "رياح"), ("abeilles", "النحل")
LIST_IN_TEXT = re.compile(r"DGSVCIA\D{0,12}(\d{2}/\d{2}/\d{4})")  # "liste DGSVCIA du 22/05/2024", "DGSVCIA بتاريخ ..."
WHO_IN_TEXT = re.compile(r"(?:OMS|صنف السمية|صنف)\s+(Ia|Ib|III|II|U)(?![A-Za-z])")


def _num_text(x):
    return f"{x:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def product_block(p, text):
    """The line of product p and the indented lines under it (practical dose, reasons)."""
    lines, out = text.splitlines(), []
    for i, line in enumerate(lines):
        if p.get("nom") and p["nom"] in line and (p.get("dose") or "") in line:
            out.append(line)
            for nxt in lines[i + 1:]:
                if not nxt.startswith("  "):
                    break
                out.append(nxt)
            break
    return "\n".join(out)


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
        # rule 20: the MRL written for this product = the one of its market (EU / Tunisian list / Codex)
        expected_mrl = applicable_mrl(usages[0], crop_code(crop) if crop else None, ctx.get("market"))
        for err in check_mrl_line(text, p["nom"], expected_mrl):
            reasons.append(f"« {p['nom']} » : {err}")
        # rules 15-16: the WHO class and the bee warning of the validated tables are written for this product
        block = product_block(p, text)
        cls_expected = who_class(usages[0])
        if cls_expected:
            written = WHO_IN_TEXT.findall(block)
            if not written:
                reasons.append(f"« {p['nom']} » : classe de toxicité OMS ({cls_expected}) non écrite")
            elif any(c != cls_expected for c in written):
                reasons.append(f"« {p['nom']} » : classe de toxicité OMS fausse (liste OMS : {cls_expected})")
        if bee_toxic(usages[0]) and not any(p["nom"] in x and any(b in x for b in BEE_WORDS)
                                            for x in text.splitlines()):
            reasons.append(f"« {p['nom']} » : très toxique pour les abeilles, avertissement absent")
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

    # rule 17: protective equipment with any pesticide; rule 18: the weather warnings of the forecast, with its numbers
    # rule 19: the date of the official list, in every answer that speaks of registered products (or of none)
    facts = answer.get("faits") or {}
    if text and (produits or facts.get("aucun_produit") or facts.get("aucun_adapte")):
        dates = LIST_IN_TEXT.findall(text)
        if not dates:
            reasons.append(f"date de la liste officielle absente (liste DGSVCIA du {LIST_DATE})")
        elif any(x != LIST_DATE for x in dates):
            reasons.append(f"date de la liste officielle fausse (liste chargée : {LIST_DATE})")

    # (like rule 8, they read the text: an answer given without text is checked on its facts only)
    if produits and text and not any(m in text for m in PPE_MARKERS):
        reasons.append("équipement de protection non indiqué alors qu'un pesticide est conseillé")
    meteo = answer.get("meteo") or {}
    if produits and text and meteo:
        lines = [x for x in text.splitlines() if any(m in x for m in WEATHER_MARKERS)]
        if meteo.get("pluie") and not any(_num_text(meteo["pluie_mm"]) in x and any(w in x for w in RAIN_WORDS)
                                          for x in lines):
            reasons.append(f"pluie prévue ({meteo['pluie_mm']} mm) non signalée ou chiffre différent")
        if meteo.get("vent") and not any(_num_text(meteo["vent_max_kmh"]) in x and any(w in x for w in WIND_WORDS)
                                         for x in lines):
            reasons.append(f"vent prévu ({meteo['vent_max_kmh']} km/h) non signalé ou chiffre différent")

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
