# Calibration des modèles déployés

ECE = écart moyen entre confiance et exactitude ; « trop sûr » = confiance moyenne − exactitude.

| modèle | jeu | photos | exactitude | confiance moyenne | ECE | MCE | trop sûr |
|---|---|---|---|---|---|---|---|
| routing | validation labo | 2314 | 99.8% | 99.9% | 0.0021 | 0.0007 | +0.001 |
| routing | test labo | 2234 | 99.8% | 99.9% | 0.0014 | 0.0003 | +0.001 |
| routing | test terrain | 70 | 100.0% | 99.1% | 0.0092 | 0.0003 | -0.009 |
| diseases | validation labo | 8281 | 99.4% | 99.7% | 0.0027 | 0.1689 | +0.003 |
| diseases | validation terrain | 685 | 78.4% | 93.4% | 0.1499 | 0.4466 | +0.150 |
| diseases | test labo | 7960 | 99.5% | 99.7% | 0.0025 | 0.0867 | +0.002 |
| diseases | test terrain | 703 | 80.1% | 94.2% | 0.1419 | 0.4224 | +0.142 |
| leaf | validation labo | 10533 | 97.1% | 98.6% | 0.0148 | 0.2444 | +0.015 |
| leaf | validation terrain | 685 | 78.8% | 93.2% | 0.1492 | 0.3858 | +0.144 |
| leaf | test labo | 9911 | 97.0% | 98.7% | 0.0168 | 0.2488 | +0.017 |
| leaf | test terrain | 703 | 78.5% | 92.4% | 0.1441 | 0.3899 | +0.139 |
| crop | validation labo | 11852 | 99.9% | 99.8% | 0.0009 | 0.0571 | -0.001 |
| crop | validation terrain | 1537 | 94.1% | 98.2% | 0.0402 | 0.265 | +0.040 |
| crop | test labo | 11057 | 99.9% | 99.9% | 0.0008 | 0.0968 | -0.000 |
| crop | test terrain | 1861 | 94.3% | 98.2% | 0.0402 | 0.3307 | +0.039 |
| fruits | validation labo | 826 | 99.2% | 99.2% | 0.0101 | 0.004 | +0.001 |
| fruits | test labo | 833 | 98.3% | 99.1% | 0.0138 | 0.0052 | +0.008 |
| deficiency | validation labo | 2090 | 88.6% | 95.5% | 0.0709 | 0.3702 | +0.069 |
| deficiency | test labo | 1871 | 86.4% | 95.3% | 0.0919 | 0.2742 | +0.088 |
