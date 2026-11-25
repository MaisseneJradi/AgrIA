# leaf_s300 contre leaf (déployé)

Changement : étape 4 : taille 300 (batch 16 x accum 2), label smoothing 0.1, EMA 0.999, warm-up 1 époque ; recette leaf_v4 (aug field)

| mesure | leaf | leaf_s300 |
|---|---|---|
| Labo | 0.9697 | 0.9703 |
| Terrain | 0.7852 | 0.8137 |
| PlantDoc | 0.6751 | 0.7157 |
| Macro-F1 terrain | 0.7409 | 0.7788 |
| ECE terrain | 0.1441 | 0.062 |

McNemar terrain : 45 photos gagnées, 25 perdues, p = 0.0225
McNemar PlantDoc : +20 / −12, p = 0.215

**Verdict : CANDIDAT au remplacement (à demander)**
