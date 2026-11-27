# AgrIA – frontend React

L'application des agriculteurs, en React. Elle **ne décide rien** : elle affiche exactement les textes et les valeurs que renvoie l'API (`src/api/main.py`). Les doses, les produits, les seuils et les niveaux de confiance viennent tous du backend et des agents.

**Pile :**
- Vite 6, React 18, TypeScript strict ;
- Tailwind CSS 3.4 avec jetons de design ;
- react-router, TanStack Query, react-i18next (FR / AR, de droite à gauche), lucide-react, Radix Dialog ;
- polices auto-hébergées (Fontsource).

## Installer
```
cd frontend
npm install
```
Pour les tests de bout en bout, Chrome doit être installé sur l'ordinateur : Playwright l'utilise (`channel: "chrome"`), donc rien d'autre à télécharger.

## Développement
Lancez d'abord l'API, depuis la racine du dépôt :
```
$env:AGRIA_VLM="nvidia"; $env:AGRIA_JOURNAL="1"; python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
Puis Vite, avec rechargement à chaud :
```
cd frontend
npm run dev            # http://127.0.0.1:5173
```
- Vite transmet les routes de l'API (`/identify`, `/diagnose`, `/feedback`, `/cultures`, `/gouvernorats`, `/health`, `/openapi.json`) à `http://127.0.0.1:8000`. Le navigateur voit une seule adresse, donc pas de CORS.
- Pour une autre adresse d'API : `$env:AGRIA_API="http://..."`.
- `/styleguide` montre tous les composants en FR et AR, clair et sombre. Cette page n'existe qu'en développement : elle est exclue du build.

## Production : FastAPI sert le build
```
cd frontend
npm run build          # -> frontend/dist, puis affiche la taille du JS (budget : 200 Ko gzip)
cd ..
$env:AGRIA_UI="react"; python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```
Avec `AGRIA_UI=react`, FastAPI sert `frontend/dist` sur `/` :
- les fichiers `assets/*`, dont le nom contient une empreinte, sont mis en cache un an ;
- `index.html` n'est jamais mis en cache ;
- toute autre route de l'application (`/historique`, `/admin/test`…) renvoie `index.html`, et le routeur React s'en charge ;
- les routes de l'API sont déclarées avant : elles passent toujours en premier.

Sans `AGRIA_UI=react`, c'est l'ancienne application (`src/app/`) qui est servie, comme avant. Elle reste en place jusqu'à ce que l'application React passe l'étape 7.

## Types de l'API
Les types TypeScript sont générés à partir du schéma OpenAPI de FastAPI (`src/api/schemas.py`) :
```
npm run api:schema     # python -m src.api.export_openapi -> src/api/openapi.json
npm run api:types      # openapi-typescript -> src/api/schema.d.ts
```
Le test `tests/api/test_api.py` échoue si `openapi.json` n'est plus à jour, ou si une réponse réelle de l'API ne correspond plus au schéma.

## Commandes
| Commande | Rôle |
|---|---|
| `npm run lint` | ESLint (dont l'interdiction du texte brut dans le JSX : tout texte vient de `src/locales/*.json`) et Prettier |
| `npm run test` | Vitest, Testing Library, MSW (API simulée) |
| `npm run e2e` | Playwright sur le build (`vite preview`), téléphone 360×800, avec axe-core |
| `npm run build` | build de production et taille du bundle (`stats.html` : détail par module) |
| `npm run typecheck` | TypeScript seul |

## Parcours de l'agriculteur (étape 2)
| Adresse | Étape | Route de l'API |
|---|---|---|
| `/` | photo (appareil photo ou galerie) | — |
| `/culture` | culture à confirmer | `POST /identify` |
| `/precisions` | message, gouvernorat, précisions sur la parcelle | `GET /gouvernorats` |
| `/reponse` | réponse | `POST /diagnose` |

- **Bouton Retour du téléphone :** il ramène à l'étape précédente.
- **Accès direct à une étape :** une étape ouverte sans ce qu'elle demande renvoie à la première étape qui manque.
- **Photo :** elle est redressée selon l'orientation EXIF, réduite à 1 280 px sur son plus grand côté, puis enregistrée en JPEG 0,8 dans le téléphone (`src/lib/image.ts`). Une photo de 4 Mo devient environ 200 Ko.
- **Rechargement de la page :** les saisies sont gardées dans l'onglet (sessionStorage). La réponse, elle, n'est pas gardée : elle est redemandée, pour qu'une ancienne réponse ne soit jamais présentée comme nouvelle.
- **Gouvernorat :** il est gardé sur l'appareil (localStorage).
- **Réponse :** le `texte` de l'API est affiché tel quel. En arabe, les passages en caractères latins sont seulement isolés à l'affichage (`<bdi>`) ; un test vérifie que le texte affiché est identique, caractère pour caractère.

## Organisation
```
src/api/            client typé (client.ts), requêtes TanStack Query (queries.ts), schéma généré
src/app/            routeur, mise en page (en-tête, langue, thème)
src/components/ui/  Button, Chip, Card, Alert, Stepper, BottomSheet, Toast, Skeleton, LanguageSwitch,
                    ThemeSwitch, ConfidenceBadge (+ un test chacun, en LTR et RTL)
src/lib/            langues, thème
src/locales/        fr.json, ar.json
src/styles/         jetons de couleur (clair / sombre) et styles de base
tests/e2e/          Playwright
```

**Règles de mise en page :**
- seulement des propriétés logiques (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `border-s`) ; chaque test de composant vérifie qu'aucune classe gauche / droite n'est utilisée ;
- cibles tactiles d'au moins 48 px ;
- texte de base de 16 px (18 px en arabe).
