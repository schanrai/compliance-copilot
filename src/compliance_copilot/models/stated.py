"""The stated half of the Compliance Context Object: what the founder said (PRD §7.2).

Only the parts the covered-entity determination reads. Not the full schema.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, StrictBool, StringConstraints
from pydantic import Field as PydanticField
from pydantic import model_validator

from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.models.field import Field, FieldState


class CustomerType(StrEnum):
    """Who the founder sells to, as stated. Not a conclusion about their status."""

    CLINICS = "clinics"
    CONSUMERS = "consumers"
    EMPLOYERS = "employers"
    INSURERS = "insurers"
    COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS = (
        "companies_handling_patient_data_for_providers"
    )


CustomerTypes = Annotated[tuple[CustomerType, ...], PydanticField(min_length=1)]


class Product(ImmutableModel):
    """What product is being analysed."""

    description: Field[NonBlankStr]

    @model_validator(mode="after")
    def _description_is_answered(self) -> Self:
        if self.description.state is not FieldState.ANSWERED:
            raise ValueError(
                "product.description must be answered: identifying the product is "
                "the one fact the analysis cannot proceed without (PRD §7.4)"
            )
        return self


class HipaaSituation(ImmutableModel):
    """Situational answers the covered-entity determination reads.

    These are the facts, not the determination. A field left out was not asked.
    """

    customer_types: Field[CustomerTypes] = PydanticField(
        default_factory=Field[CustomerTypes].not_asked
    )
    customers_bill_insurers_electronically: Field[StrictBool] = PydanticField(
        default_factory=Field[StrictBool].not_asked
    )
    receives_patient_data_from_others: Field[StrictBool] = PydanticField(
        default_factory=Field[StrictBool].not_asked
    )
    has_signed_agreements_with_healthcare_orgs: Field[StrictBool] = PydanticField(
        default_factory=Field[StrictBool].not_asked
    )
    bills_insurers_electronically: Field[StrictBool] = PydanticField(
        default_factory=Field[StrictBool].not_asked
    )
    provides_care_directly: Field[StrictBool] = PydanticField(
        default_factory=Field[StrictBool].not_asked
    )


class StatedFacts(ImmutableModel):
    """Everything stated by the founder that the determination reads."""

    product: Product
    hipaa_situation: HipaaSituation


def _field_path_exists(path: str) -> str:
    """Check a dotted path names a `Field` in `StatedFacts`, and ends there."""

    segments = path.split(".")
    model: type[BaseModel] = StatedFacts
    for position, segment in enumerate(segments[1:], start=1):
        info = model.model_fields.get(segment)
        if info is None:
            raise ValueError(
                f"'{path}': '{segment}' is not a field of {model.__name__}"
            )
        annotation = info.annotation
        is_last = position == len(segments) - 1
        if isinstance(annotation, type) and issubclass(annotation, Field):
            if not is_last:
                raise ValueError(f"'{path}': continues past the field '{segment}'")
            return path
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            model = annotation
            continue
        raise ValueError(f"'{path}': '{segment}' is not a stated field or group")
    raise ValueError(f"'{path}': ends at a group, not a stated field")


FieldPath = Annotated[
    str,
    StringConstraints(pattern=r"^stated(?:\.[a-z][a-z0-9_]*)+$"),
    AfterValidator(_field_path_exists),
]
"""A path into the stated facts, e.g. `stated.hipaa_situation.customer_types`.

This is where every trace chain terminates (PRD §7.3, §13.4).
"""
