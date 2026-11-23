# Évaluation des combinaisons de modèles

Modèle de culture : `crop` · Poids : `{"crop": {"crop": 1.0, "leaf": 0.5, "diseases": 0.0, "vlm": 0.25}, "kind": {"leaf": 1.0, "vlm": 0.25}, "disease": {"diseases": 1.0, "leaf": 1.0}, "deficiency": {"leaf": 1.0, "deficiency": 0.5}}` · VLM : oui · 2026-11-22 14:11


## test_labo (358 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 99.4% | 0.3% | 358 |
| leaf | 87.4% | 0.0% | 358 |
| diseases | 88.5% | 1.1% | 358 |
| vlm | 62.0% | 20.1% | 358 |
| combinaison | 99.4% | 0.0% | 358 |
| décision (vote + contrôle VLM) | 97.5% | 0.0% | 358 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 98.6% | — | 358 |
| vlm seul | 83.8% | — | 358 |
| combinaison | 98.3% | — | 358 |


| Classe | juste | | n |
|---|---|---|---|
| carence / leaf seul | 94.4% | — | 54 |
| carence / deficiency seul | 81.5% | — | 54 |
| carence / combinaison | 100.0% | — | 54 |
| maladie (vraie culture) / diseases seul | 97.7% | — | 304 |
| maladie (vraie culture) / leaf seul | 98.0% | — | 304 |
| maladie (vraie culture) / combinaison | 98.7% | — | 304 |
| chaîne complète (culture votée -> type -> classe) | 96.9% | — | 358 |

## test_terrain (703 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 89.3% | 6.8% | 703 |
| leaf | 91.6% | 0.9% | 703 |
| diseases | 92.0% | 2.1% | 703 |
| vlm | 73.5% | 19.9% | 703 |
| combinaison | 90.3% | 0.6% | 703 |
| décision (vote + contrôle VLM) | 89.2% | 0.6% | 703 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 99.9% | — | 703 |
| vlm seul | 97.2% | — | 703 |
| combinaison | 99.9% | — | 703 |


| Classe | juste | | n |
|---|---|---|---|
| maladie (vraie culture) / diseases seul | 87.9% | — | 703 |
| maladie (vraie culture) / leaf seul | 87.8% | — | 703 |
| maladie (vraie culture) / combinaison | 87.9% | — | 703 |
| chaîne complète (culture votée -> type -> classe) | 80.8% | — | 703 |

## test_nouvelles_sources (216 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 100.0% | 0.0% | 216 |
| leaf | 77.8% | 0.5% | 216 |
| diseases | 56.5% | 8.3% | 216 |
| vlm | 70.8% | 15.3% | 216 |
| combinaison | 100.0% | 0.0% | 216 |
| décision (vote + contrôle VLM) | 97.7% | 0.0% | 216 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 74.1% | — | 216 |
| vlm seul | 95.8% | — | 216 |
| combinaison | 77.8% | — | 216 |

## journal (15 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 66.7% | 33.3% | 15 |
| leaf | 66.7% | 6.7% | 15 |
| diseases | 66.7% | 0.0% | 15 |
| vlm | 93.3% | 6.7% | 15 |
| combinaison | 66.7% | 0.0% | 15 |
| décision (vote + contrôle VLM) | 100.0% | 0.0% | 15 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 66.7% | — | 15 |
| vlm seul | 80.0% | — | 15 |
| combinaison | 60.0% | — | 15 |
