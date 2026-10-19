"""Gate 4: framework summaries, and the ambiguous deliverable."""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from rich.console import Console

from compliance_copilot.golden import case_files, load_golden_case
from compliance_copilot.models import CoveredEntityStatus, SummaryCategory
from compliance_copilot.output.ambiguous import ambiguous_output
from compliance_copilot.render.summary import ambiguous_panel, category_style, summary_panel
from compliance_copilot.router import determine
from compliance_copilot.router.summary import framework_summary

CASES = Path(__file__).parent / "cases"
CASE_FILES = case_files(CASES)


def _plain(renderable: object) -> str:
    console = Console(record=True, width=100, file=io.StringIO())
    console.print(renderable)
    return re.sub(r"\s+", " ", re.sub(r"[│╭╮╰╯─]", " ", console.export_text()))


@pytest.mark.parametrize("path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_golden_framework_summary_matches(path: Path) -> None:
    case = load_golden_case(path)
    decision = determine(case.stated)
    summary = framework_summary(decision)

    assert {entry.framework: entry.category for entry in summary} == case.expected.framework_summary
    hipaa = summary[0]
    assert hipaa.derived_from == case.expected.derived_from
    assert len(summary) == len(case.expected.framework_summary)


@pytest.mark.parametrize("path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_ambiguous_cases_have_components_1_through_4_and_6(path: Path) -> None:
    case = load_golden_case(path)
    decision = determine(case.stated)
    output = ambiguous_output(case.stated, decision)

    if case.expected.ambiguous_components is None:
        assert output is None
        assert decision.determination.value is not CoveredEntityStatus.AMBIGUOUS
        return
    assert output is not None
    assert output.present_components == case.expected.ambiguous_components
    assert case.stated.product.description.value in output.counsel_question
    assert output.counsel_question.count("?") >= 1
    assert "45 CFR 160.103" in output.counsel_question
    assert "30 minutes" in output.counsel_question
    assert "Specified, next" in output.build_regardless


def test_unresolved_and_not_assessed_render_differently() -> None:
    case = load_golden_case(CASES / "g-05.yaml")
    decision = determine(case.stated)
    summary = framework_summary(decision)
    rendered = _plain(summary_panel(summary))
    unresolved = ambiguous_output(case.stated, decision)
    assert unresolved is not None
    counsel = _plain(ambiguous_panel(unresolved))

    assert category_style(SummaryCategory.UNRESOLVED) != category_style(SummaryCategory.NOT_ASSESSED)
    assert "Unresolved — we looked and could not settle it" in rendered
    assert "Not assessed — we did not look" in rendered
    assert "Question for counsel" in counsel
    assert "we did not look" not in counsel
    assert "Specified, next" in counsel
