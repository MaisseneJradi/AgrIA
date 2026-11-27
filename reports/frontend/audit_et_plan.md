# Frontend React d'AgrIA : audit de l'application actuelle et plan

27/11/2026. Avant tout code (phase « avant l'étape 1 » du brief).

**Lu :**
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) ;
- [src/api/main.py](../../src/api/main.py) ;
- l'application actuelle [src/app/](../../src/app/) : `index.html`, `app.js` (384 lignes), `style.css`, `manifest.webmanifest` ;
- le schéma OpenAPI ;
- des réponses réelles de `/identify` et `/diagnose`.

**Captures d'écran :** 32 dans [reports/frontend/avant/](avant/).
- 8 écrans × téléphone 360×800 et ordinateur 1280×800 × FR et AR.
- Les 8 écrans : accueil, erreur sans photo, précisions ouvertes, culture détectée, chargement, résultat avec produits, détails ouverts, diagnostic non fiable.
- Prises avec Chrome sur le serveur réel (VLM actif), avec une photo de tomate (produits) et une photo d'olivier (non fiable).
- Les entrées de journal créées par ces essais ont été supprimées ensuite.

---

## 1. Audit

### Ce qui marche
- **Écran :** une seule page, utilisable sur téléphone et sur ordinateur.
- **Langue :** bascule FR / AR, avec `dir="rtl"` et `lang` réglés sur `<html>` ; le choix est gardé (localStorage).
- **Culture :** la photo déclenche `/identify` et préremplit la culture seulement si le modèle est sûr. Les 3 propositions sont des boutons d'un seul toucher. Le texte dit si la culture vient du VLM, ou si le VLM n'est pas d'accord.
- **Précisions sur la parcelle :** les champs demandés par l'API (`questions_contexte`) sont colorés.
- **Diagnostic non fiable :** aucun produit n'est affiché, seulement les questions. C'est conforme à la règle 3 du brief.
- **Mode test :** retour « correct ou non », réponse vraie, accord pour garder la photo.
- **Confidentialité :** aucune police externe, aucun traqueur ; la photo est supprimée côté serveur.
- **Taille :** pas de framework, environ 25 Ko au total.

### Ce qui est confus pour un agriculteur
1. **La réponse est un seul bloc de texte**, sur 4 700 px de haut sur téléphone (`phone_fr_6`). Produits, dose pratique, LMR, boutique, raison du choix, sécurité et météo se suivent sans titre ni carte. Le tableau « Produits homologués » répète une partie du texte, ailleurs.
2. **Les probabilités brutes sont partout** : « confiance 98 % », « Tomate 96 % », « Palmier dattier 0 % », « Gale bactérienne (38 %) ».
3. **« Ce que le modèle a vu » affiche des codes techniques** : `tomato__early_blight : 98 %`, `leaf → maladies`.
4. **Les questions de précision sont mal placées.** Le texte de la réponse les pose, mais les champs à remplir sont dans le formulaire, *au-dessus* : il faut remonter, remplir, puis relancer.
5. **Tout est sur un seul écran** : photo, message, gouvernorat, culture, 7 précisions et bouton. Il n'y a pas d'étapes : on ne voit pas ce qui est obligatoire.
6. **Le chargement n'est qu'une roue**, sans étape ni bouton pour réessayer.
7. **Les menus déroulants natifs sont petits au soleil**, et la recherche dans la liste des cultures est impossible.

