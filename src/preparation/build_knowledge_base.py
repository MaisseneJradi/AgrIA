"""Knowledge base of the agent: one fiche per disease, pest or deficiency, in French.

No open Tunisian base of disease fiches could be found (AVFA site closed to crawlers, INGC / Institut de l'Olivier /
CTV sites offline, agridata.tn holds statistics only), so each fiche joins:
  - description, symptoms, biology and control: the French Wikipedia article of the pathogen / pest (English when
    there is no French article), fetched through the MediaWiki API by its SCIENTIFIC name, split by section.
    Licence CC BY-SA 4.0: the article URL is kept in every fiche for attribution;
  - Tunisian layer: the products registered in Tunisia for that class (clean/classe_traitements.csv) and, for a
    deficiency, the fertilizers that bring the missing nutrient (clean/carence_engrais.csv).
Covered: every disease class of the image models, the deficiency classes, and the main pests of Tunisian crops
that have no image class (olive fly, medfly, date moth, date mite, red palm weevil...): the agent asks questions
for those.

Usage: python src/preparation/build_knowledge_base.py
Output: data/processed/knowledge/fiches.jsonl (one fiche per line) and fiches.csv (flat view, one row per fiche)
Cache: data/raw/knowledge/wikipedia/<lang>_<title>.json
"""
import json
import os
import re
import time
import urllib.parse
import urllib.error
import urllib.request

import pandas as pd

RAW = os.path.join("data", "raw", "knowledge", "wikipedia")
OUT = os.path.join("data", "processed", "knowledge")
CLEAN = os.path.join("data", "processed", "clean")
UA = "AgrIA-research/1.0 (student project; knowledge base of plant diseases)"

