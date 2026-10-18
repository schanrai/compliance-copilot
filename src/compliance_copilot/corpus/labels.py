"""Read `clause_type` and `modality` from the labels printed in a clause heading (PRD §15.1).

eCFR prints the labels as text: "Standard:" or "Implementation specification(s):"
before a title, and "(Required)" or "(Addressable)" after an implementation
specification's title (45 CFR 164.306(d)(1)). This module reads those
markers and nothing else. A heading with no marker reads as `None`/`None`;
nothing is inferred from the wording of the clause.

The colon matters. 164.306(c) is headed "Standards" and 164.306(d)
"Implementation specifications": general rules about the hierarchy, not
members of it, so neither carries a label.
"""

from __future__ import annotations

from compliance_copilot.models import ClauseType, Modality

STANDARD_PREFIX = "Standard:"
SPECIFICATION_PREFIXES: tuple[str, ...] = (
    "Implementation specification:",
    "Implementation specifications:",
)
MODALITY_SUFFIXES: dict[str, Modality] = {
    "(Required)": Modality.REQUIRED,
    "(Addressable)": Modality.ADDRESSABLE,
}


class LabelError(ValueError):
    """A heading carries labels that contradict each other."""


def read_labels(heading: str) -> tuple[ClauseType | None, Modality | None]:
    """The clause type and modality printed in `heading`."""

    text = heading.strip()
    modality = next(
        (m for suffix, m in MODALITY_SUFFIXES.items() if text.endswith(suffix)), None
    )
    is_standard = text.startswith(STANDARD_PREFIX)
    is_specification = text.startswith(SPECIFICATION_PREFIXES)

    if is_standard and modality is not None:
        raise LabelError(
            f"heading {heading!r} is labelled both 'Standard:' and "
            f"'({modality.value.title()})'; standards carry no modality "
            "(45 CFR 164.306(d))"
        )
    if is_standard:
        return ClauseType.STANDARD, None
    if is_specification or modality is not None:
        return ClauseType.IMPLEMENTATION_SPECIFICATION, modality
    return None, None
