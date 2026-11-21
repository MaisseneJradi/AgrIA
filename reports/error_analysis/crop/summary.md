# Analyse des erreurs : crop · test_field

1861 photos · exactitude 94.3% · macro-F1 0.8938 · ECE 0.0402

Classes faibles (recall < 0.6 with >= 5 photos) : aucune

## Par source

| source | n | accuracy | macro_f1 |
|---|---|---|---|
| gvlid | 458 | 1.0 | 1.0 |
| plantdoc | 197 | 0.8528 | 0.8504 |
| plantwild | 750 | 0.8987 | 0.8698 |
| potato_field | 456 | 0.9978 | 0.9989 |

## Les 10 confusions les plus fréquentes

| true | pred | n | share_of_true |
|---|---|---|---|
| tomato | potato | 10 | 0.0552 |
| potato | tomato | 9 | 0.018 |
| corn | wheat | 8 | 0.0976 |
| cherry | apple | 5 | 0.1613 |
| tomato | pepper | 5 | 0.0276 |
| pepper | tomato | 4 | 0.1212 |
| wheat | corn | 4 | 0.0227 |
| cherry | grape | 3 | 0.0968 |
| apple | cherry | 3 | 0.0341 |
| apple | potato | 3 | 0.0341 |

## Par classe (de la plus faible à la plus forte)

| class | support | recall | precision | f1 | conf_right | conf_wrong | most_confused_with |
|---|---|---|---|---|---|---|---|
| cherry | 31 | 0.6452 | 0.8696 | 0.7407 | 0.8944 | 0.806 | apple |
| pepper | 33 | 0.7273 | 0.7273 | 0.7273 | 0.9499 | 0.8184 | tomato |
| apple | 88 | 0.8523 | 0.8621 | 0.8571 | 0.9713 | 0.7959 | potato |
| tomato | 181 | 0.8674 | 0.8771 | 0.8722 | 0.972 | 0.8851 | potato |
| peach | 42 | 0.881 | 0.8605 | 0.8706 | 0.9875 | 0.9213 | apple |
| corn | 82 | 0.9024 | 0.9024 | 0.9024 | 0.9924 | 0.9418 | wheat |
| squash | 99 | 0.9293 | 0.9583 | 0.9436 | 0.9854 | 0.8099 | tomato |
| citrus | 61 | 0.9344 | 0.9344 | 0.9344 | 0.9995 | 0.8939 | wheat |
| wheat | 176 | 0.9716 | 0.9243 | 0.9474 | 0.9939 | 0.8134 | corn |
| potato | 501 | 0.978 | 0.9665 | 0.9722 | 0.998 | 0.8912 | tomato |
| grape | 551 | 0.9837 | 0.9927 | 0.9881 | 0.9943 | 0.8692 | tomato |
| strawberry | 16 | 1.0 | 0.9412 | 0.9697 | 0.9899 |  |  |
