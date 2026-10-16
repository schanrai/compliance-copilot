"""Phase 0a harness: settings load, and logging emits one structured line."""

from __future__ import annotations

import json

import pytest

from compliance_copilot.config import SettingsError, load_settings
from compliance_copilot.log import configure_logging


def test_harness_loads_settings_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    settings = load_settings()
    assert settings.log_level.value == "WARNING"
    assert settings.anthropic_api_key is None

    logger = configure_logging(settings)
    logger.warning("harness ok")

    line = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "harness ok"
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "compliance_copilot"


def test_invalid_log_level_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "verbose")

    with pytest.raises(SettingsError, match="LOG_LEVEL"):
        load_settings()
