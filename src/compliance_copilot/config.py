"""Runtime settings loaded from the process environment.

No paths, API keys, or model names are hard-coded. `ANTHROPIC_API_KEY` is
accepted and ignored until the stretch phase installs a model client.
"""

from __future__ import annotations

import os
from enum import StrEnum

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError


class SettingsError(Exception):
    """Raised when environment settings cannot be loaded."""


class LogLevel(StrEnum):
    """Allowed values for the LOG_LEVEL environment variable."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseModel):
    """Settings the process needs in order to start."""

    log_level: LogLevel
    anthropic_api_key: str | None


def load_settings() -> Settings:
    """Load settings from the environment.

    `load_dotenv` does not override variables that are already set, and it
    searches upward from the current working directory. A missing `LOG_LEVEL`
    falls back to INFO, which is also the value in `.env.example`. An invalid
    level fails loudly. A blank API key is treated as unset.
    """

    load_dotenv()
    raw_level = os.environ.get("LOG_LEVEL", LogLevel.INFO.value).strip()
    raw_key = os.environ.get("ANTHROPIC_API_KEY")
    api_key = raw_key.strip() if raw_key and raw_key.strip() else None
    try:
        return Settings(log_level=raw_level.upper(), anthropic_api_key=api_key)
    except ValidationError as exc:
        allowed = ", ".join(level.value for level in LogLevel)
        raise SettingsError(
            f"Invalid environment settings. LOG_LEVEL must be one of: {allowed}."
        ) from exc
