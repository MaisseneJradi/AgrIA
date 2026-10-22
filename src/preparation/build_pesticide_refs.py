"""Link the Tunisian registered pesticides (parse_pesticides_tn.py) to the EU Pesticides Database and to the image classes.

1. Active substances: each component of a product ("Azoxystrobine + Difenoconazole") gets its EU name, CAS number,
   EU approval status and residue id. Match order: synonym table (French / trade names / typos) -> exact name ->
   French ending removed (Azoxystrobine -> Azoxystrobin) -> closest name (difflib, ratio >= 0.88).
   bio_ue: the substance is allowed in organic farming (Reg. (EU) 2021/1165 Annex I: micro-organisms, copper, sulphur,
   paraffin oil, pyrethrins, spinosad, azadirachtin, pheromones, plant oils/extracts, attractants for traps...).
   It is an indication on the active substance only: the product label must still carry the organic mention.
2. Crops: the free-text crop of each usage -> project crop code + EU commodity codes (Annex I of Reg. 396/2005).
3. EU MRLs: for every matched residue, the MRL currently applicable on each plant commodity (mg/kg).
4. Targets: cible x crop -> unified_class of the image models (direct target, or vector: whitefly -> TYLCV).

Usage: python src/preparation/build_pesticide_refs.py
Inputs : data/processed/pesticides/tn_products.csv, tn_usages.csv; EU data downloaded to data/raw/eu_pesticides/
Outputs: data/processed/pesticides/substances.csv        one row per substance written in the Tunisian list
         data/processed/pesticides/product_substances.csv one row per product x active substance
         data/processed/pesticides/eu_mrl.csv            residue x EU commodity, MRL in mg/kg
         data/processed/pesticides/usage_mrl.csv         usage x substance x crop -> EU MRL for that crop
         data/processed/pesticides/class_treatments.csv  unified_class -> registered usages
         docs/culture_mapping.csv, docs/cible_class_mapping.csv (for review)
"""
import difflib
import os
import re
import sys
import unicodedata

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import eu_pesticides as eu  # noqa: E402

PEST = os.path.join("data", "processed", "pesticides")

