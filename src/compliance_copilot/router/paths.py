"""Field paths the covered-entity rules read, and the words used to show them.

`has_signed_agreements_with_healthcare_orgs` is absent on purpose. A signed
agreement does not decide covered-entity or business-associate status, so the
rules never read it and it never appears in `derived_from`.
"""

from __future__ import annotations

from compliance_copilot.models import CustomerType, Field, StatedFacts

CUSTOMERS = "stated.hipaa_situation.customer_types"
CUSTOMERS_BILL = "stated.hipaa_situation.customers_bill_insurers_electronically"
RECEIVES = "stated.hipaa_situation.receives_patient_data_from_others"
CLINICAL = "stated.hipaa_situation.receives_clinical_information"
BILLS = "stated.hipaa_situation.bills_insurers_electronically"
CARE = "stated.hipaa_situation.provides_care_directly"

# Golden-set order: the business-associate facts, then the founder's own
# covered-entity facts with care before billing (45 CFR 160.103: a provider
# who transmits).
_ORDER = (CUSTOMERS, CUSTOMERS_BILL, RECEIVES, CLINICAL, CARE, BILLS)

FIELD_LABELS: dict[str, str] = {
    CUSTOMERS: "Who your customers are",
    CUSTOMERS_BILL: "Whether the clinic you sell to bills insurers electronically",
    RECEIVES: "Whether you receive patient data from someone else",
    CLINICAL: "Whether that data includes clinical information",
    BILLS: "Whether you bill insurers electronically",
    CARE: "Whether you provide care directly",
}

CUSTOMER_LABELS: dict[CustomerType, str] = {
    CustomerType.CLINICS: "clinics",
    CustomerType.CONSUMERS: "consumers",
    CustomerType.EMPLOYERS: "employers",
    CustomerType.INSURERS: "health insurers",
    CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS: (
        "companies that handle patient data for providers"
    ),
}

_PREFIX = "stated.hipaa_situation."


class PathError(Exception):
    """A path is not one of the stated fields the determination can cite."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path

    def __str__(self) -> str:
        return f"'{self.path}' is not a hipaa_situation field the determination reads"


def ordered(paths: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Unique paths in the order the golden set lists them."""

    rank = {path: index for index, path in enumerate(_ORDER)}
    unknown = [path for path in paths if path not in rank]
    if unknown:
        raise PathError(unknown[0])
    return tuple(sorted(dict.fromkeys(paths), key=rank.__getitem__))


def field_at(stated: StatedFacts, path: str) -> Field[object]:
    """The stated field a `derived_from` path names."""

    if not path.startswith(_PREFIX):
        raise PathError(path)
    field = getattr(stated.hipaa_situation, path.removeprefix(_PREFIX), None)
    if not isinstance(field, Field):
        raise PathError(path)
    return field


def customer_phrase(types: tuple[CustomerType, ...]) -> str:
    """'clinics', or 'consumers and clinics'."""

    names = [CUSTOMER_LABELS[customer_type] for customer_type in types]
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"
