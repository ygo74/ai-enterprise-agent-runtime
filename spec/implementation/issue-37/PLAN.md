# PLAN — Issue #37 : endpoint MCP pour les agents

## SPEC approuvée

La portée est définie dans [`SPEC.md`](SPEC.md), approuvée par l’utilisateur. Le dépôt principal `ai-enterprise-agent-runtime` fournit l’API et l’hébergement génériques; le dépôt secondaire `ai_agents` active la surface pour Mail et Wiki. Les historiques Git restent séparés.

## Architecture existante et réutilisation

- Les agents Python sont déclarés via `AgentDefinition` et servis par `ManagedAgentWorker`. Le worker possède déjà `ConversationEntrypoint`, `ConversationRuntimeCache`, le délai maximal d’un tour et le cycle de vie des conversations.
- `HostingFactory` traduit actuellement `agent.yaml.http.endpoints` en surfaces HTTP OpenAI ou Anthropic. Le schéma et `HttpEndpoint` sont propres à Python.
- Le paquet `ygo74-agent-runtime-mcp` héberge déjà les serveurs FastMCP avec `McpServerHost`, qui applique une `AuthenticationPolicy`, publie la santé et les métadonnées OAuth facultatives, et place le contexte authentifié sur la requête ASGI.
- FastMCP est déjà une dépendance facultative du runtime pour son client MCP. L’extra serveur HTTP du paquet `mcp` contient le SDK FastMCP et Starlette.
- Mail et Wiki utilisent le même `ManagedAgentWorker` sous des façades framework différentes : Mail l’instancie directement et Wiki passe par `LangGraphWorker`. Les entrées `MailAgentEntrypoint` et `WikiAgentEntrypoint` conservent les règles d’identité propres à chaque agent.
- Réutiliser `McpServerHost` pour l’authentification et la gestion Streamable HTTP, `ManagedAgentWorker` pour les conversations et `AgentOutputSerializer` pour la réponse. Ne pas ajouter de deuxième cache, de client MCP entrant maison, ni de types de domaine Mail/Wiki au runtime commun.

## Décisions d’implémentation

1. Le type `mcp` sera une surface sélectionnable dans `agent.yaml.http.endpoints`. Il s’agit de MCP Streamable HTTP sur le même hôte FastAPI que les routes existantes, avec l’URL protocolaire `/mcp`; ce n’est pas un second processus ou port.
2. L’opération unique de chaque serveur s’appellera `invoke_agent`. Elle accepte `message` et un `conversation_id` facultatif qui vaut `default` s’il est omis. Le SDK injecte le contexte de requête séparément des arguments exposés au client.
3. Le principal transmis à l’agent est exclusivement le contexte authentifié conservé par `McpServerHost` dans la portée de la requête. Le message et l’identifiant de conversation sont les seuls arguments métier. L’endpoint échoue fermé si le contexte est absent ou mal formé.
4. La réponse MCP est un objet JSON structuré dérivé du `StandardExchangeResponse` : sortie typée sérialisée, statut, identifiant de conversation et métadonnées de confirmation en attente. Les erreurs d’invocation demeurent des erreurs d’outil MCP.
5. La nouvelle surface réutilise l’authentification configurée dans `http.security`. Un champ facultatif `http.mcp.resource_url` fournit l’URL canonique requise pour les métadonnées de ressource protégée lorsque la politique JWT est utilisée; il accepte une référence d’environnement complète pour les déploiements. L’absence de cette URL avec `mcp` + JWT est une erreur de configuration avant l’enregistrement des routes.
6. Le sous-serveur MCP sera monté à la racine après les routes FastAPI existantes, afin de laisser celles-ci et `/health/ready` accessibles. Le cycle de vie de l’hôte parent démarrera explicitement le gestionnaire de session FastMCP et fermera l’authentificateur MCP. Le paquet MCP doit fournir cette intégration de montage, car le cycle de vie d’une sous-application ASGI montée n’est pas exécuté automatiquement.
7. La fonctionnalité reste facultative à l’installation. Le paquet `agents` ajoute un extra serveur distinct de son extra `mcp` client, et `ai_agents` l’active dans les extras HTTP utilisés par les services concernés.

La documentation officielle du SDK MCP décrit l’app ASGI Streamable HTTP et précise que l’hôte parent doit démarrer le gestionnaire de session lorsqu’une sous-application est montée : [Python SDK — Add to an existing app](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md). Le dépôt borne le SDK à `mcp>=1.24,<2`; l’implémentation vérifiera les mêmes points avec cette ligne v1, sans adopter d’API v2.

## Portée par dépôt

### 1. `ai-enterprise-agent-runtime` — branche `chore/adhoc-repo-local-vibe-workflow`

#### Contrats et configuration

