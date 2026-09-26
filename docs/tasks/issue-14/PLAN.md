# Implementation Plan

## Issue

#14 — Library documentation for Python

## Specification

./SPEC.md

## Objectif

Create a navigable Python documentation guide for all currently shipped Python
distributions and their user-facing capabilities. Connect each workflow to the
existing examples, make the installation and quickstart instructions practical,
and require both repository agent instruction entry points to maintain these
docs as the Python API evolves.

## Préconditions

- [x] SPEC approved by the requester.
- [x] Repository is `/data/repos/ai-enterprise-agent-runtime` and was clean on
  `main` when the SPEC was created.
- [x] Package metadata, current Python source layout, README, existing guides,
  examples, and agent instruction files have been reviewed.
- [x] PLAN approved by the requester.

## Étapes

### Étape 1 — Add the Python documentation landing page and installation guide

**Objectif :** Give Python users a clear entry point and help them choose the
smallest suitable distribution and optional extras.

**Fichiers/composants :**

- `docs/python/README.md` (new landing page and documentation map)
- `docs/python/installation.md` (new package selection and installation guide)
- Reference only: `packages/python/{meta,agents,security,mcpserver}/pyproject.toml`

**Modifications :**

- Describe the roles and dependency boundaries of the security, agents, MCP
  server, and meta distributions.
- Document Python 3.12+, the `http`, `mcp`, and `mcp-server` extras where
  applicable, virtual environment setup, and editable installs for repository
  contributors using the actual package metadata.
- Provide a capability map that links readers to the agent runtime, security,
  MCP, and existing detailed guides.
- Distinguish the MCP client shipped with the agents distribution from MCP
  server hosting shipped with the MCP distribution.

**Validation :**

- Cross-check distribution names, version floor, dependency descriptions, and
  extra names against each `pyproject.toml`.
- Verify landing page links target pages and files present in the repository.

### Étape 2 — Document agent hosting and runtime capabilities

**Objectif :** Explain the Python agent developer path from configuration and
request handling through discovery and operational extensions.

**Fichiers/composants :**

- `docs/python/quickstart.md` (new end-to-end path linked to a runnable example)
- `docs/python/agent-runtime.md` (new capability and key API guide)
- `docs/examples/python-fastapi-quickstart/` (new local echo example)
- Reference/update as needed: `docs/examples/python-langchain-fastapi/README.md`
  and the existing `01-get-started` / `04-human-in-the-loop` examples
- Reference only: Python `configuration`, `contracts`, `endpoints`, `handlers`,
  `routing`, `middleware`, `discovery`, `sessions`, `humanapproval`, and
  `observability` domains

**Modifications :**

- Cover FastAPI endpoint registration and configuration for Chat Completions,
  Responses, Anthropic Messages, streaming, and discovery/model listing.
- Explain `StandardExchangeRequest` / `StandardExchangeResponse`, handler
  registration and route selection, middleware order, and the separation of
  transport mapping from business logic.
- Summarize descriptors, capabilities, discovery visibility/access, session
  behavior, human approval, and logging/OpenTelemetry entry points; link to the
  existing descriptor, configuration, authorization, and human-approval
  examples for details.
- Make the quickstart lead to a local FastAPI example, state all prerequisites,
  and provide requests that exercise the documented endpoint surfaces.
- Add a small echo example that exposes the three supported endpoint families
  without an external LLM or credential, so newcomers can exercise the runtime
  and the documentation has a local smoke-check target.
- Correct existing LangChain examples' source paths and environment-file
  instructions where review finds them inconsistent with their code.
- Avoid repeating provider wire schemas; link to the canonical feature
  contracts and quickstart validation guide.

**Validation :**

- Verify every API name and option against the implemented Python source and
  the active feature contract.
- Check quickstart commands and environment variables against the referenced
  example files.
- Run the selected quickstart smoke check if its documented credentials and
  external services are available; otherwise record the exact limitation and
  validate the local setup commands and request against the example source.

### Étape 3 — Document security and MCP use

**Objectif :** Make the remaining Python distribution capabilities discoverable
without duplicating the existing detailed hosting walkthroughs.

