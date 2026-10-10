"""Discover the directory containing an agent's delivered configuration."""

from __future__ import annotations

import os
from pathlib import Path

from ygo74.agent_runtime.domains.errors import DomainError

CONFIG_DIR_VARIABLE = "YGO74_AGENT_RUNTIME_CONFIG_DIR"
DEFAULT_CONFIG_DIR = "config"


class ConfigurationNotFoundError(DomainError):
    """Raised when the configuration directory or one of its files is missing."""


class ConfigurationDirectory:
    """Resolve and navigate the files delivered alongside an agent.

    Args:
        path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
    """
    def __init__(self, path: Path) -> None:
        """Initialize the instance runtime data with the supplied collaborators and configuration.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        self._path = path

    @classmethod
    def resolve(cls, *, base_path: Path | None = None) -> ConfigurationDirectory:
        """Use the configured directory, or ``config`` below the working directory.

        Args:
            base_path (Path | None): Optional root used to resolve relative configuration paths.
        """
        override = os.environ.get(CONFIG_DIR_VARIABLE, "").strip()
        if override:
            return cls(Path(override))
        return cls((base_path or Path.cwd()) / DEFAULT_CONFIG_DIR)

    @property
    def path(self) -> Path:
        """The resolved directory, which may not exist yet."""
        return self._path

    def require(self, *parts: str) -> Path:
        """Return an existing path below the configuration root.

        Args:
            parts (str): Path components joined beneath the configured configuration root.
        """
        candidate = self._path.joinpath(*parts)
        if not candidate.exists():
            raise ConfigurationNotFoundError(
                f"{candidate} is missing; set {CONFIG_DIR_VARIABLE} to the delivered configuration"
            )
        return candidate

    def children(self, *parts: str) -> tuple[Path, ...]:
        """Return child directories in name order.

        Args:
            parts (str): Path components joined beneath the configured configuration root.
        """
        parent = self.require(*parts)
        return tuple(sorted((child for child in parent.iterdir() if child.is_dir()), key=lambda path: path.name))
