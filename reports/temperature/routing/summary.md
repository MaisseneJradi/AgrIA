# Température : routing (routing)

T = 1.2532 ajustée sur val, mesurée sur test.

| | exactitude | confiance moyenne | ECE | NLL |
|---|---|---|---|---|
| avant (T = 1) | 99.8% | 99.9% | 0.0014 | 0.0062 |
| après (T = 1.2532) | 99.8% | 99.9% | 0.0013 | 0.0058 |

Couverture et exactitude des réponses données sur test, selon le seuil :

| seuil | couverture avant | exactitude avant | couverture après | exactitude après |
|---|---|---|---|---|
| 0.5 | 100.0% | 99.8% | 100.0% | 99.8% |
| 0.6 | 100.0% | 99.8% | 100.0% | 99.8% |
| 0.7 | 100.0% | 99.8% | 99.9% | 99.9% |
| 0.8 | 99.9% | 99.9% | 99.9% | 99.9% |
| 0.85 | 99.9% | 99.9% | 99.8% | 100.0% |
| 0.9 ← seuil actuel | 99.8% | 100.0% | 99.7% | 100.0% |
| 0.95 | 99.7% | 100.0% | 99.5% | 100.0% |
| 0.98 | 99.4% | 100.0% | 99.1% | 100.0% |

Seuil proposé (le plus bas dont les réponses sont justes à ≥ 95% sur val) :
- avant : 0.5 → sur test couverture 100.0%, exactitude 99.8%
- après : 0.5 → sur test couverture 100.0%, exactitude 99.8%
