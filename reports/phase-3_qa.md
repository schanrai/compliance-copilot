# Phase 3 QA — Covered-entity determination

**Date:** 2026-10-18
**Question:** Do the plain-Python rules reproduce every golden case's covered-entity status, ambiguity cause, and `derived_from`, including the wellness-app flip and a health-plan customer whose clinic-billing question was not asked?
**Verdict:** Gate 3 passes. `uv run pytest`: 274 passed. No new packages. No model. Clauses were not retagged and the lexicon was not changed. Phase 6 is not cut.

## Gate 3

| Check | Result |
|---|---|
| Every golden case's `covered_entity_status`, `ambiguity_cause`, and `derived_from` match | **Pass.** G-01 through G-08 |
| G-02 → G-03 flips from neither to business associate | **Pass.** The four intake fields that change are `customer_types`, `customers_bill_insurers_electronically`, `receives_patient_data_from_others`, and `has_signed_agreements_with_healthcare_orgs`. The agreement is recorded and not used |
| G-06 is a business associate and the clinic-billing question was not asked | **Pass.** `customers_bill_insurers_electronically` is `not_asked` and is not in `derived_from` |
| Unit tests cover each rule branch, including `skipped`, `not_asked`, and `unknown_to_user` | **Pass.** The three states produce different unresolved questions. None of them is read as no |
| The determination prints with its reasoning | **Pass.** `determine tests/golden/cases/g-01.yaml` |

The trace for each case starts at intake and stops at the router. An `unknown_to_user` answer is its own intake step (`marked_unknown`). Intake and router each write one structured log line.

## How the rules read the fields

Recorded in `docs/implementation.plan.md` under Phase 3. The one that was left open: `receives_clinical_information` is read only once a covered-entity customer and received patient data are both established.

**Updated 2026-10-19.** Yes and no are both cited. Neither is contested. `not_asked`, `skipped`, and `unknown_to_user` are left out of `derived_from`. G-04 is a business associate (`reports/g-04_phi.md`).

A signed agreement is never an input. Billing through a billing company is not a separate rule; the unresolved question uses the intake wording.

## Limits

- A settled covered-entity or business-associate result is not downgraded when the other branch is open. A determined result cannot carry an unresolved question. A founder who is a clear business associate, and who also might be a covered entity, is reported as a business associate.
- A subcontractor customer makes the result `missing_fact` when no customer is a settled covered entity: whether the end providers bill insurers is not in the intake. A health plan in the same list settles business-associate status. Updated 2026-10-19 (`reports/g-07_missing_fact.md`).
- Employers are not read as group health plans. Clearinghouses, and a founder who is themselves a health plan, are not in the intake.
- When more than one cause is present, `missing_fact` wins, then a document the tool cannot see, then a contested question.

## Deferred

- Framework summary, and ambiguous-output components 1–4 and 6. Phase 4.
- The cited requirement. Phase 5.
- The derived requirement. Phase 6, which this gate does not cut.
