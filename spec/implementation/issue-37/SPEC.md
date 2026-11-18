# SPEC — Issue #37 : exposer les agents comme opérations MCP

## Source et dépôts

- Issue : [MCP endpoints #37](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/37)
- Dépôt principal : `ai-enterprise-agent-runtime`, propriétaire des API génériques du runtime.
- Dépôt secondaire : `ai_agents`, propriétaire des compositions Mail et Wiki à exposer.
- L’issue demande un nouveau type d’endpoint pour présenter un agent comme une opération MCP, puis son activation pour Mail et Wiki.

## Objectif

Permettre à un client MCP d’invoquer un agent hébergé comme une opération MCP, en réutilisant les contrats d’invocation et les mécanismes de serveur du runtime. Activer cette surface pour les agents Mail et Wiki sans dupliquer leurs règles métier ni leurs adaptateurs de framework.

## Contexte actuel

- Le runtime Python fournit les endpoints HTTP des agents et un paquet MCP séparé qui héberge des outils MCP avec authentification HTTP.
- Le paquet MCP est volontairement indépendant du paquet `agents`; les sémantiques des outils restent détenues par l’application.
- `ai_agents` expose Mail et Wiki par HTTP. Les deux applications possèdent une entrée de conversation qui construit un tour avec l’identité authentifiée, appelle leur moteur de conversation et rend une réponse typée.
- Mail exige une adresse e-mail pour choisir la boîte. Wiki exige un sujet utilisateur, mais pas d’adresse e-mail.
- Les applications utilisent déjà des contrôles d’autorisation et de confirmation pour les opérations d’écriture. Le modèle ne peut ni accorder une permission ni confirmer une opération.

## Portée

### Runtime (`ai-enterprise-agent-runtime`)

- Ajouter une API Python réutilisable pour exposer une invocation d’agent sous forme d’opération MCP.
- Garder le contrat d’invocation indépendant de Mail, Wiki et de leurs frameworks. Réutiliser les contrats d’échange, de sortie et de contexte existants lorsque cela convient.
- Rendre cette intégration optionnelle avec les extras MCP appropriés; les imports et usages sans MCP doivent rester disponibles sans installer le SDK MCP.
- Réutiliser l’hébergement et les contrôles d’authentification MCP existants plutôt que créer une seconde politique de transport ou de sécurité.
- Définir les erreurs et la conversion des entrées/sorties MCP de façon typée et documentée.

### Dépôt secondaire (`ai_agents`)

- Composer la nouvelle API avec l’entrée de conversation existante de Mail.
- Composer la nouvelle API avec l’entrée de conversation existante de Wiki.
- Fournir une configuration exploitable par un client MCP et documenter le démarrage et l’authentification de chaque service.
- Préserver les surfaces HTTP, les contrats d’identité, les politiques d’autorisation, les demandes de confirmation et les connexions MCP existantes vers les systèmes d’entreprise.

## Comportement attendu et critères d’acceptation

1. Une application peut déclarer une opération MCP qui délègue à un agent existant sans importer de types Mail, Wiki ou de framework dans le runtime générique.
2. L’opération accepte une entrée de conversation valide et retourne une réponse MCP correspondant au résultat typé de l’agent. Les échecs d’invocation restent visibles comme erreurs MCP et ne deviennent pas des réponses de succès vides.
3. Pour un transport HTTP protégé, l’identité utilisée par l’agent provient du contexte authentifié par le serveur MCP. Les arguments de l’opération ne peuvent pas remplacer le sujet, l’e-mail ou les permissions du principal.
4. L’intégration Mail refuse un appel si le principal authentifié ne contient pas l’e-mail exigé. L’intégration Wiki continue d’accepter un principal avec sujet sans exiger d’e-mail.
5. Les appels conservent les vérifications de permission et de confirmation existantes; une invocation MCP ne permet pas de contourner les contrôles d’écriture.
6. Les agents Mail et Wiki du dépôt `ai_agents` sont invocables via l’opération MCP, tandis que leurs surfaces HTTP et leurs comportements actuels restent disponibles.
7. L’installation et l’import des fonctionnalités MCP restent optionnels pour les applications qui n’activent pas ce type d’endpoint.
8. La documentation runtime et les guides d’exploitation de `ai_agents` expliquent le nom et les arguments de l’opération, son résultat, le transport et l’authentification.

## Hors portée

- Ajouter une parité MCP .NET ou Java; les APIs de serveur MCP du dépôt sont Python uniquement.
- Exposer séparément chaque capacité métier Mail ou Wiki comme outil MCP. L’objectif de cette issue est d’exposer l’agent lui-même comme une opération.
- Modifier les outils MCP qui donnent accès à Gmail, Confluence ou aux autres systèmes d’entreprise.
- Remplacer ou affaiblir les politiques d’identité, d’autorisation, de permission ou de confirmation des agents.
- Fusionner les dépôts, publier des paquets ou déployer les services.

## Contraintes d’architecture et de sécurité

- Les dépendances restent dirigées vers les contrats du runtime; le runtime ne dépend pas des domaines d’application Mail/Wiki ni de Microsoft Agent Framework ou LangChain.
- Le point de composition spécifique à chaque agent reste dans `ai_agents`.
- Le contexte d’identité doit être dérivé du contexte authentifié de la requête MCP, jamais d’un champ libre fourni par le modèle ou le client dans les arguments.
- Les contenus de courrier et de wiki demeurent des entrées non fiables. Les secrets et contenus sensibles ne sont pas ajoutés aux logs.
- Aucun nouvel état durable n’est requis par le simple adaptateur d’opération. Si la conversation nécessite une durée de vie ou une partition différente de celle des moteurs existants, le PLAN devra définir cette politique avant implémentation.
- La validation est Python uniquement. Le PLAN identifiera les tests de contrat et d’intégration requis dans chaque dépôt, ainsi que les exemples et guides à mettre à jour.
- Aucun budget de performance distinct n’est fourni par l’issue. Le PLAN précisera si le coût du nouvel adaptateur nécessite une mesure séparée; l’invocation du modèle et les échanges MCP existants restent hors de son budget propre.

## Décisions à préciser dans le PLAN

- La forme exacte de l’opération et de ses arguments (par exemple, message et identifiant de conversation facultatif) doit être alignée sur les contrats de conversation déjà utilisés par les deux agents.
- La projection MCP de la réponse doit conserver assez d’information pour représenter réponse, identifiant de conversation et confirmations en attente sans exposer les arguments ou contenus sensibles.
- Le PLAN doit déterminer comment l’authentification HTTP existante des agents est réutilisée pour le transport MCP et comment le contexte FastMCP est relié au contexte d’invocation partagé.
- Le PLAN doit préciser si l’activation utilise un processus MCP streamable HTTP dédié par agent ou une composition de serveur dans le processus d’hébergement existant, en tenant compte des points d’entrée et cycles de vie déjà présents.

## Impacts

- **Contrat public :** ajout d’une API d’intégration MCP côté Python et d’un contrat MCP d’invocation agent; compatibilité à documenter avant sa stabilisation.
- **Parité :** exception Python explicite, cohérente avec l’hébergement MCP existant.
- **Sécurité :** impact élevé, car le transport présente des capacités d’agent; identité authentifiée et contrôles d’écriture doivent rester effectifs.
- **État :** réutilisation prévue du moteur de conversation et de sa partition par principal; aucun nouvel état local au runtime n’est attendu.
- **Documentation et exemples :** guide MCP runtime et documentation de démarrage des services Mail/Wiki.
- **Validation :** tests ciblés de l’opération MCP, du contexte utilisateur authentifié, des erreurs et de la préservation des barrières Mail/Wiki, selon les validations approuvées au PLAN.
