"""Labels are read from the printed heading, never inferred (PRD §15.1)."""

from __future__ import annotations

import pytest

from compliance_copilot.corpus.labels import LabelError, read_labels
from compliance_copilot.models import ClauseType, Modality


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Standard: Audit controls", (ClauseType.STANDARD, None)),
        (
            "Unique user identification (Required)",
            (ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.REQUIRED),
        ),
        (
            "Encryption and decryption (Addressable)",
            (ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.ADDRESSABLE),
        ),
        (
            "Implementation specification: Mechanism to authenticate electronic "
            "protected health information (Addressable)",
            (ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.ADDRESSABLE),
        ),
        (
            "Implementation specification: Timeliness of notification",
            (ClauseType.IMPLEMENTATION_SPECIFICATION, None),
        ),
        (
            "Implementation specifications: Content of notification",
            (ClauseType.IMPLEMENTATION_SPECIFICATION, None),
        ),
        ("Standards", (None, None)),
        ("Implementation specifications", (None, None)),
        ("Business associate", (None, None)),
    ],
)
def test_labels_are_read_from_the_heading(
    heading: str, expected: tuple[ClauseType | None, Modality | None]
) -> None:
    assert read_labels(heading) == expected


def test_standard_heading_with_a_modality_is_a_contradiction() -> None:
    with pytest.raises(LabelError, match="standards carry no modality"):
        read_labels("Standard: Audit controls (Required)")
