# Decisions — institutional questions that block SAR

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
**Status:** all decisions are **Open**. Nothing in this file is adopted policy. Options and
recommendations are proposals for the named owners to accept, modify or reject.

Owners use the institutional roles named in the audit brief: **UCN**, **GCO**, **Registrar**,
**DPO**, **Records**, **IT**. Where a decision requires academic authority without a current COMPASS
role, the Registrar/UCN pair is named; COMPASS has no Registrar role
(`be/compass/accounts/policy.py:20-76`).

## 1. Decision register summary

### 1.1 Blocks SAR-1 (profile-only foundation)

| ID | Decision | Owner | Why SAR-1 cannot proceed without it | Evidence needed | Status |
|---|---|---|---|---|---|
| D-SAR-01 | Is a current Program required in the profile, and what is its authoritative source? | Registrar + UCN; GCO consult | Determines whether the profile stays College-only or requires a Program writer | Approved source; conflict rule with per-year Inventory | Open |
| D-SAR-02 | Who may mark placement `VERIFIED`, and what does that label prove? | Registrar + UCN; DPO review | Prevents an unverified migration from becoming a false certification | Authority, evidence, permitted reliance, revocation | Open |
| D-SAR-03 | Which existing affiliations are backfilled, and how are they labeled/excluded? | GCO + Registrar + Records; IT executes | Decides inclusion of inactive/non-Student affiliations and the `UNVERIFIED` rule | DQ-02/DQ-03 counts; approved inclusion matrix | Open |
| D-SAR-04 | What does `placement_effective_at` mean, and may it be null? | Registrar + Records | Current rows have no academic effective date; guessing would create false history | Date vs datetime semantics; null allowed; timezone | Open |
| D-SAR-05 | Who receives `student_academics.view_self`, `.view`, `.manage`, `.verify`, `.import` grants, and with what scope? | IT + GCO + DPO; UCN for authority | No Registrar role exists; today only `organization.manage` covers affiliation writes | Role/designation/override matrix; College/assignment/history scope | Open |
| D-SAR-06 | What retention and disposition applies to the profile, its audit events and backfill evidence? | DPO + Records | The retention register covers only Tracer/E-Counseling, all `NOT_ADOPTED` | Approved schedule; access/export restrictions | Open |
| D-SAR-07 | How does the profile represent removal, withdrawal, graduation or “no current placement”? | Registrar + Records + GCO | A 1:1 profile has no status; deleting would destroy the only current projection | Approved state model; history expectations | Open |
| D-SAR-08 | Which component is the single writer during coexistence, and how is dual-write activated/rolled back? | IT + GCO | SAR-1 must not create a second authoritative placement writer | Activation gate, failure policy, reconciliation thresholds | Open |

### 1.2 Blocks period/graduation models

| ID | Decision | Owner | Why it blocks the model | Evidence needed | Status |
|---|---|---|---|---|---|
| D-SAR-09 | What term/period calendar and codes are official? | Registrar + UCN | `AcademicYear` has no dates or terms; Good Moral's two semesters are not a calendar | Term definitions, dates, irregular-period handling | Open |
| D-SAR-10 | Which enrollment classifications and Student-lifecycle transitions are official? | Registrar + UCN + GCO | No enrollment field exists; lifecycle is not enrollment and can go stale | Status list, criteria, effective dating, ownership | Open |
| D-SAR-11 | Who confirms graduation and the official graduation date, and how are unfinished Exit Interviews/Good Moral handled? | Registrar + Records + GCO | Tracer is self-reported year-only; Good Moral date is request input | Authority, evidence, date semantics, pending-work rule | Open |
| D-SAR-12 | What support is required for multiple programs/degrees and subsequent enrollment? | Registrar + UCN + Records | Tracer has one response per instrument version; no degree history | Approved multiplicity model and uniqueness rule | Open |
| D-SAR-13 | What are the retention and point-in-time reporting requirements for academic history and names? | Records + IT + UCN + Registrar | No effective-dated names; historical display uses current catalog labels | Retention schedule; as-of semantics; name history | Open |
| D-SAR-14 | Who approves corrections to previously verified facts, and what evidence is required? | Registrar + GCO + DPO | Period/graduation records would otherwise be silently editable | Correction workflow, audit and notification rules | Open |
| D-SAR-15 | Which initial academic fields are mandatory vs optional during provisioning/import? | UCN + Registrar + GCO | Current provisioning has no academic fields; requiring them changes operations | Approved mandatory set and error policy | Open |
| D-SAR-16 | May Students view their academic records and request corrections? | GCO + DPO + Registrar | Affects `view_self`, correction UX and disclosure scope | Approved visibility, wording, dispute process | Open |
| D-SAR-17 | What verification is required for F4/F6, and will Year Levels beyond 1–4 be supported? | GCO + UCN | F4 hardcodes 1–4 and depends on Program policy; ORG D7–D11 remain open | Approved eligibility/form/template policy | Open |
| D-SAR-18 | Is any Faculty academic-contact attestation approved, and what transfer/historical-access custody applies? | GCO + UCN + Registrar + DPO + Records | FAC-D9 and FAC-D10 are pending; no attestation exists | Approved need, wording, limitations, custody matrix | Open |

