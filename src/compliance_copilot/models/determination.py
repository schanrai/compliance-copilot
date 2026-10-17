"""The covered-entity determination and the framework summary (PRD §7.2, §9, §11.2)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field as PydanticField
from pydantic import model_validator

from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.models.stated import FieldPath


class CoveredEntityStatus(StrEnum):
    COVERED_ENTITY = "covered_entity"
    BUSINESS_ASSOCIATE = "business_associate"
    NEITHER = "neither"
    AMBIGUOUS = "ambiguous"


class AmbiguityCause(StrEnum):
    """The three named causes of an ambiguous determination (PRD §9)."""

    MISSING_FACT = "missing_fact"
    CONTESTED_QUESTION = "contested_question"
    REQUIRES_DOCUMENT_WE_CANNOT_SEE = "requires_document_we_cannot_see"


class Applicability(StrEnum):
    """The three determination states. Never a forced binary (PRD §9)."""

    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    AMBIGUOUS = "ambiguous"


class SummaryCategory(StrEnum):
    """Every framework lands in exactly one (PRD §11.2)."""

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    UNRESOLVED = "unresolved"
    NOT_ASSESSED = "not_assessed"


class Framework(StrEnum):
    """The v1 frameworks a framework summary must account for (PRD §5.1)."""

    HIPAA = "HIPAA"
    HBNR = "HBNR"
    FTC_5 = "FTC_5"
    WA_MHMDA = "WA_MHMDA"
    CT = "CT"
    NV = "NV"
    TX_NE = "TX_NE"
    SOC_2 = "SOC_2"
    PCI_DSS = "PCI_DSS"


_APPLICABILITY_BY_STATUS: dict[CoveredEntityStatus, Applicability] = {
    CoveredEntityStatus.COVERED_ENTITY: Applicability.APPLIES,
    CoveredEntityStatus.BUSINESS_ASSOCIATE: Applicability.APPLIES,
    CoveredEntityStatus.NEITHER: Applicability.DOES_NOT_APPLY,
    CoveredEntityStatus.AMBIGUOUS: Applicability.AMBIGUOUS,
}

_CATEGORY_BY_APPLICABILITY: dict[Applicability, SummaryCategory] = {
    Applicability.APPLIES: SummaryCategory.IN_SCOPE,
    Applicability.DOES_NOT_APPLY: SummaryCategory.OUT_OF_SCOPE,
    Applicability.AMBIGUOUS: SummaryCategory.UNRESOLVED,
}


def applicability_of(status: CoveredEntityStatus) -> Applicability:
    return _APPLICABILITY_BY_STATUS[status]


def hipaa_category_of(status: CoveredEntityStatus) -> SummaryCategory:
    """The HIPAA summary category a covered-entity status puts HIPAA in."""

    return _CATEGORY_BY_APPLICABILITY[applicability_of(status)]


def framework_coverage_problems(frameworks: Iterable[Framework]) -> list[str]:
    """Problems with a summary's framework list: duplicates or missing frameworks."""

    counts = Counter(list(frameworks))
    problems: list[str] = []
    duplicated = sorted(f.value for f, n in counts.items() if n > 1)
    if duplicated:
        problems.append(f"frameworks listed more than once: {', '.join(duplicated)}")
    missing = sorted(f.value for f in Framework if f not in counts)
    if missing:
        problems.append(f"frameworks missing from the summary: {', '.join(missing)}")
    return problems


def _duplicates(items: Iterable[str]) -> list[str]:
    return sorted(item for item, n in Counter(items).items() if n > 1)


class Determination(ImmutableModel):
    """The covered-entity determination, as derived by the Router.

    Ambiguous carries exactly one named cause and at least one unresolved
    question. A determined result carries neither.
    """

    value: CoveredEntityStatus
    derived_from: Annotated[tuple[FieldPath, ...], PydanticField(min_length=1)]
    ambiguity_cause: AmbiguityCause | None = None
    unresolved_questions: tuple[NonBlankStr, ...] = ()

    @model_validator(mode="after")
    def _ambiguity_is_consistent(self) -> Self:
        problems: list[str] = []
        duplicated = _duplicates(self.derived_from)
        if duplicated:
            problems.append(f"derived_from repeats paths: {', '.join(duplicated)}")
        if self.value is CoveredEntityStatus.AMBIGUOUS:
            if self.ambiguity_cause is None:
                problems.append("an ambiguous determination needs an ambiguity_cause")
            if not self.unresolved_questions:
                problems.append(
                    "an ambiguous determination needs at least one unresolved question"
                )
        else:
            if self.ambiguity_cause is not None:
                problems.append(
                    f"'{self.value}' is determined; it must not carry an ambiguity_cause"
                )
            if self.unresolved_questions:
                problems.append(
                    f"'{self.value}' is determined; it must not carry unresolved questions"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def applicability(self) -> Applicability:
        return applicability_of(self.value)

    @property
    def hipaa_category(self) -> SummaryCategory:
        return hipaa_category_of(self.value)


class FrameworkSummaryEntry(ImmutableModel):
    """One framework's line in the framework summary.

    In scope, out of scope and unresolved come from a determination, so they
    trace to intake answers. Not assessed means the tool did not look, so
    there is nothing to trace.
    """

    framework: Framework
    category: SummaryCategory
    derived_from: tuple[FieldPath, ...] = ()
    reason: NonBlankStr

    @model_validator(mode="after")
    def _derived_from_matches_category(self) -> Self:
        if self.category is SummaryCategory.NOT_ASSESSED:
            if self.derived_from:
                raise ValueError(
                    f"{self.framework} is not assessed: the tool did not look, so "
                    "derived_from must be empty"
                )
        elif not self.derived_from:
            raise ValueError(
                f"{self.framework} is {self.category}: derived_from must name the "
                "intake answers behind it"
            )
        duplicated = _duplicates(self.derived_from)
        if duplicated:
            raise ValueError(f"derived_from repeats paths: {', '.join(duplicated)}")
        return self
