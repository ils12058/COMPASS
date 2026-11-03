# Decisions consumed by SAR-2A

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries remain
recorded there as **Open**, with institutional owners.
**Status of this file:** SAR-2A applies the task's **provisional engineering defaults** so the
canonical cutover can be implemented without inventing institutional policy. These are not UCN, GCO,
Registrar, DPO, Records or IT approvals. The cutover is destructive to the repository only; it was
not merged, deployed or run against a shared environment.

## 1. Applied defaults — D-SAR-01 to D-SAR-08

| ID | Question (SAR-0) | SAR-2A default | Where enforced |
|---|---|---|---|
| D-SAR-01 | Is a current Program required, and what is its authoritative source? | **College-only.** `current_program` stays present and null; there is no Program writer, reader, API field or Inventory copy. | Model; `set_current_placement` always nulls Program; no API field |
| D-SAR-02 | Who may mark placement `VERIFIED`, and what does that prove? | **UNVERIFIED only.** No verify capability, service, endpoint, action or UI. Every write resets the status to `UNVERIFIED`. | Model default; writer services; read-only badge |
| D-SAR-03 | Which existing affiliations are backfilled, and how are they labeled/excluded? | **No backfill.** No data migration or import; the product is not deployed and local rows may be dropped. Seeds create placements through the writer. | Deleted backfill command; seed `ensure_organization` |
| D-SAR-04 | What does `placement_effective_at` mean, and may it be null? | **Null** always; no writer, API field or inferred date. | Writer services; model |
| D-SAR-05 | Who receives `student_academics.*` grants? | **No new capability.** Reads and writes reuse `organization.manage`; writes also require recent MFA. No role or designation grant changed. | `student_academics/api.py`; `organization.manage` policy |
| D-SAR-06 | What retention/disposition applies? | Treat the profile as the **current operational placement** of the Student account until a separate schedule is approved; clearing retains the row. | `clear_current_placement`; no delete path |
| D-SAR-07 | How is removal/withdrawal/graduation/“no current placement” represented? | **Keep the row**, null College and Program, reset to `UNVERIFIED`, null effective date; never delete. The cleared row disappears from the directory. | `clear_current_placement`; list filter `current_college__isnull=False` |
| D-SAR-08 | Which component is the single writer, and how is dual-write activated/rolled back? | **`compass.student_academics.services` is the sole writer.** `StudentAffiliation` is deleted. No gate, no coexistence period and no rollback flag. | Model deletion migration `0005`; all call sites |

### Explicit supersession of SAR-1 D-SAR-08

SAR-1 chose **`StudentAffiliation` as the sole writer** and kept the profile as a gated shadow
projection (D-SAR-08 Option A in `docs/sar-1/decisions-consumed.md`). SAR-2A **supersedes that
choice**: the profile is now the canonical current-placement store and its services module is the
sole writer. The SAR-1 gate setting, environment variable, dual-write functions, backfill command,
reconciliation command and shadow-only tests are deleted, not left dormant. `docs/sar-1/` remains a
historical record and is not rewritten.

### Temporary authorization boundary

No `student_academics.*` capability exists in this slice. Reads and writes reuse
`organization.manage`; writes add recent MFA. This is a **deliberate temporary authorization
boundary**, not an institutional grant decision. D-SAR-05 remains open: a later slice that adds
dedicated capabilities must revisit the read/write split, MFA policy, College/assignment/history
scope and designation grants explicitly. Until then, anyone holding `organization.manage` can read
the directory and, with recent MFA, write a placement.

## 2. Behavior-preservation deviations

The cutover preserves observable behavior, which leaves two intentional naming residues:

| Surface | Residue | Reason |
|---|---|---|
| Report PDF label | `Applied — Student's current Guidance affiliation` | Report output must remain byte-identical after the source swap |
| Counselor resolution reason | `NO_AFFILIATION` | Existing API/report consumers and tests depend on the reason code |

Neither string is a model, route, capability or writer. They are documented here so a later
terminology slice can change them deliberately rather than accidentally.

## 3. Deferred decisions — D-SAR-09 to D-SAR-20

Not consumed, not implemented and not required for SAR-2A. They remain blockers for period records,
graduation, enrollment, verification, imports, display, history and institutional cutover.

| ID | Deferred question |
|---|---|
| D-SAR-09 | Official term/period calendar and codes |
| D-SAR-10 | Official enrollment classifications and Student-lifecycle transitions |
| D-SAR-11 | Graduation confirmation authority, official date, unfinished Exit Interview/Good Moral handling |
| D-SAR-12 | Multiple programs/degrees and subsequent enrollment |
| D-SAR-13 | Retention and point-in-time reporting for academic history and names |
| D-SAR-14 | Corrections to previously verified facts |
| D-SAR-15 | Mandatory vs optional academic fields during provisioning/import |
| D-SAR-16 | Student visibility and correction requests |
| D-SAR-17 | F4/F6 verification and Year Levels beyond 1–4 |
| D-SAR-18 | Faculty academic-contact attestation and transfer/historical-access custody |
| D-SAR-19 | Inventory Program College vs placement College precedence |
| D-SAR-20 | Reconciliation definitions for reports, profiling and operational Student lists |

## 4. Non-negotiable boundaries preserved

- No institutional policy was invented: every unresolved semantic remains open in the SAR-0
  register.
- No Program, enrollment, graduation, verification or effective-date fact is created or inferred.
- No `student_academics.*` capability, role grant or designation grant was added.
- `FacultyAffiliation` and all Faculty code are untouched.
- No data migration, backfill, import or seed rewrite of historical facts.
- No production or staging contact, deployment, push, PR or merge.
