# Plan d'implémentation

## Issue et SPEC

[#34 — Agent definition in the yaml file et rate limit](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/34)

[SPEC approuvée](./SPEC.md)

## Objectif

Ajouter au manifeste Python `agent.yaml` les réglages des routes d'invocation,
de l'authentification JWT/API key et de la limitation de débit FastAPI. Valider
et livrer d'abord cette interface dans `ai-enterprise-agent-runtime`, puis
migrer les deux services HTTP Mail et Wiki de `ai_agents` vers le contrat livré.

Le PLAN ne change pas la portée Python-only approuvée par la SPEC et ne modifie
aucun runtime .NET ou Java.

## Dépôts, dépendances et branches

| Ordre | Dépôt | Rôle | Branche proposée |
|---|---|---|---|
| 1 | `/data/repos/ai-enterprise-agent-runtime` | Contrat, chargement, hôte FastAPI, limiteur, documentation et samples | `feature/34-agent-yaml-http-settings` |
| 2 | `/data/repos/ai_agents` | Migration des manifestes et des compositions HTTP Mail/Wiki | `feature/34-agent-yaml-http-settings` |

Les working trees observés sont sur `main`; celui du runtime contient la SPEC
et son index, et celui de `ai_agents` est propre. Après approbation du PLAN,
créer les branches séparément à partir de `main` synchronisée avec
`origin/main`, en conservant la SPEC sur la branche du runtime. Ne pas écraser
les changements préexistants.

La Pull Request runtime est la dépendance de la Pull Request `ai_agents` et doit
être intégrée en premier. Le workflow CI de `ai_agents` installe actuellement le
runtime tagué `V0.8.1`; il devra viser la version/tag qui contient les nouveaux
champs avant que la PR consommateur soit fusionnable. Ne pas faire le merge ni
publier de version/tag dans le cadre de ce PLAN.

## Choix de la bibliothèque de limitation

- Retenir SlowAPI derrière l'extra `http` du paquet `agents`, avec une contrainte
  de version supérieure ou égale à `0.1.10` et inférieure à `0.2`, à confirmer
  dans le lock/les métadonnées PyPI au moment de l'implémentation. PyPI publie
  `0.1.10` depuis juin 2026; son dépôt documente l'usage Starlette/FastAPI,
  les routes synchrones et asynchrones et les stockages mémoire et Redis.
- Intégrer le contrôle au niveau des fonctions de route déjà enregistrées
  directement sur `FastAPI` dans `fastapi_endpoints.py`, avec leur paramètre
  `Request` existant. Ne pas adopter le middleware SlowAPI et ses
  `default_limits` pour ce premier changement.
- Ce choix tient compte du problème ouvert SlowAPI #281 : le calcul des limites
  par défaut ne fonctionne plus avec des routes incluses par `APIRouter` sous
  FastAPI `0.137+`. Le runtime enregistre aujourd'hui ses routes directement
  avec `app.post`, et le plan ajoute des tests d'intégration sur ce chemin et
  sur les versions FastAPI prises en charge. Si l'intégration route-par-route
  échoue ou impose une borne FastAPI qui n'est pas acceptable, arrêter avant
  l'implémentation de la fonctionnalité, comparer à nouveau les bibliothèques
  et soumettre une SPEC/PLAN révisée.
- Conserver le stockage mémoire par défaut; accepter un URI de stockage explicite
  (par exemple Redis) résolu au démarrage uniquement si une référence
  `${VARIABLE_NAME}` est utilisée. Documenter que seul un backend partagé
  coordonne les workers ou instances.

Références primaires : [SlowAPI sur PyPI](https://pypi.org/project/slowapi/),
[dépôt SlowAPI](https://github.com/laurents/slowapi), [limitation des routes
incluses avec FastAPI 0.137+](https://github.com/laurents/slowapi/issues/281).

## Constitution Check

- **Parité :** PASS avec l'exception Python explicitement approuvée dans la SPEC.
  Les manifestes et la limitation FastAPI sont des surfaces Python; la livraison
  ne revendique pas de parité .NET/Java.
- **Réutilisation :** PASS. Étendre `AgentManifestInput`, `AgentManifest`, le
  schéma et `AgentManifestLoader`; réutiliser `AuthenticationPolicy`, les
  authentificateurs/résolveurs de clés, `HostingFactory`, `WorkerSettings` et
  l'enregistrement de routes existants. Vérifier ces points avant d'ajouter un
  nouvel adaptateur.
- **Sécurité et typage :** PASS si les valeurs de secrets restent des références
  typées jusqu'à la composition HTTP, sont converties en champs protégés au
  dernier moment, et ne sont jamais incluses dans erreurs/logs. La validation
  des configurations JWT/API key doit échouer avant toute route partielle.
- **Tests :** PASS après un cycle red-green-refactor. Ajouter d'abord les tests
  de contrat et d'intégration qui échouent pour le manifeste, les routes,
  l'authentification et la limite 429. Étendre les tests d'intégration des deux
  agents. Pas de changements des contrats partagés dotnet/java.
- **UX et observabilité :** PASS si les erreurs nomment le chemin YAML sans
  recopier les secrets, si les réponses 401/403 existantes restent stables et
  si le dépassement de quota utilise 429 sans lancer le handler.
- **Performance :** mesurer le chemin mémoire selon le budget SPEC de 5 ms p95
  maximum hors agent; mesurer et rapporter séparément le backend partagé.
- **Dépendances facultatives :** SlowAPI n'est installé/importé qu'avec l'extra
  `http`. Les manifestes sans section HTTP et les usages CLI/MCP ne doivent pas
  résoudre les références de secrets HTTP ni charger SlowAPI.
- **Exemples :** mettre à jour les deux samples ayant un `agent.yaml` dans
  `python-langchain-fastapi/06-mcp-configuration` et
  `python-agentframework-fastapi/06-mcp-configuration`, plus les guides ciblés.

## Étapes

### Étape 1 — Ajouter le contrat de manifeste et la conversion HTTP dans le runtime

- **Dépôt :** `ai-enterprise-agent-runtime`.
- **Composants :**
  - `packages/python/agents/ygo74/agent_runtime/domains/configuration/manifest_inputs.py`,
    `manifests.py`, `schemas/agent.schema.json` et
    `domains/contracts/manifests.py`;
  - `domains/endpoints/hosting_factory.py`,
    `domains/endpoints/managed_worker.py` et les intégrations
    `packages/python/langchain/.../worker.py` et
    `packages/python/agentframework/.../worker.py`;
  - la configuration d'authentification et de clés du paquet Python `security`
    seulement si un adaptateur existant ne peut représenter une option requise.
- **Changement :** ajouter des types imbriqués stricts pour surfaces, sécurité,
  JWT, API key, identité API key et limitation. Générer/actualiser le schéma
  Draft 2020-12 depuis la source typée. Garder les références `${...}` inertes
  dans un manifeste chargé; ne les résoudre qu'à la construction d'un hôte HTTP.
  À cette frontière, construire la politique d'authentification existante et
  vérifier toutes les références requises avant de créer les routes.
- **Changement :** fournir la configuration sélectionnée aux hôtes natifs et à
  `HostingFactory` sans maintenir une seconde liste de surfaces ni dupliquer la
  validation de sécurité. Garder les réglages de découverte et de cycle de vie
  non concernés.
- **Validation :** tests red d'abord pour les valeurs manquantes, inconnues,
  incompatibles, les manifestes sans section HTTP, la conservation de secrets
  sans résolution par CLI/MCP et l'échec fermé à la composition HTTP; les rendre
  verts ensuite. Vérifier le schéma généré et ses annotations
  `yaml-language-server`.

### Étape 2 — Intégrer SlowAPI aux routes FastAPI activées

- **Dépôt :** `ai-enterprise-agent-runtime`.
- **Composants :**
  - `packages/python/agents/pyproject.toml` (extra `http`),
    `domains/endpoints/fastapi_endpoints.py` et/ou un adaptateur dédié sous
    `domains/endpoints/`;
  - nouveaux tests sous `tests/integration/python/` et
    `tests/performance/python/`.
- **Changement :** appliquer le décorateur SlowAPI aux seules fonctions route
  activées; configurer les limites, stockage et gestionnaire 429 selon le
  manifeste. Conserver l'ordre qui fait que la requête est bloquée avant
  l'authentification/handler métier selon le modèle de comptage IP approuvé.
  Fermer les ressources du backend à l'arrêt ASGI s'il en possède.
- **Validation :** couvrir sous FastAPI `0.115` (plancher actuel) et `0.137+`
  l'enregistrement direct des trois routes, le seuil et le retour 429,
  l'absence de handler après dépassement, les surfaces désactivées et le
  démarrage/arrêt. Mesurer le surcoût mémoire selon le budget. Vérifier un
  stockage partagé avec un service local déterministe si disponible.

### Étape 3 — Documenter et vérifier le paquet runtime

- **Dépôt :** `ai-enterprise-agent-runtime`.
- **Composants :**
  - les deux fichiers `config/agents/.../agent.yaml` et README des samples
    `samples/python/python-langchain-fastapi/06-mcp-configuration/` et
    `samples/python/python-agentframework-fastapi/06-mcp-configuration/`;
  - `doc/python/agent-runtime.md`, `doc/python/security.md`,
    `doc/python/installation.md`, `doc/python/README.md` et le schéma éditorial
    concerné;
  - métadonnées de paquet affectées par l'extra et le versionnement.
- **Changement :** montrer un exemple API key et un exemple JWT, les trois
  surfaces, le backend mémoire et un URI Redis par référence d'environnement,
  les réponses 401/404/429 et les limites derrière proxy. Documenter que les
  quotas par adresse IP peuvent regrouper des utilisateurs derrière un proxy et
  que le stockage mémoire ne coordonne pas plusieurs processus.
- **Validation :** suite Python complète, Ruff, construction et contrôle Twine
  des distributions, installation indépendante du wheel `agents[http]`, et
  vérification que le package `agents` sans extra HTTP n'importe pas SlowAPI.
  Exécuter les tests ciblés FastAPI et le test de performance avant la suite
  complète. Ne pas lancer dotnet/java, hors portée.

### Étape 4 — Livrer le runtime avant le dépôt consommateur

- **Dépôt :** `ai-enterprise-agent-runtime`.
- **Changement :** mettre à jour le numéro de version du package si la convention
  de livraison du dépôt le requiert, examiner le diff et ouvrir une Pull Request
  liée à #34. Inclure les résultats de validation réels et la limitation de
  compatibilité SlowAPI/FastAPI dans la description.
- **Critère de passage :** la Pull Request runtime est intégrée et une version
  ou un tag utilisable par le workflow `ai_agents` contient le contrat validé.
  La suite `ai_agents` ne doit pas être migrée sur une API runtime absente de son
  installation CI `V0.8.1`.

### Étape 5 — Migrer Mail et Wiki après disponibilité du runtime

- **Dépôt :** `ai_agents`, sur sa branche dédiée après le critère de passage de
  l'étape 4.
- **Composants :**
  - `config/agents/mail/agent.yaml` et `config/agents/wiki/agent.yaml`;
  - `agents/mail/bootstrap/service.py`,
    `agents/wiki/bootstrap/service.py`, leurs réglages HTTP spécifiques et les
    tests de contrats/intégration des services;
  - `.env.example`, `docs/mail-agent-http.md`, `docs/wiki-agent-http.md`,
    `docs/configuration.md` et les instructions de lancement affectées;
  - `agents/{mail,wiki}/pyproject.toml` et `.github/workflows/quality.yml` pour
    la borne et le tag runtime disponible.
- **Changement :** remplacer le choix d'authentification et les surfaces codées
  en dur par la configuration du manifeste. Déclarer JWT ou API key et le
  principal statique API key dans chaque manifeste; Mail conserve Chat
  Completions + Responses et son email requis, Wiki conserve Chat Completions
  sans inventer d'email. Garder `max_conversations`, `idle_lifetime`, la
  construction OIDC/fermeture du client, les contrôles métier et les surfaces
  de découverte actuelles. Actualiser les références de secrets et l'aide
  opérateur sans ajouter de secret réel.
- **Validation :** tester les deux vraies fonctions `build_app`, les modes JWT
  et API key, la conservation de l'identité/conversation, les routes actuelles,
  les refus 401/404 et le chargement CLI/MCP sans secrets HTTP. Installer le
  runtime depuis la version livrée; exécuter toute la suite, Ruff et mypy
  stricts documentés par `ai_agents`.

### Étape 6 — Revue finale et Pull Request dépendante

- **Dépôt :** `ai_agents`.
- **Changement :** contrôler le diff et les références aux nouvelles options,
  mettre à jour les numéros de version/planchers nécessaires, puis ouvrir une
  Pull Request qui référence #34 et la PR runtime intégrée. Indiquer clairement
  que la PR runtime devait être intégrée en premier.
- **Validation :** `git diff --check`; vérifier qu'aucun `.env` réel ou secret
  n'est inclus. Rapporter séparément les commandes exécutées dans les deux
  dépôts et leurs statuts.

## Validations et critères de fin

- **Runtime :**
  - `python -m ruff check packages/python tests`;
  - tests contractuels et d'intégration ciblés, puis
    `python -m pytest tests/ samples/python/python-agentframework-fastapi/test_agentframework_fastapi_example.py`;
  - tests ciblés de performance pour la limite mémoire;
  - `python -m build` pour les six distributions Python, `twine check` et les
    installations wheel isolées du workflow `.github/workflows/ci.yml`;
  - `git diff --check` et revue de toutes les modifications/versionnements.
- **`ai_agents` :**
  - `python -m scripts.install --env dev` avec la version runtime intégrée;
  - `python -m ruff check .`, `python -m mypy`, puis `python -m pytest`;
  - `git diff --check`, revue des fichiers et détection des secrets.
- **Fin :** fonctionnalité runtime intégrée et disponible; les deux agents
  migrés vers cette version; CI et validations de chaque dépôt rapportées sans
  confondre leurs branches, commits ou PR.

## Risques et décisions de suivi

- **Compatibilité SlowAPI/FastAPI :** le problème #281 vise les routeurs inclus,
  tandis que ce runtime utilise `app.post` directement. La validation sur
  versions plancher et récentes est bloquante; une incompatibilité impose de
  réouvrir le choix de dépendance avant que le changement prenne de l'ampleur.
- **Rate limit par IP :** les utilisateurs derrière une même adresse publique
  partagent le quota. Ne pas accepter un identifiant tiré de JWT non validé ni
  un `X-Forwarded-For` brut pour le répartir.
- **Backend mémoire :** état local au processus et perdu au redémarrage; Redis
  est requis pour un compteur commun multi-processus/instances.
- **Dépendance entre PR :** la PR `ai_agents` suit l'intégration et la
  disponibilité du runtime; aucune PR consommateur ne doit prétendre que son
  API cible `V0.8.1`.
- **Périmètre :** toute demande d'exposer un nouvel endpoint sur Mail ou Wiki,
  d'ajouter des comptes API key dynamiques ou de modifier les runtimes .NET/Java
  requiert une mise à jour de SPEC et son approbation avant implémentation.
