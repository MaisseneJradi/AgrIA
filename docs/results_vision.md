# Résultats des modèles de diagnostic (étape 2)

Trois modèles lisent la photo après le routeur : **maladies** (51 classes de feuilles), **carences** (9 carences + sain) et **fruits** (18 classes). Tout a été entraîné et mesuré en local, sur une NVIDIA GeForce RTX 2050 (4 Go).

## 1. Ce qui a été entraîné

| Dossier `models/` | Tâche | Modèle | Jeu d'entraînement | Durée |
|---|---|---|---|---|
| `diseases_effnet` | maladies | EfficientNet-B0 | équilibré + poids de classes | 24 min |
| `diseases_raw` | maladies | EfficientNet-B0 | brut (manifest, sans poids) | 37 min |
| `diseases_mobilenet` | maladies | MobileNet-V3-Large | équilibré | 12 min |
| `diseases_vit` | maladies | ViT-B/16 (lr 5e-5, batch 16, 10 époques max) | équilibré | 2 h 20 |
| `deficiency_balanced` / `deficiency_raw` | carences | EfficientNet-B0 | équilibré / brut | 16 / 17 min |
| `fruits_balanced` / `fruits_raw` | fruits | EfficientNet-B0 | équilibré / brut | 3 / 6 min |

Réglages communs : poids ImageNet, AdamW, cosinus, précision mixte, arrêt anticipé sur la macro-F1 de validation, graine 42 (voir [ARCHITECTURE.md](ARCHITECTURE.md) et `src/vision/train.py`).

**Règle de choix, fixée avant de regarder le test :** pour chaque tâche, on garde le modèle qui a la meilleure **macro-F1 de validation**. Le test et les photos de terrain servent seulement à mesurer, jamais à choisir.

## 2. Modèles retenus

| Tâche | Modèle retenu | Val macro-F1 | Test exactitude | Test macro-F1 | Seuil `reliable` |
|---|---|---|---|---|---|
| maladies | `diseases_raw` (EfficientNet-B0, brut) | 0,986 | 0,990 | 0,968 | 0,50 |
| carences | `deficiency_raw` (EfficientNet-B0, brut) | 0,902 | 0,864 | 0,857 | 0,95 |
| fruits | `fruits_raw` (EfficientNet-B0, brut) | 0,933 | 0,983 | 0,897 | 0,50 |
| *routeur* | *EfficientNet-B0 ([results_routing.md](results_routing.md))* | *0,998* | *0,998* | *0,998* | *0,50* |

Ces modèles sont copiés dans `models/diseases/`, `models/deficiency/` et `models/fruits/`, les dossiers que lit `predict()`. La fonction a été vérifiée sur les quatre tâches.

## 3. Comparaison des modèles de maladies (CNN contre ViT, score contre vitesse)

| Modèle | Val macro-F1 | Test exactitude | Test macro-F1 | Terrain exactitude | Terrain macro-F1 | ms/photo GPU | ms/photo CPU | Taille |
|---|---|---|---|---|---|---|---|---|
| EfficientNet-B0, brut ✅ | **0,986** | 0,990 | **0,968** | 0,618 | 0,613 | 8 | 22 | 16 Mo |
| EfficientNet-B0, équilibré | 0,977 | 0,985 | 0,967 | 0,588 | 0,573 | 8 | 22 | 16 Mo |
| MobileNet-V3, équilibré | 0,965 | 0,976 | 0,955 | 0,583 | 0,568 | 5 | 18 | 16 Mo |
| ViT-B/16, équilibré | 0,981 | **0,992** | 0,965 | **0,643** | **0,629** | 20 | 105 | 327 Mo |

Écarts testés avec le test de McNemar (mêmes images, deux modèles) :

| Comparaison | Test (7 960 images) | Terrain (199 photos) |
|---|---|---|
| ViT contre EfficientNet équilibré | p < 0,001 (ViT meilleur) | p = 0,13 (non significatif) |
| ViT contre EfficientNet brut | p = 0,13 | p = 0,58 |
| EfficientNet brut contre équilibré | p = 0,001 (brut meilleur) | p = 0,49 |
| EfficientNet contre MobileNet | p < 0,001 (EfficientNet meilleur) | p = 1,0 |

**Conclusion :** sur le terrain, le ViT est 2,5 points au-dessus du modèle retenu, mais l'écart n'est pas significatif sur 199 photos. Il est aussi 5 fois plus lent sur CPU et 20 fois plus lourd. EfficientNet-B0 est le meilleur compromis. Tous les modèles restent très loin de la limite de 15 s par réponse.

## 4. Hypothèses

### H1 · Les modèles restent bons sur de vraies photos de terrain : **non confirmée**

