# SAR-0 — Student Academic Records audit

**Status:** Read-only architecture, data-flow and migration-readiness audit. No implementation.
**Audit base:** `integration/ux15-modernization` at `7afd442eed38d38ec2f18a7dc9c1715b412f5122` (FAC-5 merge `7afd442e`, 2026-11-02).
**Audit branch:** `codex/sar-0-academic-audit` (documentation only).
**Audit date:** 2026-11-03.
**Proposal reviewed:** *COMPASS — Student Academic Records*, `/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md`, lines 1–986.
**Claim labels:** every substantive claim is marked **Verified**, **Inferred** or **Unknown**.
**Data handling:** no Student PII, secrets, credentials or production data is reproduced. No database, migration, seed or deployment command was executed.

## Why this audit exists

The proposal would create a `student_academics` domain and eventually retire `StudentAffiliation`.
FAC-5 explicitly leaves “Academic contact attestation and SAR/transfer policy” as separate reviewed
work, and FUP-3C (canonical SAR-based Student College scoping) is blocked on SAR. Before any SAR-1
slice, the institution needs an evidence-based answer to: what academic data exists today, who
writes and reads it, what is safe to migrate, and which decisions block progress.

## Package map

| File | Question answered |
|---|---|
| [`current-state.md`](current-state.md) | Where academic facts live today, cardinality, invariants and history |
| [`consumers.md`](consumers.md) | Every verified backend/frontend/seed/report consumer of each academic field |
| [`data-quality.md`](data-quality.md) | Structural defects, aggregate SQL checks and population-level Unknowns |
| [`model-validation.md`](model-validation.md) | Field-by-field compatibility of the three proposed models with current data |
| [`migration-and-rollback.md`](migration-and-rollback.md) | Safe backfill, coexistence, deployment ordering, rollback and cutover gates |
| [`decisions.md`](decisions.md) | Institutional decisions, owners and what each blocks |
| [`risks.md`](risks.md) | Risk register with mitigations and rollback triggers |
| [`validation.md`](validation.md) | Method, evidence limits, paths not inspected and definition-of-done |

## Top 10 findings

| # | Finding | Claim | Evidence |
|---|---|---|---|
| 1 | No `student_academics` domain, models, migrations, tests or capabilities exist at the audit base. | **Verified** | no matches for `student_academics` under `be/compass`; capability policy at `be/compass/accounts/policy.py:608-760` |
| 2 | Academic placement is split: `StudentAffiliation` stores only the current College; the current Program and Year Level live in the per-Academic-Year Inventory. No model stores all three together. | **Verified** | `be/compass/organization/models.py:199-220`; `be/compass/inventory/models.py:207-240` |
| 3 | `StudentAffiliation` is current-state only and destructive: one row per Student, transfer overwrites the College in place, removal deletes the row, and audit metadata retains only College IDs. There is no College history table. | **Verified** | `be/compass/organization/services.py:271-325`; `be/compass/organization/models.py:199-220` |
| 4 | Inventory submission never checks that the selected Program's College matches the Student's affiliation College. The two sources can disagree without any error. | **Verified** | `be/compass/inventory/services.py:544-571`; no affiliation check in `replace_current_inventory`/`submit_current_inventory` |
| 5 | Account creation and CSV provisioning capture no Student academic placement; the CSV format has no academic columns. New Student accounts default to lifecycle `CURRENT`. | **Verified** | `be/compass/account_management/services.py:668-747`; `be/compass/account_management/csv_import.py:37-39`; `be/compass/accounts/models.py:143` |
| 6 | There is no term entity, enrollment status, source provenance or verification state anywhere in the current academic data. The Good Moral semester is a two-value text snapshot, not a term FK. | **Verified** | `be/compass/good_moral/models.py:42-45`; `be/compass/good_moral/services.py:788`; no such fields in organization/inventory models |
| 7 | Consumers read different sources for the same concept: reports profile by Inventory Program College but compute current-year coverage by affiliation College; counseling context displays affiliation College with Inventory Program/Year Level. | **Verified** | `be/compass/reports/services.py:413-433, 1011-1027`; `be/compass/counseling/context_services.py:180-243` |
| 8 | The Student lifecycle can become stale: changing a role away from `STUDENT` does not clear `student_lifecycle_status`; inactive accounts can retain `CURRENT`; eligibility predicates still depend on lifecycle plus role plus active state. | **Verified** code path; **Inferred** population impact | `be/compass/account_management/services.py:940-999`; `be/compass/accounts/services.py:113-122` |
| 9 | F4 Good Moral eligibility hardcodes Years 1–4 and depends on Program policy plus the Inventory; ORG policy decisions (D7–D11) remain blocking for any expansion or tightening. | **Verified** | `be/compass/good_moral/services.py:455-480`; `docs/org-4/institutional-decision-register.md:17-21` |
| 10 | Proposed period and graduation records cannot be backfilled from current data as verified facts. Only the affiliation College can be defensibly copied, as unverified and College-only; Program, effective date, enrollment and graduation remain non-derivable without an institutional source. | **Verified** for data availability; **Inferred** for migration consequence | `current-state.md`; `model-validation.md`; proposal lines 203–278, 659–672 |

## Recommended smallest safe SAR-1 scope

**Recommendation (not adopted policy): a profile-only, additive, dual-write foundation with no
consumer cutover and no retirement.**

1. Add a `student_academics` app containing only `StudentAcademicProfile` (1:1 `User`), with nullable
   `current_college`, nullable `current_program`, explicit verification state, effective timestamp,
   updater and timestamps.
2. Backfill only `current_college` from each existing `StudentAffiliation`, always as `UNVERIFIED`.
   Do **not** infer `current_program`, `placement_effective_at`, enrollment or graduation. Do not
   invent effective dates from affiliation `created_at`.
3. Keep `StudentAffiliation` as the only authoritative placement writer in SAR-1. Maintain the
   profile from `set_student_affiliation`/`remove_student_affiliation` in the same transaction,
   behind an explicitly approved server-side activation setting. Add reconciliation checks.
4. Add read-only profile projections (self and authorized staff) only if the capability decisions
   are approved; do not move counselor routing, reports, Good Moral, Inventory, Tracer, referrals,
   counseling or follow-ups to the new source.
5. Do not create period or graduation records, do not add CSV academic provisioning, and do not
   retire or alter `StudentAffiliation`, `StudentInventory`, `GoodMoralRequest` or
   `GraduateTracerResponse`.

**Why this is the smallest safe slice:** it creates one owner for current College, proves the
backfill and dual-write mechanics, and leaves every existing workflow untouched. It avoids the
unresolved questions that block period/graduation modeling (terms, enrollment, verification
authority, official graduation dates).

**Prerequisites:** decisions D-SAR-01 through D-SAR-08 in [`decisions.md`](decisions.md) must be
dispositioned. Period/graduation work additionally requires D-SAR-09 through D-SAR-18; any consumer
cutover also requires the conflict-precedence and reporting-reconciliation decisions D-SAR-19 and
D-SAR-20.

## What SAR-0 did not do

- No code, schema, model, migration, API, UI, seed, fixture or deployment change.
- No `makemigrations`, `migrate`, seed, database query or destructive command.
- No staging, production, merge or deployment action.
- No population-level data-quality count; the SQL in `data-quality.md` is reproducible but was not
  executed. Every population figure is **Unknown**.
- No trust in the proposal's old `staging` SHA or its current-state claims; all claims were
  re-verified against `7afd442e`.
