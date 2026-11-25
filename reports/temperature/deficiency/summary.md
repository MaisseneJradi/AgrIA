# Température : deficiency (deficiency)

T = 2.4711 ajustée sur val, mesurée sur test.

| | exactitude | confiance moyenne | ECE | NLL |
|---|---|---|---|---|
| avant (T = 1) | 76.0% | 92.2% | 0.1616 | 1.1544 |
| après (T = 2.4711) | 76.0% | 77.7% | 0.0339 | 0.7346 |

Couverture et exactitude des réponses données sur test, selon le seuil :

| seuil | couverture avant | exactitude avant | couverture après | exactitude après |
|---|---|---|---|---|
| 0.5 | 96.9% | 77.6% | 84.1% | 84.9% |
| 0.6 | 93.2% | 79.4% | 76.1% | 88.8% |
| 0.7 | 88.6% | 81.7% | 68.5% | 91.2% |
| 0.8 | 84.4% | 83.8% | 60.1% | 94.2% |
| 0.85 | 81.5% | 85.3% | 54.6% | 95.6% |
| 0.9 | 77.8% | 86.9% | 46.3% | 97.1% |
| 0.95 ← seuil actuel | 71.8% | 89.2% | 30.3% | 98.5% |
| 0.98 | 65.8% | 91.3% | 12.3% | 99.3% |

Seuil proposé (le plus bas dont les réponses sont justes à ≥ 95% sur val) :
- avant : None → sur test couverture 0.0%, exactitude -
- après : 0.78 → sur test couverture 61.7%, exactitude 93.7%
