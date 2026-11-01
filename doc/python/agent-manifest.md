# Agent manifest (`agent.yaml`) reference

The `configuration` extra loads `agent.yaml` as a strict, typed manifest. The
packaged [Draft 2020-12 JSON Schema](../../packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/agent.schema.json)
describes the accepted keys and structural types. Unknown keys are rejected.
The runtime also checks semantic combinations, such as matching the selected
authentication mode to its settings and matching JWT algorithms to their key
source.

## Select the manifest file

`AgentManifestLoader.load(agent)` reads
`<configuration root>/agents/<agent>/agent.yaml` by default. Set the process
variable `AGENT_MANIFEST_FILENAME` to select another YAML file in the same folder:

```powershell
$env:AGENT_MANIFEST_FILENAME = "agent.local.yaml"
```

Create `agent.local.yaml` beside the existing `agent.yaml` before calling the
loader. Both files use the same schema. The loader reads this variable on each
call; absent, empty, or whitespace-only values keep the default `agent.yaml`.
Instructions still come from `AGENT.md`, and skill packages still come from
`<configuration root>/skills/<agent>/`. The existing
`YGO74_AGENT_RUNTIME_CONFIG_DIR` variable selects the configuration root.
A missing or invalid selected file raises `ConfigurationError`; there is no
fallback to another manifest.

The caller chooses the `agent` argument. For example, an application can read
`AGENT_CONFIG_SUBDIR` and pass its value to `load`; the runtime does not interpret
that application-specific selector itself.

## Top-level keys

| Key | Type | Required | Description |
|---|---|---:|---|
| `name` | non-empty string | Yes | Agent name. |
| `description` | non-empty string | Yes | Description of the agent. |
| `mcp_server` | non-empty string or `null` | No | Default MCP server name inherited by MCP-enabled skills that do not select their own server. Omit it when there is no default. |
| `skills` | array of non-empty strings | Yes | Skill names included in the agent. It must contain at least one entry. |
| `http` | object or `null` | No | Optional FastAPI invocation, authentication, and rate-limit settings. Omit it when the manifest is not used to configure an HTTP host. |

## `http` keys

| Key | Type | Required | Description |
|---|---|---:|---|
| `http.endpoints` | array of strings | Yes, when `http` is set | One or more endpoint names: `chat_completions`, `responses`, or `messages`. These enable `POST /v1/chat/completions`, `POST /v1/responses`, and `POST /v1/messages`, respectively. |
| `http.security` | object | Yes, when `http` is set | Authentication settings applied to every enabled invocation endpoint. |
| `http.rate_limit` | object or `null` | No | Optional per-client rate limits. If omitted, rate limiting is disabled. |

### `http.security`

| Key | Type | Required | Description |
|---|---|---:|---|
| `http.security.mode` | string: `jwt` or `api_key` | Yes | Selects the one authentication configuration to use. |
| `http.security.jwt` | object or `null` | Required when `mode: jwt` | JWT validation and key-source settings. It must be omitted for `mode: api_key`. |
| `http.security.api_key` | object or `null` | Required when `mode: api_key` | One API key and its fixed service identity. It must be omitted for `mode: jwt`. |

#### `http.security.jwt`

| Key | Type | Default | Description |
|---|---|---|---|
| `allowed_algorithms` | array of strings | `["HS256"]` | Allowed values are `HS256`, `HS384`, `HS512`, `RS256`, `RS384`, `RS512`, `ES256`, `ES384`, `ES512`, `PS256`, `PS384`, `PS512`, and `EdDSA`. The algorithm family must match the configured key source. |
| `required_claims` | array of strings | `["sub"]` | Claims that every token must contain. The list must not be empty or contain duplicates. |
| `issuer` | string or `null` | `null` | Expected token issuer. When no `jwks_url`, `secret`, or `public_key` is set, this issuer is used for OIDC discovery and is required. Use an HTTPS issuer URL. |
| `audience` | string, array of strings, or `null` | `null` | Expected token audience. |
| `leeway_seconds` | non-negative integer | `0` | Clock-skew allowance for token time claims. |
| `roles_claim_path` | string or `null` | `null` | Dotted claim path from which roles are read, for example `realm_access.roles`. |
| `groups_claim_path` | string or `null` | `null` | Dotted claim path from which groups are read. |
| `jwks_url` | string or `null` | `null` | Direct HTTPS URL for a JWKS document. Use asymmetric algorithms. Set at most one key source among `jwks_url`, `secret`, and `public_key`. |
| `secret` | environment-variable reference or `null` | `null` | Static symmetric signing secret, written as a complete reference such as `${JWT_SECRET}`. Use HMAC algorithms. Never put the secret itself in YAML. |
| `public_key` | environment-variable reference or `null` | `null` | Static public signing key, written as a complete reference such as `${JWT_PUBLIC_KEY}`. Use asymmetric algorithms. Never put key material itself in YAML. |

