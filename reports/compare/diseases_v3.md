# diseases_v3 contre diseases (déployé)

Changement : étape 3 : aug field2 (recadrage 0.4-1, ombre, luminosité/contraste ±20 %, flou, flou de bougé, JPEG 40-95, effacement) + CutMix/MixUp 0.3 ; époque choisie sur l'exactitude val terrain

| mesure | diseases | diseases_v3 |
|---|---|---|
| Labo | 0.9945 | 0.9837 |
| Terrain | 0.8009 | 0.7752 |
| PlantDoc | 0.7157 | 0.6497 |
| Macro-F1 terrain | 0.7607 | 0.7434 |
| ECE terrain | 0.1419 | 0.0496 |

McNemar terrain : 31 photos gagnées, 49 perdues, p = 0.0567
McNemar PlantDoc : +8 / −21, p = 0.0241

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, McNemar p = 0.0567 ≥ 0.05, labo −1.1 pts)
