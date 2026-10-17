"""The Compliance Context Object, trimmed to what the determination reads (PRD §7.2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime
from pydantic import Field as PydanticField
from pydantic import model_validator

from compliance_copilot.models._base import Identifier, ImmutableModel
from compliance_copilot.models.determination import (
    Determination,
    Framework,
    FrameworkSummaryEntry,
    framework_coverage_problems,
)
from compliance_copilot.models.stated import StatedFacts


class EntryPath(StrEnum):
    HAS_PRD = "has_prd"
    NO_PRD = "no_prd"
    EXISTING_PRODUCT_NEW_FEATURE = "existing_product_new_feature"


class DerivedFacts(ImmutableModel):
    """What the Router concluded. Empty until routing runs. Never asked of the founder."""

    covered_entity_status: Determination | None = None
    framework_applicability: tuple[FrameworkSummaryEntry, ...] = ()

    @model_validator(mode="after")
    def _summary_is_complete_and_consistent(self) -> Self:
        if not self.framework_applicability:
            return self
        problems = framework_coverage_problems(
            entry.framework for entry in self.framework_applicability
        )
        determination = self.covered_entity_status
        if determination is None:
            problems.append(
                "framework_applicability needs covered_entity_status: HIPAA's "
                "category comes from the determination"
            )
        else:
            hipaa = next(
                (e for e in self.framework_applicability if e.framework is Framework.HIPAA),
                None,
            )
            if hipaa is not None and hipaa.category is not determination.hipaa_category:
                problems.append(
                    f"HIPAA is '{hipaa.category}' but the determination "
                    f"'{determination.value}' puts it in '{determination.hipaa_category}'"
                )
        if problems:
            raise ValueError("; ".join(problems))
        return self


class ComplianceContextObject(ImmutableModel):
    """The only record Intake hands to the rest of the system.

    Stated facts are what the founder said. Derived facts are what the Router
    concluded. The two never mix (PRD §7.1 rule 1).
    """

    id: Identifier
    created_at: AwareDatetime
    entry_path: EntryPath
    stated: StatedFacts
    derived: DerivedFacts = PydanticField(default_factory=DerivedFacts)
