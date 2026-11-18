# Journal — Issue #37

## Approved scope

- User approved `SPEC.md`, then approved `PLAN.md` on 2026-11-10.
- Add an optional Python MCP operation surface to `ai-enterprise-agent-runtime`, then activate it for Mail and Wiki in the separate `ai_agents` repository.
- Preserve existing HTTP surfaces, authenticated identity and agent-level authorization/confirmation behavior. MCP uses the existing conversation cache; its process-local behavior and affinity requirement remain documented.
- The initial plan excluded commits and pushes. On 2026-11-11, the user requested a new PR in each repository; separate commits, pushes, and PR creation are now in scope. Merges, package releases, image publication, and deployment remain out of scope.

## Repositories and branches

- `/data/repos/ai-enterprise-agent-runtime` — `feature/37-mcp-agent-endpoints`, based on the current `origin/main`
- `/data/repos/ai_agents` — `feature/37-mcp-agent-endpoints`, based on the current `origin/main` (independent Git history)

## Progress

- 2026-11-10: SPEC and PLAN approved. Created this task list and journal.
- 2026-11-10: R-001 complete. Added `mcp` manifest endpoint, typed `http.mcp.resource_url`, HTTPS/env-reference validation, JWT requirement, builder resolution, and regenerated `agent.schema.json`.
- 2026-11-10: R-002 complete. Added `McpAgentEndpoint` with one `invoke_agent` tool, verified scope identity, conversation context, typed output serialization, and pending confirmation projection.
- 2026-11-10: R-003 complete. Added `McpServerHost.mount()` with parent-managed session lifespan and auth cleanup; a mounted guard protects only the MCP protocol path so unrelated parent routes and 404s retain their behavior.
- 2026-11-10: R-004 complete. Wired manifest surfaces into `HostingFactory`, moved worker readiness registration ahead of the root mount, excluded MCP from the worker's legacy default surfaces, and added the `mcp-server` extra.
- 2026-11-10: R-005 complete. Updated runtime endpoint, manifest, hosting, and MCP documentation; added a deterministic FastAPI hosting smoke app and documented JWT resource URLs, parent lifespan, and process-local cache affinity.
- 2026-11-10: A-001 complete. Added Mail and Wiki contract coverage for authenticated invocation, caller isolation, identity requirements, confirmation behavior, and preserved HTTP routes.
- 2026-11-10: A-002 complete. Enabled `/mcp` in both service manifests, supplied Mail's JWT resource URL from the environment, and added the runtime `mcp-server` extra to both HTTP extras.
- 2026-11-10: A-003 complete. Updated the environment example, Mail/Wiki HTTP guides, MCP integration spec, and deployment instructions, including cache affinity.
- 2026-11-10: FINAL review complete. The two independent worktrees contain only the issue implementation and its tracking files; no commit, push, merge, release, or deployment was performed.
- 2026-11-11: Created clean feature branches from the fetched `origin/main` refs in both repositories, retaining only the MCP implementation diffs for review.

## Validation log

