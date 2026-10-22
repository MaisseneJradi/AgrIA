"""Clean the structured data extracted from the three sources and write the final tables used by the agent.

Sources (left untouched): the DGSVCIA PDF (parse_pesticides_tn.py + build_pesticide_refs.py), agrishop.tn
(build_agrishop.py) and agriclic.tn (scrape_agriclic.py). Every table goes through the same text cleaning:
Unicode NFC, typographic quotes and non-breaking spaces made plain, runs of spaces collapsed, trailing separators
removed, glued Latin names split ('Phytophthorainfestans' -> 'Phytophthora infestans', 'Meloidogynespp' ->
'Meloidogyne spp'). Then, per table:
  pesticides  usages whose crop is no crop at all ('par cycle', 'octobre': fragments of the remarks) are rejected;
              company / manufacturer spellings merged ('BIOPROTECTIO N', 'Ets MEZGHANI', 'EtsMezghanni');
              dose split into min / max / unit / basis ('30-50 cc/hl' -> 30, 50, ml, hl); the date of the
              registration committee '(COMM 20/06/2017)' moved out of the dose into its own column;
              crop written once ('P .de terre', 'Poirrier' -> 'Pomme de terre', 'Poirier'), greenhouse flag;
              duplicate usages dropped.
  fertilizers agriclic and agrishop merged into one catalogue with one product type vocabulary; the same product
              sold by both shops is linked (same name once the pack size and the (R) sign are removed);
              organic flag, packs, prices made uniform; doses split as above.
  seeds       species, variety and brand read from the name ('SEMENCE PIMENT BAKLOUTI BADDAR').
Rejected rows go to data/processed/clean/rejects.csv with the reason; counts to docs/cleaning_report.csv.

Usage: python src/preparation/clean_structured.py   (after the four extraction scripts)
Output: data/processed/clean/*.csv
"""
import difflib
import os
import re
import unicodedata
from collections import Counter

import pandas as pd

PEST = os.path.join("data", "processed", "pesticides")
FERT = os.path.join("data", "processed", "fertilizers")
OUT = os.path.join("data", "processed", "clean")
REPORT = os.path.join("docs", "cleaning_report.csv")
log, rejects = [], []

# genera written glued to their species in the sources
GENERA = ["Phytophthora", "Phytophtora", "Bemisia", "Tetranychus", "Rhizoctonia", "Botrytis", "Spilocaea", "Uncinula",
          "Leveillula", "Ectomyelois", "Ectomeylois", "Oligonychus", "Meloidogyne", "Plasmopara", "Plasmopora",
          "Sphaerotheca", "Fusarium", "Penicillium", "Colletotrichum", "Colletotricum", "Alternaria", "Erysiphe",
          "Venturia", "Podosphaera", "Panonychus", "Aculops", "Tuta", "Ceratitis", "Bactrocera", "Chrysomphalus",
          "Helicoverpa", "Spodoptera", "Pythium", "Aschochyta", "Ascochyta", "Mycosphaerella", "Puccinia", "Septoria",
          "Pyrenophora", "Rhynchosporium", "Blumeria", "Lasioderma", "Ephestia", "Planococcus", "Aonidiella",
          "Phyllocnistis", "Aphis", "Myzus", "Thrips", "Frankliniella", "Lobesia", "Cydia", "Prays", "Saissetia",
          "Liriomyza", "Bacillus", "Trichoderma", "Beauveria", "Aureobasidium", "Pseudomonas", "Xanthomonas"]
