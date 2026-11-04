# Decisions consumed by SAR-2B + SAR-2C

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries remain
recorded there as **Open**, with institutional owners.
**Status of this file:** this slice applies the task's **provisional engineering defaults** for
D-SAR-09, D-SAR-10 and D-SAR-11 so academic periods and graduation can be implemented without
inventing institutional policy. These are **not** UCN, GCO, Registrar, DPO, Records or IT approvals.
The implementation is destructive to the repository only; it was merged into
`integration/ux15-modernization` and pushed to `origin` without a PR, and was not deployed or run
against a shared environment.

## 1. Applied defaults — D-SAR-09 to D-SAR-11

| ID | Question (SAR-0) | Default applied here | Where enforced |
|---|---|---|---|
| D-SAR-09 | Official term/period calendar and codes | **Reuse `organization.AcademicYear`** (`label`, `is_current`). A period is identified by `(student, academic_year, term)` with only `FIRST_SEMESTER` / `SECOND_SEMESTER`, labeled “First Semester” / “Second Semester”. No term dates, summer/irregular term or new calendar model. | `AcademicTerm`; unique constraint; period service; frontend labels |
| D-SAR-10 | Official enrollment classifications and Student-lifecycle transitions | Enrollment is `UNKNOWN` (default), `ENROLLED` or `NOT_ENROLLED`. **No import and no automatic `NOT_ENROLLED`** from roster absence. Student lifecycle stays Accounts-owned; the only transition in this slice is `GRADUATED` when a graduation record is recorded. | `EnrollmentStatus`; period service; graduation service; no lifecycle API |
| D-SAR-11 | Graduation confirmation authority, official date, unfinished Exit Interview/Good Moral handling | Recorded by a user holding `organization.manage` with recent MFA. `graduation_date` is the official date supplied by the actor. `verification_source` is a required short free-text provenance note (max 200 characters). Recording graduation does **not** check, require or change Exit Interview or Good Moral. It clears the current placement and sets the lifecycle to `GRADUATED` in the same transaction. **No un-graduation or revocation workflow.** | API `_require(..., recent_mfa=True)`; `record_graduation`; confirmation copy |

### 1.1 Authorization boundary

No `student_academics.*` capability exists. Reads require `organization.manage`; writes require
`organization.manage` and recent MFA. No role, capability or designation grant changed. This is a
**deliberate temporary authorization boundary**; D-SAR-05 remains open, and a later slice that adds
dedicated capabilities must revisit the read/write split, MFA policy, scope and grants explicitly.

### 1.2 Consequential-write semantics

Graduation is treated as a confirmed fact, not a workflow:

- One graduation record per Student (one-to-one), audited overwrite allowed for corrections.
- Recording or updating clears every placement fact, resets placement verification to `UNVERIFIED`,
  nulls the effective date and records the clear with `cause="graduation"`.
- Lifecycle `GRADUATED` is set in the same transaction without emitting the Accounts-owned
  lifecycle audit action.
- Exit Interview and Good Moral stay independent; no read, requirement or change.
- There is no delete, un-graduate or revocation path.

## 2. Deferred decisions — D-SAR-12 to D-SAR-20

Not consumed, not implemented and not required for this slice. They remain blockers for multiple
degrees, retention, corrections beyond audited overwrite, student visibility, Year Level policy,
Faculty custody, Inventory precedence and report reconciliation.

| ID | Deferred question |
|---|---|
| D-SAR-12 | Multiple programs/degrees and subsequent enrollment |
| D-SAR-13 | Retention and point-in-time reporting for academic history and names |
| D-SAR-14 | Corrections to previously verified facts |
| D-SAR-15 | Mandatory vs optional academic fields during provisioning/import |
| D-SAR-16 | Student visibility and correction requests |
| D-SAR-17 | F4/F6 verification and Year Levels beyond 1–4 |
| D-SAR-18 | Faculty academic-contact attestation and transfer/historical-access custody |
| D-SAR-19 | Inventory Program College vs placement College precedence |
| D-SAR-20 | Reconciliation definitions for reports, profiling and operational Student lists |

The service accepts year levels 1–8 only to validate input shape; it does **not** settle D-SAR-17.
No year level is incremented or inferred.

## 3. Non-negotiable boundaries preserved

- No institutional policy was invented: every unresolved semantic remains open in the SAR-0
  register.
- No Program, verification, effective-date, import, corrections or student-self-view feature.
- No `student_academics.*` capability, role grant or designation grant was added.
- `FacultyAffiliation` and all Faculty code are untouched.
- `StudentAcademicProfile` fields are unchanged; only the two named SAR-2A residual fixes altered
  behavior.
- No data migration or backfill; the database is rebuilt from the canonical baseline plus seeds.
- No production or staging contact, deployment or seed run against a shared environment.