- Étendre `HttpEndpoint` avec `MCP = "mcp"` et ajouter le modèle validé `http.mcp.resource_url`.
- Faire évoluer `AgentHttpConfiguration`, `AgentHttpSettingsBuilder`, `AgentHttpRuntimeSettings` et le schéma JSON `agent-manifest` pour valider la combinaison MCP/JWT et résoudre la référence d’URL au démarrage de l’hôte.
- Conserver les règles de compatibilité : `http` reste facultatif, les manifestes existants restent valides, les anciens endpoints conservent leur sens et les champs inconnus restent rejetés.

#### Endpoint et hébergement

- Ajouter `EndpointSurface.MCP` et la traduction depuis `HttpEndpoint.MCP` dans `HostingFactory`.
- Ajouter un adaptateur `McpAgentEndpoint` au paquet Python `agents`. Il enregistre `invoke_agent`, construit le payload normalisé attendu par l’entrée commune, transmet le contexte `AuthenticatedUserContext` vérifié, appelle l’entrée existante et projette la réponse typed output en objet structuré MCP.
- Ajouter un extra serveur facultatif au paquet `agents` qui dépend du paquet runtime `mcp[http]`; conserver l’extra `mcp` client séparé.
- Étendre `McpServerHost` avec le montage protégé d’un serveur FastMCP dans une application ASGI existante. Composer le gestionnaire de session FastMCP et la fermeture de l’authentificateur dans le cycle de vie du parent sans protéger une seconde fois les routes HTTP de l’agent.
- Adapter `ManagedAgentWorker.build_app()` pour enregistrer `/health/ready` avant le montage à la racine et pour garder sa fermeture de cache dans le cycle de vie déjà existant.
- Garder l’API runtime MCP non importable lorsque l’extra serveur n’est pas installé; une configuration qui sélectionne `mcp` sans extra produit une erreur d’installation explicite au démarrage.

#### Validation test-first

Ajouter d’abord les cas échouants, puis l’implémentation minimale et les contrôles de régression ciblés :

- Contrat manifeste : enum `mcp`, nouveau champ, schéma et chargement; compatibilité des manifestes existants; validation de JWT sans `resource_url`.
- Endpoint : `tools/list` publie un seul outil avec `message` et `conversation_id`; `tools/call` appelle le handler une fois et conserve sortie typée et confirmations en attente.
- Sécurité : appel non authentifié ou credential invalide refusé avant l’outil; identité et email viennent du contexte vérifié; aucun champ fourni par le client ne peut remplacer le principal.
- ASGI : `/mcp` atteint FastMCP, les routes OpenAI/Anthropic et `/health/ready` restent accessibles, le gestionnaire FastMCP démarre et s’arrête, l’authentificateur est fermé.
- Optionnalité : imports et usages HTTP sans extra MCP serveur continuent de fonctionner; une sélection MCP sans dépendance serveur échoue clairement.
- Suites existantes à couvrir ensuite : `tests/integration/python/test_manifest_http_hosting.py`, `test_manifest_configuration_schemas.py`, `test_fastapi_hosting_factory.py`, `test_mcp_server_hosting.py` et `test_mcp_server_settings.py`.

### 2. `ai_agents` — branche `chore/adhoc-repo-local-vibe-workflow` (historique indépendant)

À commencer après l’API runtime et l’intégration hôte disponibles dans le checkout partagé :

- Activer `mcp` dans `config/agents/mail/agent.yaml` et `config/agents/wiki/agent.yaml`. Mail déclare `http.mcp.resource_url` via une référence d’environnement; Wiki garde son mode API key et n’a pas besoin de métadonnées OAuth.
- Faire installer l’extra runtime serveur depuis les extras `http` des paquets Mail et Wiki, en gardant l’installation MCP client indépendante de cette surface entrante.
- Préserver les compositions `ManagedAgentWorker` et `LangGraphWorker`; leurs entrées existantes sont réutilisées et leur cache reste partitionné par sujet vérifié et `conversation_id`.
- Ajouter des tests de contrat Mail et Wiki utilisant des modèles, outils MCP et authentificateurs déterministes : appel MCP authentifié, isolation entre principaux, email requis pour Mail, sujet seul accepté par Wiki, refus/confirmation d’écriture inchangés et conservation des routes HTTP.
- Mettre à jour les exemples d’environnement, les guides HTTP Mail/Wiki et la documentation de déploiement pour décrire `/mcp`, l’authentification et la configuration de `resource_url` pour JWT.

## Ordre et dépendances

