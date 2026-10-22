"""French / Arabic / Tunisian darija / arabizi lexicon of the agent (crops, diseases, pests, symptoms, plant parts,
farm words), so that a farmer may write "el wra9 msafra fi tmatem" or "الورق مصفّر في الطماطم".

Columns: concept, type, lien (project crop code, image class or nutrient), fr, ar_msa (standard Arabic),
ar_tn (Tunisian darija, Arabic script), arabizi (Latin script with digits 3 7 9 5, variants split by |), en,
source, a_valider (True = written by hand, to be checked by a Tunisian speaker before use).
Sources, merged per concept:
  agriclic   Tunisian commercial names of crops, read from the bilingual menu of agriclic.tn (cached page);
  wikidata   standard Arabic and French labels of each pathogen / pest, by scientific name (SPARQL, P225);
  donnees    the French spellings met in the Tunisian pesticide list (docs/culture_mapping.csv), as synonyms;
  redige     darija and arabizi forms written for this project (CURATED below): to validate.

Usage: python src/preparation/build_lexicon.py
Output: data/processed/knowledge/lexique.csv
"""
import ast
import html
import json
import os
import re
import urllib.parse
import urllib.request

import pandas as pd

OUT = os.path.join("data", "processed", "knowledge")
RAW = os.path.join("data", "raw", "knowledge")
AGRICLIC_HOME = os.path.join("data", "raw", "agriclic", "html", "home.html")
UA = "AgrIA-research/1.0 (student project)"