# (id, type, French name, scientific name used to find the article, crops, image classes)
ITEMS = [
    # diseases of the image classes
    ("mildiou_tomate_pdt", "maladie", "Mildiou de la tomate et de la pomme de terre", "Phytophthora infestans",
     "tomate, pomme de terre", ["tomato__late_blight", "potato__late_blight"]),
    ("alternariose_solanacees", "maladie", "Alternariose (brûlure alternarienne)", "Alternaria solani",
     "tomate, pomme de terre", ["tomato__early_blight", "potato__early_blight"]),
    ("septoriose_tomate", "maladie", "Septoriose de la tomate", "Septoria lycopersici", "tomate",
     ["tomato__septoria_leaf_spot"]),
    ("cladosporiose_tomate", "maladie", "Cladosporiose de la tomate", "Passalora fulva", "tomate",
     ["tomato__leaf_mold"]),
    ("corynesporiose_tomate", "maladie", "Corynesporiose (tache cible)", "Corynespora cassiicola", "tomate",
     ["tomato__target_spot"]),
    ("bacteriose_xanthomonas", "maladie", "Gale bactérienne (Xanthomonas)", "Xanthomonas vesicatoria",
     "tomate, piment, poivron", ["tomato__bacterial_spot", "pepper__bacterial_spot"]),
    ("tylcv", "maladie", "Maladie des feuilles jaunes en cuillère de la tomate (TYLCV)",
     "Tomato yellow leaf curl virus", "tomate", ["tomato__yellow_leaf_curl_virus"]),
    ("tomv", "maladie", "Virus de la mosaïque de la tomate (ToMV)", "Tomato mosaic virus", "tomate",
     ["tomato__mosaic_virus"]),
    ("anthracnose_colletotrichum", "maladie", "Anthracnose (Colletotrichum)", "Colletotrichum", "tomate, grenadier",
     ["tomato__anthracnose", "pomegranate__anthracnose"]),
    ("pourriture_grise", "maladie", "Pourriture grise (Botrytis)", "Botrytis cinerea", "tomate, vigne, fraisier",
     ["tomato__mold"]),
    ("tavelure_pommier", "maladie", "Tavelure du pommier", "Venturia inaequalis", "pommier", ["apple__scab"]),
    ("rouille_pommier", "maladie", "Rouille grillagée / rouille du pommier", "Gymnosporangium juniperi-virginianae",
     "pommier", ["apple__rust"]),
    ("black_rot_pommier", "maladie", "Pourriture noire du pommier (black rot)", "Botryosphaeria obtusa", "pommier",
     ["apple__black_rot"]),
    ("oidium_cerisier", "maladie", "Oïdium du cerisier", "Podosphaera clandestina", "cerisier",
     ["cherry__powdery_mildew"]),
    ("bacteriose_pecher", "maladie", "Maladie bactérienne des taches du pêcher", "Xanthomonas arboricola",
     "pêcher", ["peach__bacterial_spot"]),
    ("black_rot_vigne", "maladie", "Black-rot de la vigne", "Guignardia bidwellii", "vigne", ["grape__black_rot"]),
    ("esca_vigne", "maladie", "Esca de la vigne", "Esca (grapevine disease)", "vigne", ["grape__esca"]),
    ("isariopsis_vigne", "maladie", "Brûlure des feuilles de la vigne (Isariopsis)", "Pseudocercospora vitis",
     "vigne", ["grape__leaf_blight"]),
    ("oeil_de_paon", "maladie", "Œil de paon de l'olivier", "Venturia oleaginea", "olivier",
     ["olive__peacock_spot"]),
    ("tuberculose_olivier", "maladie", "Tuberculose (galle) de l'olivier", "Pseudomonas savastanoi", "olivier",
     ["olive__knot_disease"]),
    ("phytopte_olivier", "ravageur", "Phytopte (acarien ériophyide) de l'olivier", "Aculus olearius", "olivier",
     ["olive__aculus_olearius"]),
    ("chancre_agrumes", "maladie", "Chancre citrique", "Xanthomonas citri", "agrumes", ["citrus__canker"]),
    ("black_spot_agrumes", "maladie", "Maladie des taches noires des agrumes", "Phyllosticta citricarpa", "agrumes",
     ["citrus__black_spot"]),
    ("gale_agrumes", "maladie", "Gale (tavelure) des agrumes", "Elsinoë fawcettii", "agrumes", ["citrus__scab"]),
    ("greening", "maladie", "Huanglongbing (greening des agrumes)", "Huanglongbing", "agrumes",
     ["orange__citrus_greening"]),
    ("parlatoria_palmier", "ravageur", "Cochenille blanche du palmier dattier", "Parlatoria blanchardi",
     "palmier dattier", ["datepalm__parlatoria_scale"]),
    ("bayoud", "maladie", "Bayoud du palmier dattier", "Fusarium oxysporum f.sp. albedinis", "palmier dattier",
     ["datepalm__fusarium_wilt"]),
    ("black_scorch", "maladie", "Pourriture noire / black scorch du palmier", "Thielaviopsis paradoxa",
     "palmier dattier", ["datepalm__black_scorch"]),
    ("graphiola", "maladie", "Faux charbon (taches foliaires) du palmier", "Graphiola phoenicis", "palmier dattier",
     ["datepalm__leaf_spots"]),
    ("diplodia_palmier", "maladie", "Pourriture du rachis (Diplodia) du palmier", "Lasiodiplodia theobromae",
     "palmier dattier", ["datepalm__rachis_blight"]),
    ("rouille_brune_ble", "maladie", "Rouille brune du blé", "Puccinia triticina", "blé", ["wheat__leaf_rust"]),
    ("rouille_mais", "maladie", "Rouille commune du maïs", "Puccinia sorghi", "maïs", ["corn__common_rust"]),
    ("helminthosporiose_mais", "maladie", "Helminthosporiose du maïs", "Exserohilum turcicum", "maïs",
     ["corn__northern_leaf_blight"]),
    ("cercosporiose_mais", "maladie", "Cercosporiose du maïs", "Cercospora zeae-maydis", "maïs",
     ["corn__gray_leaf_spot"]),
    ("oidium_cucurbitacees", "maladie", "Oïdium des cucurbitacées", "Podosphaera xanthii",
     "courgette, melon, concombre", ["squash__powdery_mildew"]),
    ("brulure_fraisier", "maladie", "Brûlure des feuilles du fraisier", "Diplocarpon earlianum", "fraisier",
     ["strawberry__leaf_scorch"]),
    ("alternaria_grenadier", "maladie", "Alternariose du grenadier", "Alternaria alternata", "grenadier",
     ["pomegranate__alternaria_spot"]),
    ("cercospora_grenadier", "maladie", "Cercosporiose du grenadier", "Cercospora punicae", "grenadier",
     ["pomegranate__cercospora_spot"]),
    ("bacteriose_grenadier", "maladie", "Bactériose du grenadier", "Xanthomonas axonopodis pv. punicae",
     "grenadier", ["pomegranate__bacterial_blight"]),
    # pests of the image classes
    ("tetranyque", "ravageur", "Tétranyque tisserand (araignée rouge)", "Tetranychus urticae", "tomate, maraîchage",
     ["tomato__spider_mites"]),
    ("tuta_absoluta", "ravageur", "Mineuse de la tomate", "Tuta absoluta", "tomate", ["tomato__leaf_miner"]),
    ("helicoverpa", "ravageur", "Noctuelle de la tomate (ver des fruits)", "Helicoverpa armigera", "tomate",
     ["tomato__fruitworm"]),
    ("bemisia", "ravageur", "Aleurode du tabac (mouche blanche)", "Bemisia tabaci", "tomate, piment",
     ["tomato__yellow_leaf_curl_virus"]),
    # physiological disorders of the fruit classes
    ("necrose_apicale", "trouble", "Nécrose apicale (cul noir) de la tomate", "Blossom-end rot", "tomate",
     ["tomato__blossom_end_rot"]),
    ("eclatement_fruits", "trouble", "Éclatement des fruits de la tomate", "Fruit cracking", "tomate",
     ["tomato__cracking"]),
    # deficiency classes
    ("carence_N", "carence", "Carence en azote", "Nitrogen deficiency", "toutes cultures", ["N_deficiency"]),
    ("carence_P", "carence", "Carence en phosphore", "Phosphorus deficiency", "toutes cultures", ["P_deficiency"]),
    ("carence_K", "carence", "Carence en potassium", "Potassium deficiency (plants)", "toutes cultures",
     ["K_deficiency"]),
    ("carence_Ca", "carence", "Carence en calcium", "Calcium deficiency (plant disorder)", "toutes cultures",
     ["Ca_deficiency"]),
    ("carence_Mg", "carence", "Carence en magnésium", "Magnesium deficiency (plants)", "toutes cultures",
     ["Mg_deficiency"]),
    ("carence_Fe", "carence", "Carence en fer (chlorose ferrique)", "Iron chlorosis", "toutes cultures",
     ["Fe_deficiency"]),
    ("carence_Zn", "carence", "Carence en zinc", "Zinc deficiency (plant disorder)", "toutes cultures",
     ["Zn_deficiency"]),
    ("carence_Mn", "carence", "Carence en manganèse", "Manganese deficiency (plant)", "toutes cultures",
     ["Mn_deficiency"]),
    ("carence_B", "carence", "Carence en bore", "Boron deficiency (plant disorder)", "toutes cultures",
     ["B_deficiency"]),
    # Tunisian pests and diseases without image class
    ("mouche_olive", "ravageur", "Mouche de l'olive", "Bactrocera oleae", "olivier", []),
    ("teigne_olivier", "ravageur", "Teigne de l'olivier", "Prays oleae", "olivier", []),
    ("psylle_olivier", "ravageur", "Psylle de l'olivier", "Euphyllura olivina", "olivier", []),
    ("ceratite", "ravageur", "Mouche méditerranéenne des fruits (cératite)", "Ceratitis capitata",
     "agrumes, pêcher, abricotier, figuier", []),
    ("pyrale_dattes", "ravageur", "Pyrale des dattes (ver de la datte)", "Ectomyelois ceratoniae",
     "palmier dattier, grenadier", []),
    ("acarien_dattes", "ravageur", "Acarien des dattes (Boufaroua)", "Oligonychus afrasiaticus", "palmier dattier",
     []),
    ("charancon_rouge", "ravageur", "Charançon rouge du palmier", "Rhynchophorus ferrugineus", "palmier", []),
    ("mineuse_agrumes", "ravageur", "Mineuse des feuilles d'agrumes", "Phyllocnistis citrella", "agrumes", []),
    ("pou_rouge_agrumes", "ravageur", "Pou rouge de Californie", "Aonidiella aurantii", "agrumes", []),
    ("carpocapse", "ravageur", "Carpocapse des pommes et des poires", "Cydia pomonella", "pommier, poirier", []),
    ("pucerons", "ravageur", "Puceron vert du pêcher", "Myzus persicae", "maraîchage, arbres fruitiers", []),
    ("thrips_californie", "ravageur", "Thrips californien", "Frankliniella occidentalis", "maraîchage, fraisier", []),
    ("eudemis", "ravageur", "Eudémis de la vigne (ver de la grappe)", "Lobesia botrana", "vigne", []),
    ("mildiou_vigne", "maladie", "Mildiou de la vigne", "Plasmopara viticola", "vigne", []),
    ("oidium_vigne", "maladie", "Oïdium de la vigne", "Erysiphe necator", "vigne", []),
    ("septoriose_ble", "maladie", "Septoriose du blé", "Zymoseptoria tritici", "blé", []),
    ("rouille_jaune", "maladie", "Rouille jaune du blé", "Puccinia striiformis", "blé, triticale", []),
    ("tache_bronzee", "maladie", "Tache bronzée (helminthosporiose) du blé", "Pyrenophora tritici-repentis", "blé",
     []),
    ("oidium_solanacees", "maladie", "Oïdium des solanacées (Leveillula)", "Leveillula taurica", "tomate, piment",
     []),
    ("nematodes_galles", "ravageur", "Nématodes à galles", "Meloidogyne", "maraîchage", []),
    ("verticilliose_olivier", "maladie", "Verticilliose de l'olivier", "Verticillium dahliae", "olivier", []),
    ("criquet_pelerin", "ravageur", "Criquet pèlerin", "Schistocerca gregaria", "toutes cultures", []),
]
# reviewed article titles, tried in order: used where a search on the name lands on a wrong or too generic page.
# An empty list = no reliable article (the fiche keeps its Tunisian layer only).
TITLES = {
    "carence_N": [("en", "Nitrogen deficiency")],
    "carence_P": [("en", "Phosphorus deficiency")],
    "carence_K": [("en", "Potassium deficiency (plants)")],
    "carence_Ca": [("en", "Calcium deficiency (plant disorder)")],
    "carence_Mg": [("en", "Magnesium deficiency (plants)")],
    "carence_Fe": [("en", "Iron deficiency (plant disorder)"), ("en", "Chlorosis")],
    "carence_Zn": [("en", "Zinc deficiency (plant disorder)")],
    "carence_Mn": [("fr", "Carence en manganèse"), ("en", "Manganese deficiency (plant)")],
    "carence_B": [("en", "Boron deficiency (plant disorder)")],
    "necrose_apicale": [("fr", "Nécrose apicale"), ("en", "Blossom-end rot")],
    "eclatement_fruits": [],
    "black_scorch": [("en", "Thielaviopsis paradoxa"), ("en", "Ceratocystis paradoxa")],
    "rouille_pommier": [("en", "Gymnosporangium juniperi-virginianae")],
    "black_rot_pommier": [("en", "Botryosphaeria obtusa")],
    "helminthosporiose_mais": [("fr", "Helminthosporiose du maïs"), ("en", "Northern corn leaf blight")],
    "rouille_mais": [("en", "Puccinia sorghi")],
    "rouille_brune_ble": [("fr", "Rouille brune du blé"), ("en", "Puccinia triticina")],
    "oeil_de_paon": [("fr", "Œil de paon de l'olivier"), ("en", "Venturia oleaginea"), ("en", "Olive peacock spot")],
    "oidium_cerisier": [("en", "Podosphaera clandestina")],
    "bacteriose_grenadier": [("en", "Xanthomonas axonopodis")],
    "bacteriose_xanthomonas": [("en", "Xanthomonas vesicatoria"), ("fr", "Xanthomonas")],
    "corynesporiose_tomate": [("en", "Corynespora cassiicola")],
    "parlatoria_palmier": [("en", "Parlatoria blanchardi")],
    "bayoud": [("fr", "Bayoud"), ("en", "Bayoud disease")],
    "esca_vigne": [("fr", "Esca (maladie)"), ("fr", "Esca"), ("en", "Esca (grape disease)")],
    "cercospora_grenadier": [],
}
# pests and diseases without image class: their Tunisian registered products, found in the usages of the list
# (crop codes, regex on the target as written in the list)
USAGE_TARGETS = {
    "mouche_olive": (["olive"], r"dacus|bactrocera|mouches? de l.?olivier"),
    "teigne_olivier": (["olive"], r"teigne|prays"),
    "psylle_olivier": (["olive"], r"psylle|euphyllura"),
    "ceratite": (None, r"ceratit|mouche mediterran"),
    "pyrale_dattes": (["datepalm", "pomegranate"], r"pyrale|ectomyelois|ectomeylois"),
    "acarien_dattes": (["datepalm"], r"oligonychus|acarien|boufaroua"),
    "charancon_rouge": (None, r"charancon"),
    "mineuse_agrumes": (["citrus"], r"mineuse|phyllocnistis"),
    "pou_rouge_agrumes": (["citrus"], r"pou rouge|aonidiella|cochenille"),
    "carpocapse": (["apple", "pear", "fruit_trees"], r"carpocapse|cydia"),
    "pucerons": (None, r"puceron"),
    "thrips_californie": (None, r"thrips|frankliniella"),
    "eudemis": (["grape"], r"eudemis|tordeuse|ver de la grappe|lobesia"),
    "mildiou_vigne": (["grape"], r"mildiou|plasmopara"),
    "oidium_vigne": (["grape"], r"oidium|uncinula|erysiphe"),
    "septoriose_ble": (["wheat", "cereals"], r"septori"),
    "rouille_jaune": (["wheat", "cereals", "triticale"], r"rouille"),
    "tache_bronzee": (["wheat", "cereals"], r"tache bronzee|helminthospori|pyrenophora"),
    "oidium_solanacees": (["tomato", "pepper"], r"leveillula|oidium"),
    "nematodes_galles": (None, r"nemato|meloidogyne"),
    "verticilliose_olivier": (["olive"], r"verticill"),
    "criquet_pelerin": (None, r"criquet"),
}
# section headings kept, by theme (lower case, no accent, French and English)
THEMES = {
    "symptomes": r"symptom|degat|dommage|signes|identification|damage|description de la maladie",
    "biologie": r"biolog|cycle|epidemiolog|developpement|reproduction|transmission|life cycle|ecolog|hote|host",
    "lutte": r"lutte|controle|traitement|gestion|prevention|methodes|management|control|treatment|prophyla",
    "repartition": r"repartition|distribution|geograph|origine|historique|history",
}
_last = [0.0]


