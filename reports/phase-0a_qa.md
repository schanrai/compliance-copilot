# Phase 0a QA

**Date:** 2026-10-16
**Question:** Does the new project install from the lockfile, pass pytest, pin every direct dependency exactly, and match the Phase 0a tree, with a clean vulnerability audit?
**Verdict:** Pass, with two notes below. No commit yet — waiting for approval. `anthropic` was not installed.

## What was checked

| Check | Result |
|---|---|
| Tooling | uv 0.10.4, Python 3.12.12. Parent directory is not a git repo. This project is its own repo, no commits yet. |
| Package health before install | Latest stable on PyPI, none yanked, repos not archived. See versions below. |
| `pip-audit` after each install | No known vulnerabilities. |
| Final audit of the full lock, including the dev group | No known vulnerabilities. |
| `uv.lock` hashes | Present on every distribution. |
| Exact pins | Every direct dependency is `==`. |
| `.env` ignored | `git check-ignore` matched `.gitignore` line 2. The probe file was deleted. |
| pytest | 2 passed, in this tree and in a fresh directory via `uv sync --frozen`. |
| Old plan path | `artifacts/module_8_ai_prds/compliance-copilot-implementation-plan.md` is gone. The file lives at `docs/implementation.plan.md`. |

A real `git clone` is not possible until the first commit exists. The fresh-directory check is the stand-in: copy the tree without `.git` or `.venv`, then `uv sync --frozen` and `uv run pytest`.

## Audit command

The plan's example pipes `uv export` into `uvx pip-audit`. On this machine that command aborts: pip-audit builds a resolver virtualenv, and `ensurepip` dies with SIGABRT. The export already contains the resolved, hashed tree, so the audit used the equivalent that does not build that virtualenv:

```bash
uv export --format requirements-txt --all-groups --no-emit-project --no-header -o /tmp/reqs.txt
uvx pip-audit --disable-pip -r /tmp/reqs.txt
```

`--all-groups` includes pytest. `--no-emit-project` leaves the local project out of the audit. `--disable-pip` is valid because the export is hashed. Result: `No known vulnerabilities found`.

## Versions pinned

Direct:

| Package | Pin | Why this version |
|---|---|---|
| pydantic | 2.14.1 | Latest stable, uploaded 2026-10-11. pydantic/pydantic, MIT. |
| pytest | 9.1.1 (dev) | Latest stable, uploaded 2026-06-19. Repo pushed 2026-10-13. pytest-dev, MIT. |
| pyyaml | 6.0.3 | Latest stable, uploaded 2025-09-25. Repo pushed 2026-10-07. yaml/pyyaml, MIT. |
| rich | 15.0.0 | Latest stable, uploaded 2026-04-12. Repo pushed 2026-06-23. Textualize/rich, MIT. |
| typer | 0.27.3 | Latest stable, uploaded 2026-10-06. fastapi/typer, MIT. Requires `rich>=13.8.0`, so rich 15.0.0 fits. |
| python-dotenv | 1.2.4 | Latest stable, uploaded 2026-10-01. theskumar/python-dotenv, BSD-3-Clause. |
| httpx | 0.28.1 | Latest **stable**, uploaded 2024-12-06. encode/httpx, pushed 2026-10-02, BSD-3-Clause. |

`httpx` 1.0.dev6 exists and was not installed. It is a pre-release. The `httpx[cli]` extra requires `rich<14`, which conflicts with rich 15.0.0. Phase 1 needs the base client, not the CLI extra, so the extra was not installed.

Not installed: `anthropic`.

Transitive packages are exact in `uv.lock` (hashes included). Installed on this Mac: annotated-doc 0.0.5, annotated-types 0.8.0, anyio 4.15.1, certifi 2026.7.22, h11 0.16.0, httpcore 1.0.9, idna 3.20, iniconfig 2.3.1, markdown-it-py 4.2.0, mdurl 0.1.2, packaging 26.3, pluggy 1.7.0, pydantic-core 2.50.1, pygments 2.21.0, shellingham 1.5.4, typing-extensions 4.16.0, typing-inspection 0.4.4. `colorama==0.4.6` is locked for Windows only and was not installed here.

## Notes, not failures

1. **Two pins are ranges, on purpose.** `requires-python = ">=3.12"` is the language floor from the plan. `uv_build>=0.10.4,<0.11.0` is the build backend constraint `uv init` wrote. Runtime and dev dependencies are exact `==`.
2. **Stale pointer outside this repo.** `curriculum/curriculum-roadmap.md` still links to `artifacts/module_8_ai_prds/compliance-copilot-implementation-plan.md`. `CLAUDE.md` and the memory file `compliance-copilot-demo-timeline.md` were updated. Those two files are not part of this git repo.
