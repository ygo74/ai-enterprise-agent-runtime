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
    """Resolve and navigate the files delivered alongside an agent."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def resolve(cls, *, base_path: Path | None = None) -> ConfigurationDirectory:
        """Use the configured directory, or ``config`` below the working directory."""
        override = os.environ.get(CONFIG_DIR_VARIABLE, "").strip()
        if override:
            return cls(Path(override))
        return cls((base_path or Path.cwd()) / DEFAULT_CONFIG_DIR)

    @property
    def path(self) -> Path:
        """The resolved directory, which may not exist yet."""
        return self._path

    def require(self, *parts: str) -> Path:
        """Return an existing path below the configuration root."""
        candidate = self._path.joinpath(*parts)
        if not candidate.exists():
            raise ConfigurationNotFoundError(
                f"{candidate} is missing; set {CONFIG_DIR_VARIABLE} to the delivered configuration"
            )
        return candidate

    def children(self, *parts: str) -> tuple[Path, ...]:
        """Return child directories in name order."""
        parent = self.require(*parts)
        return tuple(sorted((child for child in parent.iterdir() if child.is_dir()), key=lambda path: path.name))
