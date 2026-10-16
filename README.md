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

There is no demo command yet. Phase 8 adds `run <fact-pattern>`.
