"""Structured logging. One JSON object per line, written to stderr."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from compliance_copilot.config import Settings, load_settings


class StructuredFormatter(logging.Formatter):
    """Format a log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


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
