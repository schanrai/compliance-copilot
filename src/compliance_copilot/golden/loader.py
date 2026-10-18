"""Read golden-set YAML fixtures into `GoldenCase` models. Any malformed file fails loudly."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from compliance_copilot.golden.models import GoldenCase
from compliance_copilot.log import PipelineStage, log_stage
from compliance_copilot.strict_yaml import load_strict_yaml

logger = logging.getLogger(__name__)

CASE_SUFFIX = ".yaml"


class GoldenCaseError(Exception):
    """A golden-set fixture, or the fixture directory, cannot be used."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def _format_validation_error(exc: ValidationError) -> str:
    lines = [
        f"  {'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in exc.errors()
    ]
    return "fixture does not match the GoldenCase schema:\n" + "\n".join(lines)


def _read_case(path: Path) -> GoldenCase:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GoldenCaseError(path, f"cannot read file: {exc}") from exc
    try:
        data = load_strict_yaml(raw_text)
    except yaml.YAMLError as exc:
        raise GoldenCaseError(path, f"invalid YAML: {exc}") from exc
    if data is None:
        raise GoldenCaseError(path, "file is empty")
    if not isinstance(data, dict):
        raise GoldenCaseError(
            path, f"top level must be a mapping, got {type(data).__name__}"
        )
    try:
        return GoldenCase.model_validate(data)
    except ValidationError as exc:
        raise GoldenCaseError(path, _format_validation_error(exc)) from exc


def load_golden_case(path: Path) -> GoldenCase:
    """Load and validate one fixture."""

    with log_stage(logger, PipelineStage.LOAD_CASES) as record:
        record.add(path=str(path))
        case = _read_case(path)
        record.add(case_id=case.id, cases_loaded=1)
        return case


def case_files(directory: Path) -> tuple[Path, ...]:
    """The fixture files in `directory`, sorted by name.

    A `.yml` file is an error rather than being skipped, so a case cannot drop
    out of the golden set because of its extension.
    """

    if not directory.is_dir():
        raise GoldenCaseError(directory, "golden-set directory does not exist")
    wrong_suffix = sorted(p.name for p in directory.glob("*.yml"))
    if wrong_suffix:
        raise GoldenCaseError(
            directory,
            f"fixtures must use the {CASE_SUFFIX} suffix; rename: {', '.join(wrong_suffix)}",
        )
    return tuple(sorted(directory.glob(f"*{CASE_SUFFIX}")))


def load_golden_cases(directory: Path) -> tuple[GoldenCase, ...]:
    """Load every fixture in `directory`. Fails on the first bad file, on none, or on repeated ids."""

    with log_stage(logger, PipelineStage.LOAD_CASES) as record:
        record.add(directory=str(directory))
        files = case_files(directory)
        if not files:
            raise GoldenCaseError(directory, f"no {CASE_SUFFIX} golden cases found")
        cases = tuple(_read_case(path) for path in files)
        repeated = sorted(i for i, n in Counter(c.id for c in cases).items() if n > 1)
        if repeated:
            raise GoldenCaseError(directory, f"case ids repeat: {', '.join(repeated)}")
        record.add(cases_loaded=len(cases), case_ids=[c.id for c in cases])
        return cases
