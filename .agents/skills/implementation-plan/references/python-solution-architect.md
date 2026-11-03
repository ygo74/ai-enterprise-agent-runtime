# Python Solution Architect — ai-enterprise-agent-runtime

Load for plans affecting `packages/python/`, Python APIs, Python examples, or
Python-only runtime behavior.

- Preserve domain-oriented modules and the existing public package layout under
  `ygo74.agent_runtime`; inspect neighboring domain and test patterns first.
- Reuse shared contracts and abstractions when Python, .NET, and Java
  implementations must behave alike. Define Python `Protocol` boundaries for
  interchangeable implementations and select implementations at composition
  time.
- Model structured values with dataclasses, `NamedTuple`, or validated models;
  use enums for finite values. Convert untyped wire payloads at the boundary.
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