LATIN = re.compile(r"\b(" + "|".join(GENERA) + r")(spp?\b|[a-z]{3,})")
# crop code (build_pesticide_refs.py) -> French label written once
CROP_FR = {
    "tomato": "Tomate", "pepper": "Piment / Poivron", "eggplant": "Aubergine", "potato": "Pomme de terre",
    "cucumber": "Concombre", "squash": "Courgette", "watermelon": "Pastèque", "melon": "Melon",
    "cucurbits": "Cucurbitacées", "strawberry": "Fraisier", "citrus": "Agrumes", "olive": "Olivier", "grape": "Vigne",
    "apple": "Pommier", "pear": "Poirier", "peach": "Pêcher", "apricot": "Abricotier", "cherry": "Cerisier",
    "plum": "Prunier", "almond": "Amandier", "pistachio": "Pistachier", "nuts": "Fruits à coque",
    "pomegranate": "Grenadier", "fig": "Figuier", "prickly_pear": "Figuier de Barbarie", "datepalm": "Palmier dattier",
    "wheat": "Blé", "barley": "Orge", "oat": "Avoine", "triticale": "Triticale", "corn": "Maïs", "cereals": "Céréales",
    "faba_bean": "Fève / Féverole", "pea": "Petit pois", "bean": "Haricot", "chickpea": "Pois chiche",
    "lentil": "Lentille", "legumes": "Légumineuses", "fenugreek": "Fenugrec", "sugar_beet": "Betterave",
    "rapeseed": "Colza", "sunflower": "Tournesol", "onion": "Oignon", "garlic": "Ail", "artichoke": "Artichaut",
    "carrot": "Carotte", "lettuce": "Laitue", "cabbage": "Chou", "fennel": "Fenouil", "tobacco": "Tabac",
    "vegetables": "Cultures maraîchères", "fruit_trees": "Arbres fruitiers", "ornamental": "Ornement / Forêt",
    "non_crop": "Zones non cultivées", "all_crops": "Toutes cultures", "stored_products": "Denrées stockées", "rodents": "Rongeurs (locaux, champs)",
}
NUM = r"\d+(?:[.,]\d+)?"
UNIT = {"cc": "ml", "ml": "ml", "cl": "cl", "l": "l", "litre": "l", "litres": "l", "lt": "l", "g": "g", "gr": "g",
        "kg": "kg", "t": "t", "%": "%", "diffuseur": "diffuseur", "piege": "piège", "comprime": "comprimé",
        "plaquette": "plaquette", "sachet": "sachet", "boulette": "boulette"}
BASIS = [(r"h\s*l|100\s*l(?:itres?)?", "hl"), (r"ha", "ha"), (r"q(?:l|t|x|uintal)?|100\s*kg", "quintal semences"),
         (r"t(?:onnes?)?", "t"), (r"m\s*[²2]", "m²"), (r"m\s*[³3]", "m³"), (r"l(?:itres?)?", "l"),
         (r"(?:\d+\s*)?plants?|pieds?|arbres?", "plant")]
# the basis is ONE unit word, optionally after a number: '/hl', '/ha', '/100 kg', '/100 l', '/m²'
DOSE = re.compile(rf"(?P<a>{NUM})(?:\s*(?:à|-|a)\s*(?P<b>{NUM}))?\s*"
                  rf"(?P<u>cc|ml|cl|litres?|lt|l|gr|g|kg|t|%|diffuseurs?|pi[èe]ges?|comprim[ée]s?|plaq\w*|sachets?|"
                  rf"boulettes?)(?![a-zé])\.?(?:\s*(?:PC|de produit|p\.c\.?))?"
                  rf"(?:\s*(?:/|par|pour)\s*(?P<base>(?:{NUM}\s*)?(?:kg|litres?|l|[a-zA-Z²³]+)))?", re.I)
COMM = re.compile(r"\(?\s*\.?\s*(?:COMM|com)\.?\s*:?\s*(\d{1,2}\s*/+\s*\d{1,2}\s*/+\s*\d{2,4}|\d{1,2}\s+[a-zéû]+\s+\d{4})"
                  r"\s*\)?", re.I)


def note(table, step, n):
    if n:
        log.append({"table": table, "etape": step, "lignes": int(n)})


