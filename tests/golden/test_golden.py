"""Golden-set tests. Phase 0c checks every case loads; Phase 7 adds per-stage assertions."""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance_copilot.golden import case_files, load_golden_case, load_golden_cases

CASES_DIR = Path(__file__).parent / "cases"
CASE_FILES = case_files(CASES_DIR)


@pytest.mark.parametrize("path", CASE_FILES, ids=[p.stem for p in CASE_FILES])
def test_golden_case_loads_and_validates(path: Path) -> None:
    load_golden_case(path)


def test_golden_set_loads_with_unique_ids() -> None:
    if not CASE_FILES:
        pytest.skip(f"no golden cases in {CASES_DIR.name}/ yet; Phase G writes them")
    load_golden_cases(CASES_DIR)
