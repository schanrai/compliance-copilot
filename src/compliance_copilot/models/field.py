"""The `Field` wrapper every stated answer is stored in (PRD §7.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Generic, Self, TypeVar

from pydantic import model_validator

from compliance_copilot.models._base import ImmutableModel

ValueT = TypeVar("ValueT")


class FieldSource(StrEnum):
    """Where an answer came from."""

    PRD_PARSE = "prd_parse"
    QA_ANSWER = "qa_answer"
    PASTED_COPY = "pasted_copy"
    INFERRED_FROM_PRD = "inferred_from_prd"


class FieldState(StrEnum):
    """Whether the founder was asked, and what kind of answer they gave."""

    ANSWERED = "answered"
    SKIPPED = "skipped"
    NOT_ASKED = "not_asked"
    UNKNOWN_TO_USER = "unknown_to_user"


class Field(ImmutableModel, Generic[ValueT]):
    """One stated answer with its provenance and answer state.

    `unknown_to_user` is a real answer, not a missing one. It must never
    collapse into "no": it is often the direct cause of an ambiguous
    determination.

    A field that was never asked has no source. Every other state came from
    somewhere, so it must name the source. Only `answered` carries a value.
    """

    value: ValueT | None = None
    source: FieldSource | None = None
    state: FieldState

    @model_validator(mode="after")
    def _state_matches_value_and_source(self) -> Self:
        problems: list[str] = []
        if self.state is FieldState.ANSWERED:
            if self.value is None:
                problems.append("state 'answered' needs a value")
        elif self.value is not None:
            problems.append(
                f"state '{self.state}' must not carry a value; only 'answered' does"
            )
        if self.state is FieldState.NOT_ASKED:
            if self.source is not None:
                problems.append("state 'not_asked' must not name a source")
        elif self.source is None:
            problems.append(f"state '{self.state}' needs a source")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @classmethod
    def not_asked(cls) -> Self:
        """A field Intake never asked about."""

        return cls(state=FieldState.NOT_ASKED)
