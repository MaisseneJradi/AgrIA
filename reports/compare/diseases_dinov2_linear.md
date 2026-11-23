# diseases_dinov2_linear contre diseases (déployé)

Changement : étape 6 : dinov2 gelé + tête linear (caractéristiques en cache), poids terrain 5, époque choisie sur val terrain

| mesure | diseases | diseases_dinov2_linear |
|---|---|---|
| Labo | 0.9943 | 0.9632 |
| Terrain | 0.8279 | 0.7496 |
| PlantDoc | 0.7563 | 0.6599 |
| Macro-F1 terrain | 0.7859 | 0.6927 |
| ECE terrain | 0.0499 | 0.0752 |

McNemar terrain : 39 photos gagnées, 94 perdues, p = 2.06e-06
McNemar PlantDoc : +17 / −36, p = 0.0127

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, labo −3.1 pts)
