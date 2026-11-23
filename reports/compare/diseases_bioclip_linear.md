# diseases_bioclip_linear contre diseases (déployé)

Changement : étape 6 : bioclip gelé + tête linear (caractéristiques en cache), poids terrain 5, époque choisie sur val terrain

| mesure | diseases | diseases_bioclip_linear |
|---|---|---|
| Labo | 0.9943 | 0.9661 |
| Terrain | 0.8279 | 0.7624 |
| PlantDoc | 0.7563 | 0.6853 |
| Macro-F1 terrain | 0.7859 | 0.7321 |
| ECE terrain | 0.0499 | 0.093 |

McNemar terrain : 42 photos gagnées, 88 perdues, p = 6.74e-05
McNemar PlantDoc : +20 / −34, p = 0.0759

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, labo −2.8 pts)
