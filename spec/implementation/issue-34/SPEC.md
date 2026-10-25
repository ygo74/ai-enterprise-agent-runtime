# Specification

## Issue

[#34 — Agent definition in the yaml file et rate limit](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/34)

## Objective

Déclarer dans `agent.yaml` les routes HTTP FastAPI d'un agent, son mode
d'authentification et ses limites d'appels, puis migrer les exemples concernés
et les agents Mail et Wiki du dépôt `ai_agents` vers cette configuration.

## Context and problem

Le dépôt `ai-enterprise-agent-runtime` fournit déjà un chargeur typé pour
`agent.yaml`, des validateurs JWT et API key, et une fabrique FastAPI capable de
sélectionner `/v1/chat/completions`, `/v1/responses` et `/v1/messages`.
L'activation des routes et la sécurité sont toutefois assemblées séparément dans
le code applicatif. Les manifestes décrivent aujourd'hui l'identité de l'agent,
son serveur MCP par défaut et ses compétences, mais pas son hébergement HTTP.

Les secrets MCP utilisent des références entières comme `${MAIL_API_KEY}`,
résolues depuis l'environnement du processus ou le fichier `.env` du paquet.
Cette convention fournit le modèle pour les secrets HTTP. Le dépôt `ai_agents`
héberge actuellement ses services Mail et Wiki avec des paramètres HTTP
d'environnement et fixe leurs routes dans leur code.

La limite de débit doit reposer sur une bibliothèque éprouvée et compatible
FastAPI. SlowAPI est la proposition initiale : sa documentation couvre FastAPI
et Starlette, plusieurs stockages (dont mémoire et Redis), les routes sync et
async, ainsi que les limites partagées entre routes. Sa compatibilité avec la
version FastAPI réellement prise en charge par ce dépôt doit être vérifiée avant
l'approbation du PLAN; si elle impose une restriction FastAPI ou ne fonctionne
pas avec les routes du runtime, la SPEC devra être révisée avant le PLAN.

Références : [dépôt SlowAPI](https://github.com/laurents/slowapi),
[documentation SlowAPI](https://slowapi.readthedocs.io/en/stable/) et
[FastAPI-Limiter, candidat comparé](https://github.com/long2ice/fastapi-limiter).

## Repositories and roles

- `ai-enterprise-agent-runtime` (dépôt principal de l'Issue) : étendre le
  contrat de manifeste Python, son schéma et son chargement; convertir la
  configuration déclarée en réglages FastAPI typés; intégrer la limitation de
  débit et actualiser la documentation et les exemples du runtime.
- `ai_agents` (dépôt secondaire) : adapter les manifestes `config/agents/mail/
  agent.yaml` et `config/agents/wiki/agent.yaml`, puis faire consommer ces
  réglages aux compositions HTTP Mail et Wiki et actualiser leur documentation.

Le dépôt runtime doit être implémenté, validé et intégré en premier. Le dépôt
`ai_agents` pourra ensuite dépendre de cette version publiée ou du changement
intégré du runtime. Les deux dépôts garderont des branches, validations,
commits et Pull Requests indépendants.

## Scope

### Runtime

- Ajouter au contrat Python versionné de `agent.yaml` une section d'hébergement
  HTTP facultative. Lorsqu'elle est présente, elle déclare :
  - une sélection explicite d'au moins une des routes d'invocation prises en
    charge : Chat Completions, Responses et Messages;
  - une politique de sécurité `jwt` ou `api_key`, obligatoire pour cette
    section, avec validation stricte des options compatibles avec le mode choisi;
  - une section de limitation de débit facultative, désactivée si omise.
- Les routes correspondent aux surfaces existantes
  `POST /v1/chat/completions`, `POST /v1/responses` et `POST /v1/messages`.
  Aucune nouvelle route de protocole n'est ajoutée.
- Pour JWT, rendre configurables les paramètres de validation déjà pris en
  charge par le runtime : algorithmes autorisés, claims obligatoires, issuer,
  audience, tolérance d'horloge, chemins de claims pour les rôles/groupes et
  source de clé. La source de clé permet une URL JWKS directe, la découverte
  OIDC par issuer ou une clé symétrique/asymétrique statique lorsque le
  validateur existant le permet. Les URL et valeurs de clé sont validées avant
  l'enregistrement des routes.
- Pour API key, rendre configurables le nom d'en-tête, la valeur secrète et
  l'identité applicative associée à cette clé. Cette identité alimente le
  `auth_context` comme le résolveur actuel, sans exposer la clé aux traitements
  métier. Les agents qui ont besoin d'un email, comme Mail, doivent le déclarer
  plutôt que recevoir une identité implicite.
- Résoudre les valeurs secrètes entières `${VARIABLE_NAME}` à partir de
  l'environnement chargé selon les conventions existantes. Une référence
  absente ou vide empêche le démarrage. Les secrets sont conservés dans des
  champs protégés, et ne figurent ni dans les erreurs de validation ni dans les
  logs. Le manifeste conserve la référence tant qu'un hôte HTTP n'est pas
  construit : charger le même agent pour la CLI ou le MCP ne doit pas exiger les
  secrets HTTP.
- Configurer SlowAPI derrière l'extra HTTP optionnel du paquet `agents`; les
  installations sans FastAPI ni limiteur continuent à importer les contrats,
  manifestes et APIs de configuration. Les limites s'appliquent uniquement aux
  routes d'invocation activées. Une configuration typée fournit une ou plusieurs
  limites et un URI de stockage optionnel. Le stockage mémoire est local au
  processus; Redis peut être sélectionné pour partager les compteurs entre
  workers ou instances.
- Le limiteur retourne une réponse HTTP 429 lorsque la limite est dépassée et
  n'invoque pas le handler. La clé de comptage initiale est l'adresse du client
  observée par FastAPI; les déploiements derrière un proxy doivent documenter
  la configuration correcte de ce proxy. Ne pas faire confiance à des en-têtes
  de transfert fournis directement par le client.
- Une erreur de configuration, une combinaison incohérente ou l'absence d'une
  authentification sélectionnée empêche tout enregistrement partiel des routes.
  Les routes de découverte restent gouvernées par leur configuration existante,
  et toute authentification qu'elles exigent demeure cohérente avec la politique
  du service.
- Actualiser les exemples FastAPI du runtime qui livrent un manifeste
  `agent.yaml`, notamment les exemples de configuration MCP LangChain et
  Microsoft Agent Framework, ainsi que les guides et le schéma éditorial.
- Publier une référence complète de `agent.yaml` qui décrit chaque clé,
  chaque type de valeur et les valeurs par défaut; documenter la configuration
  de VS Code pour associer le schéma JSON livré aux fichiers manifestes.

Forme YAML proposée pour clarifier le contrat (les noms peuvent être ajustés
pendant le PLAN sans changer le comportement attendu) :

```yaml
http:
  endpoints: [chat_completions, responses]
  security:
    mode: api_key
    api_key:
      value: ${MAIL_HTTP_API_KEY}
      header_name: X-API-Key
      user:
        subject: mail-service-user
        email: mailbox@example.com
  rate_limit:
    limits: [60/minute]
    storage_uri: ${HTTP_LIMIT_STORAGE_URI}
```

Pour JWT, `security.jwt` porte l'issuer, l'audience, `allowed_algorithms`,
`required_claims`, `leeway_seconds`, les chemins de claims et exactement une
source de clé : `jwks_url`, la découverte OIDC de l'issuer, ou `secret` / `public_key`
pour une clé statique. Les champs secrets sont des références d'environnement;
les valeurs d'identité et les paramètres non sensibles restent littéraux.

### `ai_agents`

- Déclarer la politique d'authentification actuellement utilisée pour chacun
  des services Mail et Wiki dans son propre `agent.yaml`.
- Préserver les comportements actuels : Mail accepte soit son mode JWT/OIDC,
  soit son mode API key pour un principal configuré; Wiki garde la même
  sélection exclusive, sans inventer d'adresse email pour ses appelants.
- Déclarer dans chaque manifeste les routes actuellement exposées : Mail
  conserve Chat Completions et Responses; Wiki conserve Chat Completions.
- Remplacer dans les services HTTP la construction redondante de la politique
  d'authentification et la sélection codée en dur des routes par les réglages
  chargés du runtime. Préserver les validateurs métier, l'identité, l'état de
  conversation et la politique de découverte actuels.
- Déplacer les secrets d'authentification référencés dans les manifestes vers
  `.env.example` et la documentation; aucun secret réel ne doit être ajouté au
  dépôt.

## Out of scope

- Modifier le comportement ou les contrats des runtimes .NET et Java. Les
  manifestes YAML et leur chargeur sont une surface Python, et la limitation
  demandée vise explicitement FastAPI. Cette livraison est donc Python seulement
  et ne revendique pas la parité .NET/Java pour ces nouveaux champs.
- Ajouter l'authentification anonyme comme mode déclaratif dans cette section.
  Les applications sans section d'hébergement peuvent continuer à charger leurs
  manifestes pour les usages non HTTP; les hôtes HTTP de cette livraison
  déclarent JWT ou API key explicitement.
- Ajouter ou configurer les surfaces de découverte, A2A, les politiques
  d'autorisation métier, les providers MCP, ou les paramètres internes des
  conversations.
- Concevoir un service de stockage de limites ou un algorithme de rate limit.
  Le runtime adapte SlowAPI et ses stockages supportés.
- Ajouter plusieurs clés API, un résolveur dynamique de clés, des stratégies de
  quotas par utilisateur ou de nouvelles règles de confiance pour les proxies.

## Expected behavior

- Un manifeste existant sans configuration HTTP reste valide pour les usages
  non HTTP. Un manifeste utilisé pour construire l'un des hôtes HTTP Mail ou Wiki
  doit déclarer routes et authentification avant le démarrage du service.
- Les champs non reconnus, valeurs d'enum inconnues, limites mal formées,
  modes incomplets et options JWT/API key incompatibles échouent avec une erreur
  qui nomme le champ concerné sans afficher les valeurs secrètes.
- Les surfaces désactivées ne sont pas enregistrées et renvoient la réponse
  FastAPI 404 habituelle. Toute surface activée conserve son contrat existant,
  son streaming, son authentification, sa résolution de route et son format
  d'erreur.
- Un jeton JWT valide ou une clé API valide produit le même contexte utilisateur
  attendu par l'application actuelle. Une absence ou une invalidité de
  justificatif est refusée avant l'exécution de l'agent.
- Quand la limitation est active, les requêtes au-delà du quota reçoivent 429;
  les requêtes sous le quota poursuivent le traitement normal. Lorsqu'elle est
  omise, aucune dépendance ou vérification SlowAPI n'est requise.
- Les manifestes Mail et Wiki une fois migrés conservent les mêmes routes,
  modes d'authentification, attributs d'identité, fonctions de découverte et
  comportements applicatifs qu'avant migration.
- Les développeurs peuvent consulter la référence de chaque clé `agent.yaml`
  et configurer VS Code pour obtenir la validation structurelle à partir du
  schéma livré avec le runtime.

## Architecture, interfaces et données

- Faire évoluer ensemble `AgentManifestInput`, `AgentManifest`, le schéma Draft
  2020-12 livré, `AgentManifestLoader`, les modèles Python typés et la fabrique
  d'hébergement. Préserver les objets de manifeste existants et éviter une
  deuxième définition du même contrat.
- Réutiliser `JwtValidationConfig`, les résolveurs de clé existants,
  `AuthenticationPolicy`, `ApiKeyAuthenticator`, les politiques de découverte et
  l'enregistrement FastAPI existant. Ajouter uniquement les adaptateurs de
  configuration et le cycle de vie SlowAPI manquants.
- Le contrat de manifeste reste strict (`extra="forbid"`) et les valeurs API
  key, secret JWT et éventuel URI de stockage avec identifiants restent
  protégées en mémoire.
- Réserver SlowAPI au chemin d'installation HTTP optionnel. Son initialisation,
  son gestionnaire 429 et son stockage suivent le cycle de vie de l'application
  ASGI et n'ouvrent aucune connexion réseau lors du chargement des manifestes.
- La sécurité du runtime est partagée avec le paquet Python `security`; les
  champs spécifiques FastAPI et l'adaptation à SlowAPI sont possédés par le
  paquet Python `agents`, sans créer de dépendance inverse.

## Contraintes et décisions

- **Parité :** exception Python explicite pour le contrat `agent.yaml`, ses
  chargeurs et l'hébergement FastAPI. Aucun changement .NET/Java ni aucune
  affirmation de parité ne sont prévus par cette Issue.
- **Authentification API key :** comme l'API runtime exige un résolveur qui
  renvoie un utilisateur, le manifeste décrira une clé et un utilisateur fixe
  pour le mode démonstration/service de cette Issue. Les résolveurs multi-clés
  fournis par l'application restent hors périmètre.
- **Bibliothèque de limites :** SlowAPI est le choix proposé, avec stockage
  mémoire par défaut si aucune URI n'est déclarée et URI Redis en option. La
  compatibilité avec FastAPI et les routes de ce runtime est une condition de
  sortie du PLAN, à établir avant l'implémentation.
- **Comptage :** les quotas portent sur l'adresse cliente observée par le
  serveur et couvrent séparément chaque route d'invocation activée selon les
  règles SlowAPI. Les requêtes de découverte ne sont pas limitées par cette
  configuration.
- **UX :** les noms et erreurs de configuration désignent le chemin YAML
  précis; 401/403 existants et erreurs de validation restent inchangés; 429 est
  ajouté uniquement pour le dépassement de quota.
- **Budget de performance :** l'adaptation de limitation ajoute au plus 5 ms
  p95 avec le stockage mémoire sur le chemin local, hors handler et sérialisation
  de réponse. Le stockage partagé ajoute sa latence réseau; son budget doit être
  mesuré séparément et ne peut être assimilé au budget local.
- **Tests obligatoires :** tests de contrat/schema et de chargement typé,
  résolution des secrets/redaction, validation de la configuration JWT/API key,
  activation de routes, 401/404/429, arrêt ASGI et non-importabilité du limiteur
  sans extra HTTP. Tests d'intégration dans `ai_agents` prouvent la conservation
  de l'identité Mail/Wiki et des routes.
- **Exemples :** tous les exemples livrant un manifeste d'agent qui sert HTTP
  doivent refléter le schéma accepté et illustrer des références fictives, sans
  secret réel.

## Critères d'acceptation

1. Les manifestes acceptent et valident les paramètres HTTP, routes,
   authentification et limitation déclarés; le schéma JSON correspond au
   modèle typé.
2. Les clés API, clés ou secrets JWT et URI de stockage sensibles utilisent
   uniquement une référence `${VARIABLE_NAME}` complète; variable absente ou
   vide, la construction de l'hôte échoue sans révéler son contenu. Le
   chargement non HTTP du manifeste ne résout pas les références HTTP.
3. JWT valide correctement l'issuer, l'audience, les algorithmes, claims,
   tolérance et résolution de clé configurés; API key produit l'identité
   déclarée; mauvais justificatifs sont rejetés avant le handler.
4. Chaque sous-ensemble non vide des trois routes peut être déclaré; seules les
   routes sélectionnées sont enregistrées, et les autres donnent 404.
5. SlowAPI applique les limites à chaque route activée, renvoie 429 au-delà du
   quota, réinitialise les compteurs selon la politique du backend configuré et
   ferme ses ressources de cycle de vie lorsqu'il y en a.
6. Un manifeste sans configuration HTTP reste chargeable par les APIs
   configuration/MCP qui n'hébergent pas FastAPI.
7. Les installations de base et les extras sans `http` n'exigent ni FastAPI ni
   SlowAPI pour importer et utiliser les manifestes non HTTP.
8. Les samples configurés et les deux manifestes de `ai_agents` utilisent la
   nouvelle forme. Les tests d'intégration confirment les routes et contextes
   utilisateur existants.
9. La mesure locale confirme un surcoût SlowAPI inférieur ou égal à 5 ms p95
   hors traitement agent; les limites de stockage partagé sont documentées et
   mesurées sans être incluses dans ce budget.

## Stratégie de validation

- Runtime : tests contrat JSON Schema/Pydantic, tests ciblés d'authentification
  et de secrets, tests FastAPI pour les routes sélectionnées et désactivées,
  limites exactes et dépassement 429, test avec le stockage local et test
  d'installation/import sans extra HTTP.
- Runtime : mesurer le coût du contrôle avec le backend mémoire; tester le
  stockage partagé uniquement avec le service local déterministe prévu par le
  plan, sans service public ni identifiants réels.
- `ai_agents` : tests de configuration et d'intégration des services Mail et
  Wiki, y compris l'identité utilisateur injectée dans leur conversation.
- Exécuter les validations spécifiques documentées par chaque dépôt seulement
  après approbation du PLAN; ne pas revendiquer les contrôles non exécutés.

## Risques et questions ouvertes

- SlowAPI a une intégration FastAPI dépendante de la signature et de
  l'enregistrement des routes. Le PLAN doit confirmer que sa version publiée
  fonctionne avec les versions FastAPI supportées et ne requiert pas de borne
  incompatible avec les autres exemples.
- La limite mémoire est propre à un processus et ne coordonne pas plusieurs
  workers. Redis ou un stockage équivalent supporté est requis pour une limite
  globale en déploiement distribué.
- Les proxies peuvent faire apparaître leur adresse à la place du client. La
  configuration de confiance proxy doit être explicite dans le déploiement;
  l'en-tête `X-Forwarded-For` non vérifié ne sera pas la source de comptage.
- L'identité API key déclarée est un principal fixe; son email doit être
  renseigné pour l'agent Mail afin de préserver l'accès à la boîte et le
  partitionnement actuels.
- Le service Wiki n'expose actuellement que Chat Completions, tandis que Mail
  expose Chat Completions et Responses. Cette Issue n'active pas de route
  supplémentaire lors de leur migration.