# Tunisian spelling -> EU active substance name (key = lower case, no accent, letters and digits only)
SYNONYMS = {
    "cuivre": "Copper compounds", "cuivremetal": "Copper compounds", "oxychlorurecuivre": "Copper oxychloride",
    "oxychloruredecuivre": "Copper oxychloride", "hydroxydedecuivre": "Copper hydroxide",
    "sulfatedecuivretribasique": "Tribasic copper sulphate", "sulphatedecuivretribasique": "Tribasic copper sulphate",
    "sulfatetetracuivriquetricalcique": "Copper compounds", "soufre": "Sulphur", "folpel": "Folpet",
    "captane": "Captan", "huileminerale": "Paraffin oil/(CAS 64742-46-7)", "huiledeparaffine": "Paraffin oil/(CAS 64742-46-7)",
    "huiledeparaffinique": "Paraffin oil/(CAS 64742-46-7)", "mefenoxam": "Metalaxyl-M", "chinozole": "8-Hydroxyquinoline",
    "ddvp": "Dichlorvos", "phosphuredal": "Aluminium phosphide", "phosphuredhy": "Hydrogen phosphide",
    "phosphuredemagnesium": "Magnesium phosphide", "cyanamidedhydrogene": "Cyanamide",
    "metiramedezinc": "Metiram", "promocarb": "Propamocarb", "propamocarbhydrochloride": "Propamocarb",
    "chlormequatchlorure": "Chlormequat", "acidegibberellique": "Gibberellic acid", "arylextm": "Halauxifen-methyl",
    "arylexactive": "Halauxifen-methyl", "adepidyn": "Pydiflumetofen", "trebuniron": "Tribenuron",
    "tribuneron": "Tribenuron", "pyradaben": "Pyridaben", "kreoxim": "Kresoxim-methyl", "kresoxym": "Kresoxim-methyl",
    "isoxabene": "Isoxaben", "metamsodium": "Metam", "naturalpyrethrin": "Pyrethrins", "pyrethrine": "Pyrethrins",
    "azadirachtine": "Azadirachtin A", "huiledeneem": "Azadirachtin A", "huiledecolza": "Rapeseed oil",
    "huiledessencedorange": "Orange oil", "huileessentielledethym": "Thymol", "garlicextract": "Garlic extract",
    "capsaicine": "Capsicum oleoresin", "cinnamaldheyde": "Cinnamaldehyde", "cinnamomumzeylanicum": "Cinnamaldehyde",
    "laminarin": "Laminarin", "metaldehyde": "Metaldehyde", "methaldehyde": "Metaldehyde", "brodifacoum": "Brodifacoum",
    "difenacoum": "Difenacoum", "acetatedammonium": "Ammonium acetate", "diaminobutane": "Putrescine (1,4-Diaminobutane)",
    "putrescine": "Putrescine (1,4-Diaminobutane)", "trimethylamine": "Trimethylamine hydrochloride",
    "hydrolysatdeproteines": "Hydrolysed proteins", "proteineshydrolysees": "Hydrolysed proteins",
    "derivvesdacidesgrasvegetaux": "Fatty acids C7-C18 and C18 unsaturated potassium salts",
    "melaleucaalternifolia": "Melaleuca alternifolia (tea tree) oil", "reynoutriasachalinensis": "Reynoutria sachalinensis extract",
    "pythiumoligandrum": "Pythium oligandrum M1", "spores": "Lecanicillium muscarium (formerly Verticilium lecanii) strain Ve6",
    "lecanicillium": "Lecanicillium muscarium (formerly Verticilium lecanii) strain Ve6",
    "helicoverpaarmigera": "Helicoverpa armigera nucleopolyhedrovirus (HearNPV)",
    "splinpv": "Spodoptera littoralis nucleopolyhedrovirus", "aureobasidium": "Aureobasidium pullulans (strains DSM 14940 and DSM 14941)",
    "aurebasidium": "Aureobasidium pullulans (strains DSM 14940 and DSM 14941)", "dsm14941": "Aureobasidium pullulans (strains DSM 14940 and DSM 14941)",
    "bacillusthuringiensis": "Bacillus thuringiensis subsp. Kurstaki strain ABTS-351",
    "beauveriabassiana": "Beauveria bassiana strain ATCC 74040", "bacillusamyloliquefaciensqst": "Bacillus amyloliquefaciens strain QST 713 (formerly Bacillus subtilis strain QST 713)",
    "bacillusamyloliquefacienssouchefzb24": "Bacillus amyloliquefaciens strain FZB24", "bacillussubtilis": "Bacillus subtilis strain IAB/BS03",
    "bs03": "Bacillus subtilis strain IAB/BS03", "trichodermaasperellumicc012": "Trichoderma asperellum (formerly T. harzianum) strain ICC012",
    "trichodermagamsii": "Trichoderma gamsii (formerly T. viride) strain ICC080", "trichodermaasperellum": "Trichoderma asperellum strain T34",
    "trichodermaatroviride77b": "Trichoderma atroviride 77B", "trichodermaharzianumt22": "Trichoderma afroharzianum (formerly T. harzianum) strain T-22",
    "metarhizium": "Metarhizium brunneum strain Ma 43", "pheromone": "Straight Chain Lepidopteran Pheromones (SCLPs) - Acetates",
    "keromone": "Ethyl acetate", "dodecatrienyl": "Straight Chain Lepidopteran Pheromones (SCLPs) - Acetates",
    "tetradeca": "Straight Chain Lepidopteran Pheromones (SCLPs) - Acetates", "methyl5nonan": "4-Methylnonan-5-ol / 4-methylnonan-5-one",
    "killdisc": "Esfenvalerate", "lambada": "Lambda-Cyhalothrin", "lambdacyhalothrin": "Lambda-Cyhalothrin",
    "alphamethrine": "Alpha-Cypermethrin", "alphacypermethrine": "Alpha-Cypermethrin", "deltametrine": "Deltamethrin",
    "acetameprid": "Acetamiprid", "dimeyhomorph": "Dimethomorph", "dimetomorphe": "Dimethomorph", "manipropamide": "Mandipropamid",
    "difeconazole": "Difenoconazole", "fludioxinil": "Fludioxonil", "chlorantranliprole": "Chlorantraniliprole",
    "forasulam": "Florasulam", "florosulame": "Florasulam", "pendimeyhalin": "Pendimethalin", "pyrachlostrobin": "Pyraclostrobin",
    "fostetyl": "Fosetyl", "fosethyl": "Fosetyl", "fosetyl": "Fosetyl", "fenhexamide": "Fenhexamid",
    "clodinafoppropagyl": "Clodinafop", "clodinafoppropargil": "Clodinafop", "clodinafoppropargyl": "Clodinafop",
    "cloquintocet": "Cloquintocet-mexyl", "mefenpyr": "Mefenpyr-diethyl", "mefempyrdiethyl": "Mefenpyr-diethyl",
    "sedexane": "Sedaxane", "propoxcarbasone": "Propoxycarbazone", "flucarbazone": "Flucarbazone",
    "triflusulfuronmethyl": "Triflusulfuron (formerly Triflusulfuron-methyl)", "dinocapmeptyl": "Meptyldinocap",
    "clorpyriphosethyl": "Chlorpyrifos", "dimethoate": "Dimethoate", "zirame": "Ziram", "etofenprox": "Etofenprox",
    "aminopyralydes": "Aminopyralid", "naphoxy2acetamide": "2-(1-Naphthyl)acetamide", "acidebetaindolbutirique": "Indolylbutyric acid",
    "acidechloro4phenoxyacetique": "4-CPA", "acetamipride": "Acetamiprid", "chromafenozide": "Chromafenozide",
    "ethametsulfuronmethyl": "Ethametsulfuron-methyl", "iodosulfuron": "Iodosulfuron", "mesosulfuron": "Mesosulfuron",
    "metsulfuron": "Metsulfuron-methyl", "tribenuron": "Tribenuron", "fluroxypyr": "Fluroxypyr", "24d": "2,4-D", "dicamba": "Dicamba", "emamectin": "Emamectin", "bixafen": "Bixafen",
    "promecarb": "Propamocarb", "swingleaglutinosa": "Swinglea glutinosa extract", "huiledepin": "Pine oil",
    "pyrimiphosmethyl": "Pirimiphos-methyl", "pyrimicarbe": "Pirimicarb", "phenothiol": "MCPA-thioethyl",
    "borax": "Disodium octaborate", "fluazaindolizine": "Fluazaindolizine", "fluazaindolzine": "Fluazaindolizine",
    "pyroxasulfone": "Pyroxasulfone", "cycloxidime": "Cycloxydim", "fluazifoppbutyl": "Fluazifop-P",
    "diaminubutane": "Putrescine (1,4-Diaminobutane)", "allyisothiocyanate": "Allyl isothiocyanate", "tolfenpyrade": "Tolfenpyrad", "simazine": "Simazine", "prometryn": "Prometryn",
}
# components that are not active substances (co-formulants, adjuvants) or units left by the splitter
NOT_SUBSTANCE = re.compile(r"^(adjuvant|surfer|polyether|alkylphenol|sodiumlaurylether|huilenonionique|polyoxyethylene|"
                           r"polyethermodified|kg|l|g|sachet|piege|diffuseur|e|z|metyl|\d+)$")
