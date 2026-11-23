# Outils de l'agent (étape 3)

Les outils donnent à l'agent des faits vérifiables : produits homologués, engrais, besoins en eau, passages des fiches, termes reconnus. Ils contrôlent aussi la réponse finale. **Aucun LLM n'est utilisé ici** : ce ne sont que des règles et des tables, testées une par une.

```python
from src.tools import get_treatments, get_fertilizers, get_water_need, search_knowledge, normalize_terms, check_answer
```

## 1. Base de données

`python src/tools/build_db.py` charge les tables propres dans `data/processed/agria.db` : SQLite, 20 tables, 4,6 Mo, construite en 10 s, hors Git. Si la base n'existe pas, elle est reconstruite automatiquement au premier appel d'un outil. Les fichiers CSV ne sont jamais modifiés.

| Table | Source |
|---|---|
| `traitements` | lignes `validated` de `docs/disease_target_mapping.csv` appliquées à `pesticides/tn_usages.csv` (identique à l'ancienne `clean/classe_traitements.csv`, plan phyto étape 2), complétée par le délai avant récolte (texte) et les restrictions de `pesticides/tn_usages.csv` et de la liste des produits |
| `usage_lmr` | LMR de l'UE de chaque substance, par usage |
| `pesticides_produits`, `pesticides_usages`, `pesticides_agrishop`, `substances` | liste tunisienne du 22/05/2024, agrishop, substances de l'UE |
| `carence_engrais`, `engrais_catalogue`, `engrais_usages`, `semences` | agriclic, agrishop |
| `besoins_eau`, `climat_mensuel`, `gouvernorats`, `sols`, `kc` | Open-Meteo 2015-2024, SoilGrids, FAO-56 |
| `lexique`, `fiches`, `varietes`, `culture_mapping`, `regles_carences` | base de connaissances |
| `meta` | date de construction et source de chaque table |

## 2. Les six outils

| Outil | Fichier | Rôle | Règles principales |
|---|---|---|---|
| `get_treatments(classe, culture=None)` | [treatments.py](../src/tools/treatments.py) | Usages homologués pour une classe du modèle | Une liste vide veut dire « aucun produit homologué ». Avec une culture, seuls les usages homologués sur cette culture, ou sur un groupe qui la contient, sont gardés. Ordre : `direct`, `vecteur`, `groupe`, `proche`. |
| `get_fertilizers(carence, culture=None, gouvernorat=None)` | [fertilizers.py](../src/tools/fertilizers.py) | Engrais correcteurs, fiabilité du diagnostic, sol | Carence jamais vue sur cette culture → `fiabilite = "hypothese"`. Règle de sol du gouvernorat (pH, sable, carbone). Fe sur sol calcaire → chélates EDDHA d'abord. Produits à traces (< 1 %) en dernier. |
| `get_water_need(gouvernorat, culture, mois, forecast=False)` | [water.py](../src/tools/water.py) | Besoin en eau FAO-56 : ET0 × Kc − pluie | Hors saison : pas de besoin calculé. Prévision Open-Meteo sur 7 jours en option, avec le Kc du mois en cours. Sans réseau, la réponse mensuelle reste donnée. |
| `search_knowledge(question, k=3, classe=None)` | [rag.py](../src/tools/rag.py) | Passages des 76 fiches, avec leur source et leur licence | Question enrichie par le lexique (darija → français). Priorité à la section demandée (lutte, symptômes, biologie). Liste vide si rien ne répond. |
| `normalize_terms(texte)` | [lexicon.py](../src/tools/lexicon.py) | Cultures, maladies, ravageurs, symptômes et organes reconnus, langue, classes possibles | Français, arabe, darija, arabizi. Pluriels et préfixes arabes acceptés. `a_valider` signale une graphie darija pas encore validée. |
| `check_answer(reponse)` | [safety.py](../src/tools/safety.py) | Contrôle final : `valide`, `raisons` (bloquantes), `avertissements` (à dire au fermier) | Les 12 règles bloquantes de la section 4 |

Les noms de culture et de gouvernorat sont acceptés sous toutes leurs formes : « tomate », « tomates », « طماطم », « tmatem », « TOMATE SOUS SERRE » ; « Gabès », « gabes », « قابس », « le kef ».

## 3. Les cas imposés par l'architecture

| Cas | Ce que font les outils | Test |
|---|---|---|
| **28 classes malades sur 48 sans produit homologué** | `get_treatments` renvoie `[]`. `check_answer` bloque tout produit cité pour ces classes, même s'il n'apparaît que dans le texte. Les conseils viennent alors des fiches (`search_knowledge`). | `test_28_classes_without_registered_product`, `test_class_without_product_and_honest_text_passes` |
| **Délai avant récolte (DAR) absent** (411 usages sur 499, 82 %) | `dar_jours = None` et le message « délai avant récolte non précisé dans la liste officielle : voir l'étiquette du produit ». Un DAR donné par la réponse alors que la liste n'en a pas est bloqué. | `test_missing_dar_is_never_estimated`, `test_blocks_wrong_or_invented_dar` |
| **Zn, B, Ca vus sur une seule culture, Fe presque seulement sur le poivron** | Sur une autre culture, `fiabilite = "hypothese"`. `check_answer` bloque si la réponse ne présente pas la carence comme une hypothèse. | `test_mono_crop_deficiency_on_another_crop_is_a_hypothesis`, `test_deficiency_on_unseen_crop_must_be_a_hypothesis` |
| **`restriction` et `autorisation_provisoire`** | Les produits réservés aux campagnes nationales ne sont jamais proposés. L'autorisation provisoire et les restrictions deviennent des avertissements à transmettre au fermier. | `test_restricted_products_are_never_proposed`, `test_provisional_authorisation_is_flagged` |
| **Confusions du modèle mesurées à l'étape 2** | Avertissement pour une carence en zinc sur poivron (48 poivrons sains sur 123 classés Zn) et pour le manganèse hors palmier (58 %). | `test_known_model_confusion_is_reported` |

## 4. Règles de `check_answer`

**Bloquantes (la réponse n'est pas envoyée) :**
1. Un pesticide non homologué pour cette classe, ou pour cette culture si elle est connue, dans la liste des produits ou cité dans le texte.
2. Une dose différente de la dose homologuée.
3. Un DAR différent de la liste, ou un DAR alors que la liste n'en donne pas.
4. Un produit ou un engrais pour une plante saine.
5. Un produit alors que le diagnostic n'est pas fiable (`reliable = False`) : il faut d'abord poser les questions de confirmation.
6. Une carence jamais vue sur cette culture, non présentée comme une hypothèse.
7. Un engrais absent du catalogue de cette carence.
8. Un produit dont la dose homologuée n'est pas écrite telle quelle sur la même ligne que le produit dans le texte.
9. Une substance ou un mot de lutte chimique (fongicide, cuivre, azoxystrobine, « traitez »…) écrit hors des lignes des produits homologués et des engrais de la réponse : un conseil ou un extrait de fiche ne porte jamais un traitement (plan phyto, étape 2).
10. Contexte connu : un produit dont le DAR est plus long que les jours qui restent avant la récolte.
11. Marché export : un produit dont une substance n'est pas approuvée (ou de statut inconnu) dans l'UE.
12. Agriculture biologique : un produit dont une substance n'est pas autorisée en bio (règles 10 à 12 : plan phyto, étape 3).

**Avertissements (à dire dans la réponse) :**
- DAR non précisé ;
- restriction ;
- autorisation provisoire ;
- produit qui vise l'insecte vecteur et non le virus ;
- cible « proche », à utiliser seulement après confirmation ;
- confusion connue du modèle.

Un mot ordinaire n'est pas pris pour un produit : « l'impact du mildiou » n'est pas le produit « Impact ». Un nom de produit d'un seul mot ne compte que s'il est écrit avec sa majuscule.

## 5. Tests

```bash
python -m unittest discover -s tests -t . -v
```

**45 tests, tous réussis, en 1,8 s.**

| Fichier | Tests | Ce qui est vérifié |
|---|---|---|
| `tests/tools/test_treatments.py` | 10 | les 62 classes, les plantes saines, les 28 classes vides, le filtre par culture, le DAR, l'ordre des relations, l'autorisation provisoire, les restrictions, les champs du contrat |
| `tests/tools/test_fertilizers.py` | 8 | les 9 carences, les plantes saines, les hypothèses hors culture vue, la règle de sol, l'EDDHA, les traces, les confusions du modèle, les erreurs |
| `tests/tools/test_water.py` | 5 | ETc = ET0 × Kc, hors saison, noms en arabe ou en arabizi, erreurs, panne de réseau (simulée) |
| `tests/tools/test_lexicon_rag.py` | 10 | les 4 écritures, darija, arabe, découpage français, gouvernorats, sources des passages, question hors sujet, filtre par classe |
| `tests/tools/test_safety.py` | 12 | les 7 règles bloquantes, les avertissements, les mots ordinaires |

## 6. Choix et limites

- **Recherche sans Chroma.** Avec 76 fiches (404 passages), un TF-IDF local, sur les mots et sur des morceaux de 3 à 5 lettres, suffit. Il est hors ligne, sans modèle à télécharger, et l'index se construit en 0,3 s. Une base vectorielle pourra le remplacer derrière la même fonction si le corpus grandit. `chromadb`, jamais utilisé, est retiré de `requirements.txt`.
- **Recherche sans classe.** Une autre fiche du même sujet peut passer devant : pour « lutter contre le mildiou de la vigne », la fiche de l'eudémis sort en premier, car la fiche du mildiou de la vigne n'a pas de section « lutte ». L'agent doit donc appeler `search_knowledge` avec la classe donnée par le modèle.
- **24 fiches sur 76 sont en anglais** (Wikipédia anglais, faute d'article français). Le champ `langue` le signale : l'agent devra traduire.
- **88 graphies darija sont encore marquées `a_valider`.** L'agent peut s'en servir pour comprendre le message, jamais pour rédiger sa réponse, tant qu'un locuteur tunisien ne les a pas relues.
- **Seulement 31 fiches sur 76 ont une section « lutte ».** Pour les autres, les conseils viennent de la description et de la biologie.
- **Les noms de produits viennent de la liste officielle telle quelle.** Certains sont peu lisibles, par exemple « BREAK ME SC SR/ Changement Nom COMMBreak thru ».
