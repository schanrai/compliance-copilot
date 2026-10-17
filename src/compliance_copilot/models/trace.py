"""The decision trace: an append-only chain of steps (PRD §13).

A `Trace` is frozen and its steps are a tuple. The only way to add a step is
`with_step`, which returns a new, re-validated trace. No method updates or
deletes a step.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, PositiveInt, model_validator
from pydantic import Field as PydanticField

from compliance_copilot.models._base import Identifier, ImmutableModel, NonBlankStr
from compliance_copilot.models.clause import ClauseId, Modality
from compliance_copilot.models.determination import (
    AmbiguityCause,
    Applicability,
    Framework,
)
from compliance_copilot.models.requirement import OutputType
from compliance_copilot.models.stated import FieldPath


class Stage(StrEnum):
    INTAKE = "intake"
    ROUTER = "router"
    SPECIALIST = "specialist"
    SYNTHESIZER = "synthesizer"
    AMENDER = "amender"
    FAILURE = "failure"


class TraceAction(StrEnum):
    """The controlled action vocabulary (PRD §13.2). Never shown to the founder."""

    CAPTURED = "captured"
    PARSED_FROM_PRD = "parsed_from_prd"
    MARKED_UNKNOWN = "marked_unknown"
    DETERMINED_IN_SCOPE = "determined_in_scope"
    DETERMINED_OUT_OF_SCOPE = "determined_out_of_scope"
    DETERMINED_UNRESOLVED = "determined_unresolved"
    MARKED_NOT_ASSESSED = "marked_not_assessed"
    RECEIVED_CLAUSE_SET = "received_clause_set"
    EMITTED_REQUIREMENT = "emitted_requirement"
    RETURNED_LOW_CONFIDENCE = "returned_low_confidence"
    KEPT_AS_IS = "kept_as_is"
    MERGED_DUPLICATES = "merged_duplicates"
    FLAGGED_OVERLAP = "flagged_overlap"
    WROTE_TO_STRICTEST = "wrote_to_strictest"
    FLAGGED_PREEMPTION = "flagged_preemption"
    CLASSIFIED_OUTPUT_TYPE = "classified_output_type"
    DERIVED_VIA_IMPLICATION = "derived_via_implication"
    WROTE_REQUIREMENT = "wrote_requirement"
    ATTACHED_OPEN_ITEM = "attached_open_item"
    TIMED_OUT = "timed_out"
    EMPTY_CLAUSE_SET = "empty_clause_set"
    CITATION_UNRESOLVED = "citation_unresolved"
    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"


A = TraceAction
ACTIONS_BY_STAGE: dict[Stage, frozenset[TraceAction]] = {
    Stage.INTAKE: frozenset({A.CAPTURED, A.PARSED_FROM_PRD, A.MARKED_UNKNOWN}),
    Stage.ROUTER: frozenset(
        {
            A.DETERMINED_IN_SCOPE,
            A.DETERMINED_OUT_OF_SCOPE,
            A.DETERMINED_UNRESOLVED,
            A.MARKED_NOT_ASSESSED,
        }
    ),
    Stage.SPECIALIST: frozenset(
        {A.RECEIVED_CLAUSE_SET, A.EMITTED_REQUIREMENT, A.RETURNED_LOW_CONFIDENCE}
    ),
    Stage.SYNTHESIZER: frozenset(
        {
            A.KEPT_AS_IS,
            A.MERGED_DUPLICATES,
            A.FLAGGED_OVERLAP,
            A.WROTE_TO_STRICTEST,
            A.FLAGGED_PREEMPTION,
        }
    ),
    Stage.AMENDER: frozenset(
        {
            A.CLASSIFIED_OUTPUT_TYPE,
            A.DERIVED_VIA_IMPLICATION,
            A.WROTE_REQUIREMENT,
            A.ATTACHED_OPEN_ITEM,
        }
    ),
    Stage.FAILURE: frozenset(
        {
            A.TIMED_OUT,
            A.EMPTY_CLAUSE_SET,
            A.CITATION_UNRESOLVED,
            A.BELOW_CONFIDENCE_THRESHOLD,
        }
    ),
}

_DETERMINATION_BY_ROUTER_ACTION: dict[TraceAction, Applicability | None] = {
    A.DETERMINED_IN_SCOPE: Applicability.APPLIES,
    A.DETERMINED_OUT_OF_SCOPE: Applicability.DOES_NOT_APPLY,
    A.DETERMINED_UNRESOLVED: Applicability.AMBIGUOUS,
    A.MARKED_NOT_ASSESSED: None,
}


class ConflictType(StrEnum):
    OVERLAP = "overlap"
    PREEMPTION = "preemption"
    NONE = "none"


class FailureMode(StrEnum):
    TIMEOUT = "timeout"
    LOW_CONFIDENCE = "low_confidence"
    EMPTY_CLAUSE_SET = "empty_clause_set"
    CITATION_UNRESOLVED = "citation_unresolved"


_FAILURE_MODE_BY_ACTION: dict[TraceAction, FailureMode] = {
    A.TIMED_OUT: FailureMode.TIMEOUT,
    A.BELOW_CONFIDENCE_THRESHOLD: FailureMode.LOW_CONFIDENCE,
    A.EMPTY_CLAUSE_SET: FailureMode.EMPTY_CLAUSE_SET,
    A.CITATION_UNRESOLVED: FailureMode.CITATION_UNRESOLVED,
}


class IntakeDetail(ImmutableModel):
    kind: Literal["intake"] = "intake"
    field_paths: Annotated[tuple[FieldPath, ...], PydanticField(min_length=1)]


class RouterDetail(ImmutableModel):
    kind: Literal["router"] = "router"
    determination: Applicability | None = None
    ambiguity_cause: AmbiguityCause | None = None

    @model_validator(mode="after")
    def _cause_only_when_ambiguous(self) -> Self:
        is_ambiguous = self.determination is Applicability.AMBIGUOUS
        if is_ambiguous and self.ambiguity_cause is None:
            raise ValueError("an ambiguous router step needs an ambiguity_cause")
        if not is_ambiguous and self.ambiguity_cause is not None:
            raise ValueError("ambiguity_cause is only valid on an ambiguous router step")
        return self


class SpecialistDetail(ImmutableModel):
    kind: Literal["specialist"] = "specialist"
    citation: ClauseId | None = None
    corpus_version: NonBlankStr | None = None
    retrieved_at: AwareDatetime | None = None
    modality: Modality | None = None


class SynthesizerDetail(ImmutableModel):
    kind: Literal["synthesizer"] = "synthesizer"
    merged_from: tuple[Identifier, ...] = ()
    conflict_type: ConflictType = ConflictType.NONE
    strictest_source: NonBlankStr | None = None


class AmenderDetail(ImmutableModel):
    kind: Literal["amender"] = "amender"
    output_type: OutputType
    implication_id: Identifier | None = None
    open_item_attached: bool = False


class FailureDetail(ImmutableModel):
    kind: Literal["failure"] = "failure"
    failure_mode: FailureMode
    affected_framework: Framework | None = None


TraceDetail = Annotated[
    IntakeDetail
    | RouterDetail
    | SpecialistDetail
    | SynthesizerDetail
    | AmenderDetail
    | FailureDetail,
    PydanticField(discriminator="kind"),
]


class TraceStep(ImmutableModel):
    """One stage's contribution to an output element's lineage.

    `rationale` is the founder-facing text. `action` is for rendering, evals
    and queries, and is never shown.
    """

    seq: PositiveInt
    stage: Stage
    agent_id: Identifier | None = None
    timestamp: AwareDatetime
    received: tuple[Identifier, ...] = ()
    produced: Identifier
    action: TraceAction
    rationale: NonBlankStr
    detail: TraceDetail

    @model_validator(mode="after")
    def _step_is_coherent(self) -> Self:
        problems: list[str] = []
        if self.detail.kind != self.stage.value:
            problems.append(
                f"detail is for stage '{self.detail.kind}', step is '{self.stage}'"
            )
        if self.action not in ACTIONS_BY_STAGE[self.stage]:
            problems.append(f"action '{self.action}' does not belong to stage '{self.stage}'")
        if self.stage is not Stage.INTAKE and not self.received:
            problems.append(f"a {self.stage} step must name what it received")

        detail = self.detail
        if isinstance(detail, RouterDetail) and self.action in _DETERMINATION_BY_ROUTER_ACTION:
            expected = _DETERMINATION_BY_ROUTER_ACTION[self.action]
            if detail.determination is not expected:
                problems.append(
                    f"router action '{self.action}' needs determination '{expected}', "
                    f"got '{detail.determination}'"
                )
        if (
            isinstance(detail, SpecialistDetail)
            and self.action is A.EMITTED_REQUIREMENT
            and detail.citation is None
        ):
            problems.append("an emitted_requirement step needs a citation")
        if (
            isinstance(detail, AmenderDetail)
            and self.action is A.DERIVED_VIA_IMPLICATION
            and detail.implication_id is None
        ):
            problems.append("a derived_via_implication step needs an implication_id")
        if isinstance(detail, FailureDetail) and self.action in _FAILURE_MODE_BY_ACTION:
            expected_mode = _FAILURE_MODE_BY_ACTION[self.action]
            if detail.failure_mode is not expected_mode:
                problems.append(
                    f"failure action '{self.action}' needs failure_mode "
                    f"'{expected_mode}', got '{detail.failure_mode}'"
                )
        if problems:
            raise ValueError(f"trace step {self.seq}: " + "; ".join(problems))
        return self


class Trace(ImmutableModel):
    """The lineage of one output element, earliest step first.

    Every chain starts at an intake step carrying field paths into the
    stated facts (PRD §13.4). Each later step must have received something an
    earlier step produced, so the steps form a chain rather than a list.
    """

    id: Identifier
    analysis_id: Identifier
    output_element_id: Identifier
    steps: Annotated[tuple[TraceStep, ...], PydanticField(min_length=1)]

    @model_validator(mode="after")
    def _chain_is_intact(self) -> Self:
        problems: list[str] = []
        if self.steps[0].stage is not Stage.INTAKE:
            problems.append(
                f"the chain must terminate at an intake step; step 1 is "
                f"'{self.steps[0].stage}'"
            )
        produced_so_far: set[str] = set()
        previous = None
        for position, step in enumerate(self.steps, start=1):
            if step.seq != position:
                problems.append(f"step at position {position} has seq {step.seq}")
            if previous is not None:
                if step.timestamp < previous.timestamp:
                    problems.append(f"step {position} is timestamped before step {position - 1}")
                if not produced_so_far.intersection(step.received):
                    problems.append(
                        f"step {position} received nothing an earlier step produced; "
                        "the chain is broken"
                    )
            produced_so_far.add(step.produced)
            previous = step
        if problems:
            raise ValueError(f"trace {self.id}: " + "; ".join(problems))
        return self

    @property
    def next_seq(self) -> int:
        return len(self.steps) + 1

    def with_step(self, step: TraceStep) -> Trace:
        """A new trace with `step` appended. This trace is unchanged."""

        return Trace(
            id=self.id,
            analysis_id=self.analysis_id,
            output_element_id=self.output_element_id,
            steps=(*self.steps, step),
        )