# Reg. (EU) 2021/1165 Annex I (organic farming): substances or families allowed, matched on the EU name
BIO = re.compile(r"(?:copper|sulphur|paraffin oil|pyrethrins|spinosad|azadirachtin|pheromone|laminarin|orange oil|"
                 r"fatty acids|rapeseed oil|garlic|capsicum|tea tree|reynoutria|swinglea|ammonium acetate|"
                 r"putrescine|trimethylamine|hydrolysed proteins|lime sulphur|potassium hydrogen carbonate|"
                 r"sodium hydrogen carbonate|kaolin|ferric phosphate|cerevisane|thymol|pine oil|nucleopolyhedrovirus)", re.I)

# crop text -> (project crop code, EU commodity codes). Order matters: first match wins. A crop "a|b" covers both
# ("Arbo + Vigne"). Reviewed 2026-10-22: short words are matched whole (\b) where they hide in others
# ("rat" in "curatif", "pepin" in "pepiniere", "mais" the conjunction).
CROPS = [
    (r"arbo.*vigne|arboriculture.*vigne", "fruit_trees|grape", ["0151010", "0151020"]),
    (r"semence.*cereal|cereal.*semence", "cereals", ["0500090", "0500010", "0500050"]),
    (r"semence.*\bble|\bble.*semence", "wheat", ["0500090"]),
    (r"semence.*orge", "barley", ["0500010"]),
    (r"semence.*(pomme de terre|p\s*\.?\s*de\s*terre)", "potato", ["0211000"]),
    (r"tomate", "tomato", ["0231010"]),
    (r"poivron|piment", "pepper", ["0231020"]),
    (r"aubergine", "eggplant", ["0231030"]),
    (r"pomme de terre|p\s*\.?\s*de\s*terre|\bpdt\b", "potato", ["0211000"]),
    (r"co[n]?combre", "cucumber", ["0232010"]),
    (r"courgette|courge", "squash", ["0232030"]),
    (r"pasteque", "watermelon", ["0233030"]),
    (r"melon", "melon", ["0233010"]),
    (r"cucurbit", "cucurbits", ["0232010", "0232030", "0233010", "0233030"]),
    (r"fraisier|fraise|frasier", "strawberry", ["0152000"]),
    (r"citronnier|citron", "citrus", ["0110030"]),
    (r"agrume|oranger|mandarinier|clementin|maltaise", "citrus", ["0110020", "0110030", "0110050"]),
    (r"olivier|olive|oliver", "olive", ["0402010", "0161030"]),
    (r"vigne de table|raisin de table", "grape", ["0151010"]),
    (r"vigne de cuve|raisin de cuve", "grape", ["0151020"]),
    (r"vigne|raisin", "grape", ["0151010", "0151020"]),
    (r"pommier", "apple", ["0130010"]),
    (r"poir+ier", "pear", ["0130020"]),
    (r"pecher|nectarin", "peach", ["0140030"]),
    (r"abricotier", "apricot", ["0140010"]),
    (r"cerisier", "cherry", ["0140020"]),
    (r"prunier", "plum", ["0140040"]),
    (r"amandier|amande", "almond", ["0120010"]),
    (r"pistach", "pistachio", ["0120100"]),
    (r"noisett", "nuts", ["0120060"]),
    (r"pignon", "nuts", ["0120090"]),
    (r"grenadier|grenade", "pomegranate", ["0163050"]),
    (r"figuier", "fig", ["0161020"]),
    (r"cactus|figue de barbarie", "prickly_pear", ["0162040"]),
    (r"palmier|datt", "datepalm", ["0161010"]),
    (r"ble dur|ble tendre|\bbles?\b|^tendre$", "wheat", ["0500090"]),
    (r"\borge\b", "barley", ["0500010"]),
    (r"avoine", "oat", ["0500050"]),
    (r"triticale", "triticale", ["0500990"]),
    (r"\bmais\b", "corn", ["0500030"]),
    (r"cereale|grandes cultures", "cereals", ["0500090", "0500010", "0500050"]),
    (r"feverole|fevrole|feve", "faba_bean", ["0260020", "0300010"]),
    (r"pois.?chiche", "chickpea", ["0300990"]),
    (r"petit pois|\bpois\b", "pea", ["0260040"]),
    (r"haricot", "bean", ["0260010"]),
    (r"lentille", "lentil", ["0300020"]),
    (r"legum\w*neuse", "legumes", ["0260020", "0300010", "0300030"]),
    (r"fenugrec", "fenugreek", []),
    (r"betterave", "sugar_beet", ["0900010"]),
    (r"colza", "rapeseed", ["0401060"]),
    (r"tournesol", "sunflower", ["0401050"]),
    (r"oignon", "onion", ["0220020"]),
    (r"\bail\b", "garlic", ["0220010"]),
    (r"artichaut", "artichoke", ["0270050"]),
    (r"carotte", "carrot", ["0213020"]),
    (r"laitue|salade", "lettuce", ["0251020"]),
    (r"\bchoux?\b", "cabbage", ["0242020"]),
    (r"fenouil", "fennel", ["0270040"]),
    (r"tabac", "tobacco", []),
    (r"maraich|\blegumes?\b|\bserres?\b", "vegetables", []),
    (r"ornement|gazon|pepiniere|substrat|forest|foret|rosier", "ornamental", []),
    (r"\barbo|arbres? fruitier|fruitier|rosacee|\bpepins?\b|noyau", "fruit_trees", []),
    (r"toutes cultures", "all_crops", []),
    (r"criquet|acridien", "non_crop", []),
    (r"sol nu|non cultiv|\bbords?\b|chemin|desherbage total|zones? non", "non_crop", []),
    (r"stock|\bgrains?\b|denree|magasin|silo|entrepot", "stored_products", []),
    (r"\brats?\b|souris|mulot|rongeur|campagnol", "rodents", []),
]
# group crops cover the project crops below when matching targets to image classes. "Cereales" in the Tunisian
# list means small-grain cereals (wheat, barley, oat): not maize.
GROUPS = {"vegetables": ["tomato", "pepper", "potato", "squash", "cucumber", "melon", "eggplant"],
          "cucurbits": ["squash", "cucumber", "melon", "watermelon"],
          "fruit_trees": ["apple", "pear", "peach", "cherry", "apricot", "plum", "almond"],
          "cereals": ["wheat", "barley", "oat"]}

