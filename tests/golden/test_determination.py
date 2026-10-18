"""Gate 3: golden determinations, the G-02 flip, and a trace that starts at intake."""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from compliance_copilot.cli import app
from compliance_copilot.config import load_settings
from compliance_copilot.golden import case_files, load_golden_case
from compliance_copilot.log import configure_logging
from compliance_copilot.models import (
    Applicability,
    CoveredEntityStatus,
    Field,
    FieldState,
    IntakeDetail,
    RouterDetail,
    Stage,
    TraceAction,
    TraceStep,
)
from compliance_copilot.render.determination import determination_panel
from compliance_copilot.router import determine, run_determination
from compliance_copilot.router.paths import CUSTOMERS_BILL

CASES = Path(__file__).parent / "cases"
CASE_FILES = case_files(CASES)
T0 = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
HIPAA_FIELDS = (
    "customer_types",
    "customers_bill_insurers_electronically",
    "receives_patient_data_from_others",
    "receives_clinical_information",
    "has_signed_agreements_with_healthcare_orgs",
    "bills_insurers_electronically",
    "provides_care_directly",
)
_FLIPPED = (
    "customer_types",
    "customers_bill_insurers_electronically",
    "receives_patient_data_from_others",
    "has_signed_agreements_with_healthcare_orgs",
)
_ROUTER_ACTION = {
    Applicability.APPLIES: TraceAction.DETERMINED_IN_SCOPE,
    Applicability.DOES_NOT_APPLY: TraceAction.DETERMINED_OUT_OF_SCOPE,
    Applicability.AMBIGUOUS: TraceAction.DETERMINED_UNRESOLVED,
}


def _snapshot(field: Field[object]) -> tuple[object, ...]:
    return (field.state, field.value)


@pytest.mark.parametrize("path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_golden_determination_matches(path: Path) -> None:
    case = load_golden_case(path)
    determination = determine(case.stated).determination

    assert determination.value is case.expected.covered_entity_status
    assert determination.ambiguity_cause is case.expected.ambiguity_cause
    assert determination.derived_from == case.expected.derived_from


def test_one_founder_answer_flips_the_wellness_app_to_a_business_associate() -> None:
    before = load_golden_case(CASES / "g-02.yaml")
    after = load_golden_case(CASES / "g-03.yaml")
    changed = [
        name
        for name in HIPAA_FIELDS
        if _snapshot(getattr(before.stated.hipaa_situation, name))
        != _snapshot(getattr(after.stated.hipaa_situation, name))
    ]

    assert changed == list(_FLIPPED)
    assert determine(before.stated).determination.value is CoveredEntityStatus.NEITHER
    assert determine(after.stated).determination.value is CoveredEntityStatus.BUSINESS_ASSOCIATE


def test_g06_is_a_business_associate_and_the_billing_question_was_not_asked() -> None:
    case = load_golden_case(CASES / "g-06.yaml")
    billing = case.stated.hipaa_situation.customers_bill_insurers_electronically
    decision = determine(case.stated)

    assert billing.state is FieldState.NOT_ASKED
    assert decision.determination.value is CoveredEntityStatus.BUSINESS_ASSOCIATE
    assert CUSTOMERS_BILL not in decision.determination.derived_from


@pytest.mark.parametrize("path", CASE_FILES, ids=[path.stem for path in CASE_FILES])
def test_golden_trace_starts_at_intake_and_stops_at_the_router(path: Path) -> None:
    case = load_golden_case(path)
    run = run_determination(case.stated, analysis_id=case.id, at=T0)
    steps = run.trace.steps
    determination = run.decision.determination
    router = steps[-1]

    assert steps[0].stage is Stage.INTAKE
    assert all(step.stage is Stage.INTAKE for step in steps[:-1])
    assert _intake_paths(steps) == set(determination.derived_from)
    assert router.stage is Stage.ROUTER
    assert router.action is _ROUTER_ACTION[determination.applicability]
    assert isinstance(router.detail, RouterDetail)
    assert router.detail.determination is determination.applicability
    assert router.detail.ambiguity_cause is determination.ambiguity_cause


def _intake_paths(steps: tuple[TraceStep, ...]) -> set[str]:
    paths: list[str] = []
    for step in steps:
        if step.stage is not Stage.INTAKE:
            continue
        assert isinstance(step.detail, IntakeDetail)
        paths.extend(step.detail.field_paths)
    return set(paths)


def test_an_unknown_answer_is_its_own_intake_step() -> None:
    case = load_golden_case(CASES / "g-05.yaml")
    run = run_determination(case.stated, analysis_id=case.id, at=T0)
    unknown = [step for step in run.trace.steps if step.action is TraceAction.MARKED_UNKNOWN]

    assert len(unknown) == 1
    assert isinstance(unknown[0].detail, IntakeDetail)
    assert unknown[0].detail.field_paths == (CUSTOMERS_BILL,)
    assert "don't know" in unknown[0].rationale


def _text(case_name: str) -> str:
    case = load_golden_case(CASES / case_name)
    run = run_determination(case.stated, analysis_id=case.id, at=T0)
    console = Console(record=True, width=100, file=io.StringIO())
    console.print(determination_panel(case.stated, run))
    return re.sub(r"[│╭╮╰╯─]", " ", console.export_text())


def test_determinations_print_the_status_and_the_reasoning() -> None:
    business_associate = _text("g-01.yaml")
    assert "Business associate" in business_associate
    assert "45 CFR 160.103" in business_associate
    assert "was not used" in business_associate

    unresolved = _text("g-04.yaml")
    assert "Ambiguous" in unresolved
    assert "genuinely contested question" in unresolved
    assert "What would settle it" in unresolved
    assert "not settled" in unresolved

    covered = _text("g-08.yaml")
    assert "Covered entity" in covered
    assert "What would settle it" not in covered

    missing = _text("g-05.yaml")
    assert "you don't know" in missing
    assert "Missing a fact" in missing


def test_determine_command_prints_a_golden_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(load_settings())

    result = CliRunner().invoke(app, ["determine", str(CASES / "g-06.yaml")])

    assert result.exit_code == 0, result.output
    assert "Business associate" in result.output
    assert "G-06: business_associate" in result.output
    assert "not asked" in result.output