**Fichiers/composants :**

- `docs/python/security.md` (new package and authentication/security guide)
- `docs/python/mcp.md` (new MCP client/server guide)
- References: `docs/examples/python-langchain-fastapi/authorization.md`,
  `docs/examples/python-langchain-fastapi/02-jwt-authentication/`,
  `docs/examples/python-langchain-fastapi/03-jwt-oidc-keycloak/`,
  `docs/examples/python-mcp-server/README.md`, and `docs/mcp-server-hosting.md`
- Reference only: `packages/python/security/` and the Python `mcp` and
  `mcpserver` domains

**Modifications :**

- Document anonymous, API key, JWT/OIDC authentication setup, caller context,
  developer-owned authorization, and the security package's permission,
  operation classification, audit, and untrusted-content domains.
- Describe MCP client bindings/transports and MCP server hosting modes, their
  package ownership, optional dependencies, authentication, health/metadata
  surfaces, and key host requirements.
- Link to detailed existing examples and identify their prerequisites rather
  than copying complete examples into the new guide.
- Make the two JWT examples load their documented `.env` files and declare the
  `python-dotenv` dependency used for that behavior.
- Mark capabilities with no runnable example as such instead of implying they
  have been demonstrated by an example.

**Validation :**

- Verify names, configuration fields, install extras, and behavior against
  source, package metadata, and the linked detailed guides.
- Check all links and shell commands against their target example files.
- Smoke-check the local MCP server example using its documented non-secret
  development mode if feasible; do not contact a production service or use
  real credentials.

### Étape 4 — Link the documentation and add the maintenance rule

**Objectif :** Make the new guide easy to find and keep it in the normal Python
change workflow.

**Fichiers/composants :**

- `README.md`
- `docs/examples/README.md`
- `docs/examples/python-langchain-fastapi/README.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.gitignore` (allow safe, tracked `.env.sample` templates under the existing
  environment-file ignore rule)

**Modifications :**

- Add concise links to the Python docs landing page from the root README and
  the general and Python example indexes.
- Add a concise instruction in both agent guidance entry points to update
  Python user docs and the related runnable examples whenever public Python
  behavior, APIs, configuration, dependencies, or supported workflows change.
- Point to `docs/python/README.md` as the current documentation source instead
  of copying documentation requirements or feature details into the agent
  instructions.

**Validation :**

- Confirm each new entry point link resolves.
- Review both instructions for consistent wording and fit with their existing
  repository guidance.

### Étape 5 — Documentation and example review

**Objectif :** Confirm the documentation is internally consistent, navigable,
and accurately tied to examples and current implementation.

**Fichiers/composants :**

- All files created or changed in Steps 1–4
- `docs/tasks/issue-14/SPEC.md` and `docs/tasks/issue-14/PLAN.md`

**Modifications :**

- Resolve findings from link, command, install metadata, example, and source
  reviews within the approved documentation scope.
- Keep issue SPEC and PLAN aligned with the delivered files and actual
  validation evidence.

**Validation :**

- Check internal Markdown links and referenced paths.
- Verify install commands and extras against package metadata.
- Follow the documented Python endpoint quickstart and run one local smoke
  request when prerequisites are available; inspect the MCP server example's
  local command path as described in Step 3.
- Review `git status`, the full documentation diff, and `git diff --check`.
- Confirm no runtime source, package metadata, or feature contract was changed.

**État :** Local Markdown links (29 files), package names/extras/Python version,
quickstart dependency pin, example source paths, environment templates, and
syntax of the changed Python examples were checked successfully. The FastAPI
quickstart and MCP server were not executed: system Python 3.14.3 has no `pip`,
and installing into an isolated venv failed because the package index could not
be resolved. Therefore no runnable example is claimed as smoke-tested here.

### Étape 6 — Publish a detailed agent descriptor and model discovery topic

**Objectif :** Give Python developers a topic-level guide for describing an
agent and making it discoverable through OpenAI's model-listing endpoints.

**Fichiers/composants :**

