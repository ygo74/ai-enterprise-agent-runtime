# Implementation Plan

## Issue

#25 — OpenAI Responses API support

## Specification

./SPEC.md

## Objectif

Livrer dans le package Python un support étendu de `POST /v1/responses`, ses
réponses structurées et ses événements SSE documentés, tout en conservant le
comportement textuel existant. Les suivis .NET et Java commenceront après
stabilisation de Python.

## Préconditions

- La SPEC de l’issue 25 est approuvée.
- L’implémentation de cette issue reste limitée à
  `packages/python/agents`; aucune implémentation .NET ou Java n’est incluse.
- Avant de figer les fixtures, choisir et enregistrer la révision exacte du
  schéma OpenAI OpenAPI citée par l’issue et l’inventaire d’événements de la
  référence Responses correspondante.
- Les suites .NET et Java existantes servent seulement à détecter une
  régression accidentelle si les contrats partagés doivent évoluer; aucun
  changement d’implémentation dans ces langages n’est prévu.

## Constitution Check

- **Parité inter-langages :** dérogation de portée explicitement demandée et
  approuvée pour cette phase Python. .NET et Java restent des suivis après
  stabilisation; la livraison ne sera pas annoncée comme stable dans les trois
  langages avant ces suivis.
- **Réutilisation :** étendre les points existants de normalisation, mapping et
  streaming; toute nouvelle classe sera précédée d’une recherche ciblée dans
  les trois domaines concernés.
- **Tests-first :** ajouter les fixtures et tests contractuels/intégration
  avant les changements aux modèles, mappers ou encodeurs.
- **Contrats et sûreté des types :** conserver un contrat d’échange neutre,
  ajouter seulement le champ facultatif `providerOptions`, typer les enveloppes
  et l’énumération des événements et garder le JSON arbitraire à la frontière
  du protocole.
- **UX et exemples :** préserver le comportement actuel des handlers texte et
  documenter les nouvelles sorties et événements Python dans un exemple
  exécutable.
- **Performance :** conserver et mesurer les budgets p95 existants pour les
  parcours Responses.
- **État :** PASS sous réserve de la dérogation temporaire de parité ci-dessus;
  aucun autre écart à la Constitution n’est prévu.

## Étapes

### Étape 1 — Figer le contrat Responses et écrire les tests rouges

**Objectif :** Définir les requêtes, réponses et événements couverts à partir
des références OpenAI versionnées, puis codifier les cas de conformité avant
toute modification d’implémentation.

**Fichiers/composants :**

- `tests/contract/`
- `tests/integration/python/`
- `tests/parity/` uniquement si un contrat partagé existant est touché

**Modifications :**

- Ajouter une fixture versionnée pour les formes de requête et de réponse de
  `POST /v1/responses`, plus une fixture par type d’événement SSE documenté.
- Enregistrer dans les fixtures la référence ou révision OpenAI utilisée afin
  que l’ensemble attendu soit stable entre les versions du runtime.
- Ajouter des tests contractuels et d’intégration pour les entrées string,
  array et multimodales; les options de requête; les sorties structurées; les
  erreurs; et tous les événements, y compris les événements terminaux.
- Ajouter les tests de compatibilité du contrat d’échange avec et sans le
  nouveau champ facultatif `providerOptions`.
- Couvrir l’analyse des événements/réponses par les types du SDK OpenAI quand
  cette dépendance est disponible; sinon comparer les payloads aux fixtures
  versionnées.
- Écrire les tests d’abord et constater leur échec sur le comportement courant.

**Validation :**

- Les nouveaux cas échouent d’abord sur les mappers actuels textuels.
- Les fixtures couvrent l’inventaire complet de la révision retenue, sans
  modifier les contrats Chat Completions ou Anthropic.

### Étape 2 — Préserver la requête Responses dans le contrat Python

**Objectif :** Acheminer au handler tout le contenu nécessaire de la requête
Responses sans casser les champs normalisés existants.

**Fichiers/composants :**

- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py`
- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/adapters.py`
- `packages/python/agents/ygo74/agent_runtime/domains/contracts/exchange_models.py`
- `specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json`
- `spec/contracts/exchange-contract.md`
- `tests/integration/python/test_metadata_preservation.py`
- Nouveaux tests Responses de l’étape 1

**Modifications :**

- Réutiliser `_build_raw_payload`, `map_to_exchange` et `normalize_request` pour
  garder l’authentification, le routage, le model ID et le forwarding des
  headers existants.
- Préserver `StandardExchangeRequest.input` comme la valeur exacte de `input`
  fournie par le client, y compris les listes et structures multimodales.
- Ajouter au contrat Standard Exchange un champ facultatif `providerOptions`,
  une collection de valeurs JSON réservée aux options du protocole qui ne sont
  pas déjà représentées par les champs normalisés (`input`, `model`, `stream`,
  métadonnées runtime). L’ajouter à la dataclass Python et à son schéma; les
  implémentations .NET/Java ne sont pas modifiées et peuvent l’omettre.
- Ajouter une représentation typée de l’enveloppe de création Responses dans
  le domaine `endpoints`; y conserver sans transformation les options Responses
  hors `input`, `model`, `stream` et `metadata` puis les sérialiser dans
  `provider_options`.
- Garder les métadonnées runtime existantes, notamment le routage, les headers
  autorisés et le contexte d’authentification, indépendantes des options
  envoyées dans le corps OpenAI.

**Validation :**

- Les tests démontrent la conservation des champs et options autorisés par la
  fixture OpenAI dans `provider_options`, sans écrasement des métadonnées ou du
  routage runtime.
- Les contrats existants restent valides lorsque le champ optionnel
  `providerOptions` est absent.
- Les tests de normalisation existants et les intégrations d’authentification,
  découverte et forwarding restent verts.

### Étape 3 — Rendre les réponses Responses structurées

**Objectif :** Produire une Response OpenAI valide sans convertir les sorties
structurées en texte, tout en maintenant la conversion de texte simple.

**Fichiers/composants :**

- `packages/python/agents/ygo74/agent_runtime/domains/mapping/response_mapper.py`
- Nouveau mapper Responses dédié dans
  `packages/python/agents/ygo74/agent_runtime/domains/mapping/`
- `packages/python/agents/ygo74/agent_runtime/domains/contracts/`
- `tests/integration/python/test_non_stream_endpoints.py`
- Fixtures de réponse de `tests/contract/`

**Modifications :**

- Étendre la recherche de réutilisation autour de `map_response` et
  `extract_output_text`; isoler les règles Responses afin de ne pas changer les
  rendus Chat Completions ou Anthropic.
- Définir des modèles Python typés pour l’enveloppe et les variantes
  structurées de sortie. Garder les valeurs JSON imbriquées en forme native au
  point de frontière, sans les aplatir.
- Mapper une sortie textuelle existante vers une Response valide, et préserver
  les sorties structurées déjà fournies par le handler.
- Inclure les champs d’enveloppe obligatoires et les champs optionnels pris en
  charge par la révision OpenAI retenue; valider les statuts et erreurs.

**Validation :**

- Les sorties textuelles conservent leur sémantique actuelle.
- Les sorties structurées passent les fixtures de contrat et sont lisibles par
  le SDK OpenAI ou valides selon le schéma versionné.
- Les tests des autres surfaces et les tests du mapper existant restent verts.

### Étape 4 — Encoder le cycle complet des événements SSE Responses

**Objectif :** Émettre les événements Responses conformes pour les flux textuels
simples et permettre aux handlers Python de fournir les événements structurés
nécessaires aux autres formes de sortie.

**Fichiers/composants :**

- `packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py`
- `packages/python/agents/ygo74/agent_runtime/domains/streaming/openai_stream_mapper.py`
- `packages/python/agents/ygo74/agent_runtime/domains/contracts/stream_events.py`
- Nouveaux modèles/encodeurs Responses dans les domaines Python
  `contracts` / `streaming`
- Tests d’intégration streaming Python et fixtures d’événements