# (crops, regex on the target, unified_class, relation, exclusion regex): the target written in the list -> image
# class. relation: direct = the pest/disease of the class; vecteur = insect spreading the virus of the class;
# proche = same symptom family, other pathogen (fallback); "groupe" is added when the usage names a crop group
# ("Arbo", "Cultures maraicheres") rather than the crop itself. Reviewed 2026-10-22:
#   - no aphid -> tomato mosaic virus: ToMV spreads by contact and seed, not by aphids;
#   - noctuelles defoliatrices (Spodoptera) eat leaves: the fruitworm class is Helicoverpa;
#   - Aculops lycopersici (russet mite) is not the spider mite of the class;
#   - Leveillula taurica is the powdery mildew of Solanaceae, not of cucurbits.
TARGETS = [
    (["tomato"], r"mildiou|phytophthora infestans", "tomato__late_blight", "direct", None),
    (["tomato"], r"alternari", "tomato__early_blight", "direct", None),
    (["tomato"], r"septori", "tomato__septoria_leaf_spot", "direct", None),
    (["tomato"], r"cladospori|fulvia|passalora", "tomato__leaf_mold", "direct", None),
    (["tomato"], r"acarien|tetranyque|tetranychus", "tomato__spider_mites", "direct", r"aculops|eriophy|bronz"),
    (["tomato"], r"tuta|mineuse", "tomato__leaf_miner", "direct", None),
    (["tomato"], r"noctuelle|helicoverpa|heliothis", "tomato__fruitworm", "direct", r"defoliat|asparagus|spodoptera"),
    (["tomato"], r"bacteri|xanthomonas|pseudomonas", "tomato__bacterial_spot", "direct", None),
    (["tomato"], r"anthracnose|colletotrichum", "tomato__anthracnose", "direct", None),
    (["tomato"], r"botrytis|pourriture grise|moisissure", "tomato__mold", "direct", None),
    (["tomato"], r"corynespora", "tomato__target_spot", "direct", None),
    (["tomato"], r"mouche blanche|aleurode|bemisia", "tomato__yellow_leaf_curl_virus", "vecteur", None),
    (["potato"], r"mildiou|phytophthora infestans", "potato__late_blight", "direct", None),
    (["potato"], r"alternari", "potato__early_blight", "direct", None),
    (["apple"], r"tavelure|venturia", "apple__scab", "direct", None),
    (["apple"], r"rouille|gymnosporangium", "apple__rust", "direct", None),
    (["apple"], r"black.?rot|pourriture noire|botryosphaeria", "apple__black_rot", "direct", None),
    (["cherry"], r"oidium", "cherry__powdery_mildew", "direct", r"grappe"),
    (["peach"], r"bacteri|xanthomonas", "peach__bacterial_spot", "direct", None),
    (["pepper"], r"bacteri|xanthomonas", "pepper__bacterial_spot", "direct", None),
    (["grape"], r"black.?rot|guignardia", "grape__black_rot", "direct", None),
    (["grape"], r"esca", "grape__esca", "direct", None),
    (["grape"], r"isariopsis|pseudocercospora", "grape__leaf_blight", "direct", None),
    (["olive"], r"oeil de paon|cycloconium|spilocaea|venturia oleaginea", "olive__peacock_spot", "direct", None),
    (["olive"], r"tuberculose|savastanoi", "olive__knot_disease", "direct", None),
    (["olive"], r"phytopte|aculus|eriophy|acarien", "olive__aculus_olearius", "direct", None),
    (["citrus"], r"chancre|xanthomonas", "citrus__canker", "direct", None),
    (["citrus"], r"phyllosticta|guignardia|taches? noires?|black spot|cbs", "citrus__black_spot", "direct", None),
    (["citrus"], r"elsinoe|tavelure", "citrus__scab", "direct", None),
    (["citrus"], r"psylle|diaphorina|trioza", "orange__citrus_greening", "vecteur", None),
    (["datepalm"], r"parlatoria|cochenille", "datepalm__parlatoria_scale", "direct", None),
    (["datepalm"], r"bayoud|fusarium", "datepalm__fusarium_wilt", "direct", None),
    (["datepalm"], r"thielaviopsis|black scorch", "datepalm__black_scorch", "direct", None),
    (["datepalm"], r"graphiola|taches? foliaires?|faux charbon", "datepalm__leaf_spots", "direct", None),
    (["datepalm"], r"dessechement foliaire|alternaria", "datepalm__leaf_spots", "proche", None),
    (["datepalm"], r"diplodia|pourriture du rachis", "datepalm__rachis_blight", "direct", None),
    (["strawberry"], r"diplocarpon|brulure", "strawberry__leaf_scorch", "direct", None),
    (["strawberry"], r"taches? pourpres", "strawberry__leaf_scorch", "proche", None),
    (["wheat"], r"rouille", "wheat__leaf_rust", "direct", r"rouille jaune|rouille noire"),
    (["corn"], r"rouille|puccinia", "corn__common_rust", "direct", None),
    (["corn"], r"helminthospori|exserohilum", "corn__northern_leaf_blight", "direct", None),
    (["corn"], r"cercospor", "corn__gray_leaf_spot", "direct", None),
    (["squash", "cucumber", "melon", "watermelon"], r"oidium", "squash__powdery_mildew", "direct", r"leveillula"),
    (["pomegranate"], r"alternari", "pomegranate__alternaria_spot", "direct", None),
    (["pomegranate"], r"anthracnose|colletotrichum", "pomegranate__anthracnose", "direct", None),
    (["pomegranate"], r"cercospor", "pomegranate__cercospora_spot", "direct", None),
    (["pomegranate"], r"bacteri|xanthomonas", "pomegranate__bacterial_blight", "direct", None),
]


