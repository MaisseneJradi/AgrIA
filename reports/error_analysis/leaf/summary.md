# Analyse des erreurs : leaf · test_field

703 photos · exactitude 78.5% · macro-F1 0.7409 · ECE 0.1441

Classes faibles (recall < 0.6 with >= 5 photos) : tomato__mosaic_virus, tomato__healthy, corn__gray_leaf_spot, cherry__healthy, apple__black_rot, tomato__bacterial_spot, potato__early_blight, tomato__late_blight

## Par source

| source | n | accuracy | macro_f1 |
|---|---|---|---|
| plantdoc | 197 | 0.6751 | 0.6772 |
| plantwild | 425 | 0.8 | 0.7697 |
| potato_field | 81 | 0.9753 | 0.9866 |

## Les 10 confusions les plus fréquentes

| true | pred | n | share_of_true |
|---|---|---|---|
| corn__gray_leaf_spot | corn__northern_leaf_blight | 8 | 0.4444 |
| corn__northern_leaf_blight | corn__gray_leaf_spot | 6 | 0.2222 |
| tomato__bacterial_spot | tomato__septoria_leaf_spot | 5 | 0.2381 |
| apple__rust | apple__scab | 5 | 0.1923 |
| tomato__septoria_leaf_spot | tomato__early_blight | 5 | 0.1724 |
| tomato__mosaic_virus | tomato__yellow_leaf_curl_virus | 4 | 0.2105 |
| potato__early_blight | potato__late_blight | 4 | 0.1818 |
| corn__common_rust | corn__northern_leaf_blight | 4 | 0.1081 |
| apple__black_rot | apple__scab | 3 | 0.5 |
| pepper__bacterial_spot | tomato__bacterial_spot | 3 | 0.1875 |

## Par classe (de la plus faible à la plus forte)

| class | support | recall | precision | f1 | conf_right | conf_wrong | most_confused_with |
|---|---|---|---|---|---|---|---|
| tomato__mosaic_virus | 19 | 0.3158 | 0.75 | 0.4444 | 0.8868 | 0.7408 | tomato__yellow_leaf_curl_virus |
| tomato__healthy | 8 | 0.375 | 0.4286 | 0.4 | 1.0 | 0.9087 | tomato__bacterial_spot |
| corn__gray_leaf_spot | 18 | 0.5 | 0.5294 | 0.5143 | 0.9325 | 0.9257 | corn__northern_leaf_blight |
| cherry__healthy | 10 | 0.5 | 0.8333 | 0.625 | 0.9482 | 0.5447 | peach__healthy |
| apple__black_rot | 6 | 0.5 | 1.0 | 0.6667 | 1.0 | 0.9624 | apple__scab |
| tomato__bacterial_spot | 21 | 0.5238 | 0.3793 | 0.44 | 0.8576 | 0.8295 | tomato__septoria_leaf_spot |
| potato__early_blight | 22 | 0.5909 | 0.6842 | 0.6341 | 0.9625 | 0.9601 | potato__late_blight |
| tomato__late_blight | 27 | 0.5926 | 0.8 | 0.6809 | 0.9203 | 0.8094 | tomato__early_blight |
| cherry__powdery_mildew | 5 | 0.6 | 0.75 | 0.6667 | 0.9998 | 0.7406 | tomato__early_blight |
| tomato__early_blight | 28 | 0.6071 | 0.5484 | 0.5763 | 0.9357 | 0.8386 | potato__early_blight |
| pepper__bacterial_spot | 16 | 0.625 | 0.6667 | 0.6452 | 0.9828 | 0.8529 | tomato__bacterial_spot |
| pepper__healthy | 8 | 0.625 | 0.4545 | 0.5263 | 0.8973 | 0.8373 | Fe_deficiency |
| apple__healthy | 9 | 0.6667 | 0.6667 | 0.6667 | 0.9666 | 0.602 | apple__scab |
| tomato__septoria_leaf_spot | 29 | 0.6897 | 0.625 | 0.6557 | 0.8735 | 0.7754 | tomato__early_blight |
| corn__northern_leaf_blight | 27 | 0.7037 | 0.5588 | 0.623 | 0.9527 | 0.7759 | corn__gray_leaf_spot |
| corn__common_rust | 37 | 0.7297 | 0.931 | 0.8182 | 0.9785 | 0.9092 | corn__northern_leaf_blight |
| apple__rust | 26 | 0.7308 | 0.9048 | 0.8085 | 0.9818 | 0.9001 | apple__scab |
| apple__scab | 34 | 0.7647 | 0.7222 | 0.7429 | 0.9375 | 0.6745 | apple__rust |
| orange__citrus_greening | 15 | 0.8 | 0.8 | 0.8 | 0.987 | 0.6556 | tomato__early_blight |
| strawberry__leaf_scorch | 6 | 0.8333 | 1.0 | 0.9091 | 0.9891 | 0.9999 | strawberry__healthy |
| grape__black_rot | 19 | 0.8947 | 0.85 | 0.8718 | 0.8939 | 0.6228 | corn__northern_leaf_blight |
| tomato__leaf_mold | 29 | 0.8966 | 0.8966 | 0.8966 | 0.9326 | 0.7232 | tomato__bacterial_spot |
| tomato__yellow_leaf_curl_virus | 20 | 0.9 | 0.72 | 0.8 | 0.9673 | 0.6169 | tomato__septoria_leaf_spot |
| potato__late_blight | 74 | 0.9459 | 0.9333 | 0.9396 | 0.9711 | 0.7737 | potato__early_blight |
| citrus__canker | 46 | 0.9565 | 0.9565 | 0.9565 | 0.9806 | 0.581 | orange__citrus_greening |
| potato__healthy | 30 | 0.9667 | 1.0 | 0.9831 | 0.9996 | 0.513 | tomato__healthy |
| squash__powdery_mildew | 66 | 0.9848 | 0.9848 | 0.9848 | 0.9888 | 0.6938 | corn__northern_leaf_blight |
| wheat__leaf_rust | 19 | 1.0 | 0.8636 | 0.9268 | 0.9729 |  |  |
| grape__healthy | 12 | 1.0 | 0.8571 | 0.9231 | 0.9651 |  |  |
| peach__healthy | 9 | 1.0 | 0.8182 | 0.9 | 0.8228 |  |  |
| strawberry__healthy | 8 | 1.0 | 0.8889 | 0.9412 | 0.9995 |  |  |
