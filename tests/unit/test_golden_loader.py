"""The golden-set loader reads YAML into the models and fails loudly on a bad file.

The fixture below exists only to exercise the loader. It is written to a
temporary directory, never to tests/golden/cases/. Its labels are not a
healthcare judgement and it is not a golden-set case.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from compliance_copilot.config import load_settings
from compliance_copilot.golden import (
    GoldenCase,
    GoldenCaseError,
    load_golden_case,
    load_golden_cases,
)
from compliance_copilot.log import configure_logging
from compliance_copilot.models import CoveredEntityStatus, Framework, FieldState

LOADER_FIXTURE: dict[str, Any] = {
    "id": "G-99",
    "title": "Loader mechanics fixture, not a golden case",
    "stated": {
        "product": {
            "description": {
                "value": "Synthetic product used only to test the loader",
                "source": "qa_answer",
                "state": "answered",
            }
        },
        "hipaa_situation": {
            "customer_types": {"value": ["employers"], "source": "qa_answer", "state": "answered"},
            "receives_patient_data_from_others": {"source": "qa_answer", "state": "unknown_to_user"},
        },
    },
    "expected": {
        "covered_entity_status": "ambiguous",
        "ambiguity_cause": "missing_fact",
        "derived_from": [
            "stated.hipaa_situation.customer_types",
            "stated.hipaa_situation.receives_patient_data_from_others",
        ],
        "framework_summary": {
            f.value: ("unresolved" if f is Framework.HIPAA else "not_assessed") for f in Framework
        },
        "requirements": [],
        "ambiguous_components": [1, 2, 3, 4, 6],
    },
}


def fixture(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(LOADER_FIXTURE)
    for dotted, value in changes.items():
        *parents, leaf = dotted.split("__")
        target = data
        for key in parents:
            target = target[key]
        target[leaf] = value
    return data


def write(directory: Path, name: str, data: Any) -> Path:
    path = directory / name
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_valid_fixture_loads_into_the_models(tmp_path: Path) -> None:
    case = load_golden_case(write(tmp_path, "g-99.yaml", fixture()))

    assert isinstance(case, GoldenCase)
    assert case.expected.covered_entity_status is CoveredEntityStatus.AMBIGUOUS
    situation = case.stated.hipaa_situation
    assert situation.receives_patient_data_from_others.state is FieldState.UNKNOWN_TO_USER
    assert situation.provides_care_directly.state is FieldState.NOT_ASKED


def test_directory_load_writes_one_structured_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(load_settings())
    write(tmp_path, "g-99.yaml", fixture())

    cases = load_golden_cases(tmp_path)

    lines = capsys.readouterr().err.strip().splitlines()
    assert len(cases) == 1
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["stage"] == "load_cases"
    assert payload["outcome"] == "ok"
    assert payload["cases_loaded"] == 1
    assert payload["case_ids"] == ["G-99"]


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("id: G-99\n  title: bad indent\n", "invalid YAML"),
        ("", "file is empty"),
        ("- id: G-99\n", "top level must be a mapping"),
        ("id: G-99\nid: G-98\n", "duplicate key 'id'"),
    ],
    ids=["bad-indent", "empty", "list", "duplicate-key"],
)
def test_malformed_yaml_fails_loudly(tmp_path: Path, raw: str, message: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(GoldenCaseError, match=message) as excinfo:
        load_golden_case(path)
    assert excinfo.value.path == path


def test_nested_duplicate_key_fails_loudly(tmp_path: Path) -> None:
    raw = yaml.safe_dump(fixture(), sort_keys=False).replace(
        "  hipaa_situation:\n",
        "  hipaa_situation:\n"
        "    provides_care_directly: {value: true, source: qa_answer, state: answered}\n"
        "    provides_care_directly: {value: false, source: qa_answer, state: answered}\n",
    )
    path = tmp_path / "dupe.yaml"
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(GoldenCaseError, match="duplicate key 'provides_care_directly'"):
        load_golden_case(path)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"id": "G-1"}, "id: String should match pattern"),
        ({"stated__hipaa_situation__is_business_associate": {"state": "not_asked"}}, "Extra inputs"),
        ({"expected__ambiguity_cause": None}, "ambiguity_cause must be set"),
        ({"expected__ambiguous_components": None}, "ambiguous_components must be a list"),
        ({"expected__derived_from": ["stated.hipaa_situation.covered"]}, "not a field of HipaaSituation"),
        ({"expected__framework_summary": {"HIPAA": "unresolved"}}, "missing from the summary"),
        (
            {"expected__framework_summary": {**LOADER_FIXTURE["expected"]["framework_summary"], "HIPAA": "in_scope"}},
            "puts HIPAA in 'in_scope'",
        ),
        (
            {"expected__requirements": [{"citation": "45-CFR-164.312-b", "evidence_type": "cited", "clause_type": "standard", "modality": None}]},
            "requirements must be empty",
        ),
        (
            {"stated__hipaa_situation__customer_types": {"value": ["employers"], "state": "answered"}},
            "needs a source",
        ),
    ],
    ids=[
        "bad-id",
        "unknown-field",
        "ambiguous-without-cause",
        "ambiguous-without-components",
        "bad-field-path",
        "incomplete-summary",
        "hipaa-category-contradicts-status",
        "requirements-on-unresolved",
        "field-without-source",
    ],
)
def test_schema_and_label_errors_fail_loudly(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    path = write(tmp_path, "bad.yaml", fixture(**changes))

    with pytest.raises(GoldenCaseError, match=message):
        load_golden_case(path)


def test_missing_expected_field_fails_loudly(tmp_path: Path) -> None:
    data = fixture()
    del data["expected"]["ambiguous_components"]

    with pytest.raises(GoldenCaseError, match="expected.ambiguous_components: Field required"):
        load_golden_case(write(tmp_path, "bad.yaml", data))


def test_empty_directory_fails_loudly(tmp_path: Path) -> None:
    (tmp_path / ".gitkeep").touch()

    with pytest.raises(GoldenCaseError, match="no .yaml golden cases found"):
        load_golden_cases(tmp_path)


def test_missing_directory_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(GoldenCaseError, match="does not exist"):
        load_golden_cases(tmp_path / "nope")


def test_yml_suffix_fails_loudly(tmp_path: Path) -> None:
    write(tmp_path, "g-99.yaml", fixture())
    write(tmp_path, "g-98.yml", fixture(id="G-98"))

    with pytest.raises(GoldenCaseError, match="rename: g-98.yml"):
        load_golden_cases(tmp_path)


def test_repeated_case_ids_fail_loudly(tmp_path: Path) -> None:
    write(tmp_path, "a.yaml", fixture())
    write(tmp_path, "b.yaml", fixture())

    with pytest.raises(GoldenCaseError, match="case ids repeat: G-99"):
        load_golden_cases(tmp_path)


def test_one_bad_file_fails_the_whole_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(load_settings())
    write(tmp_path, "a.yaml", fixture())
    write(tmp_path, "b.yaml", fixture(id="G-98", expected__ambiguity_cause=None))

    with pytest.raises(GoldenCaseError, match="b.yaml"):
        load_golden_cases(tmp_path)

    payload = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert payload["outcome"] == "error"
    assert payload["error_type"] == "GoldenCaseError"
