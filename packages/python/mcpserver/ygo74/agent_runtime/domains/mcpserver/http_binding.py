"""Where an MCP server listens, and what it calls itself.

Two addresses, and conflating them is what produced the worst defect this package
was written to prevent.

The **bind address** is which interfaces the process accepts connections on. In a
container that is every interface, because the container's network namespace is the
boundary; what keeps that safe is the credential, not the address.

The **public host** is the name callers use. It is what arrives in the ``Host``
header, what an OAuth resource identifier is built from, and what a DNS-rebinding
allow-list has to contain. A wildcard bind is not a name anything can address, so it
cannot serve as one.
"""

from __future__ import annotations

from dataclasses import dataclass

HEALTH_PATH = "/healthz"

# Addresses that mean "every interface" rather than naming one. A caller cannot put
# any of them in a `Host` header, so they cannot stand in for a public name.
_WILDCARDS = frozenset({"0.0.0.0", "::", "[::]", ""})  # noqa: S104 - matched, not bound

_LOOPBACK = "localhost"


@dataclass(frozen=True, slots=True)
class McpHttpBinding:
    """The address an MCP server is served on.

    Args:
        host: The interface to bind. ``0.0.0.0`` is normal in a container.
        port: The port to bind.
        public_host: The authority callers reach the server at, including the port
            when it is not implied - ``mail-mcp-gmail:9100``. Defaults to the bind
            address, which is right on a workstation and wrong behind a service
            name, so a deployment that has one should say it.
    """

    host: str = _LOOPBACK
    port: int = 9100
    public_host: str = ""

    def __post_init__(self) -> None:
        if not self.public_host:
            object.__setattr__(self, "public_host", self._derived_public_host())

    def _derived_public_host(self) -> str:
        """Guess the authority when the deployment did not name one.

        A wildcard bind falls back to loopback rather than to itself: guessing wrong
        towards something unusable is better than minting an authority that resolves
        nowhere and silently ends up in an OAuth resource identifier.

        An IPv6 literal is bracketed, because ``::1:9100`` is not an authority - the
        colons of the address and the colon of the port are indistinguishable, and
        both a ``Host`` header and a URL need ``[::1]:9100``.
        """
        if self.host in _WILDCARDS:
            return f"{_LOOPBACK}:{self.port}"

        host = f"[{self.host}]" if _is_ipv6_literal(self.host) else self.host
        return f"{host}:{self.port}"


def _is_ipv6_literal(host: str) -> bool:
    """Whether a bind address is a bare IPv6 literal needing brackets."""
    return ":" in host and not host.startswith("[")
