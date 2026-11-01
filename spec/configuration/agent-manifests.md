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

## Optional HTTP hosting declaration

`agent.yaml` may include an `http` section for Python FastAPI hosting. It
selects a non-empty, duplicate-free set of invocation surfaces (`chat_completions`,
`responses`, and/or `messages`), requires one explicit `jwt` or `api_key`
authentication configuration, and may declare per-client rate limits. Existing
manifests without this section remain valid for command-line, MCP, and other
non-HTTP uses.

The section is structurally validated with the rest of the manifest, but its
secret references are resolved only when an application constructs an HTTP
host through `AgentHttpSettingsBuilder`. Thus loading the same manifest for a
non-HTTP use does not require its HTTP credentials. API keys and static JWT
key material must be complete `${VARIABLE_NAME}` references. JWT configuration
uses the existing validator and supports a direct JWKS URL, issuer-based OIDC
discovery, or one static symmetric/public key source. API-key configuration
declares the authenticated service identity; a subject is required and email,
username, and display name are optional.

Rate limits are optional and apply to each enabled invocation route using the
client address observed by FastAPI. Without a storage URI, counters are local to
the process; supported Redis URIs allow workers to share counters. Client
forwarding headers are not trusted by this configuration. An omitted route
remains unregistered, and a request to it receives the host's normal 404. Limit
exhaustion returns 429 before the agent handler runs. Host-owned authentication
and storage resources are closed through the ASGI application lifecycle.

The HTTP declaration is converted into the runtime's existing authentication,
route, and rate-limit settings rather than creating a separate authorization
system. See [provider invocation surfaces](../endpoints/provider-surfaces.md),
[managed native-agent workers](../endpoints/managed-agent-worker.md), and the
[packaging and operations specification](../operations/packaging-configuration-observability.md).

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
