"""Intake and router steps for one covered-entity determination (PRD §13).

The chain starts at intake. Its field paths are the determination's
`derived_from`. A later phase appends specialist and amender steps with
`Trace.with_step`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from compliance_copilot.models import (
    Applicability,
    FieldState,
    IntakeDetail,
    RouterDetail,
    Stage,
    StatedFacts,
    Trace,
    TraceAction,
    TraceStep,
)
from compliance_copilot.router.determine import CoveredEntityDecision
from compliance_copilot.router.paths import field_at, label_for

_CAPTURED = "intake-captured"
_UNKNOWN = "intake-unknown"
_DETERMINATION = "covered-entity-status"

_ROUTER_ACTION = {
    Applicability.APPLIES: TraceAction.DETERMINED_IN_SCOPE,
    Applicability.DOES_NOT_APPLY: TraceAction.DETERMINED_OUT_OF_SCOPE,
    Applicability.AMBIGUOUS: TraceAction.DETERMINED_UNRESOLVED,
}


def determination_trace(
    stated: StatedFacts,
    decision: CoveredEntityDecision,
    *,
    analysis_id: str,
    at: datetime,
) -> Trace:
    """The trace of this determination. `at` is the intake step's timestamp."""

    paths = decision.determination.derived_from
    unknown = tuple(
        path for path in paths if field_at(stated, path).state is FieldState.UNKNOWN_TO_USER
    )
    captured = tuple(path for path in paths if path not in unknown)
    steps: list[TraceStep] = []
    if captured:
        steps.append(_intake(stated, 1, at, captured, unknown=False, received=()))
    if unknown:
        previous = steps[-1].produced if steps else None
        received = (previous,) if previous is not None else ()
        steps.append(
            _intake(
                stated,
                len(steps) + 1,
                at + timedelta(seconds=len(steps)),
                unknown,
                unknown=True,
                received=received,
            )
        )
    last = steps[-1]
    cause = decision.determination.ambiguity_cause
    steps.append(
        TraceStep(
            seq=len(steps) + 1,
            stage=Stage.ROUTER,
            agent_id="router",
            timestamp=at + timedelta(seconds=len(steps)),
            received=(last.produced,),
            produced=_DETERMINATION,
            action=_ROUTER_ACTION[decision.determination.applicability],
            rationale=decision.rationale,
            detail=RouterDetail(
                determination=decision.determination.applicability,
                ambiguity_cause=cause,
            ),
        )
    )
    return Trace(
        id=f"trace-{analysis_id}",
        analysis_id=analysis_id,
        output_element_id=_DETERMINATION,
        steps=tuple(steps),
    )


def _intake(
    stated: StatedFacts,
    seq: int,
    at: datetime,
    paths: tuple[str, ...],
    *,
    unknown: bool,
    received: tuple[str, ...],
) -> TraceStep:
    labels = "; ".join(_label(stated, path) for path in paths)
    if unknown:
        action = TraceAction.MARKED_UNKNOWN
        produced = _UNKNOWN
        rationale = f"You don't know: {labels}."
    else:
        action = TraceAction.CAPTURED
        produced = _CAPTURED
        rationale = f"Recorded: {labels}."
    return TraceStep(
        seq=seq,
        stage=Stage.INTAKE,
        agent_id="intake",
        timestamp=at,
        received=received,
        produced=produced,
        action=action,
        rationale=rationale,
        detail=IntakeDetail(field_paths=paths),
    )


def _label(stated: StatedFacts, path: str) -> str:
    label = label_for(stated, path)
    state = field_at(stated, path).state
    if state is FieldState.NOT_ASKED:
        return f"{label} (not asked)"
    if state is FieldState.SKIPPED:
        return f"{label} (skipped)"
    return label
