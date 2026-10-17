"""Clauses and per-framework metadata declarations (PRD §8.5, §15.1)."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, HttpUrl, model_validator

from compliance_copilot.models._base import Identifier, ImmutableModel, NonBlankStr

ClauseId = Identifier
"""Stable, citation-resolvable clause id, e.g. `45-CFR-164.312-b`."""

FrameworkId = Identifier
"""Corpus-level framework id a clause belongs to, e.g. `HIPAA-Security`.

Kept as data rather than an enum: the set grows with ingestion, and a clause
whose framework has no declaration is rejected where it is used (PRD §8.5).
"""


class ClauseType(StrEnum):
    STANDARD = "standard"
    IMPLEMENTATION_SPECIFICATION = "implementation_specification"


class Modality(StrEnum):
    """Required/Addressable. Belongs to implementation specifications only (45 CFR 164.306(d))."""

    REQUIRED = "required"
    ADDRESSABLE = "addressable"


class ClauseStatus(StrEnum):
    """v1 covers in-force regulation only."""

    IN_FORCE = "in-force"


class Jurisdiction(StrEnum):
    FEDERAL = "federal"
    STATE = "state"


class Clause(ImmutableModel):
    """One clause of regulation text, with metadata read from the source.

    `clause_type` and `modality` have no default: each is read from the source
    at ingestion, never inferred. `operative_terms` are copied verbatim from
    `text`. `implications` is provisional (PRD §8.7 Option A, not decided).
    """

    id: ClauseId
    framework: FrameworkId
    text: NonBlankStr
    heading: NonBlankStr
    clause_type: ClauseType | None
    modality: Modality | None
    status: ClauseStatus
    jurisdiction: Jurisdiction
    operative_terms: tuple[NonBlankStr, ...] = ()
    implications: tuple[Identifier, ...] = ()
    source_url: HttpUrl
    retrieved_at: AwareDatetime

    @model_validator(mode="after")
    def _metadata_is_coherent(self) -> Self:
        problems: list[str] = []
        if (
            self.modality is not None
            and self.clause_type is not ClauseType.IMPLEMENTATION_SPECIFICATION
        ):
            problems.append(
                f"modality '{self.modality}' is only valid on an implementation "
                f"specification, not on clause_type '{self.clause_type}' "
                "(45 CFR 164.306(d))"
            )
        not_verbatim = [t for t in self.operative_terms if t not in self.text]
        if not_verbatim:
            problems.append(
                "operative terms must be copied verbatim from the clause text; not "
                f"found: {not_verbatim}"
            )
        for name, values in (
            ("operative_terms", self.operative_terms),
            ("implications", self.implications),
        ):
            repeated = sorted(v for v, n in Counter(values).items() if n > 1)
            if repeated:
                problems.append(f"{name} repeats: {repeated}")
        if problems:
            raise ValueError(f"clause {self.id}: " + "; ".join(problems))
        return self


class FrameworkDeclaration(ImmutableModel):
    """A framework's clause-type and modality scheme, declared before its corpus ships.

    `clause_types` empty means the framework has no standard/specification
    hierarchy, so clause_type is null. `grades_specifications` means its
    implementation specifications carry Required or Addressable. A framework
    with no declaration cannot ship (PRD §8.5).
    """

    framework: FrameworkId
    clause_types: frozenset[ClauseType]
    grades_specifications: bool

    @model_validator(mode="after")
    def _grading_needs_specifications(self) -> Self:
        if (
            self.grades_specifications
            and ClauseType.IMPLEMENTATION_SPECIFICATION not in self.clause_types
        ):
            raise ValueError(
                f"{self.framework}: grades_specifications needs "
                "implementation_specification in clause_types"
            )
        return self

    def violations(
        self, clause_type: ClauseType | None, modality: Modality | None
    ) -> list[str]:
        """Reasons a clause_type/modality pair breaks this declaration. Empty if valid."""

        problems: list[str] = []
        if not self.clause_types:
            if clause_type is not None:
                problems.append(
                    f"{self.framework} declares no clause-type hierarchy; clause_type "
                    f"must be null, not '{clause_type}'"
                )
        elif clause_type not in self.clause_types:
            allowed = ", ".join(sorted(t.value for t in self.clause_types))
            problems.append(
                f"{self.framework} declares clause types {{{allowed}}}; got '{clause_type}'"
            )
        if modality is not None:
            if clause_type is not ClauseType.IMPLEMENTATION_SPECIFICATION:
                problems.append(
                    f"modality '{modality}' is only valid on an implementation "
                    f"specification, not on '{clause_type}'"
                )
            elif not self.grades_specifications:
                problems.append(
                    f"{self.framework} does not grade its obligations; modality must "
                    f"be null, not '{modality}'"
                )
        elif (
            self.grades_specifications
            and clause_type is ClauseType.IMPLEMENTATION_SPECIFICATION
        ):
            problems.append(
                f"{self.framework} grades implementation specifications; modality "
                "must be required or addressable. A missing label is an extraction "
                "failure, not a null"
            )
        return problems