### Bugs trouvés
| # | Bug | Où |
|---|---|---|
| B1 | **Accord pour garder la photo impossible quand le diagnostic est correct** : « Oui » envoie l'avis tout de suite (`garder_photo=non`), puis affiche la case d'accord, sans moyen de la renvoyer. | `app.js` l. 371-379 |
| B2 | En arabe, la case « Maladie détectée » reste en français, avec le % (« Gale bactérienne (Xanthomonas) (38 %) »). Pour un diagnostic **non fiable**, elle montre quand même un nom de maladie comme s'il était détecté. | `phone_ar_8`, `render()` l. 238 |
| B3 | Diagnostic d'olivier non fiable : « الزراعة : طماطم » (tomate) s'affiche alors que la photo et le VLM disent olivier à 95 %. L'application affiche `culture.code` sans dire qu'il n'est pas confirmé. | `phone_ar_8`, l. 236 |
| B4 | Changer de langue après un résultat ne traduit pas la réponse (le texte reste dans la langue de la requête) : la page mélange les deux langues. | `setLang()` |
| B5 | La photo est envoyée en taille réelle (jusqu'à 10 Mo, 2 fois : `/identify` puis `/diagnose`). C'est très lent en 3G, sans compression ni correction de l'orientation EXIF. | `identify()`, `submit` |
| B6 | Pas de service worker : le manifeste existe, mais l'application ne s'installe pas comme une vraie PWA et ne s'ouvre pas hors ligne. | `manifest.webmanifest` |
| B7 | Ordinateur : le champ « Gouvernorat » est mal aligné quand les propositions de culture s'affichent (grille à 2 colonnes). | `desktop_fr_7` |
| B8 | En arabe, les nombres et unités s'affichent dans le mauvais sens (« % 95 », « % 38 ») et la trace des agents reste en français. | `phone_ar_4`, `phone_ar_8` |

L'en-tête qui se superpose au milieu des captures pleine page vient de l'en-tête fixe (`sticky`) pendant la capture. Ce n'est pas un bug visible par l'utilisateur.

---

## 2. Ce que le React ne peut pas faire sans une évolution de l'API (proposée, rien n'est fait)

La règle 1 du brief (« le frontend ne décide rien, il affiche ce que l'API renvoie ») bloque trois écrans du brief dans l'état actuel de l'API :

| # | Besoin du brief | Situation actuelle | Proposition |
|---|---|---|---|
| A1 | Types générés par `openapi-typescript` | **Aucune route n'a de schéma de réponse** (`"schema": {}` partout) : les types générés seraient vides. | Ajouter des modèles Pydantic `response_model` à chaque route. **Le JSON ne change pas.** |
| A2 | **Cartes de traitement** : dose officielle, dose pratique, DAR, raison du choix, sécurité, abeilles, lien boutique | `produits[]` ne contient que `nom`, `dose`, `dar_jours`. Tout le reste n'existe **que dans `texte`**. Le découper côté navigateur serait fragile, et ce serait au frontend de décider. | Ajouter `cartes` à la réponse, construit par `redaction.py` **avec les mêmes phrases** que `texte`. Un test vérifierait que chaque phrase de `cartes` figure mot pour mot dans `texte` : ce que le Vérificateur contrôle reste exactement ce qui est affiché. |
| A3 | Confiance « en mots » (sûr / probable / pas sûr) | Seulement `confiance` (nombre) et `fiable`. Choisir les seuils côté navigateur, ce serait « changer un seuil ». | Ajouter `diagnostic.niveau` : `sur`, `probable` ou `incertain`, calculé par l'agent Diagnostic avec ses seuils actuels. |
| A4 | Contact du CRDA du gouvernorat | Aucune donnée de contact dans le projet | Il faut une source officielle (liste des CRDA) : à me fournir, ou ce point est abandonné. |
| A5 | Photo de référence de la maladie | Aucune | Laisser de côté, ou ajouter une photo sous licence par fiche (données à télécharger, avec votre accord). |
| A6 | Retour de test : correct / partiellement / faux, vraie culture, vrai problème, commentaire | `/feedback` n'accepte que `correct` = oui ou non et un texte libre | Champs **facultatifs** ajoutés : `verdict` (correct, partiel, faux), `vraie_culture`, `vrai_probleme`, `commentaire`. L'ancienne application continue de fonctionner. |
| A7 | Page d'administration `/admin/test` | Aucune route ; `journal_report.py` est un script | `GET /admin/journal` (filtres, précision par culture) et `GET /admin/journal.csv`, protégées par le jeton `AGRIA_ADMIN_TOKEN` vérifié par le serveur. |
| A8 | Propositions de `/identify` en arabe | `top3[]` n'a que `fr` | Ajouter `ar`. En attendant, le frontend peut prendre les noms dans `/cultures`, ce qui n'est qu'un affichage. |

Je propose de faire **A1 à l'étape 1**, et A2, A3 et A6 aux étapes où elles servent, avec votre accord à chaque fois. A1 ne touche ni aux agents, ni au Vérificateur, ni au contenu des réponses.

---

## 3. Plan technique

### Dossiers
```
frontend/
  package.json, vite.config.ts, tsconfig.json (strict), tailwind.config.ts, postcss.config.js,
  eslint.config.js, .prettierrc, playwright.config.ts, README.md
  public/                 icônes PWA, favicon
  src/
    api/                  schema.d.ts (généré), client.ts (fetch + gestion d'erreurs), hooks TanStack Query
    app/                  routeur, fournisseurs (Query, i18n, thème), mise en page
    components/ui/        Button, Chip, Card, Alert, Stepper, BottomSheet, Toast, Skeleton,
                          LanguageSwitch, ConfidenceBadge (+ *.test.tsx)
    features/diagnosis/   étapes Photo, Culture, Contexte, Réponse, store (Zustand)
    features/history/     historique local (IndexedDB) – chargement différé
    features/test-mode/   bandeau, formulaire d'avis
    pages/                Styleguide (dev), About, Admin (chargement différé)
    lib/                  image (redimensionnement, EXIF), parole, formats
    locales/              fr.json, ar.json
    styles/               tokens.css (variables clair / sombre), polices
  tests/e2e/              Playwright + axe
```

### Bibliothèques (dernières versions de ces familles, figées dans `package-lock.json`)
| Rôle | Paquet | Version |
|---|---|---|
| Build | vite, @vitejs/plugin-react | 6.x, 4.x |
| UI | react, react-dom | **18.3** (comme demandé) |
| Langage | typescript | 5.7, `strict` |
| Style | tailwindcss, postcss, autoprefixer | **3.4** (configuration par `tailwind.config` et jetons, comme demandé) |
| Pages | react-router-dom | 6.28 |
| Appels API | @tanstack/react-query | 5.x |
| État du parcours | zustand (+ persist dans sessionStorage) | 5.x, environ 1 Ko |
| Langues | i18next, react-i18next | 24.x, 15.x |
| Primitives | @radix-ui/react-dialog (BottomSheet) ; liste de cultures faite maison | 1.1 |
| Icônes | lucide-react (seulement les icônes importées) | 0.46x |
| Polices auto-hébergées | @fontsource-variable/fraunces, @fontsource-variable/dm-sans, @fontsource/noto-naskh-arabic | 5.x |
| Types API | openapi-typescript | 7.x |
| PWA | vite-plugin-pwa (Workbox) | 0.21 |
| Historique | idb-keyval | 6.x, environ 1 Ko |
| Tests | vitest, @testing-library/react, @testing-library/user-event, jsdom, msw | 2.x, 16.x, 14.x, 25.x, 2.x |
| Bout en bout | @playwright/test, @axe-core/playwright | 1.49, 4.10 |
| Qualité | eslint 9, typescript-eslint 8, eslint-plugin-react-hooks, eslint-plugin-i18next (textes bruts dans le JSX), prettier 3 | |
| Mesures | rollup-plugin-visualizer, lighthouse | 5.x, 12.x |

**Image :** redimensionnement à 1 280 px et JPEG 0,8 avec `createImageBitmap(file, {imageOrientation: "from-image"})` et un canvas (orientation EXIF corrigée), sans bibliothèque.

**Navigateur pour les tests :** Playwright et Lighthouse utilisent **Chrome déjà installé** (`channel: "chrome"`), donc rien à télécharger.

**Taille :** environ 300 Mo de `node_modules`, ignorés par Git.

### Comment FastAPI servira le build
- **Développement :** `npm run dev` (Vite sur le port 5173) avec un *proxy* vers `http://127.0.0.1:8000` pour `/identify`, `/diagnose`, `/feedback`, `/cultures`, `/gouvernorats`, `/health`, `/openapi.json` et `/admin`. Même origine pour le navigateur, donc pas de CORS.
- **Production :** `npm run build` crée `frontend/dist`. Dans `src/api/main.py` (servir des fichiers seulement, aucune route de l'API ne change) :
  - si `frontend/dist` existe et que `AGRIA_UI` ne vaut pas `ancien`, FastAPI sert `dist` sur `/` avec un **retour vers `index.html`** pour les routes de l'application (`/historique`, `/a-propos`, `/admin/test`…), après les routes de l'API ;
  - l'ancienne application reste disponible sur **`/ancien/`** (règle 6) jusqu'à votre accord après l'étape 7 ;
  - en-têtes de cache : `assets/*` gardés un an (noms avec empreinte), `index.html` et `sw.js` jamais mis en cache.
- **Les deux modes** seront décrits dans `frontend/README.md`.

### Ordre de travail
Les étapes 1 à 7 du brief, une par branche `feat/react-<n>` que vous créez. À chaque étape : rapport, captures, tests et taille du bundle, puis j'attends votre accord. Les tests du backend restent tous verts, et je ne fais ni commit ni push.

---

## 4. Ce que j'attends de vous
1. **Accord sur ce plan**, et création de la branche : `git checkout -b feat/react-1`.
2. **Accord ou refus pour A1** (schémas de réponse Pydantic, JSON inchangé) dès l'étape 1.
3. **Avis de principe sur A2, A3 et A6.** Sans A2, l'étape 3 ne pourra afficher que le `texte` en sections, sans vraies cartes par produit.
4. **A4 (contacts des CRDA) et A5 (photos de référence)** : avez-vous une source, ou on les laisse de côté ?
5. **Téléchargement des paquets npm** listés ci-dessus (environ 300 Mo dans `frontend/node_modules`) : d'accord ?
