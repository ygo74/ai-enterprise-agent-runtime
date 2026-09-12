"""Tests of the package's public surface.

Two things are asserted here, and both exist because the surface is resolved
lazily. Names are looked up on first use so that importing the security model or
an agent contract does not load the endpoint adapters - and with them, FastAPI -
into a process that has no use for a web stack.

Laziness has a cost: the export table and ``__all__`` are two lists of the same
thing, and a name added to one and forgotten in the other would either be
invisible to ``from ... import *`` or advertised and unresolvable. The first test
pins them together. The second pins the isolation the laziness was introduced
for, in a subprocess, because this test session imports FastAPI elsewhere.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

import ygo74.agent_runtime as runtime


def test_every_advertised_name_resolves() -> None:
    unresolvable = [name for name in runtime.__all__ if not hasattr(runtime, name)]

    assert not unresolvable, f"advertised but not importable: {unresolvable}"


def test_the_export_table_and_all_stay_in_step() -> None:
    assert sorted(runtime.__all__) == sorted(runtime._EXPORTS)


def test_dir_lists_the_surface_without_importing_it() -> None:
    assert sorted(dir(runtime)) == sorted(runtime.__all__)


def test_an_unknown_name_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no attribute 'NotAThing'"):
        runtime.NotAThing  # type: ignore[attr-defined]  # noqa: B018


def test_importing_a_domain_does_not_load_the_transport() -> None:
    """The reason the surface is lazy at all.

    A subprocess, deliberately: by the time this runs, the suite has exercised
    the FastAPI endpoints, so an in-process assertion would prove nothing.
    """
    probe = textwrap.dedent(
        """
        import sys

        import ygo74.agent_runtime.domains.security.permissions
        import ygo74.agent_runtime.domains.contracts.capability_registry
        import ygo74.agent_runtime.domains.auth.agent_principal

        print(",".join(sorted(name for name in sys.modules if name in {"fastapi", "starlette"})))
        """
    )

    finished = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
    )

    assert finished.stdout.strip() == "", f"a domain import pulled in a web stack: {finished.stdout.strip()}"
