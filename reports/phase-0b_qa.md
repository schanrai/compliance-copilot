# Phase 0b–0c QA

**Date:** 2026-10-17
**Question:** Do the Phase 0 models and harness meet QA gate 0? Can an invalid requirement be constructed? Is the trace append-only? Does the golden-set loader fail loudly on a bad file?
**Verdict (updated 2026-10-17, after Phase G):** Gate 0 passes. Re-checked once the eight golden cases existed: a fresh directory (`uv sync --frozen`, no `.git` or `.venv`) ran `pytest` with 139 passed; `pip-audit --disable-pip` reported no known vulnerabilities; the eight cases load; the three requirement-rejection tests passed inside that run. A real `git clone` is still impossible until the first commit. The original verdict below was written before the cases existed.

## Gate 0

| Check | Result |
|---|---|
| Fresh directory → `uv sync --frozen` → `pytest` | **Pass.** 129 passed, 2 skipped. Same method as Phase 0a: copy the tree without `.git` or `.venv`. A real clone would not include this uncommitted work |
| `pip-audit` clean; versions pinned exactly | **Pass.** `No known vulnerabilities found`, using the Phase 0a audit command. Nothing installed. `pyproject.toml` and `uv.lock` unchanged |
| All 8 golden cases load and validate | **Pass, re-checked after Phase G.** Included in the fresh-directory run: 139 passed |
| Cited requirement, `modality: required` on a `standard` → rejected | **Pass.** `test_gate0_cited_requirement_with_required_modality_on_a_standard_is_rejected`. Removing the rule turns this test red, so it tests the rule |
| Derived requirement missing `implication_id` → rejected | **Pass.** `test_gate0_derived_requirement_missing_implication_id_is_rejected` |
| Requirement with no `evidence_type` → rejected | **Pass.** `test_gate0_requirement_with_no_evidence_type_is_rejected`. The field has no default |
| No hard-coded paths or keys | **Pass.** A grep for user paths and key patterns found none. The golden test finds `cases/` relative to its own file |

## What was built

- **Models** (`src/compliance_copilot/models/`):
  - `Field` with four states. Only `answered` carries a value. `not_asked` has no source; the other three states need one. Booleans are strict, so `"yes"` and `1` are rejected
  - `ComplianceContextObject`: the product description, `hipaa_situation` (including `customers_bill_insurers_electronically` and the subcontractor customer type), and the derived block. Unstated `hipaa_situation` fields default to `not_asked`
  - `Clause` and `FrameworkDeclaration`. Operative terms must appear verbatim in the clause text
  - `Requirement`, with checks 1–4 and 6 as validators. `timing` accepts only `applies_now` and `design_triggered`
  - `Trace` and `TraceStep`, using the §13.2 action enum
  - `Determination` and `FrameworkSummaryEntry`
- **Checks 1–3 need the corpus.** It is passed in as a `RequirementContext` (clauses, framework declarations, implication ids, earlier requirements). With no context, the requirement is rejected. `model_construct` and `model_copy(update=...)` skip validation, so both are disabled on every model.
- **Trace is append-only.** It is frozen and its steps are a tuple. `with_step` returns a new, re-validated trace. A test pins the public surface to `with_step` and `next_seq`. A trace is rejected unless step 1 is an intake step with field paths into `stated`, and each later step consumed something an earlier step produced.
- **Golden loader** (`src/compliance_copilot/golden/`) fails loudly on:
  - invalid YAML, an empty file, or a top level that is not a mapping
  - **duplicate keys**, which plain `safe_load` silently keeps the last value of
  - unknown fields, missing `expected` fields, or a bad field path
  - a `.yml` suffix, an empty directory, or repeated ids
  - labels that contradict each other, e.g. ambiguous with no cause, a HIPAA category that doesn't follow the status, or requirements on a case where HIPAA isn't in scope
- **Logging:** `log_stage(logger, stage, run_id)` writes exactly one JSON line per stage, on success or failure, and re-raises the error. The loader uses it.

## For the Phase G chat: the fixture format the loader accepts

- `stated.product.description` is **required and must be `answered`** (PRD §7.4). The plan's template left it out.
- Field shape: `{value, source, state}`. Write `not_asked` as `{state: not_asked}` with no source. `unknown_to_user` and `skipped` need a `source` and no `value`.
- `customer_types` values: `clinics`, `consumers`, `employers`, `insurers`, `companies_handling_patient_data_for_providers`.
- `framework_summary` must list all nine keys exactly once: `HIPAA`, `HBNR`, `FTC_5`, `WA_MHMDA`, `CT`, `NV`, `TX_NE`, `SOC_2`, `PCI_DSS`.
- Every `expected` key must be written out, including `ambiguity_cause: null` and `ambiguous_components: null` on determined cases.
- `derived_from` paths must name real stated fields, e.g. `stated.hipaa_situation.customer_types`.
- No extra keys such as `notes`.

## Open issues to decide

1. **Resolved 2026-10-17 (Phase G).** No billing-company field. The intake question now asks whether the clinic bills insurers "either directly or through a billing company" (PRD §21 item 2). G-06 was then replaced: it is software sold to a health insurer, not the billing-company case. Original note: `customers_bill_insurers_electronically` is a bool, so a clinic that bills through a billing company looked the same as one that bills no insurer.
2. **The derived requirement has nothing to derive from.** Check 3 says `derived_from` must point at a cited requirement in the same analysis. The prototype cites only 164.312(b), not 164.404(b) or 164.410(b). Phase 6 will fail check 3 unless one of these happens:
   - Phase 5 or 6 also emits a cited requirement for the breach-notification clause, or
   - the decision is logged as a PRD §21 item.

   The unit tests currently point the derived requirement at the 164.312(b) requirement, which only exercises the mechanics. **Decide before Phase 6.**

## Decisions made in this phase (not in the PRD)

- A `not_asked` field has no source. The PRD's `Field` lists four sources and is silent on never-asked fields.
- A corpus framework id is a string, not an enum. A clause whose framework has no declaration is rejected when a requirement cites it. The PRD's rule is that a framework without a declaration cannot ship.
- An ambiguous determination needs at least one unresolved question. A determined one carries no cause and no questions.

## Deferred

- **Check 5 (scope)** is deferred to Phase 2, as planned.
- **Real framework declarations** for `HIPAA-Security` and the breach rule ship with the Phase 1 corpus. The test declarations in `tests/unit/factories.py` are not the corpus.
- **`GOLDEN_CASES_DIR` env setting** is deferred until the Phase 8 CLI needs one. Tests locate `cases/` relative to their own file.
- **Untouched:** pre-existing uncommitted changes in `docs/implementation.plan.md`, `corpus/patterns.yaml` (deleted) and `corpus/implications.yaml` (new).