def key(s):
    s = str(s).replace("œ", "oe").replace("Œ", "OE")
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def plain(s):
    s = str(s).replace("œ", "oe").replace("Œ", "OE")  # NFKD drops the ligature: oeil -> il
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def components(s):
    """'Azoxystrobine + Difenoconazole' -> ['Azoxystrobine', 'Difenoconazole'] (concentrations and units dropped)."""
    if not isinstance(s, str):
        return []
    out = []
    for part in re.split(r"\s*(?:\+|&)\s*", s):
        part = re.sub(r"\d+(?:[.,]\d+)?\s*(?:g|mg|ml|%|kg|l)\b.*$", "", part, flags=re.I).strip(" :;,(")
        if part and not NOT_SUBSTANCE.match(key(part)):
            out.append(part)
    return out


class SubstanceMatcher:
    def __init__(self):
        recs = {}
        for r in eu.active_substances():  # several records per substance (one per regulation): keep one
            recs.setdefault(r["substance_name"], r)
        self.recs = recs
        self.by_key = {}
        for name in recs:
            for k in {key(name), key(re.split(r"[(/]", name)[0])}:
                self.by_key.setdefault(k, name)

    def match(self, raw):
        k = key(raw)
        inner = re.findall(r"\(([^)]*)\)", raw)
        for cand, how in [(k, "synonym")] + [(key(i), "synonym") for i in inner]:
            for sk, name in SYNONYMS.items():
                if cand == sk or (len(sk) >= 3 and cand.startswith(sk)) or (len(sk) >= 8 and sk in cand):
                    return self._found(name, how)
        for cand in [k, key(re.sub(r"\(.*", "", raw))] + [key(i) for i in inner]:
            for variant in (cand, cand[:-1] if cand.endswith("e") else cand, re.sub(r"e$", "", cand) + "e"):
                if variant in self.by_key:
                    return self._found(self.by_key[variant], "exact")
        # ester / salt written in the Tunisian list but not in the EU name: Bensulfuron-methyl -> Bensulfuron
        bare = re.sub(r"(methyle?|ethyle?|sodium|potassium|butyl|propargyl|mexyl|ehe|acide)+$", "", k)
        if bare != k and bare in self.by_key:
            return self._found(self.by_key[bare], "exact")
        close = difflib.get_close_matches(key(re.sub(r"\(.*", "", raw)), list(self.by_key), n=1, cutoff=0.9)
        if close:
            return self._found(self.by_key[close[0]], "fuzzy")
        return {"eu_name": "", "match": "none"}

    def _found(self, name, how):
        r = self.recs.get(name)
        if r is None:  # synonym target spelled differently in the EU list: closest EU name
            close = difflib.get_close_matches(key(name), list(self.by_key), n=1, cutoff=0.8)
            if not close:
                return {"eu_name": name, "match": how + "_not_in_eu_db"}
            r = self.recs[self.by_key[close[0]]]
        res = re.search(r"pest_res_id_list=(\d+)", r.get("pest_res_mrl_webpage") or "")
        return {"eu_name": r["substance_name"], "match": how, "cas": r.get("as_cas_number") or r.get("cas_number"),
                "eu_status": r["substance_status"], "eu_category": r.get("substance_category"),
                "micro_organism": r.get("as_micro_org") == "Yes", "residue_id": int(res.group(1)) if res else None,
                "residue_name": (r.get("pesticide_residue_linked") or "").strip()}


