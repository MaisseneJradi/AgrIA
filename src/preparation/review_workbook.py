"""Review workbook of the 'proposed' rows (phyto plan): one Excel sheet per CSV of docs/, a decision per row, then
the decisions written back into the CSV files.

    python src/preparation/review_workbook.py export                       -> reports/relecture/relecture_<date>.xlsx
    python src/preparation/review_workbook.py import <fichier.xlsx>        report only (what would change)
    python src/preparation/review_workbook.py import <fichier.xlsx> --apply

In the workbook the reviewer fills only the two yellow columns: "Décision" (validé | rejeté | empty = not reviewed
yet) and "Note du relecteur". Import:
  - a row is found again by its line in the CSV AND its fingerprint (hash of the whole row at export): a row that
    changed since the export (shop refresh, new rule run...) is skipped and reported, never overwritten;
  - only rows still 'proposed' change: validé -> validated, rejeté -> rejected (never used, like proposed); the note
    is added to the note column ("relecture <date> : ...");
  - only the lines decided are rewritten, the rest of each file stays byte for byte as it was;
  - after a change of docs/disease_target_mapping.csv the SQLite base is rebuilt (build_db.py: table traitements).
Restart the server after an import: the agents read the tables at start.
"""
import argparse
import csv
import datetime
import hashlib
import io
import json
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
OUT = ROOT / "reports" / "relecture"
DECISIONS = {"valide": "validated", "validated": "validated", "rejete": "rejected", "rejected": "rejected"}
FONT = "Arial"


@dataclass
class Spec:
    sheet: str
    file: str
    columns: list
    unlocks: str
    rejected: str
    keep: object = None          # row -> bool: rows of the CSV put in the sheet (always: status proposed)
    order: object = None         # row -> sort key
    wide: tuple = ()             # long text columns (wrapped)
    extra: dict = field(default_factory=dict)  # column -> function(row) for read-only help columns


def _shop_urls():
    path = ROOT / "data" / "processed" / "shop" / "shop_products.csv"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["id"]: r.get("product_url", "") for r in csv.DictReader(f)}


SPECS = [
    Spec("1_Cibles_maladies", "disease_target_mapping.csv",
         ["unified_class", "crops", "nom", "type_nom", "relation", "groupe", "n_usages", "n_produits",
          "exemples_cibles", "source", "note"],
         "la cible écrite dans la liste DGSVCIA (« nom ») compte pour cette maladie : ses produits homologués "
         "apparaissent dans les réponses",
         "cette cible ne correspond pas à la maladie", wide=("exemples_cibles", "note")),
    Spec("2_DAR_completes", "phi_completions.csv",
         ["product_id", "produit", "culture", "phi_days", "phi_texte", "source", "note"],
         "le délai avant récolte complété est affiché (au lieu de « DAR non indiqué »)",
         "le DAR proposé est faux ou mal sourcé", wide=("note",)),
    Spec("3_Toxicite_OMS", "substance_hazard.csv",
         ["substance", "classe_oms", "nom_oms", "cas", "correspondance", "source", "note"],
         "la classe de toxicité OMS est écrite dans la réponse et compte dans le tri (le moins toxique d'abord)",
         "la substance de l'OMS n'est pas celle de la liste"),
    Spec("4_Abeilles", "bee_hazard.csv",
         ["substance", "tres_toxique_abeilles", "nom_pan", "cas", "correspondance", "source", "note"],
         "l'avertissement « très toxique pour les abeilles » est écrit",
         "la substance PAN n'est pas celle de la liste"),
    Spec("5_Groupes_FRAC_IRAC", "moa_groups.csv",
         ["substance", "groupe", "liste", "nom_liste", "groupe_libelle", "faible_risque", "correspondance", "source",
          "note"],
         "le groupe FRAC / IRAC sert à la rotation (ne pas répéter le groupe du dernier traitement)",
         "le groupe ou la substance est faux", wide=("groupe_libelle",)),
    Spec("6_Prevention", "conseils_prevention.csv",
         ["unified_class", "ordre", "conseil_fr", "conseil_ar", "origine", "note"],
         "le conseil de prévention est donné quand aucun produit n'est homologué",
         "le conseil est faux, inadapté à la Tunisie, ou mal traduit", wide=("conseil_fr", "conseil_ar")),
    Spec("7_LMR_Codex", "codex_commodity_mapping.csv",
         ["culture", "denree_codex", "niveau", "note"],
         "la LMR Codex de cette denrée est donnée pour le marché local",
         "la denrée Codex ne correspond pas à la culture"),
    Spec("8_Boutique_liens", "shop_product_mapping.csv",
         ["shop_product_id", "name", "kind", "target_id", "target_label", "match_score", "verdict", "reasons",
          "note"],
         "le produit de la boutique est proposé (avec son lien) sous le produit homologué ou pour le besoin de la "
         "carence",
         "même composition non confirmée : jamais proposé",
         keep=lambda r: bool(r.get("target_id")),
         order=lambda r: ({"apparié": 0, "incertain": 1}.get(r.get("verdict"), 2), -float(r.get("match_score") or 0)),
         wide=("reasons", "target_label"), extra={"page": lambda r, urls: urls.get(r["shop_product_id"], "")}),
    Spec("9_Allegations", "shop_unapproved_claims.csv",
         ["shop_product_id", "name", "shop_category", "category_agria", "allegation", "extrait", "product_url",
          "note"],
         "validé = vraie allégation de protection sans homologation : le produit n'est jamais proposé",
         "pas une vraie allégation (ex. « ne possède pas d'action insecticide ») : le produit redevient possible",
         wide=("extrait", "note")),
    Spec("10_Engrais_besoins", "fertiliser_needs.csv",
         ["carence", "nutriment", "teneur_min_pct", "chelates_sol_calcaire", "source", "note"],
         "le besoin d'engrais de la carence sert à choisir les engrais de boutique",
         "la teneur ou le chélate proposé est faux", wide=("note",)),
    Spec("11_Engrais_doses", "fertiliser_dose_ranges.csv",
         ["nutriment", "culture", "type_application", "min", "max", "unite", "source", "note"],
         "la « dose indiquée par le fabricant » est affichée si elle est dans cette fourchette",
         "la fourchette est fausse ou sans source (INRAT / FAO / CRDA)", wide=("source", "note")),
]


