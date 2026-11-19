# Évaluation des combinaisons de modèles

Modèle de culture : `crop` · Poids : `{"crop": {"crop": 1.0, "leaf": 0.0, "diseases": 1.0, "vlm": 0.0}, "kind": {"leaf": 1.0, "vlm": 0.5}, "disease": {"diseases": 1.0, "leaf": 0.0}, "deficiency": {"leaf": 1.0, "deficiency": 0.0}}` · VLM : oui · 2026-11-19 18:53


## test_labo (358 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 99.2% | 0.3% | 358 |
| leaf | 89.1% | 2.2% | 358 |
| diseases | 87.7% | 3.1% | 358 |
| vlm | 62.0% | 20.1% | 353 |
| combinaison | 99.2% | 0.0% | 358 |
| décision (vote + contrôle VLM) | 98.6% | 0.0% | 358 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 98.0% | — | 358 |
| vlm seul | 84.1% | — | 353 |
| combinaison | 98.0% | — | 358 |


| Classe | juste | | n |
|---|---|---|---|
| carence / leaf seul | 96.3% | — | 54 |
| carence / deficiency seul | 81.5% | — | 54 |
| carence / combinaison | 96.3% | — | 54 |
| maladie (vraie culture) / diseases seul | 98.0% | — | 304 |
| maladie (vraie culture) / leaf seul | 98.7% | — | 304 |
| maladie (vraie culture) / combinaison | 98.0% | — | 304 |
| chaîne complète (culture votée -> type -> classe) | 95.0% | — | 358 |

## test_terrain (199 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 85.9% | 7.5% | 199 |
| leaf | 82.9% | 8.0% | 199 |
| diseases | 83.4% | 6.5% | 199 |
| vlm | 74.9% | 17.1% | 199 |
| combinaison | 86.9% | 2.0% | 199 |
| décision (vote + contrôle VLM) | 85.4% | 1.0% | 199 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 96.0% | — | 199 |
| vlm seul | 98.0% | — | 199 |
| combinaison | 98.0% | — | 199 |


| Classe | juste | | n |
|---|---|---|---|
| maladie (vraie culture) / diseases seul | 74.9% | — | 199 |
| maladie (vraie culture) / leaf seul | 74.4% | — | 199 |
| maladie (vraie culture) / combinaison | 74.9% | — | 199 |
| chaîne complète (culture votée -> type -> classe) | 63.8% | — | 199 |

## test_nouvelles_sources (216 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 100.0% | 0.0% | 216 |
| leaf | 69.0% | 14.4% | 216 |
| diseases | 40.7% | 15.7% | 216 |
| vlm | 70.8% | 15.3% | 216 |
| combinaison | 99.5% | 0.0% | 216 |
| décision (vote + contrôle VLM) | 96.8% | 0.0% | 216 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 69.0% | — | 216 |
| vlm seul | 95.8% | — | 216 |
| combinaison | 71.3% | — | 216 |

## journal (15 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 33.3% | 46.7% | 15 |
| leaf | 20.0% | 53.3% | 15 |
| diseases | 26.7% | 26.7% | 15 |
| vlm | 93.3% | 6.7% | 15 |
| combinaison | 26.7% | 26.7% | 15 |
| décision (vote + contrôle VLM) | 66.7% | 0.0% | 15 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 66.7% | — | 15 |
| vlm seul | 80.0% | — | 15 |
| combinaison | 66.7% | — | 15 |
