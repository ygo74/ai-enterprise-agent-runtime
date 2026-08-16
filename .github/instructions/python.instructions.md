---
applyTo: '**/*.py'
description: Python coding conventions for the agent runtime libraries and examples.
---

# Python conventions

Write Python the way a .NET developer expects to read it: explicit types,
cohesive classes, and named value sets instead of loose primitives.

## Classes over scattered functions

- Group related behavior in a class. Do not spread free-standing helper
  functions that share a concern across a module.
- A module should expose a small number of named types, not a bag of functions.
- Module-level functions are acceptable only for pure, stateless, single-purpose
  utilities that belong to no type.
- Prefer constructor injection of collaborators over module-level globals.

## Typed data, never bare dictionaries

- Model structured data with `@dataclass(slots=True)`, `NamedTuple`, or a
  Pydantic model. Do not pass `dict[str, Any]` around as an ad-hoc record.
- `dict` is acceptable only for genuine key/value collections (lookups, caches,
  raw wire payloads at the system boundary) — never as a substitute for a type.
- Convert wire payloads into typed objects at the boundary, and back to `dict`
  only when serializing out (`to_dict()` / model dump).
- Annotate every parameter, return value, and attribute. Code must be clean
  under Pylance strict mode.

## Enums for fixed text values

- When a property accepts several fixed text values, define an `Enum` or
  `StrEnum` instead of comparing string literals.
- Use `StrEnum` when the value must serialize as a plain string on the wire.
- Do not scatter literal strings such as `"jwt"` or `"api_key"` across modules;
  reference the enum member.

## Contracts between interchangeable implementations

- Define shared contracts with `typing.Protocol`, adding `@runtime_checkable`
  only when an `isinstance` check is genuinely needed at a boundary.
- Select the concrete implementation at runtime from the incoming data rather
  than branching on flags inside one large class.

## Control flow

- Use early returns and guard clauses; keep nesting shallow.
- Raise domain-specific exceptions instead of returning sentinel values.
- Validate developer-supplied hook results at the boundary before trusting them.

## Reuse first

- Before adding a class or module, search for an existing one to extend.
- Keep methods small and single-purpose, consistent with the project
  constitution (DRY, SOLID, early-leave).
