# Delivered agent manifests

## Why manifests exist

An agent package needs to describe its identity and the capabilities it offers
without letting deployment data import or construct arbitrary Python code.
Versioned manifests keep this delivered description stable while the
application composition root binds it to code-owned skills and policies.

## Inputs and loading

The Python `configuration` extra loads delivered configuration. An application
may select its root with `YGO74_AGENT_RUNTIME_CONFIG_DIR`; otherwise the loader
uses `config` below the selected base directory. `.env` loading is optional and
never replaces a value already set in the process environment.

Each agent has an `agent.yaml` manifest and a separate non-empty `AGENT.md`
instruction file. The manifest declares a name, description, and ordered skill
names. Each declared skill package has `skill.yaml`; it declares a tool name,
implementation identifier, model-facing description, security operation,
permission name, confirmation default, and optional logical MCP tool names. A
separate `SKILL.md` can provide reasoning instructions; a deterministic skill
may omit it.

The loader rejects missing files, invalid YAML shapes, unknown fields, and
invalid typed values. A malformed or missing declared skill fails the agent
load; the runtime does not silently drop it. The fixed Draft 2020-12 schemas
are packaged with the Python distribution under stable identifiers:

- `urn:ygo74:agent-runtime:agent-manifest:1`
- `urn:ygo74:agent-runtime:skill-manifest:1`

## Structural validation and security checks

Schema validation describes the accepted file shape. It does not grant a
permission or prove that a declared operation is safe. The application resolves
permission names against its `PermissionRegistry`, binds the manifest to
implemented skills, and enforces its code-owned `SecurityFloor`. A permission
that is unknown or an operation below the security floor fails during loading.
The model cannot change these decisions by editing its answer.

`AGENT.md` and `SKILL.md` are trusted delivered inputs, not manifest-schema
fields. They must be controlled as deployment configuration. Content returned
from tools remains untrusted and is fenced separately before reasoning.

## Compatibility and acceptance

The manifest shape is a versioned Python public contract. A structural change
updates the typed input models, packaged schemas, schema identifiers when
needed, and documentation together. It does not change the responsibility of
the application to provide code, permissions, domain validation, or tool
authorization.

An accepted configuration has both manifests in the documented schema, every
declared skill resolves to a delivered package and implementation, every
permission resolves in the application registry, and every operation meets the
security floor. Configuration loading does not require FastAPI or the MCP SDK.

See the [configuration guide](../../doc/python/agent-runtime.md#delivered-agent-configuration),
the [`configuration` package](../../packages/python/agents/ygo74/agent_runtime/domains/configuration/),
and [`test_manifest_configuration_schemas.py`](../../tests/integration/python/test_manifest_configuration_schemas.py).
