# diseases_dinov2_mlp contre diseases (déployé)

Changement : étape 6 : dinov2 gelé + tête mlp (caractéristiques en cache), poids terrain 5, époque choisie sur val terrain

| mesure | diseases | diseases_dinov2_mlp |
|---|---|---|
| Labo | 0.9943 | 0.9861 |
| Terrain | 0.8279 | 0.8051 |
| PlantDoc | 0.7563 | 0.7005 |
| Macro-F1 terrain | 0.7859 | 0.7604 |
| ECE terrain | 0.0499 | 0.0827 |

McNemar terrain : 49 photos gagnées, 65 perdues, p = 0.16
McNemar PlantDoc : +19 / −30, p = 0.152

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, McNemar p = 0.16 ≥ 0.05)
