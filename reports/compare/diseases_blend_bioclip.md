# diseases_blend_bioclip contre diseases (déployé)

Changement : étape 6 : moyenne pondérée CNN déployé (s300) + bioclip gelé/MLP, poids choisi sur val terrain

| mesure | diseases | diseases_blend_bioclip |
|---|---|---|
| Labo | 0.9943 | 0.9941 |
| Terrain | 0.8279 | 0.8321 |
| PlantDoc | 0.7563 | 0.7614 |
| Macro-F1 terrain | 0.7859 | 0.7939 |
| ECE terrain | 0.0499 | 0.09 |

McNemar terrain : 13 photos gagnées, 10 perdues, p = 0.678
McNemar PlantDoc : +6 / −5, p = 1

**Verdict : garder le modèle déployé** (McNemar p = 0.678 ≥ 0.05)