| Modèle de maladies | Test (laboratoire, surtout PlantVillage) | Terrain (PlantDoc, 199 photos, 24 classes) |
|---|---|---|
| retenu (EfficientNet brut) | 99,0 % | **61,8 %** |
| meilleur sur le terrain (ViT) | 99,2 % | 64,3 % |

- **La chute est de près de 40 points**, avec le même écart pour les quatre modèles. Le problème vient des données, pas de l'architecture. Les modèles apprennent des photos de laboratoire (feuille seule, fond uni, bonne lumière) et ne les retrouvent pas sur le terrain.
- **Classes les plus faibles sur le terrain** (rappel du modèle retenu) : moisissure des feuilles de la tomate 0,17, mosaïque de la tomate 0,20, alternariose de la tomate 0,22, tache bactérienne de la tomate 0,29, alternariose de la pomme de terre 0,33, septoriose de la tomate 0,36.
- **Classes bonnes sur le terrain** : oïdium de la courge 1,00, vigne saine 1,00, fraisier sain 1,00, rouille du maïs 0,90, tomate saine 0,88, pourriture noire de la vigne 0,88.
- **Les cultures tunisiennes sont plus faibles même en laboratoire** : olivier, source OLID 87,8 % ; palmier dattier 93,6 % ; agrumes 93,6 %, contre 99,5 % pour PlantVillage. Les classes les plus faibles du test sont toutes tunisiennes : taches foliaires du palmier (F1 0,60), tuberculose de l'olivier (0,67, 4 images seulement), black scorch du palmier (0,85), cochenille parlatoria (0,88), maladie des taches noires des agrumes (0,91).
- **Dans le modèle des fruits, les agrumes restent faibles** : 68 % sur 22 images, contre 99 % pour la grenade et 98 % pour la tomate.

### H2 · Une carence n'est bien reconnue que sur les cultures où elle a été vue : **en partie confirmée**

Rappel du modèle retenu, sur la culture qui domine chaque classe et sur les autres cultures :

| Classe | Culture dominante | Rappel sur la culture dominante | Rappel sur les autres cultures |
|---|---|---|---|
| N | riz | 1,00 (68) | 0,89 (289) |
| Mn | palmier dattier | 1,00 (52) | **0,58** (12) |
| K | poivron | 0,99 (147) | 0,91 (255) |
| sain | tomate | 0,95 (41) | **0,73** (349) |
| Mg | poivron | 0,93 (107) | 0,93 (68) |
| P | poivron | 0,91 (74) | 0,94 (82) |
| Fe | poivron | 0,82 (148) | 0,90 (10) |
| B, Ca | café | 0,80 / 0,92 | non mesurable (une seule culture) |
| Zn | poivron | **0,69** | non mesurable (une seule culture) |

- Pour N, Mn, K et la classe saine, le score baisse hors de la culture dominante. Mg et P tiennent.
- **Cultures fragiles** : café 76 %, margose 75 %, courge serpent 76 %, blé 85 %. Sur le blé, la carence en azote n'est reconnue que dans 73 % des cas.
- **Poivron sain pris pour une carence** : sur 123 poivrons sains, 48 sont classés carence en zinc et 10 carence en phosphore. Les poivrons sains viennent de PlantVillage, les poivrons carencés d'une autre source. Pour l'agent, une carence en zinc sur poivron doit donc toujours être confirmée par des questions.
- Ces résultats confirment les règles de `regles_carences.json` : hors de la culture vue, le résultat est une hypothèse à confirmer, jamais un diagnostic.

### H3 · L'équilibrage améliore les classes rares : **faible effet, non confirmée globalement**

| Tâche | Macro-F1 test, équilibré / brut | Rappel moyen des 10 classes les plus rares, équilibré / brut | McNemar (test) |
|---|---|---|---|
| maladies | 0,967 / 0,968 | **0,880** / 0,855 | p = 0,001 (brut meilleur en exactitude) |
| carences | 0,849 / 0,857 | **0,873** / 0,861 | p = 0,06 |
| fruits | **0,929** / 0,897 | **0,867** / 0,802 | p = 1,0 |
| maladies, terrain | 0,573 / 0,613 | — | p = 0,49 |

- L'équilibrage aide un peu les classes les plus rares : tuberculose de l'olivier 0,75 contre 0,50, carence en zinc 0,85 contre 0,69, verdissement des agrumes (fruit) 0,67 contre 0,33. Ces classes comptent très peu d'images de test (3 à 16), et l'effet n'est pas significatif.
- Sans équilibrage, l'exactitude globale et la validation sont meilleures. Les poids de classes et les copies augmentées poussent le modèle à trop prédire les classes rares.
- Selon la règle de choix, les modèles bruts sont retenus. Pour les fruits, le modèle équilibré a pourtant une meilleure macro-F1 de test (0,929). Ce choix est fragile parce que la validation des fruits contient très peu d'images par classe rare. Pour protéger plutôt les classes rares, il suffit de copier `models/fruits_balanced/` dans `models/fruits/`.

