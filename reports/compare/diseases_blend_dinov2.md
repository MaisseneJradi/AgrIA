# diseases_blend_dinov2 contre diseases (déployé)

Changement : étape 6 : moyenne pondérée CNN déployé (s300) + dinov2 gelé/MLP, poids choisi sur val terrain

| mesure | diseases | diseases_blend_dinov2 |
|---|---|---|
| Labo | 0.9943 | 0.9913 |
| Terrain | 0.8279 | 0.8435 |
| PlantDoc | 0.7563 | 0.7665 |
| Macro-F1 terrain | 0.7859 | 0.8052 |
| ECE terrain | 0.0499 | 0.1229 |

McNemar terrain : 36 photos gagnées, 25 perdues, p = 0.2
McNemar PlantDoc : +15 / −13, p = 0.851

**Verdict : garder le modèle déployé** (McNemar p = 0.2 ≥ 0.05)