- `docs/python/agent-discovery.md` (new canonical topic page)
- `docs/python/README.md` (add the topic to the guide index)
- `docs/python/agent-runtime.md` (replace the brief discovery summary with a
  link to the detailed topic)
- `docs/examples/python-langchain-fastapi/agent-descriptor.md` (retain this
  existing path as a short pointer to the canonical topic)
- Reference only: `AgentDescriptor`, `AgentCapabilitySet`, `AgentSkill`,
  `DescriptorRegistry`, `DiscoveryConfiguration`, `add_ai_endpoints`,
  `add_discovery_endpoints`, OpenAI model projection, and discovery endpoint
  integration tests/contracts.

**Modifications :**

- Explain each descriptor field by purpose, distinguish the advertised
  `agent_id` from the internal `route_key`, and cover ID validation, UTC
  creation time, capabilities, skills, visibility, metadata, and the rule never
  to place secrets in public metadata.
- Give a cohesive Python example that declares the descriptor and capabilities
  (and a skill where useful), puts it in `DescriptorRegistry`, and shows both
  registration choices:
  `add_ai_endpoints(..., descriptor_registry=..., discovery=...)` when adding
  model discovery with invocation routes, and `add_discovery_endpoints(...)`
  when registering model discovery routes directly.
- Describe `DiscoveryConfiguration(enable_openai_models=True)`, the conditions
  under which each registration path adds model routes, and the optional
  authenticator and `AgentAccessPolicy` parameters on direct discovery
  registration.
- Show `GET /v1/models` and `GET /v1/models/{agent_id}` requests with
  representative OpenAI-compatible responses. Explain the native model
  fields, the `x-agent-runtime` extension, list ordering, empty listings, exact
  matching, and the absence of `route_key` from public output.
- Show how to pass the returned `id` as `model` in an invocation request, and
  explain listed versus hidden descriptors and how access-policy filtering
  differs from visibility.
- Link to the existing runnable LangChain example, authorization guide,
  descriptor schema, and endpoint contract. Keep Anthropic wire details and A2A
  card hosting outside this topic.

**Validation :**

- Check every documented field, option, route, response attribute, default,
  and access behavior against the Python source, versioned descriptor/endpoint
  contracts, and existing model-discovery integration tests.
- Check every code fragment against the existing example and ensure both
  registration snippets use the actual Python signatures.
- Verify the topic navigation and cross-links, retain the old example guide
  path, and run `git diff --check`.
- Do not run runtime tests or claim a smoke check: this step changes docs only
  and relies on an existing example that may require external dependencies.

**Critères de réussite :**

- A reader can declare an agent, choose either supported registration path,
  retrieve its public model ID, and use that ID in an invocation request.
- The central docs expose a canonical topic page and all current links to the
  previous example guide still work.
- No runtime source, package metadata, schema, or endpoint contract changes.

**État :** The canonical topic page and navigation links are in place. Relative
Markdown links in the affected topic/navigation pages resolve; fenced Python
snippets parse and the JSON response example parses. `git diff --check` passes.
No runtime tests or application smoke checks were run; this step changes
documentation only.

### Étape 7 — Expand the Python security implementation guide

**Objectif :** Turn the existing central security summary into a practical guide
to the authentication, authorization, and application-level security APIs
already shipped by the Python runtime.

**Fichiers/composants :**

- `docs/python/security.md` (expand the canonical security topic page)
- `docs/python/README.md` (describe the expanded security guide)
- Reference only: FastAPI authentication and header forwarding, auth context,
  JWT/API-key/custom authenticators, `AuthenticationPolicy`, agent access
  policy, permission and security domain primitives, and their integration
  tests.
- Existing walkthroughs: `docs/examples/python-langchain-fastapi/authorization.md`,
  `02-jwt-authentication/`, `03-jwt-oidc-keycloak/`,
  `04-human-in-the-loop/README.md`, and `docs/mcp-server-hosting.md`.

**Modifications :**

- Establish the boundary between authentication, agent access policy,
  handler-level authorization, and application-owned permission decisions.
