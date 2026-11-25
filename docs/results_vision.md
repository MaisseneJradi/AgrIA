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

1. **Mieux exploiter les photos de terrain.** Le jeu d'entraînement PlantDoc (1 911 photos de terrain après filtrage des classes) est déjà dans le train, mais il ne pèse que 4,8 % des images, contre 83 % pour PlantVillage, et aucune photo de terrain ne sert à la validation. Essais faits : validation de terrain, suréchantillonnage et augmentations « terrain » (section 9) ; modèle « feuille » carence/maladie (section 10). À plus long terme, collecter des photos tunisiennes, surtout pour l'olivier, le palmier, les agrumes et la tomate.
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

## 9. Essais sur les photos de terrain (H1)

PlantDoc train (1 911 photos de terrain) était déjà dans l'entraînement, mais ne pesait que 4,8 % des images, sans validation de terrain. Trois leviers ont été essayés sur le modèle des maladies (EfficientNet-B0, jeu brut), sans nouvelle donnée :
- **validation de terrain** : 287 photos PlantDoc (15 % du train, 24 classes) mises de côté à la lecture (`--field-val`) ; l'époque est choisie sur la moyenne des macro-F1 laboratoire et terrain ;
- **suréchantillonnage** des photos de terrain ×5 (`--field-weight 5`) ;
- **augmentations « terrain »** sans changement de couleur : recadrage fort, rotation, perspective, léger flou (`--aug field`).

| Modèle | Validation terrain (287) | **Test terrain (199)** | Test laboratoire |
|---|---|---|---|
| retenu à l'étape 2 (`diseases_raw`) | — | 61,8 % | 99,0 % |
| essai 1 : validation de terrain seule (`diseases_fval_base`, époque 18) | 68,6 % | 60,8 % | 99,4 % |
| essai 2 : + suréchantillonnage ×5 + augmentations (`diseases_fval_w5aug`) | 67,9 % | **63,3 %** | 98,4 % |

