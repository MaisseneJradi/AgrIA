# diseases_s300 contre diseases (déployé)

Changement : étape 4 : taille 300 (batch 16 x accum 2), label smoothing 0.1, EMA 0.999, warm-up 1 époque ; recette v2 (aug field)

| mesure | diseases | diseases_s300 |
|---|---|---|
| Labo | 0.9945 | 0.9943 |
| Terrain | 0.8009 | 0.8279 |
| PlantDoc | 0.7157 | 0.7563 |
| Macro-F1 terrain | 0.7607 | 0.7859 |
| ECE terrain | 0.1419 | 0.0499 |

McNemar terrain : 41 photos gagnées, 22 perdues, p = 0.0226
McNemar PlantDoc : +16 / −8, p = 0.152

**Verdict : CANDIDAT au remplacement (à demander)**