- Document the FastAPI authentication defaults and options for required
  credentials, JWT validation/key resolvers, API-key user resolution, custom
  authenticator chains, and credential precedence.
- Explain the handler's normalized `auth_context`, projected identity/roles/
  groups/scopes/claims, the fact that raw API keys are not passed through, and
  how JWT claim paths configure role/group projection.
- Explain shared `AgentAccessPolicy` behavior for invocation and discovery,
  request-body authorization with `AuthorizationError`, relevant 401/403 and
  discovery filtering/404 behavior, and eager authorization before streaming.
- Document allowlisted header forwarding, refusal to forward credential
  headers, and separate conversation ID promotion.
- Describe the MCP server's explicit `AuthenticationPolicy` modes and link to
  the hosting guide for OAuth protected-resource and transport details.
- Describe the security primitives with small, source-backed composition
  examples: `Permission`, `PermissionRegistry`, `UserContext`,
  `ToolOperationDescriptor`, `SecurityFloor`, `AuditTrail` implementations,
  `UntrustedText`, `UntrustedFence`, and `PromptEnvelopeBuilder`.
- State that identity-provider roles are not automatically mapped to domain
  permissions, that these building blocks need application composition, and
  that content fencing alone does not prevent side effects or prompt injection.
- Link each flow to the existing runnable or detailed walkthrough and identify
  primitives without a standalone runnable example.

**Validation :**

- Verify option names, defaults, class/method signatures, caller-context fields,
  status codes, and policy behavior against Python source and focused
  integration tests.
- Check the JWT and Keycloak walkthrough prerequisites, configuration names,
  and commands against their app/source files and README instructions; check
  the MCP reference against `docs/mcp-server-hosting.md`.
- Check local Markdown links and code-block syntax, and run `git diff --check`.
- Do not modify or run runtime tests and do not claim the external JWT/OIDC or
  MCP example was smoke-tested; this step expands docs and links existing
  workflows only.

**Critères de réussite :**

- A reader can configure one of the supported FastAPI authentication methods
  and knows whether anonymous requests are accepted and what identity reaches
  the handler.
- A reader can choose where an authorization rule belongs and understands
  which behavior is automatic versus application-owned.
- A reader can identify how the MCP authentication policy differs from the
  FastAPI endpoint options and where to follow the complete hosting setup.
- The domain security primitives are described with their enforcement limits,
  and the page does not claim that they implement a complete RBAC system or
  automatically enforce application permissions.
- `docs/python/security.md` remains the single central security topic page;
  examples remain linked as focused walkthroughs rather than duplicated.

**État :** The canonical security guide and its landing-page summary are
expanded. API options and behavior were checked against the Python source,
existing authentication/authorization integration tests, and the linked JWT,
Keycloak, MCP-hosting, and human-approval instructions. Local links and fenced
Python/JSON snippets in the affected documentation resolve and parse;
`git diff --check` passes. Runtime tests and external-service smoke checks were
not run, as this step changes documentation only.

### Étape 8 — Add a Python human-in-the-loop topic guide

**Objectif :** Explain how developers compose deterministic human approval for
Python agent operations, including both approval obtained before a tool call
and an approval resumed through a later HTTP request.

**Fichiers/composants :**

- `docs/python/human-in-the-loop.md` (new canonical topic page)
- `docs/python/README.md` (index the topic)
- `docs/python/agent-runtime.md` (replace the brief approval overview with a
  link to the topic page)
- Reference only: `humanapproval` policy, authority, broker, gate, ledger,
  operation runner, tickets, command parser, renderer, and the security
  operation/permission/audit types used by them.
- Existing workflow: `docs/examples/python-langchain-fastapi/04-human-in-the-loop/`
  and `tests/integration/python/test_human_approval.py`.

**Modifications :**

- Establish the flow boundary: operation metadata and permissions are declared
  by the application; policy decides whether confirmation is required; an
  authority or framework obtains the human decision; an execution gate checks
  the permission and matching user/request before protected work; orchestration
  stores pending state and resumes the agent.