# (concept, type, lien, fr, ar_tn, arabizi, en) written for the project: to validate with Tunisian speakers
CURATED = [
    # crops
    ("tomate", "culture", "tomato", "tomate", "طماطم", "tmatem|tmatim|tomatem|tmatm", "tomato"),
    ("piment", "culture", "pepper", "piment / poivron", "فلفل", "felfel|filfil|flfl|felfla", "pepper"),
    ("pomme_de_terre", "culture", "potato", "pomme de terre", "بطاطا", "batata|btata", "potato"),
    ("olivier", "culture", "olive", "olivier / olive", "زيتون / زيتونة", "zitoun|zitouna|zitoune|zaytoun", "olive"),
    ("agrumes", "culture", "citrus", "agrumes", "قوارص", "9wares|qwares|kouares|9ouares", "citrus"),
    ("orange", "culture", "citrus", "orange", "بردقان", "bordgen|bordguen|bordgan", "orange"),
    ("citron", "culture", "citrus", "citron", "قارص", "9ares|qares|gares", "lemon"),
    ("vigne", "culture", "grape", "vigne / raisin", "عنب / دالية", "3neb|aneb|3nab|dalia", "grapevine"),
    ("palmier", "culture", "datepalm", "palmier dattier / dattes", "نخلة / تمر / دقلة", "na5la|nakhla|tmar|deglet",
     "date palm"),
    ("ble", "culture", "wheat", "blé", "قمح", "9am7|gamh|qmah|9mah", "wheat"),
    ("orge", "culture", "barley", "orge", "شعير", "ch3ir|cha3ir|chair", "barley"),
    ("pommier", "culture", "apple", "pommier / pomme", "تفاح", "tfa7|teffe7|toffe7|tfeh", "apple"),
    ("poirier", "culture", "pear", "poirier / poire", "إنجاص", "enjass|ingass|ijass", "pear"),
    ("pecher", "culture", "peach", "pêcher / pêche", "خوخ", "5o5|khoukh|5ou5", "peach"),
    ("abricotier", "culture", "apricot", "abricotier / abricot", "مشمش", "mechmech|michmich", "apricot"),
    ("cerisier", "culture", "cherry", "cerisier / cerise", "حب الملوك", "7ab lmlouk|hab el moulouk", "cherry"),
    ("prunier", "culture", "plum", "prunier / prune", "عوينة", "3wina|awina|3ouina", "plum"),
    ("amandier", "culture", "almond", "amandier / amande", "لوز", "louz|lowz", "almond"),
    ("figuier", "culture", "fig", "figuier / figue", "كرموس / تين", "karmous|kermous|karmouss", "fig"),
    ("grenadier", "culture", "pomegranate", "grenadier / grenade", "رمان", "romman|rommen|rmen|roumen",
     "pomegranate"),
    ("fraisier", "culture", "strawberry", "fraisier / fraise", "فراولو / فراولة", "fraoula|frawla|fraise",
     "strawberry"),
    ("melon", "culture", "melon", "melon", "بطيخ", "bat5|battikh|bettikh", "melon"),
    ("pasteque", "culture", "watermelon", "pastèque", "دلاع", "della3|dela3|dellaa|dla3", "watermelon"),
    ("concombre", "culture", "cucumber", "concombre", "خيار / فقوس", "5iyar|khyar|fa9ous|fakous", "cucumber"),
    ("courgette", "culture", "squash", "courgette / courge", "قرع / كوسة", "9ar3|gar3|kousa|9ra3", "squash"),
    ("aubergine", "culture", "eggplant", "aubergine", "بادنجان", "badenjen|bedenjel|badinjan", "eggplant"),
    ("mais", "culture", "corn", "maïs", "قطانية / ذرة", "dhra|thra|mais", "maize"),
    ("oignon", "culture", "onion", "oignon", "بصل", "bsal|bssal", "onion"),
    ("ail", "culture", "garlic", "ail", "ثوم", "thoum|toum", "garlic"),
    ("feve", "culture", "faba_bean", "fève / féverole", "فول", "foul|fool", "faba bean"),
    ("petit_pois", "culture", "pea", "petit pois", "جلبانة", "jelbana|jalbana|jlbana", "pea"),
    ("pois_chiche", "culture", "chickpea", "pois chiche", "حمص", "7ommos|hommos|7oms", "chickpea"),
    ("artichaut", "culture", "artichoke", "artichaut", "قنارية", "9naria|qnaria|gnaria", "artichoke"),
    ("carotte", "culture", "carrot", "carotte", "سفنارية / جزر", "sfenaria|sfinaria|jazar", "carrot"),
    ("fenouil", "culture", "fennel", "fenouil", "بسباس", "besbes|bisbas", "fennel"),
    ("chou", "culture", "cabbage", "chou", "كرنب", "kromb|krumb|kromba", "cabbage"),
    # diseases and pests (Tunisian field names; French loanwords are common)
    ("mildiou", "maladie", "tomato__late_blight potato__late_blight", "mildiou", "ميلديو / المرض",
     "mildiou|meldiou|mildyou", "late blight / downy mildew"),
    ("oidium", "maladie", "squash__powdery_mildew cherry__powdery_mildew", "oïdium (poudre blanche)",
     "الغبرة البيضاء / الرمدة", "oidium|ghabra bidha|romda", "powdery mildew"),
    ("rouille", "maladie", "wheat__leaf_rust corn__common_rust apple__rust", "rouille", "الصدى / الصدأ",
     "rouille|sda|sada", "rust"),
    ("pourriture", "symptome", "tomato__mold", "pourriture", "خامج / عفن", "5amej|khamej|3fen", "rot"),
    ("tuta", "ravageur", "tomato__leaf_miner", "Tuta absoluta (mineuse de la tomate)", "توتا / الدودة",
     "tuta|touta|douda", "tomato leaf miner"),
    ("mouche_blanche", "ravageur", "tomato__yellow_leaf_curl_virus", "mouche blanche (aleurode)",
     "الذبانة البيضاء", "dhebbana bidha|debbana bidha|mouche blanche", "whitefly"),
    ("pucerons", "ravageur", "", "pucerons", "القمل / المن", "9mel|guemel|pucerons", "aphids"),
    ("acariens", "ravageur", "tomato__spider_mites olive__aculus_olearius", "acariens (araignée rouge)",
     "العنكبوت الأحمر / الأكاريان", "akarien|3ankbout a7mar", "mites"),
    ("boufaroua", "ravageur", "", "acarien des dattes (Boufaroua)", "بوفروة", "boufaroua|bou faroua",
     "old world date mite"),
    ("bayoud", "maladie", "datepalm__fusarium_wilt", "bayoud du palmier", "البيوض", "bayoudh|bayoud",
     "bayoud disease"),
    ("charancon_rouge", "ravageur", "", "charançon rouge du palmier", "السوسة الحمراء", "sousa 7amra|sousa hamra",
     "red palm weevil"),
    ("mouche_olive", "ravageur", "", "mouche de l'olive", "ذبانة الزيتون", "dhebbanet zitoun|dbena zitoun",
     "olive fly"),
    ("mouche_fruits", "ravageur", "", "cératite (mouche des fruits)", "ذبانة الغلة / ذبانة القوارص",
     "dhebbanet el ghalla|ceratite", "medfly"),
    ("oeil_de_paon", "maladie", "olive__peacock_spot", "œil de paon de l'olivier", "عين الطاووس",
     "3in tawous|oeil de paon", "olive peacock spot"),
    ("tuberculose_olivier", "maladie", "olive__knot_disease", "tuberculose de l'olivier", "سلّ الزيتون / القرحة",
     "sell zitoun|9or7a", "olive knot"),
    ("cochenille", "ravageur", "datepalm__parlatoria_scale", "cochenille", "القشرية / البق الدقيقي",
     "cochenille|9echria", "scale insect"),
    ("virus", "maladie", "tomato__yellow_leaf_curl_virus tomato__mosaic_virus", "virus", "فيروس / الكرمشة",
     "virus|virous|karmcha", "virus"),
    ("nematodes", "ravageur", "", "nématodes (galles sur racines)", "النيماتود / العقد في العروق",
     "nematod|3o9ad fel 3rou9", "root-knot nematodes"),
    # symptoms
    ("jaunissement", "symptome", "N_deficiency Fe_deficiency Mg_deficiency", "jaunissement", "مصفّر / صفار",
     "msaffer|msafra|sfar|safra", "yellowing"),
    ("taches", "symptome", "", "taches", "تنقيط / نقاط / تبقيع", "n9at|tan9it|bou9a3", "spots"),
    ("taches_noires", "symptome", "citrus__black_spot", "taches noires", "نقاط سود", "n9at soud|n9at kahla",
     "black spots"),
    ("dessechement", "symptome", "", "dessèchement", "يبس / يابس", "yebes|yebset|yabes", "drying"),
    ("fletrissement", "symptome", "", "flétrissement", "ذبلان / ذبلت", "dhbel|dbel|dhebla", "wilting"),
    ("enroulement", "symptome", "tomato__yellow_leaf_curl_virus", "feuilles enroulées / gaufrées", "مكمّش / تكمّش",
     "mkammech|tkammech|mkarmech", "leaf curl"),
    ("brulure", "symptome", "", "brûlure", "محروق / حرقة", "ma7rou9|ma7rouk|7ar9a", "scorch, burn"),
    ("trous", "symptome", "tomato__leaf_miner tomato__fruitworm", "trous / galeries", "تقوب / ثقوب",
     "t9oub|tkoub", "holes, mines"),
    ("chute", "symptome", "", "chute des fruits / feuilles", "الطيحان / يطيح", "tay7an|yti7|ta7", "fruit drop"),
    ("poudre_blanche", "symptome", "squash__powdery_mildew", "poudre blanche", "غبرة بيضاء", "ghabra bidha",
     "white powder"),
    ("eclatement", "symptome", "tomato__cracking", "fruit éclaté / fendu", "مشقوق / مفلّق", "mach9ou9|mfalle9",
     "cracked fruit"),
    ("cul_noir", "symptome", "tomato__blossom_end_rot", "cul noir (nécrose apicale)", "تحت الحبة كحل",
     "ta7t el 7abba ka7el|cul noir", "blossom-end rot"),
    # plant parts
    ("feuille", "organe", "", "feuille / feuilles", "ورقة / ورق", "wer9a|war9a|wra9|wrak", "leaf"),
    ("fruit", "organe", "", "fruit / récolte", "غلة / حبة / ثمرة", "ghalla|7abba|thamra", "fruit"),
    ("fleur", "organe", "", "fleur", "نوار", "nouar|nwar", "flower"),
    ("tige", "organe", "", "tige / branche", "ساق / عرف / فرع", "se9|3ref|far3", "stem, branch"),
    ("racine", "organe", "", "racine", "عرق / عروق", "3er9|3rou9", "root"),
    ("tronc", "organe", "", "tronc", "جذع", "jedh3|jed3", "trunk"),
    # farm words
    ("traitement", "general", "", "traitement / pesticide", "دوا / مداوة", "dwa|mdewa|dawa", "pesticide, treatment"),
    ("pulveriser", "general", "", "pulvériser / traiter", "رش / يرش", "rach|yrech|rech", "to spray"),
    ("engrais", "general", "", "engrais", "سماد / غبرة", "smad|ghabra", "fertilizer"),
    ("ammonitrate", "general", "N_deficiency", "ammonitrate", "أمونيتر", "amonitre|amonitr", "ammonium nitrate"),
    ("irrigation", "general", "", "irrigation / arrosage", "سقي / ماء", "s9i|sa9i|ma", "irrigation"),
    ("serre", "general", "", "serre", "سيرة / بيت مكيف", "serra|sirra", "greenhouse"),
    ("champ", "general", "", "champ / parcelle / verger", "سانية / جنان / غابة", "senia|jnen|ghaba",
     "field, orchard"),
    ("recolte", "general", "", "récolte / production", "صابة", "saba|sabba", "harvest, yield"),
    ("secheresse", "general", "", "sécheresse / manque d'eau", "عطش / جفاف", "3atach|jafef", "drought"),
    ("chaleur", "general", "", "chaleur", "سخانة", "s5ana|skhana", "heat"),
    ("pluie", "general", "", "pluie", "نو / مطر", "nou|now|matar", "rain"),
    ("gel", "general", "", "gel / froid", "جليد / برد", "jlid|bard", "frost, cold"),
    ("carence", "general", "", "carence / manque", "نقص", "na9s|nouk9a", "deficiency"),
    ("azote", "general", "N_deficiency", "azote (N)", "آزوت", "azot|azote", "nitrogen"),
    ("fer", "general", "Fe_deficiency", "fer (Fe)", "حديد", "7did|hdid", "iron"),
    ("potassium", "general", "K_deficiency", "potassium (K)", "بوتاس", "potass|potasse", "potassium"),
]
WIKIDATA_ITEMS = os.path.join("src", "preparation", "build_knowledge_base.py")


