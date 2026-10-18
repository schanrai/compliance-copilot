"""Run the covered-entity determination and record its trace.

Logging is here. The rules and the trace builder stay pure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from compliance_copilot.log import PipelineStage, log_stage
from compliance_copilot.models import Field, StatedFacts, Trace
from compliance_copilot.router.determine import CoveredEntityDecision, determine
from compliance_copilot.trace.determination import determination_trace

logger = logging.getLogger(__name__)


class RunError(Exception):
    """The determination could not be run."""


@dataclass(frozen=True, slots=True)
class CoveredEntityRun:
    """What Phase 3 produces: the determination, its reasoning, and its trace."""

    decision: CoveredEntityDecision
    trace: Trace


def run_determination(
    stated: StatedFacts,
    *,
    analysis_id: str,
    at: datetime | None = None,
) -> CoveredEntityRun:
    """Accept the stated facts, determine, and write the intake and router steps.

    `at` timestamps the trace. The default is the current time, in UTC.
    """

    moment = _aware(at)
    with log_stage(logger, PipelineStage.INTAKE, run_id=analysis_id) as record:
        record.add(fields=_field_states(stated))
    with log_stage(logger, PipelineStage.ROUTER, run_id=analysis_id) as record:
        decision = determine(stated)
        trace = determination_trace(stated, decision, analysis_id=analysis_id, at=moment)
        cause = decision.determination.ambiguity_cause
        record.add(
            covered_entity_status=decision.determination.value.value,
            ambiguity_cause=None if cause is None else cause.value,
            derived_from=list(decision.determination.derived_from),
        )
    return CoveredEntityRun(decision=decision, trace=trace)


def _aware(at: datetime | None) -> datetime:
    if at is None:
        return datetime.now(UTC)
    if at.tzinfo is None:
        raise RunError("trace timestamp must be timezone-aware")
    return at


def _field_states(stated: StatedFacts) -> dict[str, str]:
    situation = stated.hipaa_situation
    return {
        name: field.state.value
        for name in type(situation).model_fields
        if isinstance(field := getattr(situation, name), Field)
    }