### 1.3 Blocks any consumer cutover, not SAR-1

| ID | Decision | Owner | Why it blocks cutover | Evidence needed | Status |
|---|---|---|---|---|---|
| D-SAR-19 | When Inventory Program College and affiliation College disagree, which source governs routing, reporting and Good Moral? | GCO + Registrar + UCN | Consumers currently disagree; a mechanical cutover would spread the conflict | Approved precedence/conflict rule and exception handling | Open |
| D-SAR-20 | What reconciliation definitions apply to report coverage, profiling and operational student lists? | Records + IT + GCO | Reports use affiliation for coverage and Inventory for profiles | Agreed denominators, inclusion rules and published notes | Open |

## 2. SAR-1 blocking decisions — options for review

### D-SAR-01 — Current Program authority

- **Option A (recommended for review):** SAR-1 is College-only; `current_program` is always null and
  the profile explicitly labels Program as unknown. No conflict with Inventory.
- **Option B:** Copy the latest submitted Inventory Program into the profile and mark it
  `UNVERIFIED`. Risk: the Inventory Program can belong to a different College; copying would
  legitimize an invalid combination.
- **Option C:** Wait for a Registrar/SIS import. This is outside the proposal's initial scope
  (proposal lines 870–881) and would delay SAR-1.

**Recommendation:** A. Record B and C as rejected or deferred by the owner, with reasons.

### D-SAR-02 — Verification authority

- **Option A (recommended for review):** SAR-1 supports only `UNVERIFIED`; no verifier capability is
  granted. Verification is designed with the period/graduation model.
- **Option B:** Grant `.verify` to a named designation and record verifier/timestamp on the profile.
  This requires adding fields the proposal does not include on the profile.
- **Option C:** Treat Account Management's `organization.manage` as verification authority. This
  contradicts the proposal's principle that account-management authority does not certify academic
  standing (lines 619–625).

**Recommendation:** A for SAR-1; decide B/C structure now so the profile fields are not designed
twice.

### D-SAR-03 — Backfill inclusion

- **Option A (recommended for review):** Backfill every existing affiliation, including inactive
  account affiliations, preserving the College as `UNVERIFIED`, and publish the exclusion counts.
  Do not backfill non-Student-role rows until explained.
- **Option B:** Backfill only active Student accounts; leave the rest for a later remediation.
- **Option C:** Do not backfill; start empty and dual-write new changes. This loses the existing
  College placement and makes the profile immediately incomplete.

**Recommendation:** A if DQ-02 shows only inactive-account rows; otherwise B plus a remediation
decision.

### D-SAR-04 — Effective date

- **Option A (recommended for review):** Null is allowed and expected for backfilled rows. New
  verified changes may carry an approved date.
- **Option B:** Use affiliation `updated_at` as the effective date. This conflates record update
  time with academic change time and is not supported by current data.
- **Option C:** Require a date on every profile write. This blocks legacy backfill and records an
  invented fact.

