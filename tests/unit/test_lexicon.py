"""The shipped broadening lexicon: allowed links only, and longest-match lookup."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from compliance_copilot.corpus.lexicon import Lexicon, load_lexicon


def test_shipped_lexicon_is_the_allowed_nest() -> None:
    lexicon = load_lexicon()
    by_term = {entry.term: entry for entry in lexicon.terms}

    assert by_term["electronic protected health information"].narrower_than == (
        "protected health information",
    )
    assert by_term["protected health information"].narrower_than == (
        "individually identifiable health information",
        "health data",
    )
    assert by_term["electronic protected health information"].aliases == (
        "ePHI",
        "electronic PHI",
    )


def test_longer_term_hides_the_term_inside_it() -> None:
    found = load_lexicon().terms_in(
        "electronic protected health information and ePHI, not health data"
    )

    assert found == {"electronic protected health information", "health data"}


def test_health_data_is_broader_than_electronic_protected_health_information() -> None:
    pairs = load_lexicon().broader_uses(
        "implement comprehensive audit logging for all health data",
        ("record and examine activity", "electronic protected health information"),
    )

    assert pairs == [("health data", "electronic protected health information")]


def test_unknown_narrower_than_target_is_rejected() -> None:
    with pytest.raises(ValidationError, match="not a term"):
        Lexicon.model_validate(
            {
                "terms": [
                    {
                        "term": "electronic protected health information",
                        "narrower_than": ["system"],
                    }
                ]
            }
        )
