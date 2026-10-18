"""Gate 1, verbatim: the shipped JSON is exactly what the saved eCFR responses produce.

Rebuilds every corpus file offline from `data/ecfr/<date>/` and compares it
field by field, so a hand edit to clause text, a heading or a label fails here.
`operative_terms` and `implications` are tagged by hand after ingestion, so the
comparison ignores them.
"""

from __future__ import annotations

from datetime import date

import pytest

from compliance_copilot.config import DEFAULT_ECFR_WEB_BASE_URL
from compliance_copilot.corpus.extract import build_corpus_files
from compliance_copilot.corpus.ingest import SNAPSHOT_ROOT, read_snapshots
from compliance_copilot.corpus.loader import DEFAULT_DATA_DIR, read_corpus_file
from compliance_copilot.corpus.manifest import load_manifest
from compliance_copilot.corpus.models import CorpusFile

SNAPSHOT_DATES = sorted((DEFAULT_DATA_DIR / SNAPSHOT_ROOT).iterdir())


def test_exactly_one_snapshot_date_is_shipped() -> None:
    assert len(SNAPSHOT_DATES) == 1, [p.name for p in SNAPSHOT_DATES]


@pytest.fixture(scope="module")
def rebuilt() -> dict[str, CorpusFile]:
    manifest = load_manifest()
    snapshot_dir = SNAPSHOT_DATES[0]
    snapshots = read_snapshots(snapshot_dir, manifest, date.fromisoformat(snapshot_dir.name))
    files = build_corpus_files(manifest, snapshots, DEFAULT_ECFR_WEB_BASE_URL)
    return {
        framework.output_filename: corpus_file
        for framework, corpus_file in zip(manifest.frameworks, files, strict=True)
    }


def test_shipped_files_are_exactly_the_manifest_outputs(rebuilt: dict[str, object]) -> None:
    shipped = {p.name for p in DEFAULT_DATA_DIR.glob("*.json")}

    assert shipped == set(rebuilt)


def _without_hand_tags(corpus_file: CorpusFile) -> dict[str, object]:
    """The eCFR rebuild leaves operative terms and implications empty."""

    dumped = corpus_file.model_dump(mode="json")
    for clause in dumped["clauses"]:
        del clause["operative_terms"]
        del clause["implications"]
    return dumped


def test_shipped_corpus_matches_a_rebuild_from_the_saved_ecfr_responses(
    rebuilt: dict[str, CorpusFile],
) -> None:
    for filename, expected in rebuilt.items():
        shipped = read_corpus_file(DEFAULT_DATA_DIR / filename)
        assert _without_hand_tags(shipped) == _without_hand_tags(expected), filename
