"""Tests of the public surface, now that it is split across three distributions.

The runtime used to advertise one flat list of 154 names from
``ygo74.agent_runtime``. That facade could not survive the split: a regular package
can be contributed by exactly one distribution, so an editable install of the other
two became invisible - which is how this repository develops. The names are reached
through their domain module now, which is what the overwhelming majority of
consumer code already did.

What is asserted here is what replaced it. First, that the three distributions
really do merge into one namespace rather than shadowing each other. Second, and
more important than before, that they stay *separable*: the reason for splitting is
that hosting an MCP server should not drag in an agent's web stack, and that claim
is only worth making if something checks it.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

SECURITY_MODULES = (
    "ygo74.agent_runtime.domains.security.permissions",
    "ygo74.agent_runtime.domains.security.user_context",
    "ygo74.agent_runtime.domains.auth.authenticator",
    "ygo74.agent_runtime.domains.auth.apikey_authenticator",
)

AGENT_MODULES = (
    "ygo74.agent_runtime.domains.contracts.capability_registry",
    "ygo74.agent_runtime.domains.discovery.agent_descriptor",
    "ygo74.agent_runtime.domains.humanapproval.confirmation",
)

NEWLINE = "\n"


def _modules_loaded_by(imports: tuple[str, ...], watched: tuple[str, ...]) -> str:
    """Import modules in a clean interpreter and report which watched ones loaded.

    A subprocess, deliberately: by the time these run, the session has imported half
    the runtime, so an in-process assertion about what is *not* loaded would prove
    nothing.
    """
    body = textwrap.dedent(
        """
        import sys

        {imports}

        watched = {watched!r}
        print(",".join(sorted(name for name in sys.modules if name in watched)))
        """
    ).format(imports=NEWLINE.join(f"import {module}" for module in imports), watched=set(watched))

    finished = subprocess.run(
        [sys.executable, "-c", body],
        capture_output=True,
        text=True,
        check=True,
    )
    return finished.stdout.strip()


@pytest.mark.parametrize("module", SECURITY_MODULES + AGENT_MODULES)
def test_a_domain_of_either_distribution_imports(module: str) -> None:
    """The namespace merges: neither distribution shadows the other."""
    __import__(module)


def test_the_namespace_is_contributed_by_more_than_one_distribution() -> None:
    """The property the whole split rests on.

    If this collapses to a single path, a regular package has reappeared somewhere
    under ``ygo74.agent_runtime`` and one distribution has silently swallowed the
    others' modules.
    """
    import ygo74.agent_runtime.domains as domains

    assert len(list(domains.__path__)) >= 2, f"namespace collapsed to {list(domains.__path__)}"


def test_the_security_foundation_loads_no_web_stack() -> None:
    """The reason the security distribution depends on nothing else.

    An MCP server hosts no agent and serves no discovery descriptor. If importing its
    authentication model pulled in FastAPI, the separation would be a directory
    layout rather than a fact.
    """
    loaded = _modules_loaded_by(SECURITY_MODULES, ("fastapi", "starlette", "mcp"))

    assert loaded == "", f"the security foundation pulled in {loaded}"


def test_a_domain_import_does_not_load_the_transport() -> None:
    """Kept from the lazy-facade era, because the guarantee outlived the facade."""
    loaded = _modules_loaded_by(AGENT_MODULES, ("fastapi", "starlette"))

    assert loaded == "", f"a domain import pulled in a web stack: {loaded}"
