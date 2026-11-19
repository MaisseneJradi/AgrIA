# Évaluation des combinaisons de modèles

Modèle de culture : `crop_v3b` · Poids : `{"crop": {"crop": 1.0, "leaf": 0.0, "diseases": 1.0, "vlm": 0.0}, "kind": {"leaf": 1.0, "vlm": 0.0}, "disease": {"diseases": 1.0, "leaf": 0.0}, "deficiency": {"leaf": 1.0, "deficiency": 0.0}}` · VLM : non · 2026-11-19 14:19


## test_labo (358 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 98.3% | 0.6% | 358 |
| leaf | 89.1% | 2.2% | 358 |
| diseases | 87.7% | 3.1% | 358 |
| combinaison | 98.9% | 0.0% | 358 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 98.0% | — | 358 |
| combinaison | 98.0% | — | 358 |


| Classe | juste | | n |
|---|---|---|---|
| carence / leaf seul | 96.3% | — | 54 |
| carence / deficiency seul | 81.5% | — | 54 |
| carence / combinaison | 96.3% | — | 54 |
| maladie (vraie culture) / diseases seul | 98.0% | — | 304 |
| maladie (vraie culture) / leaf seul | 98.7% | — | 304 |
| maladie (vraie culture) / combinaison | 98.0% | — | 304 |
| chaîne complète (culture votée -> type -> classe) | 94.7% | — | 358 |

## test_terrain (199 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 80.4% | 8.0% | 199 |
| leaf | 82.9% | 8.0% | 199 |
| diseases | 83.4% | 6.5% | 199 |
| combinaison | 86.4% | 2.5% | 199 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 96.0% | — | 199 |
| combinaison | 96.0% | — | 199 |


| Classe | juste | | n |
|---|---|---|---|
| maladie (vraie culture) / diseases seul | 74.9% | — | 199 |
| maladie (vraie culture) / leaf seul | 74.4% | — | 199 |
| maladie (vraie culture) / combinaison | 74.9% | — | 199 |
| chaîne complète (culture votée -> type -> classe) | 60.8% | — | 199 |

## test_nouvelles_sources (216 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 100.0% | 0.0% | 216 |
| leaf | 69.0% | 14.4% | 216 |
| diseases | 40.7% | 15.7% | 216 |
| combinaison | 100.0% | 0.0% | 216 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 69.0% | — | 216 |
| combinaison | 69.0% | — | 216 |

## journal (15 photos)

| Culture | juste | fausse et sûre (≥ 85 %) | n |
|---|---|---|---|
| crop | 26.7% | 20.0% | 15 |
| leaf | 20.0% | 53.3% | 15 |
| diseases | 26.7% | 26.7% | 15 |
| combinaison | 33.3% | 13.3% | 15 |


| Carence ou maladie | juste | | n |
|---|---|---|---|
| leaf seul | 66.7% | — | 15 |
| combinaison | 66.7% | — | 15 |
