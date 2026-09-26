# Specification

## Issue

#14 — Library documentation for Python

## Objectif

Provide a discoverable, practical documentation set for the capabilities of the
currently shipped Python runtime packages, connect it to runnable examples, and
make documentation maintenance part of the repository's agent guidance.

## Contexte

The repository currently has a high-level root README, feature specifications,
package metadata, and several Python examples. Those materials explain selected
parts of the runtime, but they do not provide one complete path for Python users
to choose and install a package, start a service, understand the available
features, and find the matching example.

The Python runtime is published as `ygo74-agent-runtime-security`,
`ygo74-agent-runtime-agents`, and `ygo74-agent-runtime-mcp`, with
`ygo74-agent-runtime` as a meta-package. The current packages cover security and
authentication, agent endpoints and discovery, routing and middleware,
conversation/session support, human approval, MCP client and server hosting,
and observability. The repository's agent entry points are `AGENTS.md` and
`.github/copilot-instructions.md`.

## Problème

Python developers must currently piece together installation steps, APIs,
configuration, endpoint behavior, and examples from package metadata, the
active feature specification, and separate example READMEs. There is no
maintained Python documentation entry point that explains the library as a
whole or maps its features to examples that can be run.

## Périmètre

- Add a central Python documentation guide under `docs/python/`, covering the
  shipped distributions and their installation extras, a quickstart, the
  currently supported endpoint and discovery surfaces, standard exchange and
  handler flow, routing and middleware, authentication and authorization,
  session and human-approval support, MCP client/server use, and observability.
- Explain key configuration choices and direct readers to the authoritative
  feature contracts and relevant reference examples rather than duplicating
  contract definitions.
- Add or revise runnable Python examples only where needed to demonstrate a
  documented capability that is not already covered. Link each documented
  workflow to its corresponding example and state its prerequisites.
- Link the root README and the relevant Python examples index to the new
  documentation.
- Update `AGENTS.md` and `.github/copilot-instructions.md` with a concise rule to
  update Python docs and their examples when public Python behavior, APIs,
  configuration, dependencies, or supported workflows change.
- Keep this documentation focused on the Python runtime as requested. Author it
  in English to match the existing repository documentation.

## Hors périmètre

- Writing .NET or Java library documentation; their documentation can be added
  after the Python runtime is ready for broader use cases.
- Changing library behavior, public APIs, packaging, dependencies, or feature
  contracts.
- Replacing the existing feature specification, package documentation, or
  example-specific walkthroughs with duplicate copies.
- Documenting internal implementation details as supported public APIs.

## Comportement attendu

1. A Python user can start at a single linked documentation entry point and
   identify the correct distribution and extras for the runtime they host.
2. The guide takes a user from installation to a working endpoint or MCP server
   and describes the current Python capabilities and important configuration
   choices.
3. Endpoint documentation covers OpenAI Chat Completions and Responses,
   Anthropic Messages, streaming, and agent discovery, with links to their
   authoritative contracts and runnable examples.
4. Security, handlers/contracts, middleware/routing, sessions/human approval,
   MCP, and observability are discoverable and each documented usage flow links
   to an example or explicitly identifies the lack of one.
5. Repository agent guidance requires relevant docs and examples to be updated
   along with public Python changes.

## Architecture concernée

- `docs/python/` (new Python library guide and navigation).
- `README.md` and `docs/examples/python-langchain-fastapi/README.md` (links into
  the guide).
- `docs/examples/python-langchain-fastapi/` and
  `docs/examples/python-mcp-server/` (existing executable workflows, updated
  only where needed).
- `AGENTS.md` and `.github/copilot-instructions.md` (documentation maintenance
  instructions).
- `packages/python/*/pyproject.toml` and
  `specs/001-openai-endpoint-exposure/` (reference sources, not design changes).

## Contraintes

- Treat package metadata and implemented Python behavior as authoritative for
  install commands and support claims; the package metadata currently requires
  Python 3.12 or newer.
- Keep endpoint contracts and provider wire details linked to the existing
  feature contracts; do not introduce different behavior through the docs.
- Preserve clear separation between the MCP client in the agents distribution
  and MCP server hosting in the MCP distribution.
- Documentation must distinguish implemented behavior from framework-specific
  example code and state external prerequisites such as credentials or services.
- This is documentation-only, so there is no cross-language implementation
  parity change. The developer-facing setup and behavior described for the
  Python packages must remain consistent across all linked guides and examples.
- No runtime performance target applies to this documentation change; there
  must be no runtime performance impact.

## Critères d'acceptation

- A Python documentation landing page covers all currently shipped Python
  distributions and the user-facing capabilities they provide.
- Installation commands reflect the package names, extras, and Python version
  declared by the package metadata.
- A new user can follow a quickstart to start and call an endpoint-backed Python
  example, with matching links for other documented workflows.
- Each documented user-facing workflow links to a runnable example or clearly
  identifies that no example currently exists; no claim is made that an
  unverified example is runnable.