Les essais « suréchantillonnage seul » et « augmentations seules » ont été arrêtés pour libérer le GPU (section 10). Les écarts sur 199 photos restent dans le bruit (± 3,4 points) : aucun levier ne rapproche des 90 % visés. **La suite passe par des photos de terrain tunisiennes** (journal de l'application, `data/journal/`).

## 10. Un modèle « feuille » qui sépare carence et maladie

**Problème vu dans l'application.** Les deux modèles des feuilles ne savent pas départager : le modèle des carences n'a jamais vu de feuille malade (septoriose et chancre classés « carence en potassium » à 96-98 %), le modèle des maladies n'a jamais vu de carence (carence en magnésium classée « moisissure des feuilles » à 100 %).

**Solution.** Une tâche `leaf` (src/vision/dataset.py) : les 51 classes de maladies et les 9 carences dans un même modèle, construite à la lecture sans modifier les manifests. Les feuilles saines du jeu des carences rejoignent la classe saine de leur culture ; **1 938 images du jeu des carences, déjà présentes dans le jeu des maladies** (même md5 ou dhash), sont écartées pour qu'aucune photo ne soit à la fois en entraînement et en test. 60 classes, 48 001 images d'entraînement. Réglages de l'essai 2, patience 8 : meilleure époque 14 sur 20 (`models/leaf`, copie de `models/leaf_v2`).

| Test laboratoire (9 532 images) | Anciens modèles séparés | Modèle feuille |
|---|---|---|
| carences reconnues comme carences | impossible à départager | **97,0 %** |
| maladies reconnues comme maladies | impossible à départager | **98,9 %** |
| carences : classe exacte | 86,4 % | **89,4 %** |
| maladies : classe exacte | **99,0 %** | 98,2 % |
| photos de terrain (199 maladies) | **61,8 %** | 59,3 % |

Sur le terrain, le modèle feuille est trop sûr de lui (au-dessus de 0,9 : 77 % de réponses justes, contre 89 % pour le modèle des maladies). **Choix retenu dans l'agent Diagnostic** : le modèle feuille décide du *type* de problème (somme de ses probabilités de carence, face aux classes de la culture indiquée), puis :
- carence → la carence du modèle feuille (le meilleur sur les carences) ;
- maladie → le modèle des maladies limité à la culture (le meilleur et le mieux calibré sur le terrain).

Une première version, arrêtée trop tôt (époque 2 sur 6, patience 4, `models/leaf_v1`), était moins bonne sur les classes exactes (carences 78,8 %) ; elle n'a pas été utilisée. Le seuil du modèle feuille est calibré sur la validation complète (0,71) ; les seuils de l'agent (0,9 maladie, 0,95 carence) restent ceux qui décident.

**Limite.** Les carences du jeu d'entraînement viennent surtout du poivron, du riz, du palmier et du café (6 à 8 images par carence pour la tomate) : sur des photos de carence de la tomate, le modèle voit encore une maladie. Il faudra des photos de carences sur les cultures tunisiennes.

## 11. Carences des cultures du projet : nouvelles données et modèle feuille v3

Les carences du jeu d'origine venaient surtout du poivron, du riz, du palmier et du café ; sur des photos de carence de la tomate, le modèle voyait une maladie. Quatre jeux publics, uniquement sur des cultures du projet, ont été ajoutés le 16/11/2026 avec `add_source.py` (aucune ligne existante modifiée, 25 lignes dans `docs/extra_class_mapping.csv`) :

| Jeu | Culture | Préparation | Images ajoutées | Licence et citation |
|---|---|---|---|---|
| Maize Nutrient Deficiency Dataset (Mendeley 10.17632/34gb2gr7p2.1, Inde, terrain) | maïs | telle quelle | Mg 123, P 113, N 99, K 56, saines 72 | CC BY 4.0 |
| Tomato Leaf Disease Classification Dataset (Mendeley 10.17632/jttrv2w27r, Bangladesh, fond blanc) | tomate | 17 doublons internes retirés (`clean_duplicates.py`) | Mg 738, saines 369 | CC BY 4.0 (Rachin et Likhon, 2025) |
| Tomato-Village, variante a (Gehlot, Saxena et Gandhi, *Multimedia Systems*, 2023, 10.1007/s00530-023-01158-y ; Rajasthan) | tomate | `prepare_tomato_village.py` : une image par feuille (le jeu contient les copies augmentées des auteurs : 497 paires miroir/rotation, dont 217 entre train et test) | Mg 431, N 177, K 34, saines 216 | **pas de licence** dans le dépôt : citer les auteurs |
| CitrusUAT (Zenodo 10.5281/zenodo.8294078, Mexique ; MD5 vérifié) | agrumes | `prepare_citrusuat.py` : photo recadrée sur la feuille avec le masque fourni | Fe 100, Mg 100, Zn 100, N 50, Mn 30, saines 100 | CC BY 4.0 |

Manifest des carences : 13 771 → **16 679 images**, aucun doublon (`check_duplicates.py`). Les règles des carences (`regles_carences.json`) sont recalculées sur le train brut (`deficiency_crop_support.py`) : Mg et N « fiables » sur la tomate et le maïs, Fe et Zn vus sur les agrumes ; les carences de l'olivier, de la vigne, de la pomme de terre et des arbres fruitiers restent des hypothèses (aucun jeu public trouvé).

**Modèle feuille v3** (mêmes réglages que la v2, meilleure époque 18 sur 20, `models/leaf` = copie de `models/leaf_v3`) :

| Test laboratoire | v2 | **v3** |
|---|---|---|
| carences classées carences | 97,0 % (1 449) | **97,6 %** (1 724) |
| carences : bon nutriment | 89,4 % | **91,4 %** |
| maladies classées maladies | 98,9 % | 98,9 % |
| maladies : classe exacte | 98,2 % | **98,4 %** |
| photos de terrain (199 maladies) | 59,3 % | 59,8 % |

Sur les images de test des nouvelles sources, bon nutriment : tomate Mendeley 98,2 %, Tomato-Village 95,7 %, CitrusUAT 98,3 %, maïs 86,7 %. Sur les photos du journal de l'application, une tomate carencée en magnésium est maintenant reconnue (« carence en magnésium », 89 %, avant : « moisissure des feuilles », 100 %) ; la seconde reste vue comme une maladie (part de carence 38 %, avant 11 %).

## 12. Modèle de culture (agent Identification de la culture)

Tâche `crop` (src/vision/dataset.py) : la culture de la feuille, 15 classes (14 cultures du projet, « orange » comptée avec les agrumes, et « autre_plante » pour le riz, le café, les courges…), construite sur le jeu feuille dédoublonné ; EfficientNet-B0, poids par classe, validation de terrain, suréchantillonnage ×5 et augmentations « terrain ».

| | v1 (installée, `models/crop`) | v2 (essai, `models/crop_v2`) |
|---|---|---|
| test laboratoire | 99,9 % | 99,9 % |
| photos de terrain (199) | **86,9 %** | 85,9 % |
| 15 photos d'Internet du journal : bonne culture | 6/15 | 6/15 |
| idem : fausse avec ≥ 85 % de confiance | **5** | 7 |
| idem : vraie culture dans le top 3 | 9/15 | 11/15 |

**Cause des erreurs.** Chaque culture vient presque d'une seule source (olivier 100 % d'un seul jeu ; agrumes 84 % PlantVillage, feuilles jaunies du greening sur fond uni) : le modèle apprend en partie le style des photos de chaque source (apprentissage par raccourci). Une feuille d'agrume verte photographiée sur l'arbre devient « poivron 98 % » ou « cerisier 98 % ».

**v2 essayée** (18/11/2026) : 4 532 images utilisées seulement par le modèle de culture (`crop_manifest.csv`, ajoutées avec `add_source.py` : maladies et ravageurs de CitrusUAT, maladies de la tomate des jeux Mendeley et Tomato-Village, 32 doublons retirés), tirage équilibré par source (`--sampler source`), augmentations de luminosité, contraste, saturation et effacement (`--aug crop`, teinte inchangée). Mieux sur les agrumes (2/6 au lieu de 1/6), moins bien sur l'olivier, plus d'erreurs sûres d'elles : **non installée**. Rééquilibrer les mêmes sources ne suffit pas ; il faut d'autres sources par culture (olivier surtout), ou un deuxième avis (VLM).