- Document `ConfiguredConfirmationPolicy` precedence accurately: a floor that
  makes confirmation mandatory takes priority, followed by per-user
  `always_confirm`, per-user `auto_approve`, and the operation default. Explain
  that risk classification describes an operation but does not alone force an
  approval.
- Explain `ConfirmationRequest` / `ConfirmationDecision`, `ConfirmationGate`,
  and `GatedOperationRunner`: permission enforcement, same-user and
  same-request checks, expected refusal errors, and the four audit outcomes.
  Link back to `docs/python/security.md` for general treatment of permissions,
  security floors, operation descriptors, and audit records.
- Distinguish the broker/ledger authority path from the HTTP ticket pattern.
  Explain the `ConfirmationAuthority`, `ConfirmationBroker`,
  `ConfirmationLedger`, and fail-closed `UnattendedApprovalAuthority` roles.
- Explain `ConfirmationTicket` and `PendingConfirmationStore` guarantees and
  the implementation boundary: subject and conversation binding, exact stored
  argument replay, single claim, expiry, and generic rejection for unknown or
  out-of-scope tickets. Explain that a production store must make claims atomic.
- Describe `ConfirmationPresenter` and `ConfirmedOperationRunner` without
  implying that the runner itself supplies the skill's policy/gate; a skill
  implementation must still enforce its permission and confirmation contract.
- Document the command parser's exact `CONFIRM` / `CANCEL` grammar and its
  placement before ordinary text reaches the model. Explain ticket consumption
  on denial as well as approval, bounded rendering of retrieved detail, and
  suppression of embedded ticket references.
- Trace the existing LangChain/LangGraph example as a framework-specific
  bridge: policy-driven eager interrupts, one decision for each suspended call
  in framework order, `approve` / `reject` only, tickets between HTTP requests,
  and replay of stored tool arguments without a second model decision.
- State the example's in-memory boundaries (graph checkpoint, ticket store, and
  per-conversation turn bookkeeping), explain the needs of multi-worker or
  restart-safe hosting, and link to the existing README for prerequisites and
  the complete run/call/answer sequence.
- Identify reusable approval APIs not directly used by the example and avoid
  presenting the example bridge as a runtime integration or the package as a
  provider of a universal approval UI or durable backend.

**Validation :**

- Verify policy precedence, gate checks, ticket ownership/expiry/claim behavior,
  parser grammar, renderer containment, audit outcomes, and public class/method
  names against the Python sources and focused approval integration tests.
- Check the example's dependency versions, required environment variables,
  external OpenAI/Microsoft Learn prerequisites, and storage limitations against
  its source, requirements, and README. Do not run the external example.
- Verify local Markdown links and fenced Python/JSON snippets, and run
  `git diff --check`.
- Do not change or run runtime tests; record that the topic guide is documentation
  only and make no smoke-test claim.

**Critères de réussite :**

- A Python developer can distinguish policy, human decision collection,
  enforcement, audit, and framework orchestration, and choose the appropriate
  existing flow for their application.
- The guide explains the exact behavior and safety boundaries of both broker/
  ledger and cross-request ticket flows without implying the model grants the
  final approval or can alter approved arguments.
- The existing LangGraph example is accurately linked and its prerequisites,
  in-memory limitations, and framework-specific components are clear.
- The new topic is reachable from the Python landing page and agent runtime
  guide; example setup remains in the existing walkthrough.
- No runtime source, package metadata, or endpoint contract changes.

**État :** The canonical human-in-the-loop guide, Python documentation links,
and issue 14 addenda are complete. Policy, gate, broker, ticket, parser, and
renderer behavior and public API names were checked against the Python source
and the focused approval integration tests; example prerequisites and its
in-memory boundaries were checked against the example source and README. Local
links and fenced Python/JSON snippets in the affected Python documentation
resolve and parse, and `git diff --check` passes. Runtime tests and the external
example were not run because this step changes documentation only.

## Tests

No runtime or contract tests are planned because the change adds documentation
and updates repository guidance only. Validation uses package metadata review,
Markdown link/path checking, command inspection, and the example smoke checks
described above. If a documentation example requires a code fix, revise this
scope before including any runtime changes.

## Validation finale

