# Delivered configuration

The optional `configuration` extra owns configuration-directory resolution,
`.env` loading, typed `agent.yaml` and `skill.yaml` models, and packaged JSON
Schemas. The `ConfigurationDirectory` is passed to the loaders so applications
can select an explicit root. Agent and skill Markdown instructions are loaded
as separate inputs; they are not validated by the YAML schemas.

```mermaid
classDiagram
    class ConfigurationDirectory
    class AgentManifestLoader
    class SkillManifestLoader
    class AgentManifest
    class SkillManifest
    AgentManifestLoader --> ConfigurationDirectory : reads files
    SkillManifestLoader --> ConfigurationDirectory : reads files
    AgentManifestLoader --> AgentManifest : returns validated model
    SkillManifestLoader --> SkillManifest : returns validated model
```

```mermaid
sequenceDiagram
    participant App as Application composition
    participant Dir as ConfigurationDirectory
    participant Loader as Manifest loader
    participant Model as Typed manifest model
    App->>Dir: resolve configured root
    Dir->>Loader: locate YAML and Markdown inputs
    Loader->>Model: parse and validate YAML structure
    Model-->>App: validated manifest
```

Keep unknown-field rejection and schema identifiers in sync with typed models.
Semantic checks, such as matching a permission to an application's
`PermissionRegistry` or enforcing its security floor, remain outside structural
schema validation.

Source: [`domains/configuration`](../../packages/python/agents/ygo74/agent_runtime/domains/configuration/).
Tests: [manifest configuration schemas](../../tests/integration/python/test_manifest_configuration_schemas.py)
and [descriptor validation](../../tests/integration/python/test_descriptor_validation.py).

See the [manifest specification](../../spec/configuration/agent-manifests.md)
and [Python configuration guide](../../doc/python/README.md).
