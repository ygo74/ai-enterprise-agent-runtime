# Implementation Plan

## Issue and SPEC

[#29 — samples and documentation enhancement + fix](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/29)

[Approved SPEC](./SPEC.md)

## Objective

Move and improve the Python sample catalog, add six MAF scenarios matching the
LangChain user tasks, and reorganize user-facing documentation around shared
runtime concepts. Leave existing .NET and Java samples and documentation
content untouched while documenting how future language catalogs fit the
layout.

## Repositories and prerequisites

- Repository: `ai-enterprise-agent-runtime` only.
- SPEC approval received. Implementation remains gated on approval of this
  PLAN.
- Before implementation, create `feature/29-python-samples-docs` from the
  current `main` aligned with `origin/main`, carrying the approved issue
  records. Preserve the approved SPEC and PLAN in the work branch.
- Do not modify Python package runtime behavior, .NET/Java sample content,
  .NET/Java documentation content, or historical implementation task records.

## Constitution Check

- **Cross-language parity:** PASS. Runtime contracts do not change. User guides
  describe shared behavior; no .NET/Java implementation parity is implied.
- **Reuse and simplicity:** PASS. Reorganize existing documentation and sample
  code before adding new MAF scenarios. Keep framework-specific work in the
  sample folders and central explanations in `doc/python/`.
- **Reuse evidence:** Existing quickstart, LangChain, MAF, and MCP-server
  samples and the related Python guides were reviewed. Reuse the LangChain
  scenarios as the MAF task map; retain valid authorization, configuration, and
  descriptor material from LangChain's root Markdown in the appropriate
  central Python guides.
- **Testing:** No runtime behavior changes are planned. Do not add or run tests
  for this documentation/sample reorganization. Keep existing CI coverage
  wired to the moved Python MAF sample test and update its paths.
- **UX consistency:** PASS. `doc/users/` remains language-neutral, with shared
  HTTP/JSON examples permitted and Python setup/API details linked to
  `doc/python/`.
- **Performance and observability:** Not applicable; no runtime code or
  execution path changes.
- **Domain organization:** PASS. Samples are discoverable from a language-first
  index; user guides follow the domain order approved in the SPEC.
- **Language idiom:** Any new MAF sample code uses typed MAF/runtime APIs and
  follows the repository Python conventions. No .NET or Java code is added.
- **Adoption examples:** PASS. The Python catalog retains LangChain + FastAPI
  examples and grows a corresponding MAF + FastAPI catalog, with framework
  limits stated in its READMEs.

## Scope and anticipated files

**Sample layout:**

- Add `samples/README.md` and `samples/python/README.md`.
- Move the four Python sample projects from `samples/examples/` into
  `samples/python/`; keep the existing .NET and Java directories under
  `samples/examples/` and leave their catalog entries unchanged.
- Create the Python catalog README from the current Python entries, then update
  those entries in `samples/examples/README.md` to point to the new catalog.
  Keep that legacy index in place and leave its .NET/Java entries unchanged.
- In `samples/python/python-fastapi-quickstart/`, create:
  `01-basic-endpoint/`, `02-structured-outputs/`,
  `03-jwt-authentication/`, and `04-jwt-oidc-keycloak/`, each with its own
  README and requirements file.
- In `samples/python/python-langchain-fastapi/`, map current scenarios to
  consecutive folders: `01-get-started`, `02-human-in-the-loop`, `03-rag`,
  `04-native-langgraph`, `05-managed-worker`, and `06-mcp-configuration`.
  Retain only the catalog README as a root Markdown guide.
- In `samples/python/python-agentframework-fastapi/`, provide the same six
  user-task categories as the LangChain catalog using MAF-specific designs:
  `01-get-started`, `02-human-in-the-loop`, `03-rag`, `04-native-agent`,
  `05-managed-worker`, and `06-mcp-configuration`.
- Move `python-mcp-server` under `samples/python/` without changing its
  behavior.

**Documentation, contributor guidance, and references:**

- Revise `doc/users/README.md` and the pages under `doc/users/` to match the
  approved sequence. Keep shared examples language-neutral; move Python-only
  commands and implementation guidance to the corresponding `doc/python/`
  pages. Split security and discovery into distinct user-guide entries and add
  shared hosting, conversation, and configuration entry points where needed.
- Update relevant pages under `doc/python/`, including installation,
  quickstart, security, discovery, runtime, approval, MCP, outputs, and both
  framework integration guides. Consolidate still-valid material from the
  three LangChain root guides before removing them.
- Update `doc/contributors/parity-status.md`, `packages/python/agentframework/README.md`,
  repository `README.md`, `AGENTS.md`, `.agents/skills/user-docs/SKILL.md`,
  `.agents/skills/python-package-version-bump/SKILL.md`, and
  `.github/workflows/ci.yml` where they refer to the old Python sample paths or
  layout.
- Update all other current Python sample links found by repository-wide path
  search. Keep historical records under `specs/` and `spec/implementation/`
  unchanged.

## Steps

### Step 1 — Establish the Python catalog and move the sample projects

- **Objective:** Make the new Python-first location discoverable while leaving
  existing .NET/Java sample material untouched.
- **Files or components:** `samples/README.md`,
  `samples/python/README.md`, `samples/examples/README.md`, the four Python
  project directories under `samples/examples/`.
- **Change:** Create `samples/python/README.md` from the current Python catalog
  entries; add a root guide that links to it and describes the future
  `samples/<language>/` convention without placeholder directories. Move only
  Python project trees into `samples/python/`. Keep
  `samples/examples/README.md` in place, redirect its Python entries to the new
  catalog, and leave its .NET/Java entries and trees unchanged.
- **Validation:** Review the tree and both indexes; confirm no .NET/Java files
  or README content changed.

### Step 2 — Isolate the four FastAPI quickstart scenarios

- **Objective:** Give the basic endpoint, structured output, JWT, and Keycloak
  walkthroughs separate, numbered folders.
- **Files or components:** `samples/python/python-fastapi-quickstart/` and
  links to its examples in documentation.
- **Change:** Move each app and its supporting files into its numbered folder.
  Give each a self-contained README and dependency file. Update the quickstart
  catalog and links to identify the new entry points.
- **Validation:** Review each README's run location and dependencies; confirm
  no quickstart link points to an app at the project root.

### Step 3 — Renumber and consolidate the LangChain catalog

- **Objective:** Remove numbering gaps and centralize reusable guidance.
- **Files or components:** `samples/python/python-langchain-fastapi/`,
  `doc/python/security.md`, `doc/python/agent-discovery.md`,
  `doc/python/agent-runtime.md`, and links to numbered scenarios.
- **Change:** Rename scenarios to `01`–`06`, updating intra-sample links and
  commands. Review `agent-descriptor.md`, `authorization.md`, and
  `configuration.md` against the current Python guides. Merge any unique,
  valid explanation into the appropriate central guide, update links, then
  remove the three root guides so only the catalog README remains at root.
- **Validation:** Review the six-folder order and root contents; scan for links
  to the old names and removed guide paths.

### Step 4 — Build the six MAF sample scenarios

- **Objective:** Give MAF users examples for the same adoption tasks while
  reflecting MAF and runtime behavior accurately.
- **Files or components:** `samples/python/python-agentframework-fastapi/` and
  `doc/python/agentframework.md` where sample links or limitations need updates.
- **Change:** Organize the existing offline sample as the getting-started
  scenario and add focused approval, RAG, native-agent, managed-worker, and
  declarative-MCP scenarios. Keep each scenario's instructions and dependencies
  with that scenario. State where MAF's approval bridge or hosting composition
  differs from LangGraph. Preserve the existing shared MAF test file and point
  CI to its relocated path.
- **Validation:** Review scenario READMEs against the MAF package APIs, current
  support limits, and corresponding LangChain tasks. Check all local links and
  dependency paths without executing sample tests.

### Step 5 — Reorder user guides and clarify the documentation boundary

- **Objective:** Present shared runtime concepts in the issue's requested order
  and route Python implementation questions to Python documentation.
- **Files or components:** `doc/users/*.md`, `doc/python/*.md`,
  `.agents/skills/user-docs/SKILL.md`.
- **Change:** Rework the user index and pages for installation, BYOA, hosting,
  endpoints/outputs, framework integrations, conversations, configuration,
  approval, MCP server hosting, security, and discovery. Replace Python-only
  code and setup commands in user pages with shared protocol examples or links
  to `doc/python/`. Retain a conceptual complete-agent walkthrough and link it
  to the runnable Python examples. Update the skill to state the same rules.
- **Validation:** Compare index and headings with the approved sequence; scan
  `doc/users/` for fenced Python code, Python-only install/run commands, and
  old sample paths; check cross-links into `doc/python/`.

### Step 6 — Update live references and review the complete change

- **Objective:** Keep active instructions, Python docs, and CI aligned with the
  moved samples.
- **Files or components:** Python path references identified by repository-wide
  search, `README.md`, `AGENTS.md`, `.agents/skills/python-package-version-bump/SKILL.md`,
  `doc/contributors/parity-status.md`, `packages/python/agentframework/README.md`,
  `.github/workflows/ci.yml`.
- **Change:** Update commands, links, and CI dependency/test paths that refer to
  the moved Python samples. Leave .NET/Java-specific paths and historical task
  records untouched.
- **Validation:** Search current repository content for old Python sample
  paths, inspect expected remaining references in historical records, review
  `git status` and the full diff, and run `git diff --check`.

## Validation and risks

- No automated test or sample command execution is planned; the change does not
  alter runtime behavior, and the user has not requested test execution.
- Review Markdown links and shell command working directories against the final
  tree. Existing CI remains the automated check for the moved MAF sample tests
  after its paths are updated.
- Main risk: some MAF capabilities do not line up one-to-one with LangGraph
  examples. Describe supported paths and limitations in the sample guides;
  do not simulate unavailable framework behavior.
- Transition risk: `samples/examples/` remains temporarily for the untouched
  .NET/Java samples. Its README must direct Python users to the new catalog and
  avoid implying that those language directories have been migrated.

## Completion criteria

- Every acceptance criterion in [SPEC.md](./SPEC.md) is satisfied.
- Python samples, indexes, docs, and CI refer to the new layout; .NET/Java
  samples and documentation remain unchanged.
- `doc/users/` follows the approved order and language-neutral content rule.
- `git diff --check` passes and no stale current Python sample links remain.