def plain(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def api(lang, **params):
    """One MediaWiki API call, at most one every 1.5 s; on HTTP 429 waits as long as Retry-After asks (5 tries)."""
    url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"format": "json", "maxlag": 5,
                                                                                **params})
    for k in range(5):
        time.sleep(max(0.0, _last[0] + 1.5 - time.time()))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                _last[0] = time.time()
                return json.load(r)
        except urllib.error.HTTPError as e:
            _last[0] = time.time()
            if e.code != 429 or k == 4:
                raise
            time.sleep(int(e.headers.get("Retry-After") or 30 * (k + 1)))


def page(lang, title):
    """Article by exact title (redirects followed), cached; {} when the page does not exist."""
    path = os.path.join(RAW, f"{lang}_{re.sub(r'[^A-Za-z0-9]+', '_', plain(title))}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    pages = api(lang, action="query", prop="extracts|info", explaintext=1, exsectionformat="wiki", redirects=1,
                inprop="url", titles=title)["query"]["pages"]
    p = next(iter(pages.values()))
    data = {} if "missing" in p else {"lang": lang, "title": p.get("title"), "url": p.get("fullurl"),
                                      "text": p.get("extract", "")}
    os.makedirs(RAW, exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    return data


def article(fid, name):
    """Article of a fiche: the reviewed title of TITLES when there is one (a search lands on wrong pages for
    common-language names: 'Potassium deficiency' -> 'Iode'), else a search on the scientific name, kept only
    when the WHOLE name is in the title or the first paragraphs (not just the genus). French first, then English."""
    for lang, title in TITLES.get(fid, []):
        data = page(lang, title)
        if data.get("text"):
            return data
    if fid in TITLES:
        return {}
    for lang in ("fr", "en"):
        hits = api(lang, action="query", list="search", srsearch=f'"{name}"', srlimit=3)["query"]["search"]
        for h in hits[:1]:
            data = page(lang, h["title"])
            if data.get("text") and plain(name) in plain(data["title"] + " " + data["text"][:3000]):
                return data
    return {}


def sections(text):
    """Wikipedia plain text -> {'intro': ..., '<heading>': ...} (headings '== X ==', any level)."""
    parts = re.split(r"\n(={2,4})\s*(.+?)\s*\1\n", "\n" + text)
    out = {"intro": parts[0].strip()}
    for k in range(1, len(parts) - 2, 3):
        body = parts[k + 2].strip()
        if body:
            out[parts[k + 1].strip()] = body
    return out


def themed(secs):
    out = {"description": secs.get("intro", "")}
    for theme, rx in THEMES.items():
        txt = "\n\n".join(f"{h}\n{b}" for h, b in secs.items() if h != "intro" and re.search(rx, plain(h)))
        out[theme] = txt
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    treat = pd.read_csv(os.path.join(CLEAN, "classe_traitements.csv"))
    fert = pd.read_csv(os.path.join(CLEAN, "carence_engrais.csv"))
    uses = pd.read_csv(os.path.join(CLEAN, "pesticides_usages.csv"))
    uses["cible_plain"] = uses["cible"].map(plain)
    fiches = []
    for fid, kind, nom, sci, crops, classes in ITEMS:
        a = article(fid, sci)
        t = themed(sections(a.get("text", ""))) if a else {}
        if fid in USAGE_TARGETS:  # no image class: the usages whose target names this pest / disease
            ucrops, rx = USAGE_TARGETS[fid]
            u = uses[uses["cible_plain"].str.contains(rx, na=False)]
            if ucrops:
                keep = [bool(set(str(c).split("|")) & set(ucrops)) for c in u["crop"]]
                u = u[pd.Series(keep, index=u.index, dtype=bool)]
            tr = u.assign(relation="direct")
        else:
            tr = treat[treat["unified_class"].isin(classes)]
        products = [{"nom_commercial": r.nom_commercial, "substances": r.substances_ue, "culture": r.culture,
                     "cible": r.cible, "dose": r.dose, "dar_jours": None if pd.isna(r.dar_jours) else int(r.dar_jours),
                     "relation": r.relation, "bio_ue": bool(r.bio_ue) if pd.notna(r.bio_ue) else None}
                    for r in tr.drop_duplicates(["nom_commercial", "culture", "cible"]).itertuples()]
        ff = fert[fert["unified_class"].isin(classes)]
        engrais = [{"nom": r.nom, "teneur_pct": None if pd.isna(r.teneur_pct) else r.teneur_pct,
                    "source": r.source, "preuve": r.preuve} for r in ff.drop_duplicates("nom").head(15).itertuples()]
        fiches.append({"id": fid, "type": kind, "nom": nom, "nom_scientifique": sci, "cultures": crops,
                       "classes_modele": classes, **t,
                       "traitements_homologues_tn": products, "engrais_conseilles": engrais,
                       "source_texte": a.get("url"), "langue_texte": a.get("lang"),
                       "licence_texte": "CC BY-SA 4.0 (Wikipédia)" if a else None,
                       "source_traitements": "DGSVCIA, liste des pesticides homologués (22/05/2024)" if products else None})
    with open(os.path.join(OUT, "fiches.jsonl"), "w", encoding="utf-8") as f:
        for x in fiches:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    flat = pd.DataFrame([{**{k: v for k, v in x.items() if not isinstance(v, list)},
                          "classes_modele": " ".join(x["classes_modele"]),
                          "n_traitements_tn": len(x["traitements_homologues_tn"]),
                          "n_engrais": len(x["engrais_conseilles"]),
                          "n_caracteres": sum(len(x.get(k) or "") for k in ["description", *THEMES])}
                         for x in fiches])
    flat.to_csv(os.path.join(OUT, "fiches.csv"), index=False, encoding="utf-8")
    print(flat[["id", "langue_texte", "n_caracteres", "n_traitements_tn", "n_engrais"]].to_string(index=False))
    print(f"\n{len(flat)} fiches: {flat['langue_texte'].value_counts(dropna=False).to_dict()} "
          f"(None = no article found)")


if __name__ == "__main__":
    main()
