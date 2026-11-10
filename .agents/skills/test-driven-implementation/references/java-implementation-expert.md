# Java Implementation Expert — ai-enterprise-agent-runtime

- Follow the configured JDK, Maven/Gradle conventions, compiler checks, and
  tests for the affected module.
- Use typed records/classes, enums, constructor injection, and existing Spring
  Boot/Spring AI APIs. Keep transport conversion at the boundary and use
  standard SLF4J/Micrometer instrumentation.
- Declare each concrete implementation with `implements` and inject interfaces
  from the composition boundary. For state retained beyond one operation, use
  an in-memory development/test adapter and a PostgreSQL or Redis production
  adapter selected by configuration.
- Document every class and method, including its purpose and arguments, using
  the repository's standard Java documentation form. In every non-trivial
  method, put concise comments in the body to explain algorithm stages,
  ordering, and invariants; avoid line-by-line narration of obvious code.
- Add focused failing tests first, use deterministic fixtures, preserve
  language-neutral contract behavior, and update a runnable Spring AI example
  when public usage changes.