**Modifications :**

- Réutiliser `_stream_response` pour le cycle de vie générique et isoler un
  encodeur Responses avec une énumération typée de chaque type d’événement
  documenté dans la référence retenue.
- Conserver la compatibilité des handlers qui émettent des chaînes ou deltas
  textuels en générant les événements de cycle de vie et de texte requis.
- Ajouter un événement Responses typé pour qu’un handler puisse fournir des
  événements structurés, incluant leur type et leur payload conforme; encoder
  chaque événement dans l’ordre fourni sans en réduire le contenu.
- Représenter les terminaisons réussies et en erreur avec les événements
  Responses appropriés. Pour cette surface, fermer le flux conformément à la
  référence plutôt que d’ajouter un marqueur provenant d’un autre protocole.
- Garder la conversion des événements Chat Completions et Anthropic inchangée.

**Validation :**

- Une fixture par type d’événement est encodée correctement en SSE et analysée
  par le SDK OpenAI ou validée contre le contrat versionné.
- Les tests couvrent l’ordre, la terminaison, les erreurs, les interruptions,
  le flux textuel existant et la conservation des payloads structurés.
- Les tests streaming des autres surfaces ne changent pas.

### Étape 5 — Documenter l’intégration Python et valider les budgets

**Objectif :** Montrer l’usage du payload complet, d’une réponse structurée et
des événements de streaming Responses, puis confirmer la compatibilité et les
budgets Python.

**Fichiers/composants :**

- `docs/python/agent-runtime.md`
- Exemple Python ciblé sous `docs/examples/python-langchain-fastapi/` ou
  `docs/examples/python-fastapi-quickstart/`
- `tests/performance/python/`
- `tests/performance/baselines/performance_thresholds.json` seulement si une
  mesure Responses spécifique est ajoutée
- `docs/tasks/issue-25/PLAN.md`

**Modifications :**

- Expliquer les nouveaux champs que le handler reçoit et les modèles de sortie
  et d’événement structurés, avec un exemple exécutable adapté au runtime
  Python.
- Ajouter au quickstart un serveur de démonstration sans modèle, déclenché par
  les mots-clés `test:rag`, `test:content` et `test:mcp`, afin qu’un client
  OpenAI-compatible puisse inspecter les annotations, les collections de
  contenu et les sorties d’outils MCP en streaming comme hors streaming.
- Mesurer les cas Responses représentatifs sans relâcher les seuils existants :
  normalisation/dispatch <10 ms p95, pipeline <50 ms p95 hors handler, premier
  événement <300 ms p95.
- Mettre à jour le PLAN avec les fichiers finaux, décisions et résultats réels.

**Validation :**

- Exécuter l’exemple ou son scénario de fumée documenté.
- Exécuter les tests contractuels, d’intégration, de parité concernés et de
  performance Python.
- Exécuter les contrôles CI Python du dépôt : Ruff sur `packages/python` et
  `tests`, puis `pytest tests/`.
- Revoir `git status`, `git diff`, `git diff --check` et vérifier qu’aucune
  implémentation .NET/Java n’a été ajoutée.

## Tests

- Contrat Responses versionné : toutes les formes de requête/réponse prises en
  charge et chaque type d’événement SSE documenté.
- Intégration FastAPI : payload simple, array et multimodal, options préservées,
  sortie structurée, événements de texte et structurés, erreur et interruption.
- Compatibilité : mapping Responses textuel, autres surfaces OpenAI/Anthropic,
  auth, routage, découverte, headers et middleware.
- Performance : trois budgets p95 existants, avec mesures sur les parcours
  Responses pertinents.
- Validation finale Python CI : Ruff et pytest, ainsi que le contrôle de
  schéma/SDK OpenAI selon les dépendances présentes.

## Validation finale

- Ruff : PASS avec `/tmp/issue16-venv/bin/python -m ruff check
  packages/python/agents tests
  docs/examples/python-fastapi-quickstart/responses_structured_app.py`.
