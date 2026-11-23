# diseases_t224 contre diseases (déployé)

Changement : étape 4 (témoin) : taille 224, label smoothing 0.1, EMA 0.999, warm-up 1 époque ; recette v2 (aug field)

| mesure | diseases | diseases_t224 |
|---|---|---|
| Labo | 0.9945 | 0.9932 |
| Terrain | 0.8009 | 0.7994 |
| PlantDoc | 0.7157 | 0.7208 |
| Macro-F1 terrain | 0.7607 | 0.7661 |
| ECE terrain | 0.1419 | 0.0541 |

McNemar terrain : 23 photos gagnées, 24 perdues, p = 1
McNemar PlantDoc : +12 / −11, p = 1

**Verdict : garder le modèle déployé** (pas de gain sur le terrain, McNemar p = 1 ≥ 0.05)
