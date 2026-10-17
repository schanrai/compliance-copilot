"""The decision trace is an append-only chain that starts at intake (PRD §13)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from compliance_copilot.models import (
    AmbiguityCause,
    Applicability,
    FailureDetail,
    FailureMode,
    IntakeDetail,
    RouterDetail,
    SpecialistDetail,
    Stage,
    Trace,
    TraceAction,
    TraceStep,
)

T0 = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)
CUSTOMERS_PATH = "stated.hipaa_situation.customer_types"


def intake_step(**overrides: Any) -> TraceStep:
    fields: dict[str, Any] = {
        "seq": 1,
        "stage": Stage.INTAKE,
        "timestamp": T0,
        "produced": "cco-1",
        "action": TraceAction.CAPTURED,
        "rationale": "You told us you sell to clinics.",
        "detail": IntakeDetail(field_paths=(CUSTOMERS_PATH,)),
    }
    fields.update(overrides)
    return TraceStep(**fields)


def router_step(**overrides: Any) -> TraceStep:
    fields: dict[str, Any] = {
        "seq": 2,
        "stage": Stage.ROUTER,
        "timestamp": T0 + timedelta(seconds=1),
        "received": ("cco-1",),
        "produced": "det-1",
        "action": TraceAction.DETERMINED_IN_SCOPE,
        "rationale": "Clinics that bill insurers electronically are covered entities.",
        "detail": RouterDetail(determination=Applicability.APPLIES),
    }
    fields.update(overrides)
    return TraceStep(**fields)


def specialist_step(**overrides: Any) -> TraceStep:
    fields: dict[str, Any] = {
        "seq": 3,
        "stage": Stage.SPECIALIST,
        "agent_id": "hipaa",
        "timestamp": T0 + timedelta(seconds=2),
        "received": ("det-1",),
        "produced": "req_164_312_b",
        "action": TraceAction.EMITTED_REQUIREMENT,
        "rationale": "Audit controls are a Security Rule standard.",
        "detail": SpecialistDetail(citation="45-CFR-164.312-b"),
    }
    fields.update(overrides)
    return TraceStep(**fields)


def trace(*steps: TraceStep) -> Trace:
    return Trace(id="trace-1", analysis_id="analysis-1", output_element_id="req_164_312_b", steps=steps)


def test_chain_from_intake_through_specialist_is_accepted() -> None:
    chain = trace(intake_step(), router_step(), specialist_step())

    assert [s.stage for s in chain.steps] == [Stage.INTAKE, Stage.ROUTER, Stage.SPECIALIST]


def test_with_step_returns_a_new_trace_and_leaves_the_original_unchanged() -> None:
    original = trace(intake_step())

    extended = original.with_step(router_step(seq=original.next_seq))

    assert len(original.steps) == 1
    assert len(extended.steps) == 2
    assert extended.next_seq == 3


def test_no_public_method_can_update_or_delete_a_step() -> None:
    added = {n for n in dir(Trace) if not n.startswith("_")} - set(dir(BaseModel))

    assert added == {"with_step", "next_seq"}


def test_steps_cannot_be_reassigned_or_rewritten() -> None:
    chain = trace(intake_step(), router_step())

    assert isinstance(chain.steps, tuple)
    with pytest.raises(ValidationError, match="frozen"):
        chain.steps = (chain.steps[0],)  # type: ignore[misc]
    with pytest.raises(TypeError, match="skips validation"):
        chain.model_copy(update={"steps": (chain.steps[0],)})
    with pytest.raises(TypeError, match="skips validation"):
        Trace.model_construct(steps=())


def test_chain_must_start_at_intake() -> None:
    with pytest.raises(ValidationError, match="must terminate at an intake step"):
        trace(router_step(seq=1))


def test_empty_trace_is_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        trace()


def test_seq_must_be_contiguous() -> None:
    with pytest.raises(ValidationError, match="has seq 3"):
        trace(intake_step(), router_step(seq=3))


def test_steps_must_be_in_time_order() -> None:
    with pytest.raises(ValidationError, match="timestamped before"):
        trace(intake_step(), router_step(timestamp=T0 - timedelta(seconds=1)))


def test_each_step_must_consume_an_earlier_output() -> None:
    with pytest.raises(ValidationError, match="chain is broken"):
        trace(intake_step(), router_step(received=("something-else",)))


def test_appending_a_broken_step_is_rejected() -> None:
    with pytest.raises(ValidationError, match="chain is broken"):
        trace(intake_step()).with_step(router_step(received=("unknown",)))


def test_action_must_belong_to_the_stage() -> None:
    with pytest.raises(ValidationError, match="does not belong to stage 'router'"):
        router_step(action=TraceAction.EMITTED_REQUIREMENT)


def test_detail_must_match_the_stage() -> None:
    with pytest.raises(ValidationError, match="detail is for stage 'intake'"):
        router_step(detail=IntakeDetail(field_paths=(CUSTOMERS_PATH,)))


def test_router_action_must_match_its_determination() -> None:
    with pytest.raises(ValidationError, match="needs determination 'applies'"):
        router_step(detail=RouterDetail(determination=Applicability.DOES_NOT_APPLY))


def test_ambiguous_router_step_needs_a_cause() -> None:
    with pytest.raises(ValidationError, match="needs an ambiguity_cause"):
        RouterDetail(determination=Applicability.AMBIGUOUS)

    step = router_step(
        action=TraceAction.DETERMINED_UNRESOLVED,
        detail=RouterDetail(
            determination=Applicability.AMBIGUOUS, ambiguity_cause=AmbiguityCause.MISSING_FACT
        ),
    )
    assert step.action is TraceAction.DETERMINED_UNRESOLVED


def test_emitted_requirement_needs_a_citation() -> None:
    with pytest.raises(ValidationError, match="needs a citation"):
        specialist_step(detail=SpecialistDetail())


def test_failure_action_must_match_its_mode() -> None:
    with pytest.raises(ValidationError, match="needs failure_mode 'timeout'"):
        specialist_step(
            stage=Stage.FAILURE,
            action=TraceAction.TIMED_OUT,
            detail=FailureDetail(failure_mode=FailureMode.EMPTY_CLAUSE_SET),
        )


def test_non_intake_step_must_name_what_it_received() -> None:
    with pytest.raises(ValidationError, match="must name what it received"):
        router_step(received=())


def test_intake_field_paths_must_exist() -> None:
    with pytest.raises(ValidationError, match="not a field of HipaaSituation"):
        IntakeDetail(field_paths=("stated.hipaa_situation.is_business_associate",))


def test_trace_round_trips_through_json() -> None:
    chain = trace(intake_step(), router_step(), specialist_step())

    assert Trace.model_validate_json(chain.model_dump_json()) == chain
