# G-04 — Appointment data is protected health information

**Date:** 2026-10-19
**Question:** For a scheduling tool sold to clinics that bill insurers electronically, are patient names, appointment times, and provider identity — with no diagnoses, notes, or test results — protected health information? Is business-associate status contested?
**Verdict:** No. The data is PHI. G-04 is a business associate. Relabelled the same day.

## Findings

1. **45 CFR 160.103.** Health information includes information that relates to "the provision of health care to an individual." Individually identifiable health information is that information when a health care provider, health plan, employer, or clearinghouse creates or receives it and it identifies the person, or could reasonably be used to. Held or sent electronically, it is protected health information. A diagnosis is not an element of the test.
2. **HHS.** A software vendor that hosts a covered entity's patient information is a business associate ([FAQ 256](https://www.hhs.gov/hipaa/for-professionals/faq/256/is-software-vendor-business-associate/index.html)). The conduit exception covers transmission only, like the postal service, with storage only while the data is in transit ([cloud computing guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/health-information-technology/cloud-computing/index.html)). A scheduling tool needs routine access to the appointments, so it is not a conduit.
3. **Why the tool called it contested.** The G-04 label and the PRD §9.1 worked example said contested. The Phase 1 corpus stored the PHI definition without the two definitions it depends on (`health information`, `individually identifiable health information`), which PRD §15 requires. There was no stored text to reason from, so the rationale said "is not settled" with nothing behind it.

## What changed

- Ingested the two missing 160.103 definitions from the existing 2026-10-15 eCFR snapshot. Operative terms tagged by the same rule as Phase 2.
- Linked `individually identifiable health information ⊂ health information` in the lexicon.
- G-04 expected status is `business_associate`. HIPAA is in scope. The rationale walks health information → individually identifiable health information → protected health information, and the panel lists those clause ids.
- The prototype still does not ask storage versus pass-through. Received data is treated as maintained.
- `receives_clinical_information` no longer changes the status. Yes and no are both cited.

## What stays open

- PRD §9.1 worked example is frozen and wrong. Logged as PRD §21 item 12.
- No golden case now produces `contested_question`. A later honest contested case is identifiers without a name (for example an IP address on a public appointment page).
- Definition-closure gaps that remain: subcontractor, health care clearinghouse, workforce, organized health care arrangement (Phase 1 QA).
