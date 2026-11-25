# Température : leaf_s300 (leaf)

T = 0.9283 ajustée sur val_field, mesurée sur test_field.

| | exactitude | confiance moyenne | ECE | NLL |
|---|---|---|---|---|
| avant (T = 1) | 81.4% | 80.0% | 0.0612 | 0.7708 |
| après (T = 0.9283) | 81.4% | 84.0% | 0.0439 | 0.7583 |

Couverture et exactitude des réponses données sur test_field, selon le seuil :

| seuil | couverture avant | exactitude avant | couverture après | exactitude après |
|---|---|---|---|---|
| 0.5 | 90.3% | 86.1% | 92.5% | 85.2% |
| 0.6 | 86.2% | 88.6% | 88.3% | 87.6% |
| 0.7 | 78.7% | 91.3% | 83.4% | 89.8% |
| 0.8 | 67.0% | 93.0% | 74.8% | 92.8% |
| 0.85 | 56.5% | 93.7% | 67.4% | 93.0% |
| 0.9 ← seuil actuel | 34.1% | 95.0% | 54.9% | 94.0% |
| 0.95 | 8.1% | 96.5% | 22.1% | 93.5% |
| 0.98 | 3.1% | 100.0% | 5.5% | 100.0% |

Seuil proposé (le plus bas dont les réponses sont justes à ≥ 95% sur val_field) :
- avant : 0.97 → sur test_field couverture 4.7%, exactitude 100.0%
- après : 0.98 → sur test_field couverture 5.5%, exactitude 100.0%
