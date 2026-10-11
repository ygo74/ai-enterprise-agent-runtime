---
name: python-package-version-bump
description: Prepare a coordinated version bump for this repository's Python packages before building a release. Update package versions and internal dependency requirements across package metadata, docs, and examples. Do not use for third-party dependency upgrades or publishing.
---

# Python Package Version Bump

Prepare the Python distributions for a new release of this repository. The
result is a reviewed version and dependency update that can be built and
published later.

## Scope

The current PyPI release workflow builds these six distributions from
`packages/python/`:

- `security`
- `agents`
- `mcpserver`
- `meta`
- `langchain`
- `agentframework`

Check `.github/workflows/python-publish.yml` before each release. Use its
current package list as the source of truth. The .NET and Java projects have
separate versioning and are not part of this Python release unless the user
asks for a multi-language release.

## Choose the target version

1. Use the exact version if the user provides one.
2. Otherwise inspect the current package versions, recent release tags, the
   version bump commits, and changes since the last release. Do not assume the
   latest Git tag is newer than the versions in the package manifests.
3. Keep all six Python distributions on one version when the current release
   manifests and publishing workflow show a coordinated release. If the
   versions have drifted, preserve that state and ask before aligning them.
4. Follow the change's compatibility impact: use a patch for compatible fixes,
   a minor version for new or incompatible changes before `1.0`, and a major
   version for incompatible changes after `1.0`. Ask the user if the impact is
   unclear or if a prerelease format is needed.

Do not edit files until the target version is clear. Preserve existing work in
the worktree and do not include unrelated changes in the release diff.

## Update package versions and internal requirements

Update each released distribution's `[project].version` in its
`packages/python/<package>/pyproject.toml`.

Then search the whole repository for every internal distribution name. Update
the minimum version to the target where a package requires a released runtime
package. Include optional dependencies, examples, install commands, and
packaging tests that assert dependency metadata. The current dependency shape
is:

```text
agents         -> security
mcpserver      -> security
langchain      -> agents
agentframework -> agents
meta           -> security, agents, mcpserver
```

Preserve each dependency's extras and compatibility bounds. For example, if a
requirement is `ygo74-agent-runtime-agents[http]>=0.8.0,<2`, raise its lower
bound to the target version and keep `<2` unless a separate compatibility
change justifies changing that upper bound.

Also review user documentation and `samples/examples/**/requirements*.txt` for
internal package pins and minimums. Update exact pins that are meant to show the
current release. If an example intentionally demonstrates an older release,
leave it unchanged and make its purpose clear. Search by package name, not only
by the old version number, so stale statements such as an obsolete `1.x`
requirement are found.

Do not change third-party dependency versions as part of a runtime release bump.
Change an SDK floor or bound only when the release also changes the supported
SDK compatibility, and explain that reason in the summary.

## Validate the release preparation

1. Search again for internal package references and review each remaining old
   version. Check package metadata, docs, examples, and tests.
2. Build all distributions in the publishing workflow into a temporary output
   directory. Do not leave generated artifacts in the repository:

   ```bash
   set -e
   build_dir="$(mktemp -d)"
   for project in security agents mcpserver meta langchain agentframework; do
     python -m build --outdir "$build_dir" "packages/python/$project"
   done
   python -m twine check "$build_dir"/*
   ```

3. If Twine is not installed, report that check as not run; do not claim it
   passed.
4. Run the packaging metadata and dependency checks affected by the changes.
   Do not run tests unless the user asks for them.
5. Review `git diff --check`, the complete diff, and `git status`. Keep the
   version bump limited to this release preparation.

Do not create a Git tag or release, publish to PyPI, push, or commit unless the
user separately asks for that action.

## Report

Summarize the old and new versions, the distributions updated, internal
dependency floors changed, exact pins or intentionally old examples reviewed,
and validation results. Call out any package version drift or compatibility
decision that still needs the user's choice.
