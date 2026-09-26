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

## Décisions techniques

- Place user-facing Python documentation under `docs/python/`, with one landing
  page and focused installation, quickstart, agent runtime, security, and MCP
  guides.
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