**Recommendation:** A.

### D-SAR-05 — Capability grants and scope

- **Option A (recommended for review):** SAR-1 defines no new capability grants. The profile is
  internal/shadow; if a read projection is added, it reuses an approved existing staff capability
  and current College scope. Student self-view is deferred.
- **Option B:** Introduce `.view_self` only, scoped to the authenticated Student.
- **Option C:** Introduce all five capabilities before any UI. This requires a role/designation
  matrix and a scope model that does not exist yet (no Registrar role).

**Recommendation:** A for the shadow phase; B only if D-SAR-16 approves student visibility. C is
premature.

### D-SAR-06 — Retention and privacy

- **Option A (recommended for review):** Treat the profile as an operational projection of the
  affiliation. Apply the same retention/disposition as the affiliation and its audit events until a
  specific academic-record schedule is adopted.
- **Option B:** Classify it as a separate academic record with its own schedule. This requires DPO
  and Records approval before SAR-1 writes any data.
- **Option C:** No classification; rely on general audit retention. This is unacceptable for a new
  Student record.

**Recommendation:** A only as an interim, explicitly labeled arrangement; adopt B before any
consumer cutover.

### D-SAR-07 — Removal/former placement

- **Option A (recommended for review):** Null the College and set `UNVERIFIED`, preserving the row
  and audit. The profile shows “no current placement.”
- **Option B:** Delete the profile when the affiliation is removed. This mirrors the current
  destructive behavior and loses the projection.
- **Option C:** Add a placement status field (`CURRENT`/`FORMER`/`UNKNOWN`). This is a model change
  that needs institutional semantics.

**Recommendation:** A for SAR-1; decide C before period history is introduced.

### D-SAR-08 — Coexistence and activation

- **Option A (recommended for review):** `StudentAffiliation` remains the sole writer; the profile
  is updated in the same transaction behind a server-side gate that defaults off; rollback disables
  the gate and leaves the table.
- **Option B:** Make the profile authoritative immediately and dual-write the affiliation as a
  compatibility record. This reverses the writer and requires the full conflict/consumer plan.
- **Option C:** No dual-write; backfill only. The profile becomes stale as soon as the first
  affiliation changes.

**Recommendation:** A.

## 3. Cross-reference to existing decision registers

**Verified.** These decisions overlap with existing unresolved institutional registers:

- ORG D7–D11 cover Program classification/levels, pending policy compatibility, incomplete Programs,
  expanded F4 years and pending F4 edits (`docs/org-4/institutional-decision-register.md:17-21`).
- ORG D14 covers historical-name presentation (`:24`).
- ORG D19–D20 cover migration review, backup/recovery/UAT and activation (`:29-30`).
- ORG D21 covers restructuring/import scope (`:31`).
- FAC-D4 covers Student placement and intake routing (`docs/fac-5/institutional-decisions.md:55-69`).
- FAC-D9 covers academic-contact attestation (`:121-133`).
- FAC-D10 covers transfer and SAR integration, including historical access/custody
  (`:132-145`).

**Inferred.** SAR decisions should not silently override these registers. The decision record should
cite the existing ORG/FAC ID and record whether it accepts, narrows or supersedes it.

## 4. Decision record template

Use the FAC-5 template: decision ID; accountable owner; proposed rule accepted/modified/rejected;
actual evidence reference and custody location; approved scope/validity; privacy/records review;
contract version; exceptions; withdrawal/review date; resulting implementation ticket. Leave names,
references and signatures blank until supplied by authorized officials
(`docs/fac-5/institutional-decisions.md:145-151`).

## 5. What is deliberately not decided here

This audit does not decide:

- whether the College affiliation is an academic placement, a Guidance placement or both;
- which office verifies enrollment, Program placement or graduation;
- whether Students may see or correct academic data;
- any retention period or deletion rule;
- any term calendar, enrollment status or graduation date;
- whether Faculty academic-contact attestation is needed.

Those are institutional decisions owned by UCN, GCO, Registrar, DPO, Records and IT, not by this
repository audit.