## 5. Seuils de confiance (champ `reliable`)

Calcul : `src/vision/calibrate.py`. Règle : le seuil le plus bas, jamais sous 0,5, pour lequel les réponses gardées sur la **validation** sont justes au moins 98 % du temps. Pour les carences, 98 % est hors d'atteinte, donc l'objectif est 95 %. Sous le seuil, l'agent ne donne pas de diagnostic : il demande une autre photo ou pose des questions.

| Modèle | Seuil | Test : photos gardées | Test : exactitude des gardées | Test : erreurs arrêtées | Calibration (ECE) test |
|---|---|---|---|---|---|
| routeur | 0,50 | 100 % | 99,8 % | — | 0,001 |
| maladies | 0,50 | 99,9 % | 99,1 % | 9 % | 0,004 |
| carences | 0,95 | 81 % | 93,2 % | 59 % | 0,092 |
| fruits | 0,50 | 99,8 % | 98,6 % | 14 % | 0,014 |

**Point important pour l'agent.** En laboratoire, les modèles sont bien calibrés : l'ECE est d'environ 0,004. Sur le terrain, le modèle des maladies est trop sûr de lui : l'ECE monte à 0,18. Avec le seuil 0,5, 30 % des réponses fausses sont données comme fiables. Voici ce que donnerait chaque seuil sur les 199 photos de terrain :

| Seuil | Photos traitées | Exactitude des photos traitées | Erreurs arrêtées |
|---|---|---|---|
| 0,50 (seuil actuel) | 83 % | 70 % | 34 % |
| 0,70 | 70 % | 76 % | 55 % |
| 0,80 | 62 % | 79 % | 66 % |
| **0,90** | **49 %** | **89 %** | **86 %** |
| 0,95 | 42 % | 90 % | 89 % |

Ces chiffres viennent du jeu de test. Ils ne peuvent donc pas servir à fixer le seuil sans biais. **Recommandation :** l'agent utilise 0,9 pour les maladies jusqu'à ce qu'un jeu de validation de photos tunisiennes permette de recalibrer. Ce choix est noté comme décision ouverte dans `ARCHITECTURE.md`.

## 6. Objectifs de l'étape 2

| Critère | Visé | Obtenu | Atteint |
|---|---|---|---|
| Exactitude sur le terrain (maladies) | ≥ 90 % | 61,8 % (89 % sur la moitié des photos avec un seuil de 0,9) | ❌ |
| Macro-F1 (test) | ≥ 0,85 | maladies 0,968 · fruits 0,897 · carences 0,857 | ✅ |
| Macro-F1 sur le terrain | ≥ 0,85 | 0,613 | ❌ |

## 7. Suite proposée (retour à la préparation, boucle CRISP-DM)

1. **Mieux exploiter les photos de terrain.** Le jeu d'entraînement PlantDoc (1 911 photos de terrain après filtrage des classes) est déjà dans le train, mais il ne pèse que 4,8 % des images, contre 83 % pour PlantVillage, et aucune photo de terrain ne sert à la validation. Essais en cours : validation de terrain, suréchantillonnage et augmentations « terrain » (voir la section 9). À plus long terme, collecter des photos tunisiennes, surtout pour l'olivier, le palmier, les agrumes et la tomate.
2. **Augmentations sans changement de couleur** : rotations, flou, recadrages plus forts, fonds variés. Elles rapprochent les photos de laboratoire des photos de terrain sans toucher aux symptômes.
3. **Recalibrer les seuils** sur une validation de photos de terrain, séparée des 199 photos de test.
4. **Carences** : obtenir des poivrons sains de la même source que les poivrons carencés, pour casser la confusion entre poivron sain et carence en zinc.

## 8. Refaire les mesures

```bash
python src/vision/train.py --task diseases --train-set raw --out models/diseases_raw
python src/vision/evaluate.py --task diseases --model-dir models/diseases_raw --splits val test test_field
python src/vision/calibrate.py --task diseases --model-dir models/diseases_raw
python src/vision/speed.py models/diseases_raw models/diseases_vit
python src/vision/report_vision.py      # tous les tableaux de H1 à H3
```

Fichiers produits, hors Git, dans chaque dossier `models/<nom>/` : `model.pt`, `labels.json`, `metrics.json` (seuil compris), `calibration.json`, `eval_*.json`, `confusion_*.csv`, `predictions_*.csv`. Journaux d'entraînement : `models/logs/`.
