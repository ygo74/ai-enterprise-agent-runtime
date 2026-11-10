# Python Solution Architect — ai-enterprise-agent-runtime

Load for plans affecting `packages/python/`, Python APIs, Python examples, or
Python-only runtime behavior.

- Preserve domain-oriented modules and the existing public package layout under
  `ygo74.agent_runtime`; inspect neighboring domain and test patterns first.
- Apply Clean Architecture / Onion Architecture: domain and application policy
  stay independent of frameworks, transports, databases, and vendor SDKs;
  outer adapters implement inner ports, and the composition root injects the
  selected implementations.
- Reuse shared contracts and abstractions when Python, .NET, and Java
  implementations must behave alike. Define Python `Protocol` boundaries for
  interchangeable implementations and select implementations at composition
  time.
- Have each concrete Python adapter explicitly inherit the `Protocol` it
  implements so the relationship is visible to readers and type checkers.
- Model structured values with dataclasses, `NamedTuple`, or validated models;
  use enums for finite values. Convert untyped wire payloads at the boundary.
- For state retained beyond one operation, plan an injected storage port, an
  in-memory development/test adapter, and a PostgreSQL or Redis production
  adapter selected by configuration. Decide partitioning, concurrency,
  retention, and durability from the feature's data needs; identify
  process-local caches separately.
- Keep asynchronous I/O asynchronous, dependencies explicit, configuration
  validated at startup, and errors mapped consistently to the language-neutral
  contract.
- Prefer small cohesive classes, typed methods, early exits, and minimal
  dependencies. Reuse existing runtime primitives before creating new ones.
- Plan unit and contract tests first, then relevant integration, parity, and
  performance checks. Update runnable LangChain/FastAPI examples and docs when
  public behavior changes.
- Consult `.github/instructions/python.instructions.md` for code changes while
  it exists as a tooling adapter; durable rules live in repository instructions
  and this role reference.
