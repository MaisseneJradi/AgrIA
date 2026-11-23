# Température : diseases (diseases)

T = 0.9577 ajustée sur val_field, mesurée sur test_field.

| | exactitude | confiance moyenne | ECE | NLL |
|---|---|---|---|---|
| avant (T = 1) | 82.8% | 80.8% | 0.0484 | 0.7902 |
| après (T = 0.9577) | 82.8% | 83.2% | 0.0418 | 0.7834 |

Couverture et exactitude des réponses données sur test_field, selon le seuil :

| seuil | couverture avant | exactitude avant | couverture après | exactitude après |
|---|---|---|---|---|
| 0.5 | 91.3% | 86.3% | 93.5% | 85.4% |
| 0.6 | 86.2% | 88.4% | 88.0% | 87.7% |
| 0.7 | 80.4% | 90.6% | 82.9% | 89.9% |
| 0.8 | 71.0% | 92.4% | 74.7% | 91.8% |
| 0.85 | 59.5% | 92.8% | 68.1% | 92.5% |
| 0.9 ← seuil actuel | 33.7% | 92.0% | 46.9% | 92.7% |
| 0.95 | 7.1% | 92.0% | 15.2% | 90.6% |
| 0.98 | 2.0% | 100.0% | 2.7% | 94.7% |

Seuil proposé (le plus bas dont les réponses sont justes à ≥ 95% sur val_field) :
- avant : None → sur test_field couverture 0.0%, exactitude -
- après : None → sur test_field couverture 0.0%, exactitude -
