"""Load an agent's local environment file without overriding the process."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = ".env"


class EnvironmentFile:
    """Make values from the local environment file available to configuration clients."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(ENV_FILE)

    def load(self) -> bool:
        """Load the file if present, keeping values already in the environment."""
        if not self._path.is_file():
            return False
        return load_dotenv(self._path, override=False)
