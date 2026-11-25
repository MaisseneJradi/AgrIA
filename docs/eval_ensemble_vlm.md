# Évaluation des combinaisons de modèles

Modèle de culture : `crop` · Poids : `{"crop": {"crop": 1.0, "leaf": 0.0, "diseases": 0.25, "vlm": 0.25}, "kind": {"leaf": 1.0, "vlm": 0.25}, "disease": {"diseases": 1.0, "leaf": 1.0}, "deficiency": {"leaf": 1.0, "deficiency": 0.0}}` · VLM : oui · 2026-11-21 08:18


## test_labo (358 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 99.4% | 0.3% | 358 |
| leaf | 89.7% | 3.9% | 358 |
| diseases | 87.7% | 5.3% | 358 |
| vlm | 62.0% | 20.1% | 358 |
| combinaison | 99.4% | 0.0% | 358 |
| décision (vote + contrôle VLM) | 97.2% | 0.0% | 358 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 98.9% | — | 358 |
| vlm seul | 83.8% | — | 358 |
| combinaison | 98.3% | — | 358 |


| Classe | juste | | n |
|---|---|---|---|
| carence / leaf seul | 100.0% | — | 54 |
| carence / deficiency seul | 81.5% | — | 54 |
| carence / combinaison | 100.0% | — | 54 |
| maladie (vraie culture) / diseases seul | 98.4% | — | 304 |
| maladie (vraie culture) / leaf seul | 98.4% | — | 304 |
| maladie (vraie culture) / combinaison | 99.0% | — | 304 |
| chaîne complète (culture votée -> type -> classe) | 97.2% | — | 358 |

## test_terrain (703 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 89.3% | 6.8% | 703 |
| leaf | 92.0% | 4.4% | 703 |
| diseases | 91.0% | 5.1% | 703 |
| vlm | 73.5% | 19.9% | 703 |
| combinaison | 89.6% | 0.4% | 703 |
| décision (vote + contrôle VLM) | 88.9% | 0.4% | 703 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 99.3% | — | 703 |
| vlm seul | 97.2% | — | 703 |
| combinaison | 99.4% | — | 703 |


| Classe | juste | | n |
|---|---|---|---|
| maladie (vraie culture) / diseases seul | 86.9% | — | 703 |
| maladie (vraie culture) / leaf seul | 85.2% | — | 703 |
| maladie (vraie culture) / combinaison | 86.3% | — | 703 |
| chaîne complète (culture votée -> type -> classe) | 78.2% | — | 703 |

## test_nouvelles_sources (216 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 100.0% | 0.0% | 216 |
| leaf | 70.4% | 9.3% | 216 |
| diseases | 56.5% | 22.7% | 216 |
| vlm | 70.8% | 15.3% | 216 |
| combinaison | 100.0% | 0.0% | 216 |
| décision (vote + contrôle VLM) | 97.2% | 0.0% | 216 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 70.4% | — | 216 |
| vlm seul | 95.8% | — | 216 |
| combinaison | 70.8% | — | 216 |

## journal (15 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 66.7% | 33.3% | 15 |
| leaf | 60.0% | 13.3% | 15 |
| diseases | 60.0% | 20.0% | 15 |
| vlm | 93.3% | 6.7% | 15 |
| combinaison | 66.7% | 0.0% | 15 |
| décision (vote + contrôle VLM) | 100.0% | 0.0% | 15 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 66.7% | — | 15 |
| vlm seul | 80.0% | — | 15 |
| combinaison | 66.7% | — | 15 |