- The root README and Python examples index link to the central guide.
- Both repository agent guidance entry points require documentation and example
  updates for relevant public Python changes.
- Documentation links resolve, command snippets are checked against their
  referenced files, and the docs diff has no whitespace errors.
- No executable runtime, package metadata, or feature contract behavior changes.

## Stratégie de test

- Review package names, extras, and Python version against all four Python
  `pyproject.toml` files.
- Check internal documentation links and referenced example paths.
- Follow the documented quickstart and smoke-check at least one endpoint example;
  check additional example-specific setup and commands against their source and
  requirements files.
- Review both agent guidance files for a clear, consistent docs-maintenance
  instruction.
- Run `git diff --check`; no runtime test changes are expected unless review
  finds a behavior change.

## Risques

- The runtime spans several distributions and feature domains; missing a
  distribution or presenting an optional extra as required could mislead users.
  Mitigate this with an inventory cross-check against package metadata and the
  implemented Python package tree.
- Existing example commands or dependency requirements may have drifted from
  the source. Check links and run the selected quickstart before describing it
  as working.
- Documentation can drift as the public API changes. Requiring updates in both
  repository agent entry points makes the maintenance expectation visible.

## Questions ouvertes

- None. The scope is the currently shipped Python packages and their existing
  user-facing behavior; other language documentation remains out of scope.

## Addendum — dedicated agent discovery topic

### Contexte de la demande

The initial Python guide gives discovery a short overview and points to a
descriptor walkthrough stored under the LangChain example directory. The
requester asked for documentation organized by topic, starting with how to
describe an agent and expose it through OpenAI's `GET /v1/models` endpoint.

### Périmètre complémentaire

- Add a first-class topic page at `docs/python/agent-discovery.md`, indexed from
  `docs/python/README.md` and linked from the discovery section of
  `docs/python/agent-runtime.md`.
- Consolidate the existing
  `docs/examples/python-langchain-fastapi/agent-descriptor.md` walkthrough into
  that canonical page; retain the old example path as a short link so existing
  references continue to work.
- Explain the provider-neutral `AgentDescriptor` and the purpose of its
  required and optional fields, with particular emphasis on the public
  `agent_id`, private `route_key`, capabilities, skills, visibility, and keeping
  secrets out of public metadata.
- Show how to instantiate a descriptor and capability/skill records, register
  them with `DescriptorRegistry`, and enable OpenAI model discovery using
  `DiscoveryConfiguration` through both supported registration paths:
  `add_ai_endpoints` when adding discovery alongside invocation endpoints, and
  `add_discovery_endpoints` when registering discovery routes directly.
- Explain the arguments and effect of `add_discovery_endpoints`, including that
  it registers the enabled model-listing and model-detail routes covered by
  this topic, and can receive the authenticator and `AgentAccessPolicy` used to
  protect/filter discovery. Explain that
  `add_ai_endpoints` delegates to this method only when both a descriptor
  registry and discovery configuration are supplied.
- Show requests and representative responses for `GET /v1/models` and
  `GET /v1/models/{agent_id}`, explain how a listed `id` is reused as the
  invocation `model`, and describe stable ordering, exact identifier matching,
  hidden entries, and access-policy filtering as implemented.
- Explain which OpenAI-native model fields are returned and where the runtime's
  additional description and capability data appear, while stating that
  `route_key` is never published.
- Link back to the descriptor schema, the endpoint contract, the runnable
  example, and the authorization guide. Keep Anthropic model discovery and the
  A2A card protocol details out of this first topic; note only that they share
  the provider-neutral descriptor and can have dedicated topics later.

### Hors périmètre complémentaire

- No changes to runtime code, endpoint behavior, descriptor schema, or package
  metadata.
- No new runnable application or test suite; the page documents the existing
  API and links to its existing example. Documentation claims and snippets must
  be checked against current source and tests.

### Critères d'acceptation complémentaires

- A reader can understand the difference between the advertised `agent_id`
  and internal `route_key`, construct a valid descriptor, and enable the
  OpenAI model listing without inferring missing registration steps. The page
  distinguishes registering discovery through `add_ai_endpoints` from calling
  `add_discovery_endpoints` directly.
- The page shows the shape and meaning of both list and single-model responses,
  including the `x-agent-runtime` extension, and demonstrates how to pass the
  listed ID to an invocation endpoint.
- The page describes opt-in registration and the actual hidden-agent and
  access-policy behavior without implying that discovery visibility is
  invocation authorization.
- The central Python docs link to the new topic, and existing links to the
  example-level descriptor guide continue to resolve.
- All code, field names, paths, and response details match the implementation
  and contract; internal links resolve and `git diff --check` passes.

### Décisions et questions ouvertes

- Keep English as the documentation language, consistent with issue 14 and
  existing Python guides.
- Use `docs/python/agent-discovery.md` as the canonical location, rather than
  expanding the current example-specific page in place, so the topic is
  discoverable independently of a particular agent integration.
- None.
