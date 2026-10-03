# Specification

## Issue

[#25 — OpenAI responses api support](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/25)

## Objectif

Compléter d’abord le support de l’API OpenAI Responses sur `POST /v1/responses`
dans le runtime Python : accepter les requêtes de l’API, restituer les réponses
dans son format et transmettre correctement tous les événements de streaming
documentés. Les versions .NET et Java seront traitées après la stabilisation de
la version Python.

## Contexte

La fonctionnalité 001 définit déjà une surface OpenAI Responses, un format
d’échange standard et le streaming pour les trois langages. Les adaptateurs,
routes et mappers actuels ne couvrent toutefois qu’une réponse textuelle simple
et un événement de texte générique. L’issue demande une compatibilité plus
complète avec l’API Responses, en s’appuyant sur le schéma OpenAI, sa référence
d’API, le guide de migration et les types du SDK Python cités dans l’issue.

## Problème

Une requête Responses valide peut contenir des structures autres qu’un texte
simple. La normalisation actuelle ne garantit pas que ces champs soient
préservés jusqu’au handler. De même, une réponse structurée d’un handler peut
être réduite à du texte, et le streaming ne représente pas les différents
événements du cycle de vie Responses. Les clients qui utilisent ces formes ne
peuvent donc pas compter sur une intégration conforme, en particulier avec le
SDK OpenAI.

## Périmètre

- Étendre uniquement l’opération de création `POST /v1/responses` et son mode
  streaming.
- Couvrir uniquement le runtime Python pour cette issue.
- Différer les implémentations .NET et Java jusqu’à ce que la version Python
  soit stable. Python servira de référence pour ces suivis.
- Accepter les formes d’entrée et options définies par le schéma officiel de
  création Responses, sans réduire les contenus structurés ou multimodaux à du
  texte.
- Transmettre au handler, dans le format d’échange standard, les données
  nécessaires pour interpréter la requête, y compris les options et champs
  inconnus du mapper lorsqu’ils sont autorisés par le schéma.
- Produire une réponse Responses valide qui conserve les éléments structurés
  fournis par le handler et renseigne correctement l’enveloppe, les éléments de
  sortie, les statuts et les champs optionnels applicables.
- Émettre en SSE chaque type d’événement de streaming documenté par la
  référence Responses retenue pour cette implémentation, avec son nom d’événement,
  sa structure de données et son ordre conformes au protocole.
- Ajouter les contrats, tests de conformité et exemples/documentation nécessaires
  à cette surface.

## Hors périmètre

- Les opérations distinctes de création, comme la lecture ou la suppression
  d’une réponse par identifiant, l’annulation et les conversations.
- L’exécution des outils ou la génération du contenu par le runtime. Ces
  responsabilités appartiennent au handler ou à l’agent intégré.
- La modification des surfaces Chat Completions et Anthropic Messages, sauf si
  une abstraction commune doit être étendue sans changer leur comportement.
- La prise en charge des fonctionnalités qui ne sont pas représentées par
  l’opération `POST /v1/responses` ou ses événements de streaming.

## Comportement attendu

1. Toute requête valide pour l’opération de création Responses est acceptée et
   acheminée vers le handler sélectionné. Les valeurs d’entrée, paramètres de
   génération et options Responses ne sont ni silencieusement supprimés ni
   convertis en une simple chaîne de texte.
2. Le handler reçoit une représentation conforme au contrat Standard Exchange.
   Ce contrat fournit un moyen typé et compatible entre langages de transporter
   le contenu Responses, ses options et les données nécessaires au routage.
3. Une réponse réussie du handler est rendue en objet Response conforme au
   schéma OpenAI, y compris ses éléments de sortie structurés. Les erreurs
   continuent d’utiliser les catégories et mécanismes d’erreur existants, avec
   une projection Responses lorsque le protocole le prévoit.
4. Pour une requête `stream: true`, le serveur émet les événements Responses
   documentés sous forme SSE. Chaque événement conserve son type et ses champs,
   respecte l’ordre du cycle de vie spécifié et se termine avec l’événement
   terminal approprié. Les erreurs et interruptions ne sont pas présentées
   comme une fin réussie.
5. Les réponses et événements Python peuvent être désérialisés par le SDK
   OpenAI correspondant sans erreur de validation.

## Architecture concernée

- Adaptateurs, normalisation, rendu de réponse et émission SSE des domaines
  `endpoints`, `mapping` et `streaming` dans `packages/python/agents`.
- Contrats, fixtures et tests Python de contrat, d’intégration et de
  performance sous `tests/`; les contrats partagés ne seront étendus que si
  cela est nécessaire et compatible avec les runtimes existants.
- Documentation et exemples Python OpenAI Responses sous `docs/`.

## Contraintes

- La Constitution impose une définition de contrat neutre vis-à-vis du langage,
  des représentations typées aux frontières et des tests-first. Pour cette
  livraison, l’implémentation est volontairement limitée à Python à la demande
  de l’utilisateur; l’équivalence .NET/Java est différée jusqu’à la
  stabilisation de Python et fera l’objet de suivis distincts. Cette dérogation
  est limitée à cette phase : la fonctionnalité ne sera pas déclarée stable et
  équivalente dans les trois langages avant la livraison des suivis .NET et
  Java.
- Réutiliser les adaptateurs et mappers existants lorsqu’ils conviennent;
  documenter la recherche de réutilisation lors du PLAN.
- L’inventaire des structures et événements pris en charge doit être rattaché
  à la spécification OpenAI de référence utilisée et vérifiable par des
  fixtures versionnées. Une évolution ultérieure de l’API ne doit pas modifier
  implicitement le contrat du runtime.
- Ne pas casser les payloads existants ni le comportement des autres surfaces.
- Respecter les budgets de performance existants : normalisation et dispatch
  sous 10 ms p95, pipeline hors exécution du handler sous 50 ms p95 et premier
  événement de streaming sous 300 ms p95, dans les conditions définies par le
  plan de la fonctionnalité 001.

## Critères d’acceptation

- Des tests de contrat couvrent les formes d’entrée, champs et options de
  l’opération de création Responses présents dans la spécification de référence.
- Les tests montrent que des contenus multimodaux et structurés traversent la
  normalisation Standard Exchange sans perte sémantique.
- Les réponses de succès structurées, les statuts non réussis et les champs
  optionnels applicables respectent le schéma Responses et sont analysables par
  le SDK OpenAI.
- Une fixture de conformité couvre chaque type d’événement Responses documenté
  dans la référence retenue. Les événements SSE émis ont le bon type, les champs
  requis, l’ordre et la terminaison.
- Les cas d’erreur et d’interruption de flux respectent le protocole et ne
  produisent pas de faux événement de succès terminal.
- Les tests de contrat et d’intégration Python couvrent les comportements
  Responses spécifiés. La parité .NET/Java est explicitement différée et ne
  constitue pas un critère de réussite de cette issue.
- Les tests existants des surfaces Chat Completions, Anthropic Messages,
  découverte, authentification et middleware restent compatibles.
- Les budgets de performance existants sont mesurés sur les nouveaux cas
  pertinents et ne sont pas dépassés.
- La documentation et un exemple Python indiquent comment activer
  `/v1/responses`, fournir des sorties structurées et consommer son flux SSE.

## Stratégie de test

- Ajouter d’abord des fixtures contractuelles basées sur le schéma officiel et
  des tests rouges pour la normalisation, les réponses structurées et chacun des
  types d’événements documentés.
- Ajouter des tests d’intégration Python pour les entrées simples, structurées
  et multimodales, les options de requête, les sorties structurées, les
  événements de streaming, les erreurs et les interruptions.
- Vérifier la conformité au moyen des modèles/types du SDK OpenAI lorsque le
  SDK est disponible dans les dépendances de développement; sinon, valider les
  mêmes fixtures contre le schéma versionné.
- Ajouter ou étendre les budgets de performance Responses Python.
- Exécuter les suites Python pertinentes, puis les contrôles configurés pour le
  package Python avant livraison.

## Risques

- La référence Responses évolue. Un inventaire non versionné pourrait changer
  silencieusement les comportements attendus entre versions du runtime.
- Les futures implémentations .NET et Java devront reprendre les contrats et
  fixtures stabilisés côté Python pour éviter une divergence de comportement.
- La représentation existante `chunk` / `completion` / `error` peut être trop
  limitée pour exprimer fidèlement le cycle de vie Responses; son évolution doit
  préserver la compatibilité des autres surfaces.
- Les données multimodales et les événements volumineux peuvent affecter la
  mémoire et la latence; les mesures doivent inclure des cas représentatifs.

## Questions ouvertes

- Aucune pour le périmètre décrit dans l’issue : cette SPEC traite l’opération
  `POST /v1/responses` et son streaming, les opérations Responses distinctes
  restant hors périmètre. L’implémentation .NET et Java est également différée
  jusqu’à la stabilisation de Python.
