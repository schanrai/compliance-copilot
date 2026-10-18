# Phase G QA — golden set, session 1

**Date:** 2026-10-17
**Question:** Are the golden-set labels correct under 45 CFR 160.103, and do the fixtures load into the Phase 0 models?
**Verdict:** Gate G passed. 8 of 8 cases labelled, written, and loading (`uv run pytest tests/golden`: 9 passed). The items below are follow-ups for later phases, not open Gate G checks.

## Cases written

| Case | Status | Cause | HIPAA | `derived_from` (all `stated.hipaa_situation.*`) |
|---|---|---|---|---|
| G-01 | business_associate | — | in_scope | customer_types, customers_bill_insurers_electronically, receives_patient_data_from_others, receives_clinical_information |
| G-02 | neither | — | out_of_scope | customer_types, receives_patient_data_from_others, bills_insurers_electronically |
| G-03 | business_associate | — | in_scope | customer_types, customers_bill_insurers_electronically, receives_patient_data_from_others |
| G-04 | ambiguous | contested_question | unresolved | customer_types, customers_bill_insurers_electronically, receives_patient_data_from_others, receives_clinical_information |
| G-05 | ambiguous | missing_fact | unresolved | customer_types, customers_bill_insurers_electronically, receives_patient_data_from_others |
| G-06 | business_associate | — | in_scope | customer_types, receives_patient_data_from_others |
| G-07 | ambiguous | requires_document_we_cannot_see | unresolved | customer_types, receives_patient_data_from_others, receives_clinical_information |
| G-08 | covered_entity | — | in_scope | provides_care_directly, bills_insurers_electronically |

G-07: the founder stores clinical data for a customer that handles patient data for clinics. The founder's status depends on that customer's contracts with the clinics, which the founder does not hold and the tool cannot read. Another intake question cannot settle it, so the cause is not `missing_fact`.

G-06 was replaced on 2026-10-17. The billing-company version matched G-01 once the intake question was reworded ("either directly or through a billing company", PRD §21 item 2), so it tested no new rule. The replacement is software sold to a health insurer that stores the insurer's member records. `customers_bill_insurers_electronically` is not asked: a health plan is a covered entity with no billing question. `receives_clinical_information` is not asked either; member records held by a health plan are protected health information without a clinical-content finding. The billing-company trap now lives in the intake wording and is not exercised until the Intake Agent is built.

G-05 has exactly one unknown (the clinics' billing), so only the billing rule can produce its ambiguity; a second unknown would let a Router with no billing rule pass. `receives_clinical_information` is not on its list: flipping it to false leaves the result ambiguous.

`has_signed_agreements_with_healthcare_orgs` is on no `derived_from` list: a signed agreement does not decide business-associate status (PRD §20, 2026-10-16).

## Changes made during the session

- **Story amendments** (Phase G table): G-03 and G-04 now state that the clinics bill insurance electronically. Without it, both would resolve to `missing_fact` on the clinic's status. G-05 now states that the tool receives and stores the clinics' patient records, including clinical information. G-04's cause is `contested_question`, decided 2026-10-17.
- **New stated field `receives_clinical_information`.** G-01 and G-04 were identical on every existing field. Added to the models by the Phase 0 chat; PRD §7.2 and §20 updated.
- **Gate 3 reworded:** G-02 → G-03 is one founder answer changed (four intake fields), not one field.
- **PRD §21 item 10:** wording of the `receives_patient_data_from_others` intake question.

## Disagreements

None open. Resolved during the session:
- G-01: whether billing passes through the founder's software. Resolved: the story does not say so; not added.
- G-04: whether appointment data is definitely not protected health information (which would make G-04 *neither*). Resolved: it may or may not be, so the case stays ambiguous, cause `contested_question`.

## Open

1. **G-03 does not record `receives_clinical_information`.** "Handle the clinic's patient data" does not say whether it is clinical. Decide the value, or decide how the Router treats `not_asked` on this field.
2. **Phase 3:** how the Router reads `receives_clinical_information`, including `not_asked`.
3. **Phase 4 check:** every non-HIPAA framework is `not_assessed`, but FTC Act §5 holds on both branches. The ambiguous cases' component 4 must not imply that nothing applies if the founder is not a business associate.