# ------------------------------------------------------------------ CSV records with their exact text
def read_records(path):
    """(header, [(row dict, start, end)], text, end of line): the span of each record in the text, so that a record
    can be rewritten alone."""
    text = Path(path).read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    buf = io.StringIO(text, newline="")
    reader = csv.reader(buf)
    header = next(reader)
    records, start = [], buf.tell()
    for values in reader:
        end = buf.tell()
        records.append((dict(zip(header, values)), start, end))
        start = end
    return header, records, text, eol


def fingerprint(row):
    return hashlib.sha1(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def write_record(row, header, eol):
    out = io.StringIO(newline="")
    csv.DictWriter(out, fieldnames=header, lineterminator=eol).writerow(row)
    return out.getvalue()


def plain(s):
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().strip().lower()


# ------------------------------------------------------------------ export
def rows_of(spec, docs=DOCS):
    _, records, _, _ = read_records(docs / spec.file)
    rows = [(i, r) for i, (r, _, _) in enumerate(records)
            if r.get("status") == "proposed" and (spec.keep is None or spec.keep(r))]
    return sorted(rows, key=lambda x: spec.order(x[1])) if spec.order else rows


def export(out=None, docs=DOCS, specs=SPECS):
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    date = datetime.date.today().isoformat()
    out = Path(out or OUT / f"relecture_{date}.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)
    head = Font(name=FONT, bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2E6B30")
    yellow = PatternFill("solid", fgColor="FFFF00")
    grey = Font(name=FONT, color="666666", size=9)
    normal = Font(name=FONT, size=10)
    thin = Border(bottom=Side(style="thin", color="BBBBBB"))
    wb = Workbook()
    guide = wb.active
    guide.title = "Mode_d_emploi"
    urls = _shop_urls()
    counts = []
    for spec in specs:
        rows = rows_of(spec, docs)
        ws = wb.create_sheet(spec.sheet)
        cols = ["ligne", "empreinte"] + spec.columns + list(spec.extra) + ["statut actuel", "Décision",
                                                                           "Note du relecteur"]
        for j, c in enumerate(cols, 1):
            cell = ws.cell(row=1, column=j, value=c)
            cell.font, cell.fill = head, (yellow if c in ("Décision", "Note du relecteur") else head_fill)
            if c in ("Décision", "Note du relecteur"):
                cell.font = Font(name=FONT, bold=True, color="000000")
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for i, (idx, r) in enumerate(rows, 2):
            values = [idx + 2, fingerprint(r)] + [r.get(c, "") for c in spec.columns] \
                + [f(r, urls) for f in spec.extra.values()] + [r.get("status"), None, None]
            for j, v in enumerate(values, 1):
                cell = ws.cell(row=i, column=j, value=v)
                cell.font, cell.border = normal, thin
                cell.alignment = Alignment(vertical="top", wrap_text=cols[j - 1] in spec.wide)
            for j in (len(cols) - 1, len(cols)):
                ws.cell(row=i, column=j).fill = yellow
        last = max(2, len(rows) + 1)
        dec_col = get_column_letter(len(cols) - 1)
        dv = DataValidation(type="list", formula1='"validé,rejeté"', allow_blank=True,
                            error="Choisissez validé ou rejeté (ou laissez vide)", errorTitle="Décision",
                            prompt="validé, rejeté, ou vide = pas encore relu", promptTitle="Décision")
        ws.add_data_validation(dv)
        dv.add(f"{dec_col}2:{dec_col}{last}")
        ws.cell(row=1, column=1).comment = Comment("Numéro de la ligne dans le fichier CSV (ne pas modifier)",
                                                   "AgrIA")
        ws.column_dimensions["A"].width = 7
        ws.column_dimensions["B"].hidden = True
        for j, c in enumerate(cols[2:], 3):
            ws.column_dimensions[get_column_letter(j)].width = 48 if c in spec.wide else \
                22 if c in ("Note du relecteur", "page", "source", "product_url") else 16
        ws.column_dimensions[get_column_letter(len(cols))].width = 40
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{last}"
        counts.append((spec, len(rows), dec_col, last))

    # ---- guide sheet
    g = guide
    g.column_dimensions["A"].width = 22
    g.column_dimensions["B"].width = 30
    for col, w in zip("CDEFGH", (11, 11, 11, 13, 60, 50)):
        g.column_dimensions[col].width = w
    g["A1"] = "Relecture des lignes proposées — AgrIA"
    g["A1"].font = Font(name=FONT, bold=True, size=14)
    g["A2"] = f"Fichier créé le {date} par src/preparation/review_workbook.py ; seules les lignes au statut " \
              "« proposed » y sont."
    g["A2"].font = grey
    steps = ["1. Dans chaque feuille, remplissez seulement les deux colonnes jaunes : « Décision » (validé ou rejeté, "
             "vide = pas encore relu) et « Note du relecteur » (votre source ou la raison).",
             "2. Ne modifiez pas les autres colonnes, ni l'ordre des lignes : la colonne « ligne » et une empreinte "
             "cachée retrouvent chaque ligne dans le fichier CSV.",
             "3. Vous pouvez relire en plusieurs fois : une ligne laissée vide reste « proposed ».",
             "4. Importez : python src/preparation/review_workbook.py import <ce fichier> (rapport), puis la même "
             "commande avec --apply. Relancez ensuite le serveur.",
             "Une ligne modifiée depuis l'export (rafraîchissement des boutiques…) n'est jamais écrasée : l'import "
             "la signale."]
    for k, s in enumerate(steps, 4):
        g.cell(row=k, column=1, value=s).font = normal
    r0 = 4 + len(steps) + 1
    g.cell(row=r0, column=1, value="Exemple d'une ligne remplie (feuille 2_DAR_completes)").font = \
        Font(name=FONT, bold=True)
    example = [("produit", "HALT WP"), ("culture", "tomato"), ("phi_days", "0"), ("Décision", "validé"),
               ("Note du relecteur", "COMM 28/12/2023 vérifiée : DAR non requis")]
    for j, (k, v) in enumerate(example, 1):
        g.cell(row=r0 + 1, column=j, value=k).font = Font(name=FONT, bold=True)
        c = g.cell(row=r0 + 2, column=j, value=v)
        c.font = normal
        if k in ("Décision", "Note du relecteur"):
            c.fill = yellow
    r1 = r0 + 4
    g.cell(row=r1, column=1, value="Avancement (calculé dans les feuilles)").font = Font(name=FONT, bold=True)
    hdr = ["Feuille", "Fichier", "À relire", "Validées", "Rejetées", "Restantes", "Ce que « validé » débloque",
           "Ce que veut dire « rejeté »"]
    for j, h in enumerate(hdr, 1):
        c = g.cell(row=r1 + 1, column=j, value=h)
        c.font, c.fill = head, head_fill
    for k, (spec, n, dec_col, last) in enumerate(counts, r1 + 2):
        rng = f"'{spec.sheet}'!${dec_col}$2:${dec_col}${last}"
        cells = [spec.sheet, f"docs/{spec.file}", n, f'=COUNTIF({rng},"validé")', f'=COUNTIF({rng},"rejeté")',
                 f"=C{k}-D{k}-E{k}", spec.unlocks, spec.rejected]
        for j, v in enumerate(cells, 1):
            c = g.cell(row=k, column=j, value=v)
            c.font = normal
            c.alignment = Alignment(vertical="top", wrap_text=j >= 7)
    tot = r1 + 2 + len(counts)
    g.cell(row=tot, column=1, value="Total").font = Font(name=FONT, bold=True)
    for col in "CDEF":
        c = g[f"{col}{tot}"]
        c.value = f"=SUM({col}{r1 + 2}:{col}{tot - 1})"
        c.font = Font(name=FONT, bold=True)
    g.cell(row=tot + 1, column=1, value="Part relue").font = normal
    g[f"C{tot + 1}"] = f"=IF(C{tot}=0,0,(D{tot}+E{tot})/C{tot})"
    g[f"C{tot + 1}"].number_format = "0.0%"
    g[f"C{tot + 1}"].font = Font(name=FONT, bold=True)
    g.cell(row=tot + 3, column=1, value="« À relire » est le nombre de lignes au statut proposed à la date du "
                                         "fichier (compté par le script).").font = grey
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(fullCalcOnLoad=True)  # the progress formulas are computed when Excel opens it
    wb.save(out)
    return out, [(s.sheet, n) for s, n, _, _ in counts]


# ------------------------------------------------------------------ import
def read_decisions(xlsx, specs=SPECS):
    """{file: [(line, fingerprint, decision, note)]} and the errors (unknown decision values)."""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx, read_only=True)
    try:
        return _decisions(wb, specs)
    finally:
        wb.close()  # read_only keeps the file open (Windows: Excel could not save it again)


def _decisions(wb, specs):
    out, errors = {}, []
    for spec in specs:
        if spec.sheet not in wb.sheetnames:
            continue
        rows = wb[spec.sheet].iter_rows(values_only=True)
        header = list(next(rows))
        i_line, i_fp = header.index("ligne"), header.index("empreinte")
        i_dec, i_note = header.index("Décision"), header.index("Note du relecteur")
        for k, r in enumerate(rows, 2):
            dec = plain(r[i_dec])
            if not dec:
                continue
            if dec not in DECISIONS:
                errors.append(f"{spec.sheet} ligne {k} : décision « {r[i_dec]} » inconnue (validé ou rejeté)")
                continue
            out.setdefault(spec.file, []).append((int(r[i_line]), str(r[i_fp]), DECISIONS[dec],
                                                  str(r[i_note] or "").strip()))
    return out, errors


def apply_decisions(decisions, docs=DOCS, date=None, write=False):
    """Report {file: {"validated": n, "rejected": n, "ignorees": [...]}}; with write=True the files are changed."""
    date = date or datetime.date.today().isoformat()
    report = {}
    for file, items in decisions.items():
        path = docs / file
        header, records, text, eol = read_records(path)
        by_fp = {fingerprint(r): i for i, (r, _, _) in enumerate(records)}
        new = {}
        rep = report.setdefault(file, {"validated": 0, "rejected": 0, "ignorees": []})
        for line, fp, status, note in items:
            i = line - 2
            if not (0 <= i < len(records) and fingerprint(records[i][0]) == fp):
                i = by_fp.get(fp)
            if i is None:
                rep["ignorees"].append(f"ligne {line} : modifiée depuis l'export, non écrasée")
                continue
            row = dict(records[i][0])
            if row.get("status") != "proposed":
                rep["ignorees"].append(f"ligne {line} : déjà au statut {row.get('status')}")
                continue
            row["status"] = status
            if note and "note" in row:
                row["note"] = " | ".join(x for x in (row["note"], f"relecture {date} : {note}") if x)
            new[i] = row
            rep[status] += 1
        if write and new:
            parts, pos = [], 0
            for i in sorted(new):
                _, start, end = records[i]
                parts += [text[pos:start], write_record(new[i], header, eol)]
                pos = end
            parts.append(text[pos:])
            path.write_bytes("".join(parts).encode("utf-8"))
        rep["ecrites"] = len(new) if write else 0
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--out")
    i = sub.add_parser("import")
    i.add_argument("xlsx")
    i.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "export":
        out, counts = export(args.out)
        print(f"{out} : {sum(n for _, n in counts)} lignes à relire")
        for sheet, n in counts:
            print(f"  {sheet:22s} {n:5d}")
        return 0
    decisions, errors = read_decisions(args.xlsx)
    for err in errors:
        print("erreur :", err)
    report = apply_decisions(decisions, write=args.apply)
    if not report:
        print("aucune décision dans le fichier")
    for file, r in report.items():
        print(f"docs/{file} : {r['validated']} validées, {r['rejected']} rejetées"
              + (f", {len(r['ignorees'])} ignorées" if r["ignorees"] else ""))
        for x in r["ignorees"]:
            print("   ", x)
    if not args.apply:
        print("rapport seulement : ajoutez --apply pour écrire les décisions")
        return 1 if errors else 0
    if report.get("disease_target_mapping.csv", {}).get("ecrites"):
        subprocess.run([sys.executable, str(ROOT / "src" / "tools" / "build_db.py")], check=True, cwd=ROOT)
    print("décisions écrites ; relancez le serveur pour qu'il les lise")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
