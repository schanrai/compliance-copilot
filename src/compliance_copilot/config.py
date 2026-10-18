"""Runtime settings loaded from the process environment.

No paths, API keys, or model names are hard-coded. `ANTHROPIC_API_KEY` is
accepted and ignored until the stretch phase installs a model client.
"""

from __future__ import annotations

import os
from enum import StrEnum

from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, PositiveFloat, ValidationError


class SettingsError(Exception):
    """Raised when environment settings cannot be loaded."""


class LogLevel(StrEnum):
    """Allowed values for the LOG_LEVEL environment variable."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


DEFAULT_ECFR_API_BASE_URL = "https://www.ecfr.gov/api/versioner/v1"
DEFAULT_ECFR_WEB_BASE_URL = "https://www.ecfr.gov"
DEFAULT_HTTP_TIMEOUT_SECONDS = "30"


class Settings(BaseModel):
    """Settings the process needs in order to start.

    The eCFR settings are read only by corpus ingestion; the runtime corpus
    is loaded from files and never calls the network.
    """

    log_level: LogLevel
    anthropic_api_key: str | None
    ecfr_api_base_url: HttpUrl
    ecfr_web_base_url: HttpUrl
    http_timeout_seconds: PositiveFloat


def _env(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw.strip() if raw and raw.strip() else default


def load_settings() -> Settings:
    """Load settings from the environment.

    `load_dotenv` does not override variables that are already set, and it
    searches upward from the current working directory. Unset or blank
    variables fall back to the values in `.env.example`. An invalid value
    fails loudly. A blank API key is treated as unset.
    """

    load_dotenv()
    raw_key = os.environ.get("ANTHROPIC_API_KEY")
    api_key = raw_key.strip() if raw_key and raw_key.strip() else None
    try:
        return Settings(
            log_level=_env("LOG_LEVEL", LogLevel.INFO.value).upper(),
            anthropic_api_key=api_key,
            ecfr_api_base_url=_env("ECFR_API_BASE_URL", DEFAULT_ECFR_API_BASE_URL),
            ecfr_web_base_url=_env("ECFR_WEB_BASE_URL", DEFAULT_ECFR_WEB_BASE_URL),
            http_timeout_seconds=_env(
                "HTTP_TIMEOUT_SECONDS", DEFAULT_HTTP_TIMEOUT_SECONDS
            ),
        )
    except ValidationError as exc:
        allowed = ", ".join(level.value for level in LogLevel)
        problems = "; ".join(
            f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise SettingsError(
            f"Invalid environment settings ({problems}). LOG_LEVEL must be one of: "
            f"{allowed}. ECFR_*_BASE_URL must be URLs. HTTP_TIMEOUT_SECONDS must be "
            "a positive number."
        ) from exc
