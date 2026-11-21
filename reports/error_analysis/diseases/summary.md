# Analyse des erreurs : diseases · test_field

703 photos · exactitude 80.1% · macro-F1 0.7607 · ECE 0.1419

Classes faibles (recall < 0.6 with >= 5 photos) : tomato__healthy, tomato__bacterial_spot, corn__gray_leaf_spot, tomato__mosaic_virus, cherry__healthy, apple__black_rot, potato__early_blight

## Par source

| source | n | accuracy | macro_f1 |
|---|---|---|---|
| plantdoc | 197 | 0.7157 | 0.708 |
| plantwild | 425 | 0.8047 | 0.7672 |
| potato_field | 81 | 0.9877 | 0.995 |

## Les 10 confusions les plus fréquentes

| true | pred | n | share_of_true |
|---|---|---|---|
| corn__gray_leaf_spot | corn__northern_leaf_blight | 10 | 0.5556 |
| corn__northern_leaf_blight | corn__gray_leaf_spot | 8 | 0.2963 |
| tomato__bacterial_spot | tomato__septoria_leaf_spot | 6 | 0.2857 |
| tomato__septoria_leaf_spot | tomato__early_blight | 5 | 0.1724 |
| potato__early_blight | potato__late_blight | 4 | 0.1818 |
| tomato__late_blight | potato__late_blight | 4 | 0.1481 |
| tomato__healthy | pepper__healthy | 3 | 0.375 |
| cherry__healthy | apple__healthy | 3 | 0.3 |
| tomato__mosaic_virus | tomato__healthy | 3 | 0.1579 |
| tomato__mosaic_virus | tomato__yellow_leaf_curl_virus | 3 | 0.1579 |

## Par classe (de la plus faible à la plus forte)

| class | support | recall | precision | f1 | conf_right | conf_wrong | most_confused_with |
|---|---|---|---|---|---|---|---|
| tomato__healthy | 8 | 0.375 | 0.375 | 0.375 | 0.9817 | 0.7963 | pepper__healthy |
| tomato__bacterial_spot | 21 | 0.381 | 0.5333 | 0.4444 | 0.9851 | 0.8435 | tomato__septoria_leaf_spot |
| corn__gray_leaf_spot | 18 | 0.3889 | 0.4375 | 0.4118 | 0.9403 | 0.8998 | corn__northern_leaf_blight |
| tomato__mosaic_virus | 19 | 0.4737 | 0.9 | 0.6207 | 0.8259 | 0.8415 | tomato__healthy |
| cherry__healthy | 10 | 0.5 | 1.0 | 0.6667 | 0.9166 | 0.6612 | apple__healthy |
| apple__black_rot | 6 | 0.5 | 0.6 | 0.5455 | 0.9994 | 0.6138 | apple__scab |
| potato__early_blight | 22 | 0.5909 | 0.7222 | 0.65 | 0.9877 | 0.9192 | potato__late_blight |
| cherry__powdery_mildew | 5 | 0.6 | 1.0 | 0.75 | 1.0 | 0.9672 | tomato__early_blight |
| tomato__early_blight | 28 | 0.6071 | 0.5667 | 0.5862 | 0.9688 | 0.83 | tomato__bacterial_spot |
| tomato__late_blight | 27 | 0.6296 | 0.8947 | 0.7391 | 0.9358 | 0.8392 | potato__late_blight |
| corn__northern_leaf_blight | 27 | 0.7037 | 0.6129 | 0.6552 | 0.9977 | 0.9166 | corn__gray_leaf_spot |
| tomato__septoria_leaf_spot | 29 | 0.7241 | 0.6176 | 0.6667 | 0.9233 | 0.8754 | tomato__early_blight |
| apple__scab | 34 | 0.7353 | 0.7353 | 0.7353 | 0.9554 | 0.8699 | pepper__bacterial_spot |
| pepper__healthy | 8 | 0.75 | 0.6 | 0.6667 | 0.9451 | 0.804 | apple__healthy |
| tomato__leaf_mold | 29 | 0.7931 | 0.8519 | 0.8214 | 0.9838 | 0.7162 | pepper__bacterial_spot |
| apple__rust | 26 | 0.8077 | 0.84 | 0.8235 | 0.9557 | 0.8471 | apple__scab |
| pepper__bacterial_spot | 16 | 0.8125 | 0.619 | 0.7027 | 0.9417 | 0.8137 | citrus__canker |
| strawberry__leaf_scorch | 6 | 0.8333 | 1.0 | 0.9091 | 0.9974 | 0.9866 | strawberry__healthy |
| orange__citrus_greening | 15 | 0.8667 | 0.8667 | 0.8667 | 0.9995 | 0.7519 | tomato__early_blight |
| apple__healthy | 9 | 0.8889 | 0.6154 | 0.7273 | 0.9335 | 0.9519 | citrus__canker |
| peach__healthy | 9 | 0.8889 | 1.0 | 0.9412 | 0.96 | 0.4748 | apple__scab |
| grape__black_rot | 19 | 0.8947 | 0.9444 | 0.9189 | 0.9469 | 0.5868 | grape__healthy |
| tomato__yellow_leaf_curl_virus | 20 | 0.9 | 0.6923 | 0.7826 | 0.9918 | 0.4788 | tomato__mosaic_virus |
| corn__common_rust | 37 | 0.9189 | 1.0 | 0.9577 | 0.9689 | 0.9045 | wheat__leaf_rust |
| potato__late_blight | 74 | 0.9459 | 0.8861 | 0.915 | 0.9856 | 0.8242 | potato__early_blight |
| wheat__leaf_rust | 19 | 0.9474 | 0.9 | 0.9231 | 0.9749 | 0.3007 | corn__northern_leaf_blight |
| squash__powdery_mildew | 66 | 0.9697 | 0.9846 | 0.9771 | 0.9863 | 0.6718 | tomato__yellow_leaf_curl_virus |
| citrus__canker | 46 | 0.9783 | 0.8333 | 0.9 | 0.9846 | 0.7055 | wheat__leaf_rust |
| potato__healthy | 30 | 1.0 | 1.0 | 1.0 | 0.9996 |  |  |
| grape__healthy | 12 | 1.0 | 0.9231 | 0.96 | 0.994 |  |  |
| strawberry__healthy | 8 | 1.0 | 0.8889 | 0.9412 | 0.9827 |  |  |
