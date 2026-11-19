"""Excel workbook for an Arabic speaker to check the Arabic of AgrIA (answers in French and Arabic only):
docs/validation_langue.xlsx.

Usage: python src/agent/make_validation_sheet.py
Sheets
  Mode d'emploi        how to fill the workbook
  Phrases du code      every sentence of src/agent/redaction.py (French, Arabic) + columns to fill
  Questions et avert.  the fixed questions and warnings translated in code (FIXED_AR) + columns to fill
  Exemples             complete answers written by code for real test photos, in Arabic, read as a farmer
  Lexique              the 88 darija / arabizi spellings of the lexicon marked a_valider, used only to UNDERSTAND
                       farmers' messages (optional check) + columns to fill
The reviewer writes "oui" or "non" and, when "non", the correct sentence. Nothing in the code changes until the
corrections are copied back (docs/results_agents.md says how).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AGRIA_DEVICE", "cpu")

import pandas as pd  # noqa: E402
from openpyxl.styles import Alignment  # noqa: E402

from src.agent.redaction import FIXED_AR, P  # noqa: E402

OUT = ROOT / "docs" / "validation_langue.xlsx"
FILL = {"Correct ? (oui/non)": "", "Correction": "", "Commentaire": ""}
CONTEXT = {
    "photo_absente": "le fermier n'a pas envoyé de photo", "photo_inutile": "la photo ne montre ni feuille ni fruit",
    "photo_conseil": "conseil pour refaire la photo", "doute": "le diagnostic n'est pas sûr",
    "doute_court": "le diagnostic n'est pas sûr", "pistes": "maladies possibles",
    "questions": "avant une liste de questions", "crda": "orientation vers le CRDA",
    "crda_gov": "suite de la phrase CRDA avec le gouvernorat", "crda_sans_gov": "suite sans gouvernorat",
    "sain": "plante saine", "hypothese": "carence incertaine sur cette culture", "confirmer": "avant des questions",
    "diagnostic": "diagnostic sûr", "produits": "titre de la liste des pesticides homologués",
    "produit": "une ligne de pesticide (nom, matières actives, dose, délai avant récolte)",
    "dar_jours": "délai avant récolte en jours", "dar_inconnu": "délai avant récolte absent de la liste officielle",
    "aucun_produit": "aucun pesticide homologué", "conseils": "titre des conseils tirés des fiches",
    "engrais": "titre de la liste des engrais", "eau": "besoin en eau du mois",
    "a_savoir": "titre des avertissements", "fin": "phrase de fin (dose, délai, CRDA)",
    "sain_nom": "nom « plante saine »", "carence": "nom d'une carence, ex. carence en fer (Fe)",
}
GUIDE = [
    ["But", "Vérifier que l'arabe d'AgrIA est correct, clair et naturel pour un agriculteur tunisien. AgrIA répond "
            "en français ou en arabe (pas de darija)."],
    ["Qui", "Un arabophone ; pour les termes agricoles (doses, délai avant récolte, noms de maladies), "
            "idéalement aussi un agriculteur ou un technicien du CRDA."],
    ["Comment", "Dans chaque feuille, colonne « Correct ? » : écrire oui ou non. Si non : écrire la bonne phrase dans "
                "« Correction ». Remarques libres dans « Commentaire »."],
    ["Ne pas modifier", "Les accolades {nom}, {dose}, {c}… : le code y met les valeurs (nom du produit, dose, "
                        "pourcentage). Les garder telles quelles dans les corrections."],
    ["Doses", "Les doses restent écrites comme dans la liste officielle (kg/ha, g/hl, cc/hl) : c'est voulu, "
              "pour qu'aucune traduction ne puisse les modifier."],
    ["Lexique", "Facultatif : ces mots en darija et en arabizi servent seulement à comprendre les messages des "
                "agriculteurs, jamais à leur répondre."],
    ["Après", "Rendre le fichier : les corrections seront recopiées dans src/agent/redaction.py et dans le lexique, "
              "puis les tests relancés."],
]
SCENARIOS = [
    ("mildiou, tomate", "diseases/test/tomato__late_blight/tomato__late_blight_01622", "Nabeul", 5),
    ("mosaïque, aucun produit", "diseases/test/tomato__mosaic_virus/tomato__mosaic_virus_00316", "Sousse", 5),
    ("tomate saine", "diseases/test/tomato__healthy/tomato__healthy_01351", "Nabeul", 5),
    ("carence en fer, poivron", "deficiency/test/Fe_deficiency/Fe_deficiency_00957", "Kairouan", 6),
    ("photo hors sujet", "routing/test/other/other_03785", None, None),
]
def phrases():
    return pd.DataFrame([{"Clé": k, "Contexte": CONTEXT.get(k, ""), "Français": P["fr"][k], "Arabe": P["ar"][k],
                          **FILL} for k in P["fr"]])


def fixed():
    return pd.DataFrame([{"Français": fr, "Arabe": ar, **FILL} for fr, ar in FIXED_AR.items()])


def examples():
    from src.agent.graph import diagnose
    rows = []
    for name, path, gov, month in SCENARIOS:
        photo = str(ROOT / "data" / "processed" / f"{path}.jpg")
        r = diagnose(photo, "", gov, langue="ar", mois=month)
        rows.append({"Cas": name, "Réponse en arabe écrite par le code": r["texte"], **FILL})
    return pd.DataFrame(rows)


def lexicon():
    lx = pd.read_csv(ROOT / "data" / "processed" / "knowledge" / "lexique.csv")
    lx = lx[lx["a_valider"] == True]  # noqa: E712
    return pd.DataFrame([{"Concept": r.concept, "Type": r.type, "Français": r.fr, "Darija (arabe)": r.ar_tn,
                          "Arabizi": r.arabizi, **FILL} for r in lx.itertuples()])


def main():
    sheets = {"Mode d'emploi": pd.DataFrame(GUIDE, columns=["", "Consigne"]), "Phrases du code": phrases(),
              "Questions et avertissements": fixed(), "Exemples": examples()}
    sheets["Lexique"] = lexicon()
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            for col in ws.columns:
                width = min(70, max(12, *(len(str(c.value or "")) for c in col[:30])))
                ws.column_dimensions[col[0].column_letter].width = width
                for c in col:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.freeze_panes = "A2"
    print(f"{OUT.relative_to(ROOT)}: " + ", ".join(f"{n} ({len(d)})" for n, d in sheets.items()))


if __name__ == "__main__":
    main()
