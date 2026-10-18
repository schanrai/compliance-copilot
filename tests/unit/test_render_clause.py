"""A clause prints readably with its full text and modality line (gate 1)."""

from __future__ import annotations

import io
import re

import pytest
from rich.console import Console

from compliance_copilot.corpus.loader import load_corpus
from compliance_copilot.render.clause import citation_label, clause_panel, modality_line


def _rendered(clause_id: str) -> str:
    """The panel as plain text, with the border characters removed."""

    console = Console(record=True, width=100, file=io.StringIO())
    console.print(clause_panel(load_corpus().clause(clause_id)))
    return re.sub(r"[│╭╮╰╯─]", " ", console.export_text())


@pytest.mark.parametrize(
    ("clause_id", "line"),
    [
        ("45-CFR-164.312-b", "Standard — compliance is mandatory (45 CFR 164.306(c))"),
        ("45-CFR-164.312-a-2-i", "Implementation specification — Required"),
        ("45-CFR-164.312-a-2-iv", "Implementation specification — Addressable"),
        ("45-CFR-164.404-b", "not labelled Required or Addressable"),
        ("45-CFR-160.103-def-covered-entity", "No standard or implementation specification"),
    ],
)
def test_each_label_state_has_its_own_modality_line(clause_id: str, line: str) -> None:
    assert line in modality_line(load_corpus().clause(clause_id))


def test_a_standard_never_renders_as_required() -> None:
    assert "Required" not in _rendered("45-CFR-164.312-b")


def test_every_clause_renders_its_full_text_and_modality_line() -> None:
    for clause in load_corpus().clauses:
        output = _rendered(clause.id)
        flattened = " ".join(output.split())
        for paragraph in clause.text.split("\n"):
            assert " ".join(paragraph.split()) in flattened, clause.id
        assert " ".join(modality_line(clause).split()) in flattened, clause.id


@pytest.mark.parametrize(
    ("clause_id", "label"),
    [
        ("45-CFR-164.312-b", "45 CFR 164.312(b)"),
        ("45-CFR-164.312-a-2-iv", "45 CFR 164.312(a)(2)(iv)"),
        ("45-CFR-160.103-def-business-associate", "45 CFR 160.103"),
    ],
)
def test_citation_label(clause_id: str, label: str) -> None:
    assert citation_label(clause_id) == label