**Règle retenue dans l'agent** : le modèle propose, l'agriculteur confirme. L'application pré-remplit la culture (`POST /identify`), affiche les 3 cultures les plus probables en boutons ; sans culture confirmée, aucun traitement n'est conseillé.

## 13. Combinaison des modèles et VLM (agents Identification et Diagnostic)

Les deux agents ne s'appuient plus sur un seul modèle, mais sur une **combinaison des modèles déjà entraînés et d'un VLM** (`src/agent/ensemble.py`). Les poids sont appris sur la **validation** (photos de laboratoire et 287 photos de terrain PlantDoc tenues à l'écart), puis mesurés sur tous les jeux de test (`python src/agent/eval_ensemble.py --tune --vlm`, rapport `docs/eval_ensemble_vlm.md`).

- **Culture** : vote du modèle de culture et du modèle des maladies (probabilités additionnées par culture), puis le VLM en contrôle et en secours.
- **Carence ou maladie** : part de carence du modèle feuille (poids 1), plus l'avis du VLM (poids 0,5).
- **Classe** : modèle des maladies restreint à la culture, ou carence du modèle feuille.

**Modèle de culture installé : v3a** (19/11/2026), qui inclut les nouvelles sources olivier et agrumes. Comparaison dans la combinaison (culture juste / fausse et sûre) :

| | v1 | **v3a** | v3b |
|---|---|---|---|
| terrain PlantDoc (199) | 87,4 / 1,5 | 86,9 / 2,0 | 86,4 / 2,5 |
| nouvelles sources (216) | 82,4 / 2,3 | 99,5 / 0 | 100 / 0 |
| feuilles de citronnier (lemon_bd, 36) | **0/36** | 36/36 | 36/36 |
| chaîne complète sur le terrain | 63,3 % | 62,8 % | 60,8 % |

v1 et v3a sont équivalentes sur les photos indépendantes (1 à 3 photos d'écart sur 214), mais v1 ne reconnaît aucune feuille de citronnier. v1 est conservée dans `models/crop_v1`.

**VLM** : `nvidia/nemotron-3.5-super-vl-120b-a12b` par l'API NVIDIA (clé dans `.env`, `AGRIA_VLM=nvidia`), environ 8 s par photo, réponses en cache. Ce modèle « raisonne » avant de répondre : il lui faut au moins 1 500 jetons. Seul, il est **faible sur les photos de laboratoire** (culture juste 63,8 %, fausse et sûre 19,9 % : pommier, cerisier, pêcher, pomme de terre) et sur PlantDoc (75,0 %), mais **très bon sur les photos d'Internet** du journal (14/15, contre 4/15 pour la combinaison). Il distingue bien carence et maladie (98,4 % sur le terrain). La validation lui donne un poids 0 dans le vote de la culture : il est donc utilisé en contrôle et en secours.

| Culture (juste / fausse et sûre) | labo (358) | terrain (199) | nouvelles sources (216) | journal (15) |
|---|---|---|---|---|
| combinaison sans VLM | 99,2 / 0 | 86,9 / 2,0 | 99,5 / 0 | 26,7 / 26,7 |
| **décision avec VLM** | 98,6 / 0 | 85,4 / 1,0 | 96,8 / 0 | **66,7 / 0** |

Ce que fait le VLM dans la décision :
- **Contrôle** : si le vote est sûr mais que le VLM voit une autre culture, la réponse n'est plus « sûre » et l'agriculteur doit confirmer. Cela supprime toutes les erreurs sûres d'elles sur le journal, divise par deux celles du terrain, et ne coûte rien ailleurs.
- **Secours** : si le vote hésite et que le VLM est sûr à ≥ 0,95, la culture du VLM est proposée en premier, sans jamais être « sûre ». Avec un seuil de 0,9, le VLM prenait 12 feuilles d'agrumes pour de l'olivier.
- La culture vue par le VLM figure toujours parmi les 3 propositions affichées.

Carence ou maladie, avec le VLM à poids 0,5 : terrain 96,0 → 98,0 %, nouvelles sources 69,0 → 71,3 %, labo inchangé (98,0 %).

**Limites.**
- Le seuil de secours a été choisi en regardant aussi les 15 photos du journal : c'est un petit échantillon. Il faudra le revoir sur de vraies photos d'agriculteurs tunisiens.
- 65 photos sur environ 1 400 ont reçu une réponse illisible du VLM : dans ce cas, le vote seul s'applique.
- Le VLM n'est jamais seul à décider : il ne peut pas contredire la culture donnée par l'agriculteur, et la culture reste toujours confirmée par l'agriculteur.

## 14. Photos de terrain ajoutées et nouveaux modèles (20/11/2026)

**Pourquoi.** Sur le terrain, les modèles restaient autour de 60 % (H1) : les photos de terrain ne pesaient que 4,8 % de l'entraînement et venaient toutes de PlantDoc. Trois jeux publics de **vraies photos de terrain**, uniquement des cultures du projet, ont été ajoutés (`data/README.md`, section « Field photo sources ») :

| Jeu | Culture(s) | Photos gardées | Utilisation | Licence |
|---|---|---|---|---|
| PlantWild v2 (Wei et al., 2024) | 14 cultures du projet, 49 classes sur 115 | 5 918 sur 6 774 | maladies, feuille et culture | CC BY-NC-ND 4.0 |
| Potato Leaf Disease, Uncontrolled Environment (Mendeley 10.17632/ptz377bwb8.1) | pomme de terre | 3 053 sur 3 076 | maladies (mildiou, saine) et culture | CC BY 4.0 |
| GVLiD (Mendeley 10.17632/wkymf8bhcg.5) | vigne | 3 461 → 2 268 après doublons | **culture seulement** : mêmes photos étiquetées esca et brûlure, 38 % d'images de vidéo presque identiques | CC BY 4.0 |

Refusés : Roboflow (photos de laboratoire), le jeu Mendeley « Tomato Leaf and Fruit » (feuilles posées sur du papier blanc), le piment (hors projet). Les maladies hors de nos classes (mildiou de la vigne, rouille jaune du blé…) servent seulement au modèle de culture ; elles deviendront des classes plus tard.

**Préparation** (`src/preparation/prepare_field_sources.py`, rapport `docs/field_sources_routing.csv`) : seules les classes des 14 cultures sont extraites ; le **routeur** lit chaque photo et ne garde que les feuilles (épis, fruits, tiges écartés) ; orientation EXIF appliquée. Ajout par `add_source.py`, nouveau découpage `auto_field` : 85 % entraînement, 15 % test terrain par classe. Doublons contrôlés (`check_duplicates.py`, `clean_duplicates.py`), retraits journalisés dans `docs/removed_images.csv`.

**Effet sur les jeux de test terrain** : maladies et feuille 199 → **703 photos** (PlantDoc 197, PlantWild 425, pomme de terre 81) ; culture **1 861 photos** (+ GVLiD 458). La validation terrain (15 % des photos de terrain de l'entraînement, tirée à la lecture) passe de 287 à 685 photos (1 537 pour la culture).

**Entraînement** : mêmes réglages que l'essai 2 de la section 9 (validation terrain, photos de terrain ×5, augmentations « terrain » sans changement de couleur), choix de l'époque sur la moyenne des macro-F1 labo et terrain.

| Nouveau modèle | Meilleure époque | Durée |
|---|---|---|
| `diseases_v2` (jeu brut, patience 6) | 20 sur 20 | 1 h 41 |
| `leaf_v4` (jeu brut, patience 8) | 18 sur 20 | 1 h 55 |
| `crop_v4` (jeu équilibré, 15 époques, patience 6) | 12 sur 15 | 2 h 10 |

### 14.1 Anciens et nouveaux modèles sur les mêmes jeux de test

| Modèle | Test labo, ancien → nouveau | **Test terrain, ancien → nouveau** | Macro-F1 terrain |
|---|---|---|---|
| Maladies (`diseases_raw` → `diseases_v2`) | 99,0 → 99,5 % | **52,9 → 80,1 %** (703) | 0,481 → 0,761 |
| Feuille (`leaf_v3` → `leaf_v4`) | 97,2 → 97,0 % | **50,9 → 78,5 %** (703) | 0,470 → 0,741 |
| Culture (`crop_v3a` → `crop_v4`) | 99,9 → 99,9 % | **58,9 → 94,3 %** (1 861) | 0,476 → 0,894 |

Par source (bonnes réponses sur le test terrain, ancien → nouveau) :

| Source | Maladies | Feuille | Culture |
|---|---|---|---|
| PlantDoc (197) | 61,9 → 71,6 % | 60,4 → 67,5 % | 85,8 → 85,3 % |
| PlantWild (425 ; 750 pour la culture) | 53,2 → 80,5 % | 51,8 → 80,0 % | 46,5 → 89,9 % |
| Pomme de terre au champ (81 ; 456) | 29,6 → 98,8 % | 23,5 → 97,5 % | 46,5 → 99,8 % |
| GVLiD (458) | — | — | 80,1 → 100 % |

Test de McNemar (mêmes photos, ancien contre nouveau) :

| Modèle | PlantDoc seul | Tout le test terrain |
|---|---|---|
| Maladies | 33 gagnées, 14 perdues, **p = 0,008** | 224 / 33, p < 0,001 |
| Feuille | 30 / 16, p = 0,054 | 225 / 31, p < 0,001 |
| Culture | 12 / 13, p = 1 | 692 / 34, p < 0,001 |

**Lecture honnête.**
- Les gains sur PlantWild, la pomme de terre et GVLiD sont **optimistes** : le test de chaque source vient de la même source que son entraînement (mêmes champs, mêmes appareils ; pour GVLiD, des images de vidéo voisines même après le retrait des doublons).
- **PlantDoc** est la mesure la plus indépendante : sa part d'entraînement n'a pas changé. Le modèle des maladies y gagne **9,7 points (significatif)**, le modèle feuille 7,1 points (à la limite), le modèle de culture reste stable : son gain vient des nouvelles sources.
- Aucune perte en laboratoire.
- La vraie mesure reste à faire sur des **photos tunisiennes**, d'aucune de ces sources.

Seuils calibrés sur la validation (`calibrate.py`, cible 98 %) : maladies 0,50, feuille 0,67, culture 0,50. Les seuils de l'agent (0,9 maladie, 0,95 carence) sont inchangés.

Les anciens modèles restent dans `models/diseases_raw`, `models/leaf_v3` et `models/crop_v3a` ; leurs prédictions sur le nouveau test terrain sont gardées hors Git dans `data/backup/2026-11-20/old_eval/`.

### 14.2 Combinaison des modèles et VLM avec les nouveaux modèles

Les poids sont appris de nouveau sur la validation, qui contient maintenant 685 photos de terrain au lieu de 287 (`eval_ensemble.py --tune --vlm --refresh`). Avant : les anciens modèles avec leurs poids, mesurés sur les **mêmes** jeux agrandis (`docs/eval_ensemble_avant_terrain.md`). Après : `docs/eval_ensemble_vlm.md`.

| Poids | culture | carence ou maladie | maladie |
|---|---|---|---|
| avant | culture 1, maladies 1, VLM 0 | feuille 1, VLM 0,5 | maladies 1 |
| **après** | culture 1, maladies 0,25, **VLM 0,25** | feuille 1, VLM 0,25 | maladies 1, **feuille 1** |

Le VLM entre maintenant dans le vote de la culture (poids 0,25), en plus de son rôle de contrôle et de secours.

| Décision de l'agent (vote + contrôle VLM) | Avant | **Après** |
|---|---|---|
| Culture, terrain (703) : juste / fausse et sûre | 78,0 / 2,0 % | **88,9 / 0,4 %** |
| Culture, labo (358) | 98,6 / 0 % | 97,2 / 0 % |
| Culture, nouvelles sources (216) | 96,8 / 0 % | 97,2 / 0 % |
| Culture, photos d'Internet du journal (15) | 66,7 / 0 % | **100 / 0 %** |
| Carence ou maladie, terrain | 98,4 % | **99,4 %** |
| Maladie exacte avec la vraie culture, terrain | 73,3 % | **86,3 %** |
| Carence exacte, labo (54) | 96,3 % | **100 %** |
| **Chaîne complète, terrain** (culture votée → type → classe) | 55,2 % | **78,2 %** |
| Chaîne complète, labo | 95,0 % | **97,2 %** |

**Seuil de secours du VLM (0,95) vérifié** sur les opinions en cache :

| Seuil | val labo | val terrain | test terrain | journal (15) |
|---|---|---|---|---|
| 0,90 | 87,8 % | 86,7 % | 82,4 % | 93,3 % |
| **0,95 (gardé)** | 98,6 % | 96,4 % | 88,9 % | **100 %** |
| 0,97 | 99,4 % | 99,1 % | 90,0 % | 73,3 % |
| 0,99 ou sans secours | 99,7 % | 99,1 % | 89,8 % | 66,7 % |

Les erreurs sûres d'elles restent à 0 à 0,4 % pour tous les seuils. Sur la validation seule, un seuil plus haut serait meilleur (1 à 3 points), mais ces jeux viennent maintenant des mêmes sources que l'entraînement. Les photos d'Internet du journal sont les seules proches de vraies photos d'agriculteurs, et le secours y fait passer la bonne culture de 67 % à 100 %. Une erreur du secours ne change que la culture pré-remplie : l'agriculteur la corrige parmi 3 boutons, et aucun traitement n'est conseillé sans culture confirmée. **0,95 est donc gardé.** À revoir sur des photos tunisiennes (`src/agent/ensemble.py`, `VLM_FALLBACK`).

**Installés le 21/11/2026** : `models/diseases` = `diseases_v2`, `models/leaf` = `leaf_v4`, `models/crop` = `crop_v4` ; les dossiers remplacés sont dans `models/_replaced_2026-11-21/`, les poids précédents dans `data/backup/2026-11-20/backup/weights_before_field_v2.json`.

## 15. Plan d'amélioration sur les photos de terrain (étapes 1 à 9, 21–22/11/2026)

**Règles suivies** : graine 42 ; aucun entraînement sur une photo de validation ou de test, avec un contrôle des fuites (MD5 + dHash, `src/evaluation/leakage.py`) avant chaque entraînement ; augmentations sans changement de teinte ni de saturation ; aucun modèle installé n'est écrasé (nouveaux noms, anciens dossiers dans `models/_replaced_<date>/`) ; une expérience = une ligne de `docs/experiments.csv`.

**Règle 5, pour remplacer un modèle installé** : exactitude terrain meilleure, McNemar p < 0,05 sur les mêmes photos terrain, et une perte d'au plus 1 point en labo.

Mesures : test terrain = 703 photos (PlantDoc 197, PlantWild 425, pomme de terre 81) ; validation terrain = 685 photos ; ECE sur 15 classes de confiance.

### 15.1 Étape 1 · Analyse des erreurs (`reports/error_analysis/`, `reports/gradcam/`)

`diseases_v2` sur le test terrain :
- 80,1 % de bonnes réponses, macro-F1 0,761, **ECE 0,142** : le modèle est trop sûr de lui.
- Classes faibles : tomate saine, tache bactérienne et mosaïque de la tomate, cercosporiose du maïs, cerisier sain, pourriture noire du pommier, alternariose de la pomme de terre.
- Confusions principales : cercosporiose ↔ helminthosporiose du maïs, tache bactérienne → septoriose de la tomate, mildiou de la tomate → mildiou de la pomme de terre.

La Grad-CAM, mesurée avec les masques de lésions PlantSeg, montre que l'attention du modèle se porte souvent en dehors de la feuille sur les photos de terrain.

### 15.2 Étape 2 · Protocole d'évaluation honnête (`src/evaluation/loso.py`, `calibration.py`, `stats.py`, `compare.py`)

Leave-one-source-out, 5 époques. On compare la source vue à l'entraînement à la même source jamais vue :

| Source | Vue à l'entraînement | Jamais vue |
|---|---|---|
| PlantDoc | 71,6 % | 48,7 % |
| PlantWild | 79,1 % | 51,8 % |
| Pomme de terre au champ | 98,8 % | 37,0 % |

- Le chiffre du test terrain surestime donc beaucoup ce que le modèle ferait sur des photos tunisiennes.
- PlantDoc reste la mesure la plus indépendante.
- Chaque comparaison utilise désormais McNemar exact sur les mêmes photos (`compare.py`, rapports dans `reports/compare/`).

### 15.3 Étape 3 · Augmentations « terrain » (`--aug field2`)

Augmentations : recadrage 0,4–1, ombre, flou, bruit, JPEG, aucun changement de teinte.

| Modèle | Terrain | Labo | McNemar contre le modèle installé | Décision |
|---|---|---|---|---|
| `diseases_v3` | 77,5 % | 98,4 % | p = 0,057 (+31 / −49) | non installé |
| `leaf_v5` | 77,4 % | 96,8 % | p = 0,40 | non installé |

Effet positif : les réponses **sûres et fausses** (confiance ≥ 0,9) baissent de 77 à 13 pour le modèle maladies, et de 74 à 45 pour le modèle feuille. L'exactitude, elle, ne progresse pas.

### 15.4 Étape 4 · Résolution et astuces d'entraînement (`train.py --size --accum --label-smoothing --ema --warmup`, `evaluate.py --tta`)

Les trois modèles maladies ont été entraînés avec label smoothing 0,1, EMA 0,999 des poids et 1 époque d'échauffement.

| Modèle maladies | Terrain | Labo | PlantDoc | Macro-F1 terrain | ECE terrain | McNemar contre `diseases_v2` | CPU, 1 photo |
|---|---|---|---|---|---|---|---|
| `diseases_v2` (installé) | 80,1 % | 99,5 % | 71,6 % | 0,761 | 0,142 | — | 22 ms |
| `diseases_t224` (témoin 224) | 79,9 % | — | — | — | — | p = 1 | 22 ms |
| **`diseases_s300`** | **82,8 %** | 99,4 % | **75,6 %** | **0,786** | **0,050** | **p = 0,023 (+41 / −22)** | 27 ms |
| `diseases_s384` | 82,7 % | 99,3 % | — | — | 0,022 | p = 0,033 | 37 ms |

**Lecture.**
- Le gain vient de la taille d'image, pas des autres astuces : à taille 224, le témoin ne fait pas mieux que le modèle installé.
- 300 et 384 donnent le même résultat (p = 1), mais 300 est plus rapide.
- La TTA (miroir + 3 recadrages) apporte de 0,4 à 1 point (p de 0,18 à 0,55, non significatif) et coûte environ 5 fois plus de temps CPU (131 ms au lieu de 27). **Elle n'est pas activée** (`AGRIA_TTA` non défini).

**Installé le 22/11/2026** : `models/diseases` = `diseases_s300`, car la règle 5 est respectée. L'ancien modèle est dans `models/_replaced_2026-11-22/diseases/`.

La combinaison des modèles a été ré-apprise (`eval_ensemble.py --tune --vlm --refresh`, `docs/eval_ensemble.md`) :
- chaîne complète terrain : 78,2 → **80,4 %** ;
- maladie exacte avec la vraie culture : 86,3 → 87,8 % ;
- culture : 88,9 → 89,3 % ;
- les poids précédents sont dans `models/_replaced_2026-11-22/ensemble_weights.json`.

**Modèle feuille, même recette en taille 300 (`leaf_s300`, meilleure époque 9 sur 17, patience 8)** :

| Modèle feuille | Terrain | Labo | PlantDoc | Macro-F1 terrain | ECE terrain | McNemar contre `leaf_v4` |
|---|---|---|---|---|---|---|
| `leaf_v4` (installé) | 78,5 % | 96,97 % | 67,5 % | 0,741 | 0,144 | — |
| **`leaf_s300`** | **81,4 %** | 97,03 % | 71,6 % | **0,779** | **0,062** | **p = 0,0225 (+45 / −25)** ; PlantDoc +20 / −12, p = 0,22 |

- Avec TTA, le test terrain passe de 81,4 à 82,5 % pour le nouveau modèle, et de 78,5 à 80,2 % pour l'ancien.
- Sur les photos labo de carence, l'exactitude ne change pas : 89,5 → 89,5 % en validation, 90,0 → 90,5 % en test (p = 0,49).
- Le type de problème (carence ou maladie) est plus souvent juste : 96,4 → 97,3 %.

**Installé le 22/11/2026**, car la règle 5 est respectée : `models/leaf` = `leaf_s300`, et l'ancien modèle est dans `models/_replaced_2026-11-22/leaf/`.

La combinaison a été ré-apprise une deuxième fois (`docs/eval_ensemble.md` ; les poids et le rapport précédents sont dans `models/_replaced_2026-11-22/*_apres_diseases_s300.*`) :
- chaîne complète terrain : 80,4 → **80,8 %** ;
- carence ou maladie, terrain : 99,4 → 99,9 % ;
- maladie exacte avec la vraie culture : 87,8 → 87,9 % ;
- culture, nouvelles sources : 97,2 → 97,7 %.

Le modèle de carences retrouve un poids de 0,5 dans le vote des carences. Vérifié sur toutes les photos labo de carence : 90,8 → **92,2 %** en test (McNemar +37 / −13, p = 0,0009), et 89,6 → 90,9 % en validation (p = 0,0006).


### 15.5 Étape 5 · Recadrage sur la feuille (`src/preparation/leaf_boxes.py`, `--leaf-crop`)

Le détecteur ouvert OWL-ViT base patch32 (Apache 2.0) cherche « a photo of a leaf » sur les 5 276 photos de terrain. La photo n'est recadrée que si la détection est assez sûre (score ≥ 0,1) et que la boîte couvre entre 15 et 85 % de la photo, avec une marge de 10 %. Résultat : **888 photos recadrées (16,8 %)**, surface gardée médiane 72 %. Sur les autres, le détecteur hésite (score médian 0,05) ou trouve une boîte qui couvre presque toute la photo.

Recadrage **seulement à la prédiction**, sur le modèle installé :
- test terrain 82,8 → 81,8 % (+0 / −7, **p = 0,016**) ;
- validation terrain inchangée.

**Rejeté.**

Modèle **entraîné** sur les photos terrain recadrées (`diseases_crop300`, recette `diseases_s300` + `--leaf-crop`, meilleure époque 8 sur 14) :

| | `diseases` (s300, installé) | `diseases_crop300` |
|---|---|---|
| Labo | 99,43 % | 99,33 % |
| Terrain | 82,79 % | 83,07 % |
| PlantDoc | 75,6 % | 75,1 % |
| Macro-F1 terrain | 0,786 | 0,802 |
| ECE terrain | 0,050 | 0,052 |
| McNemar terrain | — | +26 / −24, **p = 0,89** |

**Non installé.** Le gain n'est pas significatif, et le recadrage ajouterait environ 0,45 s d'OWL-ViT par photo sur CPU. Une seule photo de terrain sur six a une boîte assez sûre : le détecteur général « a photo of a leaf » ne trouve pas bien la feuille malade au milieu d'une plante. Un détecteur entraîné sur des feuilles, avec des boîtes annotées, serait nécessaire pour aller plus loin.

### 15.6 Étape 6 · Modèles de fondation gelés (`src/evaluation/foundation.py`)

DINOv2 ViT-S/14 et BioCLIP sont gelés ; leurs caractéristiques sont mises en cache dans `data/processed/features/`, et seule une tête linéaire ou MLP est entraînée (photos de terrain ×5).

| Modèle | Terrain | Labo | McNemar contre `diseases_s300` | CPU, 1 photo |
|---|---|---|---|---|
| DINOv2 + linéaire | 75,0 % | — | — | — |
| **DINOv2 + MLP** | 80,5 % | 98,6 % | p = 0,16 | 51 ms |
| BioCLIP + linéaire | 76,2 % | — | — | — |
| BioCLIP + MLP | 79,8 % | 97,8 % | p = 0,062 | 126 ms |
| Moyenne CNN + DINOv2 (poids 0,7 sur DINOv2) | **84,4 %** | 99,1 % | p = 0,20 (+36 / −25) | ~80 ms |
| Moyenne CNN + BioCLIP (poids 0,4) | 83,2 % | — | p = 0,68 | ~150 ms |

La moyenne CNN + DINOv2 obtient aussi : PlantDoc 76,7 %, macro-F1 0,805, ECE 0,123.

Leave-one-source-out (la source jamais vue, toutes ses photos) :

| Source jamais vue | DINOv2 + MLP | BioCLIP + MLP | CNN |
|---|---|---|---|
| PlantDoc | **52,2 %** | 49,4 % | 50,2 % |
| PlantWild | **56,3 %** | **56,3 %** | 52,0 % |
| Pomme de terre au champ | **49,0 %** | 47,8 % | 36,0 % |

**Lecture.**
- Les caractéristiques gelées **généralisent mieux à une source jamais vue** : jusqu'à +13 points pour la pomme de terre.
- Leur confiance moyenne est proche de leur exactitude : elles sont bien calibrées.
- Sur le test terrain, aucune ne respecte la règle 5, même la moyenne CNN + DINOv2 (+2,0 points, p = 0,20).
- Rien n'est installé. Le temps CPU reste bien sous les 15 s par réponse de l'agent.

### 15.7 Étape 7 · Température et seuils de l'agent (`src/evaluation/temperature.py`, `reports/temperature/`)

T est ajustée sur la validation terrain (val pour les tâches sans photos de terrain) ; l'effet est mesuré sur le test.

| Modèle | T | ECE avant → après | Décision |
|---|---|---|---|
| Maladies (s300) | 0,96 | 0,048 → 0,042 | déjà bien calibré par le label smoothing : T non appliquée |
| Culture | 2,18 | 0,040 → 0,012 | non appliquée : changerait les votes de la combinaison, déjà réglés sur ces confiances |
| Carence | 2,47 | 0,162 → 0,034 | T non appliquée : le modèle n'entre dans le vote des carences qu'avec un poids de 0,5, à côté du modèle feuille |
| Routeur | 1,25 | 0,0014 → 0,0013 | seuil 0,9 gardé (99,8 % juste) |
| Feuille (s300) | 0,93 | 0,061 → 0,044 | déjà proche de 1 : T non appliquée |

Le label smoothing a rendu les modèles en taille 300 **moins sûrs d'eux**. Les seuils de l'agent ont donc été revus sur la confiance de la combinaison que l'agent utilise vraiment (`src/evaluation/agent_thresholds.py`). Un nouveau seuil est le plus bas qui, sur la validation, ne donne pas plus de réponses fausses avec assurance que l'ancien système.

Le seuil de l'agent Diagnostic pour les maladies est mesuré sur la combinaison réellement utilisée (avec la vraie culture) :

| Jeu | Ancien système à 0,9 (répondues / justes / fausses) | Nouveau à 0,9 | **Nouveau à 0,8** |
|---|---|---|---|
| Validation terrain | 82,3 / 92,2 / 6,4 % | 76,4 / 94,3 / 4,4 % | **83,5 / 93,5 / 5,4 %** |
| Test terrain | 84,2 / 92,7 / 6,1 % | 77,2 / 94,1 / 4,6 % | **84,1 / 93,6 / 5,4 %** |

Revérifié après l'installation de `leaf_s300` et des nouveaux poids, au seuil de 0,8 : validation terrain 83,7 / 92,5 / 6,3 %, test terrain 83,5 / 93,7 / 5,3 %. Le seuil de 0,8 est gardé.

**Carences**, sur toutes les photos labo de carence (validation 1 949, test 1 724), sans VLM :

| Système | Seuil | Validation (répondues / justes / fausses) | Test |
|---|---|---|---|
| ancien (`leaf_v4`, modèle de carences à poids 0) | 0,95 | 81,8 / 97,9 / 1,7 % | 81,2 / 98,5 / 1,2 % |
| nouveau | 0,95 | 44,3 / 99,5 / 0,2 % | 46,9 / 99,8 / 0,1 % |
| **nouveau** | **0,7** | **73,1 / 97,8 / 1,6 %** | **74,2 / 98,5 / 1,1 %** |

Le seuil des carences passe de **0,95 à 0,7**. Avec 0,95, l'agent ne répondrait plus qu'à une carence sur deux. À 0,7, il répond avec la même exactitude qu'avant, mais à 7 points de photos en moins. Les photos sans réponse reçoivent des questions de confirmation, jamais d'engrais.

Le seuil des maladies passe de **0,9 à 0,8** (`src/agent/agents/diagnostic.py`, `AGENT_THRESHOLDS`). Il est choisi sur la validation, et le test confirme : autant de photos répondues qu'avant, mais plus de réponses justes et moins de réponses fausses données avec assurance.

Le modèle de carence seul ne fait plus que 76,0 % sur le test actuel (2 251 photos, dont les nouvelles sources tomato_mg et CitrusUAT qu'il n'a jamais vues). Il n'intervient qu'avec un poids de 0,5, à côté du modèle feuille, et devrait être ré-entraîné sur les nouvelles sources.

### 15.8 Étape 8 · Pseudo-étiquettes à relire (`src/preparation/pseudo_label.py`)

Pour chaque photo non étiquetée, le script propose une étiquette seulement si trois conditions sont réunies :
- le modèle maladies et le modèle feuille sont d'accord (avec TTA) ;
- la confiance est ≥ 0,95 (ou la confiance après température, avec `--temperature`) ;
- la photo n'est pas une image de validation ou de test (MD5 + dHash).

Le résultat est seulement un CSV à relire (`data/pseudo/review_<date>.csv`). Après relecture, `promote` copie les lignes `valide = oui` vers `data/raw/pseudo_<date>/`, toujours dans la partie entraînement, puis on lance `add_source.py`. **Pas encore lancé** : il n'y a pas encore de photos non étiquetées.

### 15.9 Étape 9 · Photos tunisiennes avec consentement (`src/preparation/field_tn.py`)

- **Application** : après « juste » ou « faux », une case « J'accepte qu'AgrIA garde cette photo pour mieux reconnaître les maladies en Tunisie », non cochée par défaut, en français et en arabe. L'API enregistre `avis.garder_photo` dans le journal.
- **`field_tn.py export`** : écrit `data/field_tn/review_<date>.csv`, avec uniquement les photos dont l'agriculteur a donné son accord. L'étiquette est pré-remplie seulement si l'agriculteur a dit que la réponse était juste.
- **`freeze`** : copie les lignes validées dans `data/field_tn/images/` et les ajoute à `manifest.csv`. Les lignes ne sont jamais réécrites, et les doublons (id ou MD5) sont refusés.
- **`verify`** : contrôle les MD5.
- `data/field_tn` est un jeu de **test gelé** (split `field_tn` dans `dataset.py` et dans le contrôle des fuites) : il ne sert jamais à l'entraînement.
- Premier export : **0 photo**, car les 52 avis enregistrés jusqu'ici datent d'avant la case de consentement.
