"""Corpus ingestion: fetch each section, keep the raw response, write the clause JSON.

The raw XML is kept under `data/ecfr/<date>/` with each fetch time, so the
shipped JSON can be rebuilt from it offline and checked character for
character (`tests/unit/test_corpus_verbatim.py`).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path

import httpx

from compliance_copilot.config import Settings
from compliance_copilot.corpus.ecfr import USER_AGENT, fetch_section
from compliance_copilot.corpus.extract import SectionSnapshot, build_corpus_files
from compliance_copilot.corpus.loader import CORPUS_SUFFIX, DEFAULT_DATA_DIR, load_corpus
from compliance_copilot.corpus.manifest import DEFAULT_MANIFEST_PATH, Manifest, load_manifest
from compliance_copilot.log import PipelineStage, log_stage

logger = logging.getLogger(__name__)

SNAPSHOT_ROOT = "ecfr"
RETRIEVED_AT_FILE = "retrieved_at.json"


class IngestError(Exception):
    """Ingestion stopped before writing a usable corpus."""


def snapshot_dir(data_dir: Path, on_date: date) -> Path:
    return data_dir / SNAPSHOT_ROOT / on_date.isoformat()


def write_snapshots(directory: Path, snapshots: Mapping[str, SectionSnapshot]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for section, snapshot in snapshots.items():
        (directory / f"{section}.xml").write_text(snapshot.xml, encoding="utf-8")
    retrieved = {s: snap.retrieved_at.isoformat() for s, snap in snapshots.items()}
    (directory / RETRIEVED_AT_FILE).write_text(
        json.dumps(retrieved, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def read_snapshots(
    directory: Path, manifest: Manifest, on_date: date
) -> dict[str, SectionSnapshot]:
    """The saved snapshots for every manifest section. Fails if any is missing."""

    try:
        retrieved = json.loads((directory / RETRIEVED_AT_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestError(f"{directory}: cannot read {RETRIEVED_AT_FILE}: {exc}") from exc
    snapshots: dict[str, SectionSnapshot] = {}
    for section in manifest.sections:
        path = directory / f"{section}.xml"
        if not path.is_file() or section not in retrieved:
            raise IngestError(f"{directory}: no saved snapshot for section {section}")
        snapshots[section] = SectionSnapshot(
            title=manifest.title,
            section=section,
            on_date=on_date,
            xml=path.read_text(encoding="utf-8"),
            retrieved_at=datetime.fromisoformat(retrieved[section]),
        )
    return snapshots


def ingest_corpus(
    settings: Settings,
    on_date: date,
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    data_dir: Path = DEFAULT_DATA_DIR,
) -> tuple[Path, ...]:
    """Fetch, snapshot, extract and write the corpus. Returns the JSON files written."""

    with log_stage(logger, PipelineStage.CORPUS_INGEST) as record:
        manifest = load_manifest(manifest_path)
        record.add(on_date=on_date.isoformat(), sections=list(manifest.sections))
        outputs = {data_dir / f.output_filename for f in manifest.frameworks}
        stale = sorted(
            p.name for p in data_dir.glob(f"*{CORPUS_SUFFIX}") if p not in outputs
        )
        if stale:
            raise IngestError(
                f"{data_dir}: corpus files not produced by the manifest: {', '.join(stale)}. "
                "Remove them or add their framework to the manifest."
            )

        with httpx.Client(
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
        ) as client:
            snapshots = {
                section: fetch_section(
                    client,
                    api_base_url=str(settings.ecfr_api_base_url),
                    title=manifest.title,
                    section=section,
                    on_date=on_date,
                )
                for section in manifest.sections
            }

        files = build_corpus_files(manifest, snapshots, str(settings.ecfr_web_base_url))
        write_snapshots(snapshot_dir(data_dir, on_date), snapshots)
        written: list[Path] = []
        for framework, corpus_file in zip(manifest.frameworks, files, strict=True):
            path = data_dir / framework.output_filename
            path.write_text(corpus_file.model_dump_json(indent=2) + "\n", encoding="utf-8")
            written.append(path)

        corpus = load_corpus(data_dir)
        record.add(files_written=[p.name for p in written], clauses=len(corpus.clauses))
        return tuple(written)
