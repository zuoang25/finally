"""Application settings loaded from the environment (and the project-root `.env`).

`load_dotenv()` never overrides variables that are already set in the real
environment, so `FINALLY_DB_PATH=... uv run ...` and Docker's `--env-file`
always win over a checked-out `.env`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_TRUTHY = {"true", "1", "yes"}
DEFAULT_PORT = 8000


def get_project_root() -> Path:
    """The project root, i.e. the parent of `backend/`."""
    # this file: backend/app/config.py
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_env_file() -> None:
    """Load the project-root `.env` once, without overriding real env vars."""
    load_dotenv(dotenv_path=get_project_root() / ".env", override=False)


def _as_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUTHY


def _as_int(raw: str | None, default: int) -> int:
    try:
        return int((raw or "").strip())
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved environment configuration (see CONTRACTS.md section 7)."""

    openrouter_api_key: str = ""
    massive_api_key: str = ""
    llm_mock: bool = False
    db_path: str | None = None
    port: int = DEFAULT_PORT

    @property
    def market_data_source_name(self) -> str:
        """`"massive"` when a Massive API key is configured, else `"simulator"`."""
        return "massive" if self.massive_api_key else "simulator"


def load_settings() -> Settings:
    """Read settings from the environment, loading the project `.env` first."""
    load_env_file()
    db_path = (os.environ.get("FINALLY_DB_PATH") or "").strip()
    return Settings(
        openrouter_api_key=(os.environ.get("OPENROUTER_API_KEY") or "").strip(),
        massive_api_key=(os.environ.get("MASSIVE_API_KEY") or "").strip(),
        llm_mock=_as_bool(os.environ.get("LLM_MOCK")),
        db_path=db_path or None,
        port=_as_int(os.environ.get("PORT"), DEFAULT_PORT),
    )
