# diseases_s384 contre diseases (déployé)

Changement : étape 4 : taille 384 (batch 12 x accum 3), label smoothing 0.1, EMA 0.999, warm-up 1 époque ; recette v2

| mesure | diseases | diseases_s384 |
|---|---|---|
| Labo | 0.9945 | 0.9925 |
| Terrain | 0.8009 | 0.8265 |
| PlantDoc | 0.7157 | 0.7513 |
| Macro-F1 terrain | 0.7607 | 0.786 |
| ECE terrain | 0.1419 | 0.0221 |

McNemar terrain : 41 photos gagnées, 23 perdues, p = 0.0328
McNemar PlantDoc : +17 / −10, p = 0.248

**Verdict : CANDIDAT au remplacement (à demander)**