- `.venv/bin/python -m pytest tests/integration/python/test_manifest_http_hosting.py -k 'mcp_resource_url or mcp_api_key'`: 3 passed, 2 deselected.
- `.venv/bin/python -m pytest tests/integration/python/test_manifest_configuration_schemas.py -k 'agent_schema_accepts_mcp_http or packaged_schema_matches_its_typed_input'`: 4 passed, 9 deselected.
- `.venv/bin/python -m pytest tests/integration/python/test_mcp_agent_endpoint.py -q`: 1 passed; this uses the MCP SDK client over the real FastAPI app and validates the manifest, factory, auth, tool schema, typed response, and confirmation metadata.
- `.venv/bin/python -m pytest tests/integration/python/test_mcp_server_hosting.py -k mounts_fastmcp -q`: 1 passed, 52 deselected.
- `.venv/bin/python -m pytest tests/integration/python/test_native_worker.py -k mcp_mount_keeps -q`: 1 passed, 18 deselected.
- `.venv/bin/python -m pytest tests/integration/python/test_fastapi_hosting_factory.py -k optional_server_extra -q`: 1 passed, 31 deselected.
- `.venv/bin/python -m pytest tests/integration/python/test_mcp_agent_endpoint.py tests/integration/python/test_manifest_http_hosting.py tests/integration/python/test_manifest_configuration_schemas.py tests/integration/python/test_mcp_server_hosting.py tests/integration/python/test_native_worker.py tests/integration/python/test_fastapi_hosting_factory.py -k 'mcp_operation_uses_verified_identity or mcp_resource_url or mcp_api_key or agent_schema_accepts_mcp_http or packaged_schema_matches_its_typed_input or mounts_fastmcp or mcp_mount_keeps or optional_server_extra' -q`: 11 passed, 112 deselected.
- From `/data/repos/ai_agents`, the Mail contract command `env PYTHONPATH=.:tests:agents/mail/src:agents/core/src:agents/maf/src:agents/langgraph/src:../ai-enterprise-agent-runtime/packages/python/agents:../ai-enterprise-agent-runtime/packages/python/security:../ai-enterprise-agent-runtime/packages/python/mcpserver:../ai-enterprise-agent-runtime/packages/python/agentframework ../ai-enterprise-agent-runtime/.venv/bin/python -m pytest tests/contract/test_mail_service_configuration.py -q` exited 0; all 4 tests completed.
- From `/data/repos/ai_agents`, each Wiki MCP contract was invoked separately with the same source roots plus `agents/wiki/src` and `mcp-servers/wiki-protocol/src`: `tests/contract/test_wiki_openai_http_surface.py -k mcp_accepts_subject_only_identity -q` and `-k mcp_keeps_wiki_write_confirmation -q`. Each printed one passing-test dot, then the Python 3.12 pytest-asyncio runner hung during selector/event-loop teardown; `timeout -k 3s -s INT 12s` interrupted each process (exit 124). Assertions in each test body completed; the runner did not provide a normal pytest summary.
- Runtime `ruff check` over changed Python source and test files passed. Runtime `ruff format --check` for the new endpoint, endpoint test, and smoke app passed (`3 files already formatted`).
- In `ai_agents`, Ruff check and format check passed for the MCP helper and both changed contract files (`3 files already formatted`). `git -c core.whitespace=cr-at-eol diff --check` passed; this repository stores the changed files with CRLF endings.
- The sample hosting smoke app imported successfully and registered `/health/ready`, the existing OpenAI routes, and the root-mounted MCP application.
- Broader runs of `test_mcp_server_hosting.py` and combined runtime suites did not finish: this environment's `starlette.testclient.TestClient(Starlette())` hangs during lifespan startup even without the MCP host. Focused async-ASGI validations above pass; revisit compatible existing tests without claiming the broader suite passed.
- On 2026-11-11, `ai_agents` full Ruff (`.venv/dev/bin/python -m ruff check .`) passed. Mypy passed against the published runtime 0.8.2 wheels used by CI (`Success: no issues found in 248 source files`). The first mypy attempt used stale runtime 0.8.0 packages and failed on missing APIs; it was rerun after reinstalling the documented dev environment and CI-matched wheels.
- The full `ai_agents` pytest run did not complete: it displayed three failures and stopped progressing around 72%; the `-x` diagnostic run identified the first failure as the existing architecture assertion that `agents/mail/src/ai_agent_lab/mail/application/approval` must not exist. That path and the architecture test are unchanged by this feature; the diagnostic run reported 1 failed, 1323 passed, and 839 skipped.
- The focused `ai_agents` Mail contract file completed with four passing tests. The focused Wiki MCP run completed the first test body, then the pytest-asyncio runner hung during selector teardown and was interrupted after 15 seconds (exit 124); earlier per-test attempts recorded both Wiki test bodies reaching their assertions before the same teardown issue.
- On 2026-11-11, runtime Ruff passed for `packages/python` and `tests`, the new sample smoke app passed its separate Ruff check, and the targeted cross-file MCP integration selection passed (11 passed, 112 deselected). `git diff --check` passed in runtime; the CRLF-aware diff check passed in `ai_agents`.
- The full runtime pytest command collected 1224 tests and stalled at about 12% in the pre-existing `test_agentframework_binding.py` area; it was interrupted after reproducing the Starlette lifespan hang already recorded above.

## Decisions and deviations

- Added an exact MCP-path guard for mounted MCP apps after a regression showed the root mount otherwise returned 401 for unrelated missing paths. This preserves the parent's HTTP routes and 404 behavior required by the approved compatibility scope.
- Wiki MCP test bodies complete successfully, but pytest-asyncio does not terminate its event loop in this environment; both targeted runs required timeout interruption after the test dot. This is recorded as a runner limitation, not a passing full pytest process.