def crop_of(culture):
    t = plain(culture)
    for rx, crop, codes in CROPS:
        if re.search(rx, t):
            return crop, codes
    return "", []


def build_mrls(residue_ids):
    """Current EU MRL of each residue on each plant commodity (codes below 1000000 = not animal products)."""
    prods = {p["product_id"]: p for p in eu.products("EN")}
    prods_fr = {p["product_id"]: p["product_name"] for p in eu.products("FR")}
    rows = []
    for rid, recs in eu.mrls_many(residue_ids).items():
        for m in recs:
            p = prods.get(m["product_id"])
            if not p or p["product_code"] >= "1000000" or m.get("applicability_text") != "Applicable":
                continue
            rows.append({"residue_id": rid, "product_code": p["product_code"], "product_en": p["product_name"],
                         "product_fr": prods_fr.get(m["product_id"]), "mrl_mg_kg": m.get("mrl_value_only"),
                         "at_lod": m.get("mrl_lod") == "*", "mrl_text": m.get("mrl_value"),
                         "regulation": m.get("regulation_number"), "application_date": m.get("application_date"),
                         "footnote": m.get("footnote_text")})
    df = pd.DataFrame(rows)
    return df.sort_values(["residue_id", "product_code", "application_date"]).drop_duplicates(
        ["residue_id", "product_code"], keep="last")


