# leaf_v5 contre leaf (déployé)

Changement : étape 3 : aug field2 (recadrage 0.4-1, ombre, luminosité/contraste ±20 %, flou, flou de bougé, JPEG 40-95, effacement) + CutMix/MixUp 0.3 ; époque choisie sur l'exactitude val terrain

| mesure | leaf | leaf_v5 |
|---|---|---|
| Labo | 0.9697 | 0.9677 |
| Terrain | 0.7852 | 0.7738 |
| PlantDoc | 0.6751 | 0.6548 |
| Macro-F1 terrain | 0.7409 | 0.7271 |
| ECE terrain | 0.1441 | 0.1075 |

McNemar terrain : 31 photos gagnées, 39 perdues, p = 0.403
McNemar PlantDoc : +16 / −20, p = 0.618

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, McNemar p = 0.403 ≥ 0.05)
