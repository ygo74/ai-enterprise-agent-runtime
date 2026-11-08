# .NET Solution Architect — ai-enterprise-agent-runtime

Load for plans affecting `packages/dotnet/`, public .NET APIs, or .NET samples.

- Preserve the existing package, namespace, dependency-injection, options, and
  hosting patterns. Inspect neighboring projects and supported target
  frameworks before choosing APIs.
- Apply Clean Architecture / Onion Architecture: domain and application policy
  remain independent of ASP.NET Core, agent frameworks, persistence providers,
  and vendor SDKs. Keep adapters and infrastructure outside those layers and
  compose them through the existing DI container.
- Define interfaces at replaceable infrastructure/application boundaries and
  inject concrete adapters through constructors or the established host DI
  registration. Keep interface implementations explicit on their class
  declarations.
- For state retained beyond one operation, plan an in-memory development
  adapter and a PostgreSQL or Redis production adapter selected by
  configuration behind an interface. Decide concurrency, retention, and
  durability from the data contract; document limits for process-local caches.
- Keep cross-language contracts explicit and align defaults, validation,
  errors, streaming, and observable behavior with Python and Java.
- Represent domain data as records or classes and finite values as enums.
  Keep wire serialization at endpoint boundaries and expose typed public APIs.
- Reuse Microsoft Agent Framework and ASP.NET Core abstractions already used by
  the repository; avoid custom containers or wrappers without a demonstrated
  gap.
- Prefer small services with clear DI lifetimes, early returns, cancellation
  propagation, and standard `ILogger`/OpenTelemetry integration.
- Plan failing contract/unit tests before implementation, then relevant
  integration, parity, and performance checks. Update runnable Microsoft
  Agent Framework samples and docs when public behavior changes.