def main():
    prod = pd.read_csv(os.path.join(PEST, "tn_products.csv"))
    use = pd.read_csv(os.path.join(PEST, "tn_usages.csv"))

    # 1. substances
    m = SubstanceMatcher()
    ps = [{"product_id": r.product_id, "substance_tn": c} for r in prod.itertuples() for c in components(r.substance)]
    ps = pd.DataFrame(ps)
    # "Chlorantraniliprole Abamectin": two substances without '+' -> one row per word when every word matches
    split = {}
    for s in ps["substance_tn"].unique():
        words = s.split()
        if m.match(s)["match"] == "none" and len(words) > 1 and all(m.match(w)["match"] != "none" for w in words):
            split[s] = list(dict.fromkeys(words))
    ps["substance_tn"] = ps["substance_tn"].map(lambda s: split.get(s, s))
    ps = ps.explode("substance_tn").drop_duplicates().reset_index(drop=True)
    subs = pd.DataFrame([{"substance_tn": s, **m.match(s)} for s in sorted(ps["substance_tn"].unique())])
    subs["bio_ue"] = subs["micro_organism"].eq(True) | subs["eu_name"].str.contains(BIO, na=False)
    subs.to_csv(os.path.join(PEST, "substances.csv"), index=False, encoding="utf-8")
    ps = ps.merge(subs[["substance_tn", "eu_name", "cas", "eu_status", "residue_id", "bio_ue"]], on="substance_tn")
    ps["residue_id"] = ps["residue_id"].astype("Int64")
    ps.to_csv(os.path.join(PEST, "product_substances.csv"), index=False, encoding="utf-8")
    agg = ps.groupby("product_id").agg(substances_ue=("eu_name", lambda s: " + ".join(x for x in s if x)),
                                       cas=("cas", lambda s: " + ".join(x for x in s.dropna() if x)),
                                       bio_ue=("bio_ue", "all")).reset_index()
    print(f"substances: {len(subs)} spellings -> {subs['eu_name'].replace('', pd.NA).nunique()} EU substances; "
          f"match {subs['match'].value_counts().to_dict()}")

    # 2. crops
    cm = use[["culture"]].drop_duplicates()
    cm[["crop", "eu_codes"]] = [(c, " ".join(k)) for c, k in (crop_of(x) for x in cm["culture"])]
    cm["n_usages"] = cm["culture"].map(use["culture"].value_counts())
    cm.sort_values("n_usages", ascending=False).to_csv(os.path.join("docs", "culture_mapping.csv"), index=False)
    use = use.drop(columns=[c for c in ("crop", "substances_ue", "cas", "bio_ue") if c in use]) \
             .merge(cm[["culture", "crop"]], on="culture", how="left").merge(agg, on="product_id", how="left")
    use.to_csv(os.path.join(PEST, "tn_usages.csv"), index=False, encoding="utf-8")
    print(f"crops: {(cm['crop'] != '').mean():.0%} of the crop spellings mapped "
          f"({use['crop'].fillna('').ne('').mean():.0%} of the usage rows)")

    # 3. EU MRLs
    mrl = build_mrls(set(ps["residue_id"].dropna().astype(int)))
    names = subs.dropna(subset=["residue_id"]).drop_duplicates("residue_id").set_index("residue_id")
    mrl.insert(1, "residue_name", mrl["residue_id"].map(names["residue_name"]))
    mrl.to_csv(os.path.join(PEST, "eu_mrl.csv"), index=False, encoding="utf-8")
    codes = cm.set_index("culture")["eu_codes"].str.split().to_dict()
    um = use.drop(columns=["cas"]).merge(ps[["product_id", "substance_tn", "eu_name", "cas", "residue_id"]], on="product_id")
    um["product_code"] = um["culture"].map(codes)
    um = um.explode("product_code").dropna(subset=["product_code", "residue_id"])
    um = um.merge(mrl[["residue_id", "product_code", "product_fr", "mrl_mg_kg", "at_lod"]], on=["residue_id", "product_code"],
                  how="left")
    um[["product_id", "usage_idx", "nom_commercial", "culture", "crop", "cible", "dose", "dar_jours", "substance_tn",
        "eu_name", "cas", "residue_id", "product_code", "product_fr", "mrl_mg_kg", "at_lod"]] \
        .to_csv(os.path.join(PEST, "usage_mrl.csv"), index=False, encoding="utf-8")
    print(f"EU MRL: {len(mrl)} residue x commodity values for {mrl['residue_id'].nunique()} residues; "
          f"usage x substance x commodity rows {len(um)}, with an EU MRL {um['mrl_mg_kg'].notna().mean():.0%}")

    # 4. targets -> image classes
    rows = []
    for r in use.itertuples():
        named = r.crop.split("|") if isinstance(r.crop, str) else []
        crops = {c for n in named for c in GROUPS.get(n, [n])}
        t = plain(r.cible)
        for tcrops, rx, cls, rel, excl in TARGETS:
            if crops & set(tcrops) and re.search(rx, t) and not (excl and re.search(excl, t)):
                if rel == "direct" and not set(named) & set(tcrops):
                    rel = "groupe"  # the usage names a crop group ("Arbo"), not the crop of the class
                rows.append({"unified_class": cls, "relation": rel, "product_id": r.product_id,
                             "usage_idx": r.usage_idx, "nom_commercial": r.nom_commercial, "type": r.type,
                             "substances_ue": r.substances_ue, "culture": r.culture, "cible": r.cible, "dose": r.dose,
                             "dar_jours": r.dar_jours, "statut": r.statut, "restriction": r.restriction,
                             "autorisation_provisoire": r.autorisation_provisoire, "bio_ue": r.bio_ue})
    ct = pd.DataFrame(rows).drop_duplicates(["unified_class", "product_id", "usage_idx"])
    ct.to_csv(os.path.join(PEST, "class_treatments.csv"), index=False, encoding="utf-8")
    review = ct.assign(cible_norm=ct["cible"].map(plain)).groupby(["unified_class", "relation", "cible_norm"]) \
               .size().rename("n_usages").reset_index()
    review.to_csv(os.path.join("docs", "cible_class_mapping.csv"), index=False)
    classes = set()
    for t in ("diseases", "fruits"):
        classes |= set(pd.read_csv(os.path.join("data", "processed", f"{t}_manifest.csv"))["class"])
    sick = sorted(c for c in classes if not c.endswith("healthy"))
    cover = ct.groupby("unified_class")["product_id"].nunique()
    print(f"classes: {cover.size}/{len(sick)} disease classes have at least one registered product")
    print(cover.reindex(sick).fillna(0).astype(int).to_string())


if __name__ == "__main__":
    main()
