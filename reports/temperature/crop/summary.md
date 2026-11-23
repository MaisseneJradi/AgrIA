# Température : crop (crop)

T = 2.1808 ajustée sur val_field, mesurée sur test_field.

| | exactitude | confiance moyenne | ECE | NLL |
|---|---|---|---|---|
| avant (T = 1) | 94.3% | 98.2% | 0.0396 | 0.3325 |
| après (T = 2.1808) | 94.3% | 94.4% | 0.0117 | 0.2128 |

Couverture et exactitude des réponses données sur test_field, selon le seuil :

| seuil | couverture avant | exactitude avant | couverture après | exactitude après |
|---|---|---|---|---|
| 0.5 | 99.6% | 94.5% | 97.9% | 95.3% |
| 0.6 | 98.8% | 94.9% | 95.7% | 96.2% |
| 0.7 | 98.1% | 95.2% | 93.8% | 96.9% |
| 0.8 | 96.7% | 95.8% | 90.4% | 97.9% |
| 0.85 | 95.8% | 96.2% | 87.7% | 98.3% |
| 0.9 ← seuil actuel | 94.5% | 96.6% | 84.7% | 98.5% |
| 0.95 | 92.7% | 97.3% | 79.4% | 99.1% |
| 0.98 | 90.4% | 97.9% | 69.4% | 99.5% |

Seuil proposé (le plus bas dont les réponses sont justes à ≥ 95% sur val_field) :
- avant : 0.64 → sur test_field couverture 98.7%, exactitude 95.0%
- après : 0.5 → sur test_field couverture 97.9%, exactitude 95.3%
