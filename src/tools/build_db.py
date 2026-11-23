"""Load the clean tables into one SQLite base: data/processed/agria.db (not in Git, rebuilt in a few seconds).

Usage: python src/tools/build_db.py
Tables
  traitements        image class -> registered product usage, from the validated rows of docs/disease_target_mapping.csv
                     applied to pesticides/tn_usages.csv (src/tools/target_mapping.py; until step 2 of the phyto plan:
                     clean/classe_traitements.csv, which they give back exactly), with the DAR text and the restrictions
                     of pesticides/tn_usages.csv and of the product list
  usage_lmr          EU maximum residue limits of each usage substance (clean/pesticides_usage_lmr.csv)
  pesticides_produits, pesticides_usages, pesticides_agrishop, substances
  carence_engrais, engrais_catalogue, engrais_usages, semences
  besoins_eau, climat_mensuel, gouvernorats, sols, kc
  lexique, fiches, varietes, culture_mapping, regles_carences (one JSON row per deficiency)
  meta               build date and source file of every table
The CSV files are never changed.
"""
import json
import sqlite3
import sys
import time

import pandas as pd

from common import DB_PATH, PROC, ROOT
from target_mapping import MAPPING
from target_mapping import load as load_mapping
from target_mapping import usage_classes

CLEAN, CTX, KNOW = PROC / "clean", PROC / "context", PROC / "knowledge"
FILES = {
    "usage_lmr": CLEAN / "pesticides_usage_lmr.csv",
    "eu_mrl": CLEAN / "eu_mrl.csv",  # with mrl_text: "No MRL required" (Annex IV) is not a missing value
    "pesticides_produits": CLEAN / "pesticides_produits.csv",
    "pesticides_usages": CLEAN / "pesticides_usages.csv",
    "pesticides_agrishop": CLEAN / "pesticides_agrishop.csv",
    "substances": CLEAN / "substances.csv",
    "carence_engrais": CLEAN / "carence_engrais.csv",
    "engrais_catalogue": CLEAN / "engrais_catalogue.csv",
    "engrais_usages": CLEAN / "engrais_usages.csv",
    "semences": CLEAN / "semences.csv",
    "besoins_eau": CTX / "besoins_eau_mensuels.csv",
    "climat_mensuel": CTX / "climat_mensuel.csv",
    "gouvernorats": CTX / "gouvernorats.csv",
    "sols": CTX / "sols.csv",
    "kc": CTX / "kc_fao56.csv",
    "lexique": KNOW / "lexique.csv",
    "varietes": KNOW / "varietes_tn.csv",
    "culture_mapping": ROOT / "docs" / "culture_mapping.csv",
}
INDEXES = [("traitements", "unified_class"), ("usage_lmr", "product_id, usage_idx"),
           ("carence_engrais", "unified_class"), ("besoins_eau", "gouvernorat, crop, mois"),
           ("pesticides_produits", "product_id")]


def class_treatments():
    """Image class -> registered use, from the VALIDATED rows of docs/disease_target_mapping.csv (target_mapping.py).
    Text cleaned as clean_structured.py cleans classe_traitements.csv (which these rows give back exactly)."""
    sys.path.insert(0, str(ROOT / "src" / "preparation"))
    from clean_structured import COMM, tidy  # noqa: E402
    ct = usage_classes(pd.read_csv(PROC / "pesticides" / "tn_usages.csv"), load_mapping())
    ct = ct.drop(columns=["restriction"])  # the restriction of the use is joined below as restriction_usage
    for c in ct.select_dtypes("object"):
        ct[c] = ct[c].map(tidy)
    # "40 cc/hl (COMM 06/12/2012)": the date of the commission decision is not part of the dose (phyto step 3; the
    # clean table pesticides_usages drops it the same way). It is kept in its own column.
    ct["comm_dose"] = ct["dose"].map(lambda s: next((m.group(1) for m in COMM.finditer(s)), None)
                                     if isinstance(s, str) else None)
    ct["dose"] = ct["dose"].map(lambda s: tidy(COMM.sub("", s)) if isinstance(s, str) else s)
    return ct.astype({"usage_idx": int, "autorisation_provisoire": bool, "bio_ue": bool})


def treatments():
    ct = class_treatments()
    use = pd.read_csv(PROC / "pesticides" / "tn_usages.csv",
                      usecols=["product_id", "usage_idx", "dar_texte", "restriction", "lmr", "remarques"])
    use = use.rename(columns={"restriction": "restriction_usage", "lmr": "remarques_lmr"})
    # a usage covering several crops is repeated once per crop with the same DAR and remarks: keep one row
    use = use.drop_duplicates(["product_id", "usage_idx"])
    prod = pd.read_csv(CLEAN / "pesticides_produits.csv",
                       usecols=["product_id", "restriction", "n_homologation", "societe", "dar_produit"])
    prod = prod.rename(columns={"restriction": "restriction_produit"})
    out = ct.merge(use, on=["product_id", "usage_idx"], how="left").merge(prod, on="product_id", how="left")
    assert len(out) == len(ct), "a usage matched several rows"
    return out


def build():
    t0 = time.time()
    tmp = DB_PATH.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    meta = []
    tables = {"traitements": (treatments(), f"{MAPPING.relative_to(ROOT)} (lignes validated) x pesticides/tn_usages.csv "
                                            "+ produits")}
    for name, path in FILES.items():
        tables[name] = (pd.read_csv(path), str(path.relative_to(ROOT)))
    codex = PROC / "pesticides" / "codex_mrl.csv"  # phyto step 7 (build_codex_mrl.py): optional, needs the internet once
    if codex.exists():
        tables["codex_mrl"] = (pd.read_csv(codex), str(codex.relative_to(ROOT)))
    fiches = pd.read_json(KNOW / "fiches.jsonl", lines=True)
    tables["fiches"] = (fiches.astype(str).replace({"nan": None, "None": None}), "knowledge/fiches.jsonl")
    rules = json.load(open(KNOW / "regles_carences.json", encoding="utf-8"))
    tables["regles_carences"] = (pd.DataFrame([{"unified_class": k, "regle": json.dumps(v, ensure_ascii=False)}
                                               for k, v in rules.items()]), "knowledge/regles_carences.json")
    for name, (df, src) in tables.items():
        df.to_sql(name, con, index=False)
        meta.append({"table": name, "rows": len(df), "source": src})
    for table, cols in INDEXES:
        con.execute(f"CREATE INDEX idx_{table} ON {table} ({cols})")
    pd.DataFrame(meta).assign(built=time.strftime("%Y-%m-%d %H:%M")).to_sql("meta", con, index=False)
    con.commit()
    con.close()
    tmp.replace(DB_PATH)
    print(f"{DB_PATH.relative_to(ROOT)}: {len(tables)} tables in {time.time() - t0:.1f} s")
    for m in meta:
        print(f"  {m['table']:20s} {m['rows']:6d} rows  <- {m['source']}")


if __name__ == "__main__":
    build()
