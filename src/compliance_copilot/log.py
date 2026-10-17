"""Structured logging. One JSON object per line, written to stderr.

`log_stage` wraps one pipeline stage and writes exactly one line when the
stage ends, whether it succeeds or raises.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from compliance_copilot.config import Settings, load_settings

_STRUCTURED_ATTR = "structured"

_RESERVED_KEYS = frozenset(
    {
        "timestamp",
        "level",
        "logger",
        "message",
        "exception",
        "stage",
        "run_id",
        "outcome",
        "duration_ms",
        "error_type",
        "error",
    }
)


class PipelineStage(StrEnum):
    LOAD_CASES = "load_cases"
    INTAKE = "intake"
    ROUTER = "router"
    SPECIALIST = "specialist"
    AMENDER = "amender"
    RENDER = "render"


class StageOutcome(StrEnum):
    OK = "ok"
    ERROR = "error"


class StructuredFormatter(logging.Formatter):
    """Format a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        structured = getattr(record, _STRUCTURED_ATTR, None)
        if isinstance(structured, Mapping):
            payload.update(structured)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: Settings | None = None) -> logging.Logger:
    """Attach one stderr handler to the `compliance_copilot` logger.

    Calling this again replaces the handler, so log lines are not duplicated.
    Library loggers are left alone.
    """

    resolved = settings if settings is not None else load_settings()
    logger = logging.getLogger("compliance_copilot")
    logger.setLevel(resolved.log_level.value)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


class StageRecord:
    """Fields a stage adds to its one log line, e.g. how many cases it loaded."""

    def __init__(self) -> None:
        self._fields: dict[str, Any] = {}

    def add(self, **fields: Any) -> None:
        clashes = _RESERVED_KEYS.intersection(fields)
        if clashes:
            raise ValueError(
                f"stage log fields cannot use reserved keys: {', '.join(sorted(clashes))}"
            )
        self._fields.update(fields)

    @property
    def fields(self) -> Mapping[str, Any]:
        return MappingProxyType(self._fields)


@contextmanager
def log_stage(
    logger: logging.Logger, stage: PipelineStage, run_id: str | None = None
) -> Iterator[StageRecord]:
    """Write one structured line when the wrapped stage ends.

    On success: level INFO, outcome `ok`. On an exception: level ERROR,
    outcome `error`, the exception type and message, and the exception is
    re-raised unchanged.
    """

    record = StageRecord()
    started = time.perf_counter()

    def emit(level: int, message: str, outcome: StageOutcome, **extra: Any) -> None:
        line: dict[str, Any] = {
            "stage": stage.value,
            "outcome": outcome.value,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            **record.fields,
            **extra,
        }
        if run_id is not None:
            line["run_id"] = run_id
        logger.log(level, message, extra={_STRUCTURED_ATTR: line})

    try:
        yield record
    except Exception as exc:
        emit(
            logging.ERROR,
            "stage failed",
            StageOutcome.ERROR,
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise
    emit(logging.INFO, "stage completed", StageOutcome.OK)