def tidy(s):
    """Plain, single-spaced text; NaN stays NaN."""
    if not isinstance(s, str):
        return s
    s = unicodedata.normalize("NFC", s)
    s = s.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "\xa0": " ", " ": " ", "–": "-",
                                   "…": "...", "​": ""}))
    s = LATIN.sub(lambda m: f"{m.group(1)} {m.group(2)}", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;")
    return s or None


def tidy_frame(df, table):
    before = df.copy()
    for c in df.select_dtypes("object"):
        df[c] = df[c].map(tidy)
    changed = sum((before[c].fillna("") != df[c].fillna("")).sum() for c in df.select_dtypes("object"))
    note(table, "texte normalisé (espaces, apostrophes, noms latins)", changed)
    return df


def plain(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def key(s):
    return re.sub(r"[^a-z0-9]", "", plain(s))


def canonical(series, table, col, cutoff=0.9):
    """Merge the spellings of one name (same letters once case/spaces/accents are dropped, or difflib >= cutoff);
    the most frequent spelling wins, upper case."""
    counts = Counter(series.dropna())
    groups = {}
    for name, _ in counts.most_common():
        k = key(name)
        hit = k if k in groups else next(iter(difflib.get_close_matches(k, list(groups), n=1, cutoff=cutoff)), None)
        groups.setdefault(hit or k, []).append(name)
    to = {n: max(g, key=counts.get).upper() for g in groups.values() for n in g}
    out = series.map(lambda x: to.get(x, x))
    note(table, f"{col}: graphies fusionnées ({len(counts)} -> {len(groups)})", (out.fillna("") != series.fillna("")).sum())
    return out


def strip_pack(name):
    """'LUNA EXPERIENCE SC 400 1L' -> 'LUNA EXPERIENCE SC 400'; '(R)' and '®' dropped."""
    s = re.sub(r"[®™]|\(R\)", "", str(name))
    return re.sub(r"\s*\b\d+(?:[.,]\d+)?\s*(?:l|cc|ml|g|gr|kg|litres?)\b\.?\s*$", "", s, flags=re.I).strip()


def parse_dose(text):
    """'30-50 cc/hl (COMM 20/06/2017)' -> min 30, max 50, unite ml, base hl, comm 20/06/2017."""
    out = {"dose_min": None, "dose_max": None, "dose_unite": None, "dose_base": None, "comm": None}
    if not isinstance(text, str):
        return out
    c = COMM.search(text)
    if c:
        out["comm"] = re.sub(r"\s*/+\s*", "/", c.group(1))
    m = DOSE.search(text)
    if not m:
        return out
    a = float(m.group("a").replace(",", "."))
    b = float(m.group("b").replace(",", ".")) if m.group("b") else a
    u = re.sub(r"s$", "", plain(m.group("u")))
    unit = UNIT.get(u) or UNIT.get(m.group("u").lower()) or ("plaquette" if u.startswith("plaq") else u)
    if unit == "cl":
        a, b, unit = a * 10, b * 10, "ml"
    base = (m.group("base") or "").strip().lower()
    out.update(dose_min=a, dose_max=b, dose_unite=unit,
               dose_base=next((lab for rx, lab in BASIS if re.fullmatch(rx, base)), None)
               # basis glued to the next word in the PDF: 'havolume', 'hlcomm', 'hectare', 'plante'
               or next((lab for pre, lab in (("hl", "hl"), ("hectare", "ha"), ("ha", "ha"), ("plant", "plant"))
                        if base.startswith(pre)), base or None))
    return out


def pesticides():
    prod = tidy_frame(pd.read_csv(os.path.join(PEST, "tn_products.csv")), "pesticides_produits")
    for col in ("societe", "fabricant"):
        prod[col] = canonical(prod[col], "pesticides_produits", col)
    prod["comm"] = prod["usage_brut"].map(lambda s: next((re.sub(r"\s*/+\s*", "/", m.group(1))
                                                         for m in COMM.finditer(s or "")), None))
    agg = pd.read_csv(os.path.join(PEST, "product_substances.csv")).groupby("product_id").agg(
        substances_ue=("eu_name", lambda s: " + ".join(x for x in s.dropna())),
        cas=("cas", lambda s: " + ".join(x.strip() for x in s.dropna())), bio_ue=("bio_ue", "all"))
    prod = prod.merge(agg, on="product_id", how="left")

    use = tidy_frame(pd.read_csv(os.path.join(PEST, "tn_usages.csv")), "pesticides_usages")
    bad = use["crop"].isna()
    rejects.extend({"table": "pesticides_usages", "raison": "pas une culture (fragment de remarque)",
                    "id": r.product_id, "texte": f"{r.culture} : {r.cible} : {r.dose}"} for r in use[bad].itertuples())
    note("pesticides_usages", "rejet : culture non reconnue (fragment de texte)", bad.sum())
    use = use[~bad].copy()
    use["culture_fr"] = use["crop"].map(lambda c: " + ".join(CROP_FR.get(x, x) for x in c.split("|")))
    use["sous_serre"] = use["culture_brut"].map(plain).str.contains(r"serre|s/s|abri", na=False)
    dose = pd.DataFrame([parse_dose(f"{d} {r}") for d, r in zip(use["dose"], use["remarques"].fillna(""))],
                        index=use.index)
    use = pd.concat([use, dose], axis=1)
    use["dose"] = use["dose"].map(lambda s: tidy(COMM.sub("", s)) if isinstance(s, str) else s)
    use["remarques"] = use["remarques"].map(lambda s: tidy(COMM.sub("", s)) if isinstance(s, str) else s)
    note("pesticides_usages", "dose découpée (min / max / unité / base)", use["dose_min"].notna().sum())
    n = len(use)
    use = use.drop_duplicates(["product_id", "crop", "sous_serre", "cible", "dose"])
    note("pesticides_usages", "doublons supprimés", n - len(use))
    use = use.merge(prod[["product_id", "societe"]], on="product_id", how="left")
    cols = ["product_id", "nom_commercial", "type", "statut", "substance", "substances_ue", "cas", "conc", "formulation",
            "societe", "culture_fr", "crop", "sous_serre", "culture", "cible", "dose", "dose_min", "dose_max",
            "dose_unite", "dose_base", "dar_jours", "dar_texte", "lmr", "remarques", "bio_ue", "restriction",
            "autorisation_provisoire", "nouveau_22_05_2024", "comm", "page"]
    use[cols].to_csv(os.path.join(OUT, "pesticides_usages.csv"), index=False, encoding="utf-8")
    prod.drop(columns=["usage_brut"]).to_csv(os.path.join(OUT, "pesticides_produits.csv"), index=False,
                                             encoding="utf-8")

    subs = tidy_frame(pd.read_csv(os.path.join(PEST, "substances.csv")), "substances")
    nocas = subs["cas"].str.contains(r"no cas|no unique|see remark", case=False, na=False)
    subs.loc[nocas, "cas"] = None
    note("substances", "CAS absent ('No CAS allocated'...) vidé", nocas.sum())
    subs.to_csv(os.path.join(OUT, "substances.csv"), index=False, encoding="utf-8")

    mrl = pd.read_csv(os.path.join(PEST, "eu_mrl.csv"))
    mrl["mrl_mg_kg"] = pd.to_numeric(mrl["mrl_mg_kg"], errors="coerce")
    for c in ("residue_name", "footnote", "product_fr", "product_en"):
        mrl[c] = mrl[c].map(tidy)
    note("eu_mrl", "LMR non numérique ('No MRL required'...) mise à vide", mrl["mrl_mg_kg"].isna().sum())
    mrl.to_csv(os.path.join(OUT, "eu_mrl.csv"), index=False, encoding="utf-8")

    keep = set(zip(use["product_id"], use["usage_idx"])) if "usage_idx" in use else None
    um = pd.read_csv(os.path.join(PEST, "usage_mrl.csv"))
    um["mrl_mg_kg"] = pd.to_numeric(um["mrl_mg_kg"], errors="coerce")
    um = tidy_frame(um[um["crop"].notna()].copy(), "usage_mrl")
    um.to_csv(os.path.join(OUT, "pesticides_usage_lmr.csv"), index=False, encoding="utf-8")

    ct = tidy_frame(pd.read_csv(os.path.join(PEST, "class_treatments.csv")), "classe_traitements")
    ct.dropna(axis=1, how="all").to_csv(os.path.join(OUT, "classe_traitements.csv"), index=False, encoding="utf-8")
    return keep


FERT_TYPE = [  # regex on sub-category / nature (plain text) -> one vocabulary for both shops
    (r"correcteur|oligo|chelat", "correcteur_carence"), (r"biostim|algue|amine|enracinement|floraison|nouaison",
                                                          "biostimulant"),
    (r"organique|humique|fulvique|amendement", "amendement_organique"), (r"foliaire", "engrais_foliaire"),
    (r"npk|soluble|fertirrigation|granul|engrais|fertilisant", "engrais_npk"), (r"regul", "regulateur_croissance"),
    (r"adjuvant|phytoprotect", "adjuvant"),
]


def fert_type(*texts):
    t = plain(" ".join(str(x) for x in texts if isinstance(x, str)))
    return next((lab for rx, lab in FERT_TYPE if re.search(rx, t)), "autre")


def fertilizers():
    ac = tidy_frame(pd.read_csv(os.path.join(FERT, "agriclic_fertilizers.csv")), "engrais_agriclic")
    ag = tidy_frame(pd.read_csv(os.path.join(FERT, "agrishop_products.csv")), "engrais_agrishop")
    nut_ac = ["N", "P2O5", "K2O", "CaO", "MgO", "SO3", "Fe", "Zn", "Mn", "B", "Cu", "Mo", "SiO2", "matiere_organique",
              "acides_humiques", "acides_fulviques", "acides_amines", "algues"]
    nut_ac = [c for c in nut_ac if c in ac]
    a = pd.DataFrame({
        "source": "agriclic", "id_source": ac["id"], "nom": ac["nom"].map(strip_pack),
        "type": [fert_type(n, s) for n, s in zip(ac["Nature"], ac["sous_categorie"])], "nature": ac["Nature"],
        "composition": ac["Composition"], "chelate": ac["chelate"], "formulation": ac["Formulation"],
        "bio": ac["Biologique"].map(lambda s: None if not isinstance(s, str) else bool(re.search(r"oui|biolog", s, re.I))),
        "conditionnement": ac["Emballage"], "distributeur": ac["Distributeur"], "fabricant": ac["Fabricant"],
        "prix_tnd": ac["prix_tnd"], "usages": ac["Usages"], "description": ac["description"], "url": ac["url"]})
    a = pd.concat([a, ac[nut_ac]], axis=1)
    a["nutriments"] = ac[nut_ac].apply(lambda r: " ".join(c for c in nut_ac if pd.notna(r[c]) and r[c] > 0), axis=1)
    e = ag[ag["categorie"] == "engrais"]
    flags = {"N": "N", "P": "P2O5", "K": "K2O", "Ca": "CaO", "Mg": "MgO", "Fe": "Fe", "Zn": "Zn", "Mn": "Mn", "B": "B",
             "Cu": "Cu", "S": "SO3", "Si": "SiO2", "acides_humiques_fulviques": "acides_humiques",
             "acides_amines": "acides_amines", "algues": "algues"}
    b = pd.DataFrame({
        "source": "agrishop", "id_source": e["id"], "nom": e["nom"].map(strip_pack),
        "type": e["sous_categorie"].map(fert_type), "nature": e["sous_categorie"], "npk": e["npk"],
        "chelate": e["chelate"], "prix_tnd": e["prix_dt"], "actif": e["actif"], "description": e["description"],
        "url": "https://www.agrishop.tn/"})
    b["nutriments"] = e.apply(lambda r: " ".join(v for k, v in flags.items() if r.get(k) is True), axis=1).values
    cat = pd.concat([a, b], ignore_index=True)
    cat["nom_cle"] = cat["nom"].map(key)
    both = cat.groupby("nom_cle")["source"].nunique()
    cat["vendu_aussi_par"] = cat.apply(lambda r: ("agrishop" if r.source == "agriclic" else "agriclic")
                                       if both.get(r.nom_cle, 0) > 1 else None, axis=1)
    note("engrais_catalogue", "même produit chez agriclic et agrishop (relié)", cat["vendu_aussi_par"].notna().sum())
    for col in ("distributeur", "fabricant"):
        cat[col] = canonical(cat[col], "engrais_catalogue", col)
    cat["conditionnement"] = cat["conditionnement"].map(lambda s: re.sub(r"(?i)\s*(litres?|lt)\b", " L",
                                                        re.sub(r"(?i)\s*(gr|grammes?)\b", " g", s)) if isinstance(s, str) else s)
    cat.to_csv(os.path.join(OUT, "engrais_catalogue.csv"), index=False, encoding="utf-8")

    us = tidy_frame(pd.read_csv(os.path.join(FERT, "agriclic_usages.csv")), "engrais_usages")
    us = pd.concat([us, pd.DataFrame([parse_dose(d) for d in us["dose"]], index=us.index).drop(columns="comm")], axis=1)
    note("engrais_usages", "dose découpée (min / max / unité / base)", us["dose_min"].notna().sum())
    us.to_csv(os.path.join(OUT, "engrais_usages.csv"), index=False, encoding="utf-8")

    # deficiency class -> fertilizers: measured content (agriclic) first, then products only named after it
    c1 = pd.read_csv(os.path.join(FERT, "agriclic_class_fertilizers.csv")).assign(source="agriclic", preuve="composition")
    c2 = pd.read_csv(os.path.join(FERT, "class_fertilizers.csv")).rename(columns={"prix_dt": "prix_tnd"}).assign(
        source="agrishop")
    c2 = c2[c2["preuve"] == "nom"]
    note("carence_engrais", "agrishop : produits retenus seulement si le nutriment est dans le nom (pas la description)",
         len(c2))
    cf = pd.concat([c1, c2], ignore_index=True)
    cf["nom"] = cf["nom"].map(strip_pack).map(tidy)
    cf["rang"] = cf["preuve"].map({"composition": 0, "nom": 1})
    cf = cf.sort_values(["unified_class", "rang", "teneur_pct"], ascending=[True, True, False]).drop(columns="rang")
    cf.to_csv(os.path.join(OUT, "carence_engrais.csv"), index=False, encoding="utf-8")

    p = ag[ag["categorie"] == "pesticides"]
    p = p.assign(nom=p["nom"].map(strip_pack), homologue_tn=p["homologation_match"].notna())
    note("pesticides_agrishop", "produits vendus sans homologation retrouvée dans la liste DGSVCIA", (~p["homologue_tn"]).sum())
    p[["id", "nom", "sous_categorie", "prix_dt", "actif", "homologue_tn", "tn_product_id", "tn_nom_commercial",
       "tn_substance", "tn_n_homologation", "description"]].to_csv(os.path.join(OUT, "pesticides_agrishop.csv"),
                                                                    index=False, encoding="utf-8")


BRANDS = {"BADDAR"}


def seeds():
    s = tidy_frame(pd.read_csv(os.path.join(FERT, "agriclic_seeds.csv")), "semences")
    rows = []
    for r in s.itertuples():
        words = re.sub(r"(?i)^semences?\s+", "", r.nom).split()
        brand = words.pop() if words and words[-1].upper() in BRANDS else None
        potager = plain(r.sous_categorie) == "potager" or plain(r.nom).startswith("semence")
        espece = words[0].capitalize() if potager and words else r.nom
        variete = " ".join(words[1:]).title() if potager and len(words) > 1 else None
        rows.append({"id": r.id, "type": "potagere" if potager else "fleur", "espece": espece, "variete": variete,
                     "marque": brand.title() if brand else None, "nom": r.nom, "prix_tnd": r.prix_tnd,
                     "poids": getattr(r, "Poids", None), "description": r.description or r.resume, "url": r.url})
    out = pd.DataFrame(rows)
    note("semences", "espèce / variété / marque lues dans le nom", out["variete"].notna().sum())
    out.to_csv(os.path.join(OUT, "semences.csv"), index=False, encoding="utf-8")


def main():
    os.makedirs(OUT, exist_ok=True)
    pesticides()
    fertilizers()
    seeds()
    pd.DataFrame(rejects).to_csv(os.path.join(OUT, "rejects.csv"), index=False, encoding="utf-8")
    rep = pd.DataFrame(log)
    rep.to_csv(REPORT, index=False, encoding="utf-8")
    print(rep.to_string(index=False))
    print()
    for f in sorted(os.listdir(OUT)):
        print(f"{f:28} {len(pd.read_csv(os.path.join(OUT, f))):>6} rows")


if __name__ == "__main__":
    main()
