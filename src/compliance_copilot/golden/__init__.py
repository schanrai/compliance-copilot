"""Golden-set fixtures: schema and loader."""

from compliance_copilot.golden.loader import (
    GoldenCaseError,
    case_files,
    load_golden_case,
    load_golden_cases,
)
from compliance_copilot.golden.models import ExpectedOutcome, ExpectedRequirement, GoldenCase

__all__ = [
    "ExpectedOutcome",
    "ExpectedRequirement",
    "GoldenCase",
    "GoldenCaseError",
    "case_files",
    "load_golden_case",
    "load_golden_cases",
]
