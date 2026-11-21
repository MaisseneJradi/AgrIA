# Data sources

| Dataset | Type | Format | Source | Owner |
|---|---|---|---|---|
| PlantVillage | Unstructured | Images | Kaggle | |
| PlantDoc | Unstructured | Images | GitHub pratikkayal/PlantDoc-Dataset | |
| Nutrient deficiency | Unstructured | Images | Kaggle | |
| Weather | Semi-structured | JSON to CSV | Open-Meteo API | |
| Soil | Semi-structured | JSON | SoilGrids API | |
| Tunisian approved pesticides | Structured | PDF to CSV | Ministry of Agriculture | |
| EU residue limits (MRL) | Structured | CSV | EU Pesticides Database | |
| Agronomic guides | Unstructured | PDF | INRAT / FAO | |

## Field photo sources added on 20/11/2026

Only the 14 project crops were extracted, and only photos the router sees as a leaf were kept
(`src/preparation/prepare_field_sources.py`, report in `docs/field_sources_routing.csv`). They were added with
`add_source.py`, split `auto_field`: 85 % train and 15 % test_field. Duplicates were removed with `clean_duplicates.py`.

| Dataset | Use | Photos added | Source | Licence |
|---|---|---|---|---|
| PlantWild v2 (Wei et al., 2024) | 24 classes mapped to the disease classes; other diseases of the project crops for the crop model only | 2,936 diseases + 2,230 crop | huggingface.co/datasets/uqtwei2/PlantWild | CC BY-NC-ND 4.0 |
| Potato Leaf Disease Dataset in Uncontrolled Environment (Shabrina et al., 2024) | healthy and *Phytophthora* (late blight) for the disease classes; the other groups for the crop model only | 547 diseases + 2,506 crop | Mendeley 10.17632/ptz377bwb8.1 | CC BY 4.0 |
| GVLiD, grapevine leaves (Gayakwad et al.) | crop model only: unreliable disease labels (same photos labelled esca and leaf blight) and 38 % near-duplicate video frames | 3,461 crop (2,268 after duplicate removal) | Mendeley 10.17632/wkymf8bhcg.5 | CC BY 4.0 |
| PlantSeg (Wei et al., 2024) | not added: every photo is already in PlantWild; the masks are kept in `data/raw/plantseg/masks` | 0 | Zenodo 10.5281/zenodo.17719108 | CC BY-NC 4.0 |

Not used:
- the Mendeley "Tomato Leaf and Fruit Disease" set, whose leaves are photographed on white paper, so they are not field photos;
- the Bangladesh chili set (user decision).
