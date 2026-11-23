# diseases_crop300 contre diseases (déployé)

Changement : étape 5 : photos terrain recadrées sur la feuille (OWL-ViT, score >= 0.1, boîte 15-85 % + marge 10 %) ; recette diseases_s300

| mesure | diseases | diseases_crop300 |
|---|---|---|
| Labo | 0.9943 | 0.9933 |
| Terrain | 0.8279 | 0.8307 |
| PlantDoc | 0.7563 | 0.7513 |
| Macro-F1 terrain | 0.7859 | 0.8021 |
| ECE terrain | 0.0499 | 0.0517 |

McNemar terrain : 26 photos gagnées, 24 perdues, p = 0.888
McNemar PlantDoc : +9 / −10, p = 1

**Verdict : garder le modèle déployé** (McNemar p = 0.888 ≥ 0.05)
