# diseases_bioclip_mlp contre diseases (déployé)

Changement : étape 6 : bioclip gelé + tête mlp (caractéristiques en cache), poids terrain 5, époque choisie sur val terrain

| mesure | diseases | diseases_bioclip_mlp |
|---|---|---|
| Labo | 0.9943 | 0.978 |
| Terrain | 0.8279 | 0.798 |
| PlantDoc | 0.7563 | 0.736 |
| Macro-F1 terrain | 0.7859 | 0.775 |
| ECE terrain | 0.0499 | 0.0822 |

McNemar terrain : 47 photos gagnées, 68 perdues, p = 0.0617
McNemar PlantDoc : +22 / −26, p = 0.665

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, McNemar p = 0.0617 ≥ 0.05, labo −1.6 pts)
