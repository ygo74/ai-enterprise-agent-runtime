---
name: origin-push
description: Prepare and push an explicitly requested commit to the current origin work branch, with required Python quality checks.
---

# Push a commit to origin

Use this skill only when the user or an approved plan asks for a commit or
push. Keep the commit limited to the approved change and push only the current
working branch.

## Before committing

1. Check `git status --short --branch`, the current branch, upstream, and the
   full staged and unstaged diff. Keep unrelated changes, generated test
   results, secrets, and parent-directory files out of the commit. Do not push
   directly to `main` or `master`.
2. If any changed or untracked file has a `.py` extension, run the Python
   quality checks used by the `test-python` job in
   `.github/workflows/ci.yml`. Prepare its Python 3.12 dependencies as
   specified by that job, then run:

   ```bash
   python -m ruff check packages/python tests
   python -m pytest tests/ samples/python/python-agentframework-fastapi/test_agentframework_fastapi_example.py --junitxml=python-test-results.xml
   ```

   Ruff and pytest are mandatory for every Python change, including test
   scripts. The Ruff command above covers the Python packages and `tests/`;
   also lint each changed Python file outside those paths with
   `python -m ruff check <path>`. If a changed Python test is outside the
   pytest paths above, run pytest for that test file as well. If any required
   check fails, do not commit or push; fix the cause and rerun the required
   checks. Do not skip a check because it is slow or because the changed file
   is under `tests/`.
3. Run `git diff --check`, stage only files in scope, inspect
   `git diff --cached`, and run `git diff --cached --check`. Commit with a
   concise message describing the change.

## Push and verify

1. Confirm the commit is on the approved working branch and that its upstream
   is `origin`. For a branch that has no upstream, push it with
   `git push --set-upstream origin <branch-name>`; otherwise use
   `git push origin <branch-name>`.
2. Never force-push, rewrite shared history, merge, or push a release tag as
   part of this procedure. If the remote rejects the push, inspect the remote
   state and report or resolve the divergence without force-pushing.
3. After a successful push, check `git status --short --branch` and inspect
   the GitHub Actions result for the pushed commit when a workflow was
   triggered. This repository's CI workflow currently runs on `main`, `master`,
   and `feature/**`; work branches outside those patterns still require the
   local checks above and may not produce an automatic CI run. Do not claim CI
   passed when no run was triggered or its result is unavailable.
