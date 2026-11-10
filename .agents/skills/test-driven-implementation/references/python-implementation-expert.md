# Python Implementation Expert — ai-enterprise-agent-runtime

- Follow the package's Python version, strict type-checking, formatting, and
  testing configuration. Read the Python repository instructions for code
  changes.
- Use typed classes/models and protocols, async APIs for async I/O, explicit
  error types, and standard logging. Keep public APIs aligned with the
  cross-language contract.
- Make each Protocol implementation explicit in the class declaration (for
  example, `class RedisConversationStore(ConversationStore):`) rather than
  relying only on structural conformance. Inject these ports through
  constructors and select adapters in the composition root.
- When retaining state beyond one operation, keep an in-memory adapter for
  development and deterministic tests, plus a PostgreSQL or Redis production
  adapter selected by configuration.
- Document every class and method, including each argument. For non-trivial
  methods, add concise comments inside the body that explain the algorithm's
  stages, ordering, and invariants. Do not add comments that only restate simple
  statements or forwarding behavior.
- Prefer existing domain classes and helpers; avoid raw dictionaries except for
  true key/value data or unparsed boundary payloads.
- Add tests first and use deterministic fakes. Update a runnable LangChain and
  FastAPI example when public usage changes.
