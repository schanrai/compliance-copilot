"""The golden-set fixture schema: one YAML file per case (implementation plan, Phase G).

The labels are a healthcare judgement written by the user. These models check
that a fixture is well formed and internally consistent. They do not judge
whether a label is right.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field as PydanticField
from pydantic import StringConstraints, model_validator

from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.models.clause import ClauseId, ClauseType, Modality
from compliance_copilot.models.determination import (
    AmbiguityCause,
    CoveredEntityStatus,
    Framework,
    SummaryCategory,
    framework_coverage_problems,
    hipaa_category_of,
)
from compliance_copilot.models.requirement import EvidenceType
from compliance_copilot.models.stated import FieldPath, StatedFacts

GoldenCaseId = Annotated[str, StringConstraints(pattern=r"^G-\d{2}$")]
AmbiguousComponent = Literal[1, 2, 3, 4, 5, 6]
"""A PRD §9.1 component number."""


class ExpectedRequirement(ImmutableModel):
    """The parts of a requirement a golden case asserts. No text: wording is not labelled."""

    citation: ClauseId
    evidence_type: EvidenceType
    clause_type: ClauseType | None
    modality: Modality | None
    implication_id: NonBlankStr | None = None

    @model_validator(mode="after")
    def _fields_match_evidence_type(self) -> Self:
        problems: list[str] = []
        if self.evidence_type is EvidenceType.CITED:
            if self.implication_id is not None:
                problems.append("a cited requirement must not carry implication_id")
            if (
                self.modality is not None
                and self.clause_type is not ClauseType.IMPLEMENTATION_SPECIFICATION
            ):
                problems.append(
                    f"modality '{self.modality}' is only valid on an "
                    f"implementation_specification, not '{self.clause_type}'"
                )
        else:
            if self.implication_id is None:
                problems.append("a derived requirement needs implication_id")
            if self.clause_type is not None or self.modality is not None:
                problems.append("a derived requirement must not carry clause_type or modality")
        if problems:
            raise ValueError(f"expected requirement {self.citation}: " + "; ".join(problems))
        return self


class ExpectedOutcome(ImmutableModel):
    """What the pipeline must produce for a case. Every field must be written out."""

    covered_entity_status: CoveredEntityStatus
    ambiguity_cause: AmbiguityCause | None
    derived_from: Annotated[tuple[FieldPath, ...], PydanticField(min_length=1)]
    framework_summary: dict[Framework, SummaryCategory]
    requirements: tuple[ExpectedRequirement, ...]
    ambiguous_components: tuple[AmbiguousComponent, ...] | None

    @model_validator(mode="after")
    def _labels_are_consistent(self) -> Self:
        problems = framework_coverage_problems(self.framework_summary)
        is_ambiguous = self.covered_entity_status is CoveredEntityStatus.AMBIGUOUS
        if is_ambiguous != (self.ambiguity_cause is not None):
            problems.append(
                "ambiguity_cause must be set if and only if covered_entity_status is "
                "ambiguous"
            )
        if is_ambiguous != (self.ambiguous_components is not None):
            problems.append(
                "ambiguous_components must be a list if and only if "
                "covered_entity_status is ambiguous; otherwise null"
            )
        if self.ambiguous_components is not None and len(
            set(self.ambiguous_components)
        ) != len(self.ambiguous_components):
            problems.append("ambiguous_components repeats a component")
        expected_hipaa = hipaa_category_of(self.covered_entity_status)
        actual_hipaa = self.framework_summary.get(Framework.HIPAA)
        if actual_hipaa is not None and actual_hipaa is not expected_hipaa:
            problems.append(
                f"framework_summary puts HIPAA in '{actual_hipaa}', but "
                f"'{self.covered_entity_status}' puts it in '{expected_hipaa}'"
            )
        if expected_hipaa is not SummaryCategory.IN_SCOPE and self.requirements:
            problems.append(
                f"HIPAA is '{expected_hipaa}', so no specialist runs and requirements "
                "must be empty (PRD §9)"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class GoldenCase(ImmutableModel):
    """One golden-set fixture: the stated facts and the expected outcome."""

    id: GoldenCaseId
    title: NonBlankStr
    stated: StatedFacts
    expected: ExpectedOutcome
