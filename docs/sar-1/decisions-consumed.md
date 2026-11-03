# Decisions consumed by SAR-1

**Source register:** `docs/sar-0/decisions.md`, D-SAR-01 through D-SAR-20. All entries are recorded
there as **Open**, with institutional owners.
**Status of this file:** SAR-1 applies the task's **provisional engineering defaults** so the shadow
slice can be implemented without inventing institutional policy. These are not UCN, GCO, Registrar,
DPO, Records or IT approvals. They are reversible and the activation gate remains off.

## 1. Applied defaults — D-SAR-01 to D-SAR-08

| ID | Question (SAR-0) | Option A applied in SAR-1 | Where enforced | Institutional owner still required |
|---|---|---|---|---|
| D-SAR-01 | Is a current Program required, and what is its authoritative source? | **College-only.** `current_program` exists but stays null; no Program writer, no Inventory copy. | `services.py` sync defaults and backfill; reconciliation `profile_program_present` | Registrar + UCN; GCO consult |
| D-SAR-02 | Who may mark placement `VERIFIED`, and what does it prove? | **UNVERIFIED only.** No `.verify` capability, service or endpoint; no verification audit event. | Model default and sync/backfill values; reconciliation `profile_verified` | Registrar + UCN; DPO review |
| D-SAR-03 | Which existing affiliations are backfilled, and how are they labeled/excluded? | **Backfill every Student-role affiliation**, including inactive Student accounts, as `UNVERIFIED`; **exclude non-Student-role rows** and report the count. Inactive College/Campus rows are copied as recorded and reported. | Backfill eligible filter, report and warning | GCO + Registrar + Records; IT executes |
| D-SAR-04 | What does `placement_effective_at` mean, and may it be null? | **Null** for both backfill and dual-write; no invented effective date. | Sync defaults, backfill, reconciliation `profile_effective_at_present` | Registrar + Records |
| D-SAR-05 | Who receives `student_academics.*` grants? | **No new capability, API or UI.** `default_permissions = ()`; no policy change. | Model Meta; no URLs or serializers | IT + GCO + DPO; UCN for authority |
| D-SAR-06 | What retention/disposition applies? | Treat the profile as an **operational projection of the affiliation** for retention until a separate schedule is approved; do not delete on removal. | Removal keeps the row; rollback keeps the table | DPO + Records |
| D-SAR-07 | How is removal/withdrawal/graduation/“no current placement” represented? | **Keep the row**, null College and Program, reset to `UNVERIFIED`, null effective date; never delete. | `clear_profile_for_removed_affiliation` | Registrar + Records + GCO |
| D-SAR-08 | Which component is the single writer, and how is dual-write activated/rolled back? | **`StudentAffiliation` remains the sole writer.** Mirror inside its transaction behind `STUDENT_ACADEMIC_PROFILE_SYNC_ENABLED`, default `false`; activation and rollback are operator procedures. | `organization.services` call sites; settings gate; `operations.md` | IT + GCO |

### Effect of the provisional defaults

- Academic truth is unchanged: affiliation remains authoritative; the profile is a projection.
- No verified academic fact is created. Every SAR-1 row is College-only and `UNVERIFIED`.
- No consumer changes, so no domain gains or loses access because of this slice.
- If any default is later rejected, the code path can be changed or the gate kept off; no
  institutional data beyond the shadow table is affected.

## 2. Deferred decisions — D-SAR-09 to D-SAR-20

These are not consumed, not implemented and not required for SAR-1. They remain blockers for later
period records, graduation, enrollment, verification, imports, display and cutover.

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
| D-SAR-19 | Inventory Program College vs affiliation College precedence |
| D-SAR-20 | Reconciliation definitions for reports, profiling and operational Student lists |

## 3. Non-negotiable boundaries preserved

- No institutional policy was invented: every unresolved semantic remains in the SAR-0 register.
- No Program, enrollment, graduation or effective-date fact is inferred.
- No row is marked `VERIFIED`.
- No consumer, API, frontend, capability, seed or provisioning change was made.
- The gate is not enabled in the repository, tests, Compose or CI.