- Tests concernés : PASS, 58 tests cumulés pour les tests contractuels et
  d’intégration Responses, les scénarios de démonstration et les suites
  existantes d’autorisation et d’authentification. Les cinq nouveaux tests de
  démonstration vérifient aussi les index des citations et les séquences SSE.
- Compatibilité Python hors MCP server hosting : PASS, 516 tests avec
  `/tmp/issue16-venv/bin/python -m pytest -q tests/
  --ignore=tests/integration/python/test_mcp_server_hosting.py`.
- La suite complète `pytest tests/` n’a pas terminé dans cet environnement :
  elle reste bloquée dès le premier test de
  `test_mcp_server_hosting.py::TestTheSecurityPosture::test_a_call_without_a_credential_is_refused`,
  avant son résultat. Ce module ne touche pas aux surfaces Responses.
- Exemple structuré : PASS; les scénarios `test:rag`, `test:content` et
  `test:mcp` passent par `/v1/responses` en mode non-streaming et streaming.
  L’exemple émet aussi les cycles d’arguments de fonction pour le scénario par
  défaut. Les jeux de données sont fixes et ne contactent aucun modèle, moteur
  RAG ou serveur MCP.
- JSON : PASS pour le schéma Standard Exchange et la fixture Responses
  versionnée.
- Mesures locales Python 3.14.3, ASGI en processus, route anonyme et handler
  sans travail : `normalize_request` p95 **0,0048 ms**, `POST /v1/responses`
  p95 **0,8939 ms**, premier événement SSE p95 **0,0759 ms**. Les trois mesures
  restent sous les budgets de 10/50/300 ms; elles ne remplacent pas un benchmark
  CI reproductible.
- Le SDK OpenAI Python n’est pas installé dans l’environnement; les fixtures et
  l’inventaire versionné servent donc de validation de contrat.
- `git diff --check` passe avec le traitement CRLF existant du dépôt.
- Aucun code .NET ou Java n’a été ajouté.

## Risques

- L’API et l’inventaire d’événements OpenAI évoluent; la référence retenue doit
  être identifiée avant d’écrire fixtures et encodeur.
- La compatibilité de texte simple doit rester assurée alors que des
  événements Responses riches sont ajoutés.
- Les sorties JSON imbriquées doivent être conservées exactement sans introduire
  de structures non typées hors des frontières wire.
- La parité .NET/Java est différée explicitement jusqu’à la stabilisation
  Python; cette issue ne devra pas être présentée comme la livraison complète
  inter-langages.

## Décisions techniques

- Garder cette livraison dans le package Python et reporter toute implémentation
  .NET/Java à des issues distinctes après stabilisation Python.
- Garder `StandardExchangeRequest.input` égal à `input` dans la requête OpenAI;
  ajouter un champ Standard Exchange optionnel `provider_options` et y
  transférer les options Responses, sans mêler ces valeurs aux métadonnées
  runtime.
- Représenter les formes imbriquées conformes au schéma OpenAI comme des valeurs
  JSON à la frontière et modéliser explicitement les enveloppes et types
  d’événement avec des types Python.
- Conserver les retours texte/deltas simples et générer le cycle SSE de texte;
  les handlers qui émettent des résultats/événements riches utilisent les
  nouveaux modèles Python Responses.
- Ajouter un mapper et un encodeur Responses dédiés, en réutilisant le routage,
  l’authentification, le formatage SSE commun et les contrats d’échange actuels
  sans modifier les surfaces Chat Completions ou Anthropic.

## Critères de réussite

- Toutes les formes et options de requête Responses prévues par la référence
  versionnée sont acceptées et conservées jusqu’au handler.
- Les réponses structurées sont conformes au schéma OpenAI et les réponses
  textuelles existantes continuent de fonctionner.
- Chaque type d’événement Responses couvert est émis avec son type, son payload,
  son ordre et sa terminaison conformes.
- Les tests Python, les contrôles CI et les budgets définis sont exécutés et
  leurs résultats consignés.
- Aucun code .NET ou Java n’est modifié; les suivis de parité restent à faire
  après stabilisation de Python.