1. Runtime R-001 : contrat/configuration `http.endpoints: mcp`, modèle et schéma.
2. Runtime R-002 : tests de contrat et de configuration en échec, puis validation des nouvelles combinaisons.
3. Runtime R-003 : adaptateur MCP typé, sérialisation et tests de l’outil MCP.
4. Runtime R-004 : montage ASGI protégé et composition du cycle de vie FastMCP; tests HTTP avec le vrai client MCP SDK.
5. Runtime R-005 : intégration `HostingFactory`/`ManagedAgentWorker`, extra serveur optionnel et régressions des routes existantes.
6. Runtime R-006 : exemple exécutable, guides et spécification de surface MCP.
7. `ai_agents` A-001 : dépendances d’installation, manifestes Mail/Wiki et références d’environnement.
8. `ai_agents` A-002 : tests d’intégration MCP des deux services, puis correction minimale.
9. `ai_agents` A-003 : guides et documentation de déploiement.
10. Revue des deux dépôts séparément; aucune fusion, publication ou livraison d’image n’est incluse.

Le runtime doit passer les validations ciblées avant que `ai_agents` n’utilise son API. Les deux dépôts gardent des historiques séparés et utilisent la branche `feature/37-mcp-agent-endpoints`. L’utilisateur a ensuite demandé une PR dans chaque dépôt; les commits, pushes et créations de PR sont inclus dans cette livraison. Aucune fusion, publication de paquet, livraison d’image ou déploiement n’est inclus.

## Compatibilité, sécurité et performance

- **Parité :** Python seulement. Les manifestes d’agent, FastAPI et le serveur MCP sont déjà des surfaces Python; aucun changement ou promesse de parité .NET/Java.
- **Compatibilité :** ajout optionnel au contrat `agent.yaml` v1, sans retirer ni modifier les surfaces OpenAI/Anthropic existantes. Les installations sans `mcp-server` restent utilisables tant que `mcp` n’est pas sélectionné.
- **Identité et autorisation :** contexte authentifié issu de `McpServerHost`; aucun sujet, email, rôle ou jeton n’est admis dans les arguments de l’outil. Mail et Wiki continuent d’appliquer leurs validations de principal, leurs règles d’écriture et leurs confirmations.
- **Ressources :** aucun nouveau cache. Les conversations restent dans le `ConversationRuntimeCache` existant, borné à 200 conversations et 30 minutes d’inactivité par défaut; le cache est local au processus et les requêtes MCP doivent atteindre la même instance pour reprendre une conversation. Le service n’ajoute ni stockage durable ni coordination inter-worker.
- **Cycle de vie :** un serveur FastMCP par application, créé au démarrage et fermé avec l’hôte ASGI. Aucun serveur, client ou pool n’est créé par appel d’outil.
- **Latence et débit :** le traitement d’agent, l’authentification et le transport réseau dominent l’appel. Le nouvel adaptateur ne fait que normaliser l’entrée et projeter la réponse; aucun budget p95 autonome ni benchmark de débit ne s’applique. La revue vérifiera qu’il n’y a pas d’I/O réseau ou de construction de ressources par invocation.
- **Secrets et logs :** l’URL de ressource est une adresse publique, pas un secret. Les tokens, emails et contenus métier ne sont pas ajoutés aux logs; erreurs et diagnostics restent corrélés par identifiants sûrs.

## Documentation et exemples

Dans le runtime : mettre à jour `spec/endpoints/provider-surfaces.md`, `spec/mcp/client-and-server.md`, `doc/python/agent-manifest.md`, `doc/python/mcp.md`, `doc/users/agent-hosting.md`, `doc/users/mcp-server-hosting.md`, `doc/contributors/mcp.md` et `samples/python/python-agentframework-fastapi/06-mcp-configuration/README.md` pour inclure un exemple d’agent exposé en MCP. Documenter aussi la configuration VS Code du schéma si le schéma d’agent évolue.

Dans `ai_agents` : mettre à jour `spec/README.md`, `spec/integrations/mcp-server-hosting.md`, les guides utilisateurs Mail/Wiki concernés et les valeurs fictives de l’exemple d’environnement. Ne pas modifier les contrats des outils Gmail ou Wiki.

## Risques et critères de fin

- **Cycle de vie FastMCP monté :** le parent doit démarrer le gestionnaire de session, car Starlette n’exécute pas le lifespan d’une sous-application montée. Couverture obligatoire par un appel MCP de bout en bout sur l’application FastAPI réelle.
- **MCP + JWT :** l’URL publique de ressource OAuth varie selon le déploiement. Une configuration manquante ou invalide empêche l’hôte de démarrer; les exemples ne contiennent que des valeurs fictives.
- **État distribué :** le cache de conversation reste local à chaque processus. Le déploiement derrière plusieurs workers exige affinité de session; le stockage partagé est hors de portée de cette issue.
- **Finalisation :** tous les critères de la SPEC sont démontrés par les validations ciblées des deux dépôts; les guides décrivent les limites du cache et les règles d’authentification; les journaux consignent les commandes et résultats réels. Les échecs ou contrôles non exécutés seront indiqués, jamais déclarés passés.
