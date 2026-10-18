# Compliance Copilot

Advisory determinations for pre-product US health founders. This repository is the prototype for the 20 October 2026 demo.

Phase 0a installs the project, loads settings from the environment, and writes structured logs. Determinations, the corpus, and the demo command are later phases.

## Requirements

- Python 3.12 or newer (`.python-version` pins 3.12)
- [uv](https://docs.astral.sh/uv/)

## Install

From this directory:

```bash
uv sync
```

`uv sync` installs the exact versions in `uv.lock`, including hashes.

## Configure

```bash
cp .env.example .env
```

`LOG_LEVEL` sets log verbosity. `ANTHROPIC_API_KEY` is unused until the stretch phase. The `anthropic` package is not installed.

## Test

```bash
uv run pytest
```

## Run

The demo command arrives in Phase 8. The corpus commands work now:

```bash
uv run python -m compliance_copilot.cli clause 45-CFR-164.312-b   # one clause, full text and modality line
uv run python -m compliance_copilot.cli clauses HIPAA             # everything get_clauses returns for HIPAA
uv run python -m compliance_copilot.cli ingest-corpus --on 2026-10-15   # refetch from the eCFR API (network)
```

The corpus is `src/compliance_copilot/corpus/data/*.json`, generated from `corpus/sources.yaml`. Do not edit the JSON by hand: a test rebuilds it from the saved eCFR responses and fails on any difference.
