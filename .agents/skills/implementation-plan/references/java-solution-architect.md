# Java Solution Architect — ai-enterprise-agent-runtime

Load for plans affecting `packages/java/`, public Java APIs, or Java samples.

- Preserve existing package boundaries, supported JDK, Spring Boot setup, and
  build conventions. Inspect neighboring modules before selecting dependencies
  or APIs.
- Apply Clean Architecture / Onion Architecture: domain and application policy
  stay independent of Spring, agent frameworks, persistence providers, and
  vendor SDKs. Keep adapters and infrastructure outside those layers and wire
  them from the composition/configuration boundary.
- Define interfaces at replaceable boundaries, declare each implementing class
  with `implements`, and inject collaborators through constructors or the
  existing Spring configuration. Avoid service locators and hidden globals.
- For state retained beyond one operation, plan an in-memory development
  adapter and a PostgreSQL or Redis production adapter selected by
  configuration behind an interface. Choose based on durability, query, and
  concurrency needs; document limits for process-local caches.
- Keep contracts language-neutral and behavior aligned with Python and .NET,
  including configuration defaults, validation, errors, streaming, and
  observable effects.
- Use records/classes for structured data and enums for finite value sets.
  Parse transport payloads into typed objects at the boundary.
- Reuse Spring Boot, Spring AI, and existing project abstractions. Keep
  constructor injection explicit, boundaries domain-oriented, and dependencies
  acyclic.
- Prefer focused classes, early exits, standard SLF4J/Micrometer observability,
  and propagated cancellation/timeouts where supported.
- Plan tests before implementation, including contract/parity and relevant
  integration/performance checks. Keep runnable Spring AI/Spring Boot samples
  and documentation aligned with public behavior.
