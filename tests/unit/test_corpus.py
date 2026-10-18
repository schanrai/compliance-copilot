"""Phase 1 corpus: the shipped clauses, `get_clauses`, and gate 1 (plan §4 Phase 1)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from compliance_copilot.corpus.loader import (
    DEFAULT_DATA_DIR,
    ClauseNotFoundError,
    CorpusError,
    get_clauses,
    load_corpus,
)
from compliance_copilot.corpus.models import ClauseSet, CorpusFile, ScopeFilter
from compliance_copilot.golden import load_golden_cases
from compliance_copilot.models import ClauseType, Framework, Modality

GOLDEN_CASES_DIR = Path(__file__).parents[1] / "golden" / "cases"

DEMO_CLAUSE_IDS = frozenset(
    {
        "45-CFR-160.103-def-business-associate",
        "45-CFR-160.103-def-covered-entity",
        "45-CFR-160.103-def-health-care-provider",
        "45-CFR-160.103-def-health-plan",
        "45-CFR-160.103-def-protected-health-information",
        "45-CFR-160.103-def-electronic-protected-health-information",
        "45-CFR-160.103-def-transaction",
        "45-CFR-164.306-c",
        "45-CFR-164.306-d",
        "45-CFR-164.312-a-1",
        "45-CFR-164.312-a-2-i",
        "45-CFR-164.312-a-2-iv",
        "45-CFR-164.312-b",
        "45-CFR-164.404-b",
        "45-CFR-164.410-b",
        "45-CFR-164.410-c",
    }
)


def _copy_corpus(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    target.mkdir()
    for path in DEFAULT_DATA_DIR.glob("*.json"):
        shutil.copy(path, target / path.name)
    return target


# --- gate 1: labels read from the source -------------------------------------------


@pytest.mark.parametrize(
    ("clause_id", "clause_type", "modality"),
    [
        ("45-CFR-164.312-b", ClauseType.STANDARD, None),
        ("45-CFR-164.312-a-1", ClauseType.STANDARD, None),
        ("45-CFR-164.312-a-2-i", ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.REQUIRED),
        ("45-CFR-164.312-a-2-iv", ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.ADDRESSABLE),
        ("45-CFR-164.404-b", ClauseType.IMPLEMENTATION_SPECIFICATION, None),
        ("45-CFR-164.410-b", ClauseType.IMPLEMENTATION_SPECIFICATION, None),
        ("45-CFR-164.410-c", ClauseType.IMPLEMENTATION_SPECIFICATION, None),
        ("45-CFR-164.306-c", None, None),
        ("45-CFR-164.306-d", None, None),
        ("45-CFR-160.103-def-business-associate", None, None),
    ],
)
def test_gate1_clause_type_and_modality_match_the_source_labels(
    clause_id: str, clause_type: ClauseType | None, modality: Modality | None
) -> None:
    clause = load_corpus().clause(clause_id)

    assert (clause.clause_type, clause.modality) == (clause_type, modality)


# --- gate 1: get_clauses ------------------------------------------------------------


def test_get_clauses_returns_the_whole_hipaa_set() -> None:
    result = get_clauses(Framework.HIPAA, corpus=load_corpus())

    assert {c.id for c in result.clauses} == DEMO_CLAUSE_IDS
    assert result.reason is None
    assert result.scope_filter is ScopeFilter.ALL


@pytest.mark.parametrize(
    "framework", [f for f in Framework if f is not Framework.HIPAA], ids=lambda f: f.value
)
def test_framework_with_no_corpus_returns_empty_with_a_reason(framework: Framework) -> None:
    result = load_corpus().get_clauses(framework)

    assert result.clauses == ()
    assert result.reason is not None and framework.value in result.reason


def test_gate1_every_golden_citation_resolves_through_get_clauses() -> None:
    corpus = load_corpus()
    hipaa_ids = {c.id for c in corpus.get_clauses(Framework.HIPAA).clauses}
    citations = {
        r.citation
        for case in load_golden_cases(GOLDEN_CASES_DIR)
        for r in case.expected.requirements
    }

    assert citations == {"45-CFR-164.312-b"}
    assert citations <= hipaa_ids


def test_golden_expected_labels_match_the_corpus_labels() -> None:
    corpus = load_corpus()
    for case in load_golden_cases(GOLDEN_CASES_DIR):
        for expected in case.expected.requirements:
            clause = corpus.clause(expected.citation)
            assert (expected.clause_type, expected.modality) == (
                clause.clause_type,
                clause.modality,
            ), f"{case.id}: {expected.citation}"


def test_shipped_declarations_cover_every_corpus_framework() -> None:
    corpus = load_corpus()
    declared = {d.framework for d in corpus.declarations}

    assert declared == {"HIPAA-Definitions", "HIPAA-Security", "HIPAA-Breach-Notification"}
    assert {c.framework for c in corpus.clauses} <= declared
    security = next(d for d in corpus.declarations if d.framework == "HIPAA-Security")
    breach = next(d for d in corpus.declarations if d.framework == "HIPAA-Breach-Notification")
    assert security.grades_specifications is True
    assert breach.grades_specifications is False


def test_every_clause_records_its_source_and_retrieval_time() -> None:
    for clause in load_corpus().clauses:
        assert str(clause.source_url).startswith("https://www.ecfr.gov/on/")
        assert clause.retrieved_at.utcoffset() is not None


def test_unknown_clause_id_raises_a_named_error() -> None:
    with pytest.raises(ClauseNotFoundError, match="not in the corpus"):
        load_corpus().clause("45-CFR-164.312-z")


def test_clause_set_cannot_be_empty_without_a_reason() -> None:
    with pytest.raises(ValidationError, match="needs a reason"):
        ClauseSet(framework=Framework.HBNR, scope_filter=ScopeFilter.ALL, clauses=())


# --- corpus files fail loudly ---------------------------------------------------------


def _security_file() -> dict[str, object]:
    return json.loads((DEFAULT_DATA_DIR / "hipaa-security.json").read_text(encoding="utf-8"))


def _clause(data: dict[str, object], clause_id: str) -> dict[str, object]:
    clauses = data["clauses"]
    assert isinstance(clauses, list)
    return next(c for c in clauses if c["id"] == clause_id)


def test_stored_label_that_contradicts_the_printed_heading_is_rejected() -> None:
    data = _security_file()
    _clause(data, "45-CFR-164.312-a-2-iv")["modality"] = "required"

    with pytest.raises(ValidationError, match=r"do not match the labels printed in heading"):
        CorpusFile.model_validate(data)


def test_specification_missing_its_printed_modality_is_rejected() -> None:
    data = _security_file()
    clause = _clause(data, "45-CFR-164.312-a-2-i")
    clause["heading"] = "Unique user identification"

    with pytest.raises(ValidationError, match=r"do not match the labels printed"):
        CorpusFile.model_validate(data)


def test_labelled_clause_outside_the_declaration_is_rejected() -> None:
    data = json.loads(
        (DEFAULT_DATA_DIR / "hipaa-breach-notification.json").read_text(encoding="utf-8")
    )
    data["declaration"] = {
        "framework": "HIPAA-Breach-Notification",
        "clause_types": ["standard", "implementation_specification"],
        "grades_specifications": True,
    }

    with pytest.raises(ValidationError, match=r"modality must be required or addressable"):
        CorpusFile.model_validate(data)


def test_clause_in_the_wrong_framework_file_is_rejected() -> None:
    data = _security_file()
    _clause(data, "45-CFR-164.312-b")["framework"] = "HIPAA-Breach-Notification"

    with pytest.raises(ValidationError, match=r"does not match the file's declaration"):
        CorpusFile.model_validate(data)


def test_clause_id_repeated_across_files_fails_the_load(tmp_path: Path) -> None:
    data_dir = _copy_corpus(tmp_path)
    shutil.copy(data_dir / "hipaa-security.json", data_dir / "copy.json")
    copy = json.loads((data_dir / "copy.json").read_text(encoding="utf-8"))
    copy["declaration"]["framework"] = "HIPAA-Security-Copy"
    for clause in copy["clauses"]:
        clause["framework"] = "HIPAA-Security-Copy"
    (data_dir / "copy.json").write_text(json.dumps(copy), encoding="utf-8")

    with pytest.raises(CorpusError, match="clause ids repeat across files"):
        load_corpus(data_dir)


def test_invalid_json_fails_the_load(tmp_path: Path) -> None:
    data_dir = _copy_corpus(tmp_path)
    (data_dir / "broken.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(CorpusError, match="invalid JSON"):
        load_corpus(data_dir)


def test_empty_corpus_directory_fails_the_load(tmp_path: Path) -> None:
    with pytest.raises(CorpusError, match="no files"):
        load_corpus(tmp_path)
