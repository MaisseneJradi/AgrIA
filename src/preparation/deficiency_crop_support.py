"""Crop bias of the deficiency classes: what the data can support, and the rules the agent applies on top.

Zn (pepper only), Fe (94 % pepper), B and Ca (coffee only) were seen on one crop: no sampling can teach the model
these deficiencies on other crops, and no other crop may be added (project rule). So:
  1. support table: for each class, the crops it was seen on in TRAIN and a reliability level
       fiable       >= 3 crops and no crop above 60 %
       limite       2+ crops but one above 60 %
       mono_culture 1 crop: outside that crop the prediction is a hypothesis
  2. agent rules (JSON): per class, the symptom pattern to confirm by questions (leaf age, pattern), the soil
     condition that makes it likely (from data/processed/context/sols.csv), and the action when the farmer's crop
     is not among the crops of the class;
  3. evaluation file: every TEST image with a flag saying whether its crop was seen for its class, so metrics
     can be reported per crop and the bias measured (balanced/deficiency_test_by_crop.csv).

Usage: python src/preparation/deficiency_crop_support.py   (after balance_training.py)
Output: docs/deficiency_crop_support.csv, data/processed/knowledge/regles_carences.json,
        data/processed/balanced/deficiency_test_by_crop.csv
"""
import json
import os

import pandas as pd

PROC = os.path.join("data", "processed")
# symptom patterns (standard plant-nutrition diagnosis: mobile nutrients show on OLD leaves first, immobile ones on
# YOUNG leaves), and the conditions that favour each deficiency
SYMPTOMS = {
    "N_deficiency": ("vieilles feuilles", "jaunissement uniforme de toute la feuille, en commençant par le bas de "
                     "la plante ; croissance ralentie", "sols sableux, pauvres en matière organique ; après fortes pluies"),
    "P_deficiency": ("vieilles feuilles", "feuilles vert foncé à reflets violacés, plante chétive, retard de floraison",
                     "sols froids, calcaires (pH élevé) ou très acides"),
    "K_deficiency": ("vieilles feuilles", "bords des feuilles qui jaunissent puis brûlent (nécrose marginale)",
                     "sols sableux, irrigation abondante, forte charge en fruits"),
    "Mg_deficiency": ("vieilles feuilles", "jaunissement entre les nervures, nervures restant vertes",
                      "sols sableux ou acides, excès de potassium"),
    "Ca_deficiency": ("jeunes feuilles et fruits", "jeunes feuilles déformées, brûlure des pointes ; cul noir des fruits",
                      "irrigation irrégulière, sécheresse, excès d'azote ammoniacal ou de potassium"),
    "Fe_deficiency": ("jeunes feuilles", "jaunissement net entre les nervures des jeunes feuilles, nervures bien "
                      "vertes ; feuilles presque blanches si sévère", "sols calcaires, pH >= 7,8, sols asphyxiés"),
    "Zn_deficiency": ("jeunes feuilles", "petites feuilles étroites en rosette, jaunissement entre les nervures, "
                      "entre-noeuds courts", "sols calcaires (pH élevé), excès de phosphore"),
    "Mn_deficiency": ("jeunes feuilles", "jaunissement diffus entre les nervures avec petites taches nécrotiques",
                      "sols calcaires (pH élevé), riches en matière organique"),
    "B_deficiency": ("bourgeons et jeunes feuilles", "pointes de croissance déformées ou mortes, feuilles épaisses et "
                     "cassantes ; fruits déformés ou fendus", "sols sableux lessivés, sécheresse, pH élevé"),
}
SOIL_RULE = {"Fe_deficiency": "phh2o_pH >= 7.8", "Zn_deficiency": "phh2o_pH >= 7.8", "Mn_deficiency": "phh2o_pH >= 7.8",
             "P_deficiency": "phh2o_pH >= 7.8", "N_deficiency": "soc_g/kg < 10", "K_deficiency": "sand_% >= 65",
             "Mg_deficiency": "sand_% >= 65", "B_deficiency": "sand_% >= 65"}


def level(n_crops, share):
    if n_crops == 1:
        return "mono_culture"
    return "fiable" if n_crops >= 3 and share <= 60 else "limite"


def main():
    man = pd.read_csv(os.path.join(PROC, "deficiency_manifest.csv"))
    bal = pd.read_csv(os.path.join(PROC, "balanced", "deficiency_train.csv"))
    seen = bal[bal["origin"] == "real"].groupby("class")["crop"].agg(lambda s: s.value_counts().to_dict())
    rows, rules = [], {}
    for cls, crops in seen.items():
        n = sum(crops.values())
        top, share = max(crops.items(), key=lambda kv: kv[1])
        lvl = level(len(crops), 100 * share / n)
        rows.append({"class": cls, "niveau": lvl, "n_cultures": len(crops), "culture_dominante": top,
                     "part_dominante_%": round(100 * share / n), "cultures_vues": " ".join(sorted(crops)),
                     "n_train_reelles": n})
        if cls == "healthy":
            continue
        where, pattern, context = SYMPTOMS[cls]
        rules[cls] = {
            "niveau": lvl, "cultures_vues": sorted(crops),
            "si_culture_non_vue": ("présenter comme hypothèse, poser les questions de confirmation et croiser avec le "
                                   "sol avant tout conseil d'engrais" if lvl != "fiable" else
                                   "conseiller normalement, en rappelant que la photo seule ne remplace pas une "
                                   "analyse de sol ou de feuille"),
            "questions_confirmation": [f"Les symptômes sont-ils surtout sur les {where} ?", f"Voyez-vous : {pattern} ?"],
            "conditions_favorables": context, "regle_sol": SOIL_RULE.get(cls),
            "source_regle_sol": "data/processed/context/sols.csv (SoilGrids, 0-30 cm, médiane autour du chef-lieu)"}
    sup = pd.DataFrame(rows).sort_values(["niveau", "class"])
    sup.to_csv(os.path.join("docs", "deficiency_crop_support.csv"), index=False)
    os.makedirs(os.path.join(PROC, "knowledge"), exist_ok=True)
    json.dump(rules, open(os.path.join(PROC, "knowledge", "regles_carences.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    test = man[man["split"] == "test"].copy()
    test["culture_vue_pour_classe"] = [crop in seen.get(cls, {}) for cls, crop in zip(test["class"], test["crop"])]
    test["culture_dominante_de_la_classe"] = test["class"].map(sup.set_index("class")["culture_dominante"])
    test.to_csv(os.path.join(PROC, "balanced", "deficiency_test_by_crop.csv"), index=False)
    print(sup.to_string(index=False))
    print(f"\nrules for {len(rules)} classes; test images: {len(test)} "
          f"({int((test['crop'] == 'pepper').sum())} pepper / {int((test['crop'] != 'pepper').sum())} other crops)")


if __name__ == "__main__":
    main()
