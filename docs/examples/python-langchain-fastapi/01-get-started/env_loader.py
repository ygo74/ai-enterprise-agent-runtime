from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


def ensure_env_loaded() -> None:
    """Load environment variables from the local example .env file if present."""

    env_path = Path(__file__).resolve().parent / ".env"

    if load_dotenv is not None:
        load_dotenv(dotenv_path=env_path, override=False)
        return

    if not env_path.exists():
        return

    # Lightweight fallback to avoid hard dependency on python-dotenv at runtime.
    import os

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
