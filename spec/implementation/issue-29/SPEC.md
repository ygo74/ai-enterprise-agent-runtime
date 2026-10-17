# Specification

## Issue

[#29 — samples and documentation enhancement + fix](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/29)

## Objective

Make runnable samples easy to find by language, give each example a clear
numbered entry point, bring the Microsoft Agent Framework (MAF) sample catalog
to the same user-task coverage as the LangChain catalog, and organize user
documentation around shared runtime concepts with language-specific guides at
the implementation level.

## Context and problem

Samples currently live together under `samples/examples/`. The FastAPI
quickstart mixes two standalone apps at its root with two numbered
authentication examples. The LangChain catalog has gaps in its numbering and
keeps authorization, configuration, and descriptor Markdown beside the
examples even though central Python guides now cover those topics. The MAF
catalog currently has one offline native-agent walkthrough, while LangChain
has six examples spanning setup, approval, RAG, framework-native hosting,
managed workers, and declarative MCP configuration.

`doc/users/` and `doc/python/` already exist, but several user pages include
Python commands or point directly to Python files. The user-guide index also
does not follow the topic order requested by the issue. Existing documentation
and CI references still use `samples/examples/`.

## Scope

- Move the Python sample projects into `samples/python/`, preserving their
  current leaf directory names. Add a top-level `samples/README.md` that
  explains the language-first convention (`samples/<language>/`) and links to
  the Python catalog. Make the layout straightforward to extend when another
  language is in scope, without adding empty language directories or guides.
  Update Python links in `samples/examples/README.md` to point to the new
  catalog, leaving its .NET and Java entries unchanged. Leave the existing
  .NET and Java sample directories and their documentation untouched under
  `samples/examples/`; moving them is explicitly deferred.
- Split `python-fastapi-quickstart` into four self-contained examples numbered
  `01` through `04`: basic endpoint, structured outputs, JWT authentication,
  and OIDC/Keycloak. Give each its own instructions and dependencies.
- Renumber the six existing LangChain scenarios consecutively from `01` to
  `06`, and keep their catalog README as the only root Markdown guide. Move
  valid reusable material from the root authorization, configuration, and
  descriptor Markdown into the relevant `doc/python/` guides; do not retain
  duplicate redirects or discard unique, still-accurate guidance.
- Expand `python-agentframework-fastapi` into six examples covering the same
  user tasks as the LangChain catalog: getting started, approval, RAG,
  framework-native hosting, managed-worker composition, and MCP configuration.
  Adapt the implementation to MAF and the runtime APIs that exist. Describe
  meaningful behavioral differences accurately; do not claim framework or
  cross-language parity where none exists.
- Reorder and revise `doc/users/` to follow the issue's requested journey:
  installation; BYOA concepts (how a developer supplies business rules, tools,
  skills, and a system prompt) and the six hosting/configuration choices; agent
  hosting; endpoints and outputs; framework integrations; conversations; agent,
  skill, and MCP configuration; human approval; MCP server hosting; security;
  and discovery. Reuse or split current pages as needed so each topic has a
  clear entry point in that order.
- Keep `doc/users/` language-neutral: it may use shared HTTP/JSON examples and
  describe runtime concepts, but it must not include Python code or Python-only
  setup commands. Link Python implementation details to `doc/python/`. Keep
  Python API details and runnable Python instructions in `doc/python/`. Do not
  add .NET or Java documentation in this issue; make the docs and samples
  indexes easy to extend with language-specific guides when those are in scope.
- Update `.agents/skills/user-docs/SKILL.md` to preserve this audience split and
  the language-first sample layout. A separate sample-authoring skill is not
  required for this change; the top-level sample guide documents the structure.
- Update Python documentation, contributor guidance, CI, and other active
  references affected by the moves. Leave .NET/Java-specific content and paths
  untouched. Do not rewrite historical issue records solely to change old
  paths.

## Out of scope

- Changing runtime APIs, protocol behavior, or library support across languages.
- Implementing .NET or Java features solely to make their samples match Python.
- Claiming the MAF examples are behaviorally identical to LangChain examples;
  they demonstrate comparable user tasks through each framework's supported
  integration.
- Adding new user-facing runtime capabilities, publishing packages, or changing
  release policy.

## Expected behavior

1. A developer can start at `samples/README.md` and find the Python catalog
   through its README. The guide makes the future language-first extension
   pattern clear. Python sample instructions, dependencies, relative links, CI
   paths, and documentation links agree with the new layout.
2. The four FastAPI quickstart scenarios are isolated in numbered directories
   and can be followed independently. The LangChain catalog has continuous
   numbering, and no topic-specific guide remains at its root apart from its
   README.
3. The MAF catalog covers the same six adoption tasks as LangChain. The root
   README explains when to use each scenario, what the runtime handles, and any
   framework-specific limits.
4. The `doc/users/README.md` reading order matches the sequence above. Shared
   user pages explain what each runtime domain does and direct Python readers
   to `doc/python/` for code and language-specific setup.
5. The user-docs skill gives future contributors the same audience boundary,
   documentation order, and sample discovery expectations.
6. All current Python documentation links and automation follow the moved
   samples. The top-level sample guide states the convention for adding
   language catalogs later. Historical implementation records remain intact.

## Architecture, interfaces, and data

This is a Python documentation and sample-layout change. No package API, wire
contract, configuration schema, or runtime data model changes. .NET/Java sample
content and language documentation are outside the scope of this issue.

## Constraints and decisions

- Preserve example behavior and secrets hygiene while moving files. Each MAF
  example must use MAF APIs; it must not disguise a LangChain example as a MAF
  port.
- Use the existing LangChain scenarios as the six reference user tasks, with
  numbering made contiguous before matching the MAF catalog to them.
- Keep central, maintained explanations in `doc/python/`; sample READMEs should
  focus on running and understanding their own example.
- Retain old issue/task records as historical artifacts; update live build,
  contributor, and user-facing paths.
- No performance budget applies because runtime behavior is unchanged.

## Acceptance criteria

- Python samples are grouped under `samples/python/` and indexed from
  `samples/README.md`. The guide describes how to add a language directory in a
  future change without creating placeholders now.
- The FastAPI quickstart contains four isolated numbered scenarios.
- LangChain contains six consecutively numbered examples; its root has only
  its catalog README plus non-Markdown shared source required by the examples.
- MAF contains six documented examples corresponding to the same user tasks,
  with any integration-specific limitations stated in the relevant README.
- `doc/users/` follows the requested order and contains no Python code examples
  or Python-only installation/run commands. Language-neutral protocol examples
  are allowed.
- Python implementation guidance is under `doc/python/`. Existing .NET/Java
  samples and documentation remain untouched.
- The user-docs skill and current CI/documentation links reflect the new layout.
- No runtime API, protocol contract, or behavior changes are introduced.

## Validation strategy

Review moved paths and README instructions; check Markdown links and repository
references for stale sample paths; compare the user-document index and page
headings with the requested order; and review the documentation split for
Python-specific commands or code in `doc/users/`. Since runtime contracts do
not change, parity and performance suites are not applicable. Automated tests
are outside this SPEC unless the user separately requests test execution.

## Risks and open questions

- The MAF examples include framework-specific workflows such as the approval
  ticket bridge and managed conversation factory. Their behavior must be
  described precisely instead of presented as a literal port of LangGraph.
- Existing .NET and Java examples remain in `samples/examples/` until a future
  change moves them. `samples/README.md` must make the target convention clear
  without implying that this issue migrated them.
- Approval requested for the six-task interpretation of “same examples” and
  the rule that `doc/users/` may contain shared HTTP/JSON examples but no
  Python-specific snippets or commands. .NET and Java sample/documentation work
  is excluded from this SPEC as requested.
