# CMS trees — deferred golden cases (G-09 to G-12)

**Date:** 2026-10-20  
**Question:** What golden cases cover the CMS Covered Entity Decision Tool trees the prototype does not walk — founder as health plan, founder as clearinghouse, employer as group health plan?  
**Verdict:** Specified here. **Not wired.** Today's `HipaaSituation` has no fields for these facts; putting fixtures in `tests/golden/cases/` would fail the determination tests. Labels are a healthcare judgement (Phase G). Confirm with counsel before they become ground truth.

**Source:** [CMS Covered Entity Decision Tool](https://www.cms.gov/regulations-and-guidance/administrative-simplification/hipaa-aca/downloads/coveredentitieschart20160617.pdf) (June 2016). 45 CFR 160.103. PRD §21 items 15 and 19. **Exact questions:** PRD [§18 items 18–26](../../../artifacts/module_8_ai_prds/compliance-copilot-prd-v4.md#18-verify-before-stating-as-fact) (the whole of §18 is the counsel list).

**Do not load these until** the intake fields below exist and the router reads them. Founder CE still wins when it applies (Phase 3 decision 4).

---

## Proposed intake fields (situational — never a legal label)

| Field | Founder-facing fact | CMS tree |
|---|---|---|
| `founder_provides_or_pays_for_health_coverage` | Does your company provide, pay for, or arrange health coverage as an insurer, HMO, or similar plan — not as a clinic billing a plan? | Health plan (private benefit / issuer) |
| `founder_converts_standard_health_transactions_for_another_entity` | Does your product convert health information between a HIPAA standard electronic format and another format, **for another company**? | Clearinghouse |
| `employer_customers_use_the_product_for_their_group_health_plan` | When you sell to employers: is the product used to run or hold data for the employer's **group health plan** (enrollment, eligibility, claims), as opposed to a perk or wellness benefit that is not the plan? | Group health plan |
| `employer_plan_has_50_or_more_participants_or_is_not_self_administered` | Does that plan cover 50 or more people, **or** is it administered by someone other than the employer who set it up? CMS: a plan that is **both** under 50 **and** self-administered is **not** a health plan | Group health plan exception (endnotes 5–6) |

---

## G-09 — Founder is a health plan

**Scenario.** The founder's company is a digital health plan (issuer / HMO). It does not furnish care as a clinic. It does not "bill insurers" — it **is** the plan. It holds member eligibility and claims data.

**Why it's in.** Today's router only makes the founder a covered entity on `provides_care_directly` **and** `bills_insurers_electronically` (G-08). A plan that answers both no is labelled *neither*. CMS: a health insurance issuer or HMO is a health plan, therefore a covered entity.

**Proposed stated (once fields exist)**

- `provides_care_directly`: no  
- `bills_insurers_electronically`: no / not asked  
- `founder_provides_or_pays_for_health_coverage`: yes  
- customers: consumers (members)

**Proposed label:** **Covered entity.** HIPAA in scope.  
**Current prototype:** *neither* — do not add this YAML to `tests/golden/cases/` yet.

---

## G-10 — Founder is a clearinghouse

**Scenario.** The product takes clinic claim or eligibility files in a nonstandard format and converts them to a HIPAA standard transaction (or the reverse) **for those clinics**. It does that for another legal entity.

**Why it's in.** CMS clearinghouse tree: process or facilitate processing of health information from nonstandard to standard (or the reverse) **for another legal entity** → health care clearinghouse → covered entity. Today's router may call this a business associate (receives clinic data, clinics bill). A clearinghouse is a covered entity in its own right. Decision 4: founder CE wins.

**Proposed stated**

- `founder_converts_standard_health_transactions_for_another_entity`: yes  
- `customer_types`: clinics  
- `customers_bill_insurers_electronically`: yes  
- `receives_patient_data_from_others`: yes  

**Proposed label:** **Covered entity** (clearinghouse), not business associate. HIPAA in scope.  
**Current prototype:** *business associate* if clinics bill and data is received.

---

## G-11 — Employer customers; product runs the group health plan

**Scenario.** Sold to employers. The product enrolls employees, holds plan eligibility, or otherwise runs the employer's **group health plan**. The plan has 50 or more participants, or is administered by someone other than the employer.

**Why it's in.** Phase 3 decision 8: employers are not covered entities and are not read as group health plans. CMS: that plan **is** a health plan (hence a CE) unless it is both under 50 and self-administered. The founder who maintains PHI for that plan is a business associate.

**Proposed stated**

- `customer_types`: employers  
- `employer_customers_use_the_product_for_their_group_health_plan`: yes  
- `employer_plan_has_50_or_more_participants_or_is_not_self_administered`: yes  
- `receives_patient_data_from_others`: yes  

**Proposed label:** **Business associate.** The group health plan is the covered entity. HIPAA in scope.  
**Current prototype:** *neither*.

---

## G-12 — Employer customers; tiny self-administered plan (counter-case)

**Scenario.** Same as G-11 except the plan has fewer than 50 participants **and** the employer administers it itself.

**Why it's in.** CMS endnotes 5–6: that arrangement is **not** a health plan. Without this pair, G-11 would over-include.

**Proposed label:** **Neither** (unless another customer is a CE). HIPAA out of scope.  
**Current prototype:** *neither* — same answer, wrong reason (it never asked about the plan).

---

## What is still not a case

- Billing the **patient** does not make a covered provider. That stays G-08 / the existing care + health-plan-transaction pair (PRD §21 item 15).  
- Government programs (Medicare as a plan, Medicaid agency) — still out unless a later case needs them.  
- G-06 already covers **selling to** an insurer. G-09 is the founder **being** the plan.