When using OIDC discovery, set `issuer` and leave `jwks_url`, `secret`, and
`public_key` unset. With a direct JWKS URL or a static key, `issuer` is optional
and, when supplied, is still checked against the token.

#### `http.security.api_key`

| Key | Type | Required | Default | Description |
|---|---|---:|---|---|
| `value` | environment-variable reference | Yes | — | API key reference, for example `${MAIL_HTTP_API_KEY}`. A raw key is not accepted in the manifest. |
| `header_name` | non-empty string | No | `X-API-Key` | Valid HTTP header name that carries the API key. |
| `user` | object | Yes | — | Fixed identity attached to an accepted key. |

`http.security.api_key.user` accepts these keys:

| Key | Type | Required | Description |
|---|---|---:|---|
| `subject` | non-empty string | Yes | Stable subject identifier for the authenticated service identity. |
| `email` | non-empty string or `null` | No | Email address associated with the service identity. |
| `username` | non-empty string or `null` | No | Username associated with the service identity. |
| `name` | non-empty string or `null` | No | Display name associated with the service identity. |

#### `http.rate_limit`

| Key | Type | Required | Description |
|---|---|---:|---|
| `limits` | array of strings | Yes, when `rate_limit` is set | One or more limits in the form `<positive integer>/<period>`, where period is `second`, `minute`, `hour`, `day`, `month`, or `year`; for example, `[60/minute]`. |
| `storage_uri` | URI, environment-variable reference, or `null` | No | Omit it to keep counters in process memory. Supported URI schemes are `redis://`, `rediss://`, and `memory://`. An environment reference such as `${HTTP_LIMIT_STORAGE_URI}` can hold a Redis URI. |

Use environment references in the exact form `${VARIABLE_NAME}` for API keys,
JWT key material, and storage URIs containing credentials. Load the values into
the process environment before constructing the HTTP host. Manifest loading for
CLI or MCP use leaves HTTP references unresolved.

## Validate `agent.yaml` in VS Code

Install the [YAML extension by Red Hat](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
(`redhat.vscode-yaml`). In the application repository, create or edit
`.vscode/settings.json` and associate the manifest schema with the agent
manifest paths:

```json
{
  "yaml.schemas": {
    "https://raw.githubusercontent.com/ygo74/ai-enterprise-agent-runtime/main/packages/python/agents/ygo74/agent_runtime/domains/configuration/schemas/agent.schema.json": [
      "config/agents/**/agent.yaml"
    ]
  }
}
```

Change the glob if your manifests live elsewhere. After the schema is available
on `main`, this setting makes VS Code validate matching files as they are
edited. For a stable schema that matches a released runtime, replace `main` in
the URL with the release tag that contains the schema.

The runtime repository's samples use the equivalent per-file
`yaml-language-server` comment and a relative path to the packaged schema. A
workspace setting is usually easier for an application repository because it
does not require adding a schema comment to every manifest. The editor checks
the JSON Schema's structural constraints; loading the manifest in the runtime
also enforces semantic rules such as JWT key-source and algorithm compatibility.

## Example

This API-key example combines route selection, an environment reference, a
service identity, and an in-memory per-client limit:

```yaml
name: mail-assistant
description: Answers questions about a mailbox.
mcp_server: mail
skills:
  - find_mail
  - send_mail
http:
  endpoints: [chat_completions, responses]
  security:
    mode: api_key
    api_key:
      value: ${MAIL_HTTP_API_KEY}
      user:
        subject: mail-assistant-service
        email: mailbox@example.test
  rate_limit:
    limits: [60/minute]
```