- Python docs provide one entry point for package selection, installation,
  quickstart, agent hosting, security, and MCP capabilities.
- Every described feature is supported by Python source or the feature
  contract, and links to a relevant example or states that no example exists.
- Python package names, extras, and version prerequisites match the package
  metadata.
- Existing examples used by the guides have their prerequisites and run
  instructions documented accurately.
- Root and Python example navigation both reach the new guide.
- Both repository agent instruction entry points require relevant docs and
  examples to be maintained.
- Markdown links, referenced paths, command snippets, and `git diff --check`
  have been reviewed; any executed smoke checks have recorded results, and
  unexecuted examples are clearly identified.
- The agent discovery topic documents both combined registration through
  `add_ai_endpoints` and direct model-route registration through
  `add_discovery_endpoints`, with behavior verified against the current API.
- The central security guide accurately documents FastAPI and MCP
  authentication, authorization boundaries, and the security domain building
  blocks without overstating automatic enforcement.
- The Python human-in-the-loop topic distinguishes the reusable approval APIs
  from the example-specific LangGraph bridge and accurately describes the
  broker/ledger and cross-request ticket patterns.
- No runtime behavior or cross-language parity surface changed.

## Risques

- The documentation spans four distributions and several distinct domains.
  The package selection table and domain checklist in the landing page reduce
  the chance of omitting a package capability.
- Some sample workflows need API keys, Docker, or an external MCP service. State
  these dependencies, prefer local smoke checks, and do not label a workflow
  verified without actually running it.
- Repeating detail already documented in example guides can create conflicting
  instructions. Keep the new guides as navigation and capability reference,
  and link to existing step-by-step guides.
- The implementation may reveal capability gaps or inaccurate examples. Keep
  resulting code or API changes out of this documentation plan and update the
  SPEC for approval if they are necessary.
- The existing descriptor walkthrough is stored under an example folder and
  already has inbound links. Make the new topic canonical while retaining the
  old path as a pointer, so existing example links do not break and the content
  is not maintained in two places.
- The security overview already has focused authorization and authentication
  examples. Expand the canonical overview and link to those walkthroughs instead
  of copying their full setup instructions into another page.
- The human-in-the-loop example already contains a detailed runnable sequence.
  Keep it as the setup walkthrough and explain the reusable approval contracts
  on the Python topic page without implying that the example exercises every
  generic API.

## Décisions techniques

- Place user-facing Python documentation under `docs/python/`, with one landing
  page and focused installation, quickstart, agent runtime, security, and MCP
  guides.
- Place the detailed agent descriptor/model discovery guidance at
  `docs/python/agent-discovery.md`; keep the current example-level path as a
  compatibility pointer and link to it from the central docs.
- Document both `add_ai_endpoints` (combined endpoint registration) and
  `add_discovery_endpoints` (direct model discovery registration) because both
  are existing supported FastAPI integration paths.
- Keep `docs/python/security.md` as the canonical security guide and preserve
  the example-specific JWT, OIDC, authorization, MCP, and human-approval pages
  as linked walkthroughs.
- Add `docs/python/human-in-the-loop.md` as the canonical approval topic and
  preserve `04-human-in-the-loop/README.md` as the detailed LangGraph walkthrough.
- Reuse and link to current examples and contracts; only revise example files
  when necessary to correct or complete a documented path.
- Update both `AGENTS.md` and `.github/copilot-instructions.md` because both are
  repository-level agent entry points.
- Write the new guides in English to match the current documentation.
- Treat documentation links, metadata checks, command review, and example
  smoke checks as the relevant quality evidence; do not add runtime tests for
  this docs-only change.

## Critères de réussite

- A Python user can find installation and an endpoint-backed quickstart
  from the root README.
- All shipped Python distributions and their main user-facing capabilities are
  covered or explicitly mapped to detailed existing documentation.
- The documented endpoint, security, and MCP paths have accurate configuration
  and prerequisites and point to relevant examples.
- Agents are instructed to maintain Python documentation alongside public
  API, configuration, dependency, behavior, and workflow changes.
- No change extends beyond the approved documentation scope.