def agriclic_names():
    """'Tomate - طماطم' pairs of the agriclic.tn menu (home page cached by scrape_agriclic.py, else downloaded)."""
    if os.path.exists(AGRICLIC_HOME):
        h = open(AGRICLIC_HOME, encoding="utf-8").read()
    else:
        h = urllib.request.urlopen(urllib.request.Request("https://www.agriclic.tn/", headers={"User-Agent": UA}),
                                   timeout=60).read().decode("utf-8", "replace")
        os.makedirs(os.path.dirname(AGRICLIC_HOME), exist_ok=True)
        open(AGRICLIC_HOME, "w", encoding="utf-8").write(h)
    pairs = {}
    for m in re.finditer(r'href="https://www\.agriclic\.tn/\d+-[a-z0-9-]+"[^>]*>(.*?)</a>', h, re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", " ", m.group(1)))).strip()
        mm = re.match(r"(.+?)\s*-\s*([؀-ۿ][؀-ۿ \-]*)$", t)
        if mm:
            pairs[mm.group(1).strip().lower()] = mm.group(2).strip()
    return pairs


def wikidata_labels():
    """Scientific name -> (fr, ar, en) labels, for the organisms of the knowledge base (cached)."""
    path = os.path.join(RAW, "wikidata_labels.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    src = open(WIKIDATA_ITEMS, encoding="utf-8").read()
    items = ast.literal_eval(re.search(r"ITEMS = (\[.*?\n\])", src, re.S).group(1))
    vals = " ".join(json.dumps(i[3]) for i in items)
    q = (f'SELECT ?name ?fr ?ar ?en WHERE {{ VALUES ?name {{ {vals} }} ?item wdt:P225 ?name . '
         'OPTIONAL { ?item rdfs:label ?fr FILTER(lang(?fr)="fr") } OPTIONAL { ?item rdfs:label ?ar FILTER(lang(?ar)="ar") } '
         'OPTIONAL { ?item rdfs:label ?en FILTER(lang(?en)="en") } }')
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
    rows = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120))
    out = {}
    for b in rows["results"]["bindings"]:
        out.setdefault(b["name"]["value"], {k: b[k]["value"] for k in ("fr", "ar", "en") if k in b})
    os.makedirs(RAW, exist_ok=True)
    json.dump({"items": [list(i) for i in items], "labels": out}, open(path, "w", encoding="utf-8"),
              ensure_ascii=False)
    return {"items": [list(i) for i in items], "labels": out}


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = [{"concept": c, "type": t, "lien": l, "fr": fr, "ar_msa": "", "ar_tn": tn, "arabizi": az, "en": en,
             "source": "redige", "a_valider": True} for c, t, l, fr, tn, az, en in CURATED]
    # agriclic: Tunisian names of crops, they confirm (or add to) the curated darija
    ac = agriclic_names()
    by_fr = {r["fr"].split(" /")[0].lower(): r for r in rows if r["type"] == "culture"}
    for fr, ar in ac.items():
        r = by_fr.get(fr.replace("blé dur", "blé").replace("blé tendre", "blé"))
        if r and ar.replace("ال", "") not in r["ar_tn"]:
            r["ar_tn"] += f" / {ar}"
        if r and "agriclic" not in r["source"]:
            r["source"] += "+agriclic"
        else:
            rows.append({"concept": re.sub(r"\W+", "_", fr), "type": "culture", "lien": "", "fr": fr, "ar_msa": "",
                         "ar_tn": ar, "arabizi": "", "en": "", "source": "agriclic", "a_valider": False})
    # wikidata: standard Arabic of each organism of the knowledge base
    wd = wikidata_labels()
    for fid, kind, nom, sci, crops, classes in wd["items"]:
        lab = wd["labels"].get(sci, {})
        if lab.get("ar") or lab.get("fr"):
            rows.append({"concept": fid, "type": kind, "lien": " ".join(classes), "fr": nom, "ar_msa": lab.get("ar", ""),
                         "ar_tn": "", "arabizi": "", "en": lab.get("en", sci), "source": "wikidata",
                         "a_valider": False})
    # donnees: French spellings of the crops in the Tunisian list, as synonyms of the crop code
    cm = pd.read_csv(os.path.join("docs", "culture_mapping.csv")).dropna(subset=["crop"])
    for crop, g in cm.groupby("crop"):
        rows.append({"concept": f"graphies_{crop}", "type": "synonymes_fr", "lien": crop, "fr": " | ".join(g["culture"]),
                     "ar_msa": "", "ar_tn": "", "arabizi": "", "en": "", "source": "donnees", "a_valider": False})
    lex = pd.DataFrame(rows)
    lex.to_csv(os.path.join(OUT, "lexique.csv"), index=False, encoding="utf-8")
    print(lex.groupby(["type", "source"]).size().unstack(fill_value=0).to_string())
    n_arabizi = sum(len([v for v in s.split("|") if v]) for s in lex["arabizi"])
    print(f"\n{len(lex)} entries; arabizi spellings: {n_arabizi}; to validate: {int(lex['a_valider'].sum())}")


if __name__ == "__main__":
    main()
