# .NET Implementation Expert — ai-enterprise-agent-runtime

- Follow the solution's supported target frameworks, nullable settings,
  analyzers, formatter, and test conventions.
- Use typed records/classes, enums, cancellation tokens, constructor
  injection, and standard logging. Preserve ASP.NET Core and Microsoft Agent
  Framework APIs already in use.
- Declare interface implementations explicitly on concrete classes and inject
  the interfaces at composition boundaries. For state retained beyond one
  operation, use an in-memory development/test adapter and a PostgreSQL or
  Redis production adapter selected by configuration.
- Document every class and method, including its purpose and arguments, using
  the repository's standard .NET documentation form. In every non-trivial
  method, put concise comments in the body to explain algorithm stages,
  ordering, and invariants; avoid line-by-line narration of obvious code.
- Keep wire mapping at boundaries and align status, error, and configuration
  behavior with the shared contract. Prefer focused tests and deterministic
  fakes.
- Update a runnable Microsoft Agent Framework example when public usage changes.
