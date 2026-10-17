"""`log_stage` writes exactly one structured line per pipeline stage.

Logging is configured inside each test body: the handler binds to the
current stderr, and pytest swaps stderr between fixture setup and the test.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from compliance_copilot.config import load_settings
from compliance_copilot.log import PipelineStage, configure_logging, log_stage


def configured_logger(monkeypatch: pytest.MonkeyPatch) -> logging.Logger:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    return configure_logging(load_settings())


def lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in capsys.readouterr().err.strip().splitlines()]


def test_successful_stage_writes_one_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = configured_logger(monkeypatch)

    with log_stage(logger, PipelineStage.ROUTER, run_id="G-01") as record:
        record.add(determination="business_associate")

    [payload] = lines(capsys)
    assert payload["stage"] == "router"
    assert payload["run_id"] == "G-01"
    assert payload["outcome"] == "ok"
    assert payload["determination"] == "business_associate"
    assert payload["level"] == "INFO"
    assert payload["duration_ms"] >= 0


def test_failed_stage_writes_one_line_and_reraises(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logger = configured_logger(monkeypatch)

    with pytest.raises(RuntimeError, match="boom"):
        with log_stage(logger, PipelineStage.SPECIALIST):
            raise RuntimeError("boom")

    [payload] = lines(capsys)
    assert payload["outcome"] == "error"
    assert payload["level"] == "ERROR"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error"] == "boom"
    assert "run_id" not in payload


def test_stage_fields_cannot_overwrite_reserved_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = configured_logger(monkeypatch)

    with pytest.raises(ValueError, match="reserved keys: outcome"):
        with log_stage(logger, PipelineStage.INTAKE) as record:
            record.add(outcome="fine")
