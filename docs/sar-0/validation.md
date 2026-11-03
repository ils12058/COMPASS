# Validation — method, evidence limits and definition of done

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
**Audit branch:** `codex/sar-0-academic-audit`.
**Date:** 2026-11-03.

## 1. Method

**Verified.** The audit was performed by static inspection of the repository at the exact base SHA,
using read-only Git and file-reading commands. No database connection, migration, seed, server,
browser or deployment command was executed. No Student PII, secret, credential or production record
was read or reproduced.

Commands used (representative, all read-only):

```text
git rev-parse HEAD
git rev-parse origin/integration/ux15-modernization
git log -1 --format='%H %ci %s'
git status --short
rg -n "StudentAffiliation|organization_student_affiliation" be/compass
rg -n "class StudentAffiliation|class StudentInventory|class GraduateTracerResponse" be/compass
rg -n "student_academics" be/compass
rg -l "StudentAffiliation" be/tests | wc -l
rg -l "StudentInventory" be/tests | wc -l
rg -l "GraduateTracerResponse" be/tests | wc -l
rg -l "GoodMoralRequest" be/tests | wc -l
ls be/tests/test_*.py | wc -l
ls fe/tests/*.mjs | wc -l
```

**Verified.** The working tree was clean at the start; only this `docs/sar-0/` package is added.

## 2. Claim-label legend

- **Verified** — directly observed in the cited file/line at the audit base, or produced by the
  stated read-only command.
- **Inferred** — a conclusion drawn from verified code/data shape, explicitly identified as an
  audit judgment.
- **Unknown** — not observable from the repository, not queried, or dependent on institutional
  policy/live data.

## 3. Evidence gathered

**Verified.**

- `be/compass/organization/models.py`: AcademicYear, Program policy fields, StudentAffiliation,
  FacultyAffiliation, CounselorResponsibility.
- `be/compass/organization/services.py`: affiliation write/remove, counselor resolution, role
  transition guard.
- `be/compass/organization/api.py`: affiliation endpoints and authorization.
- `be/compass/organization/access_scope.py`: operational and general guidance scope.
- `be/compass/organization/academic_years.py`: label/current rules.
- `be/compass/organization/program_policy.py`: policy validation.
- `be/compass/organization/catalog_services.py`: retirement impact and affiliation counts.
- `be/compass/accounts/models.py`: User, lifecycle, uniqueness.
- `be/compass/accounts/services.py`: `is_current_student`.
- `be/compass/accounts/policy.py`: roles, designations, capability grants.
- `be/compass/inventory/models.py` and `services.py`: Inventory fields, submission validation,
  policy enforcement, staff scope.
- `be/compass/good_moral/models.py` and `services.py`: snapshots, F4 eligibility, affiliation
  prerequisite, graduate variant.
- `be/compass/graduate_tracer/models.py` and `services.py`: graduation fields and service checks.
- `be/compass/account_management/services.py` and `be/compass/account_management/csv_import.py`: provisioning and CSV headers.
- `be/compass/account_management` role/lifecycle transitions.
- `be/compass/reports/services.py`: profile filters and coverage population.
- `be/compass/operational_students.py`: operational Student selection.
- `be/compass/guidance_followups/policy.py`, `be/compass/guidance_followups/recovery.py`, `be/compass/guidance_followups/workspace.py`: affiliation scope.
- `be/compass/appointments/services.py` and `access.py`: default provider and visibility.
- `be/compass/counseling/context_services.py`, `be/compass/counseling/continuity_access.py`, `continuity_services.py`,
  `be/compass/counseling/coverage_selection.py`, `be/compass/counseling/handoff_services.py`: affiliation scope and context merge.
- `be/compass/guidance_messages/services.py`, `referrals/faculty_placement.py`,
  `be/compass/referrals/services.py`, `call_slips/services.py`, `student_support/services.py`,
  `assessment_records/services.py`, `group_sessions/models.py`: affiliation usage or verified
  absence.
- `be/compass/audit/actions.py`: audit action names.
- `be/compass/privacy_governance/retention_policy_register.py`, `activity_export.py`: retention
  coverage and export content.
- Migrations: organization `0001`/`0002`, accounts `0001`, inventory `0001`, good_moral `0001`,
  graduate_tracer `0001`.
- Seeds: `be/compass/staging_seed/organization.py`, `be/compass/staging_seed/history.py`, `verify.py`,
  `scenarios/rich.py`, `scenarios/background.py`.
- Frontend: affiliation page, create account, import accounts, inventory education section,
  Graduate Tracer form sections, Good Moral request page, `lib/year-level.ts`, generated
  affiliation client models.
- Documentation: `docs/fac-5/readiness.md`, `docs/fac-5/institutional-decisions.md`,
  `docs/org-0/current-state-audit.md`, `docs/org-0/dependency-and-history-matrix.md`,
  `docs/org-0/open-decisions.md`, `docs/org-1/program-policy.md`,
  `docs/org-4/institutional-decision-register.md`, `docs/org-4/academic-policy-and-history.md`,
  and the proposal lines 1–986.

**Verified test/fixture footprint (repository counts):**

| Evidence | Count |
|---|---|
| Backend test files (`be/tests/test_*.py`) | 210 |
| Frontend test files (`fe/tests/*.mjs`) | 180 |
| Backend test files referencing `StudentAffiliation` | 121 |
| Backend test files referencing `StudentInventory` | 81 |
| Backend test files referencing `GraduateTracerResponse` | 37 |
| Backend test files referencing `GoodMoralRequest` | 56 |

**Inferred.** These counts show that the existing behaviors are heavily regression-tested. They do
not prove that any test asserts cross-source College/Program consistency, because the search was
file-level, not assertion-level.

## 4. Paths and domains explicitly not inspected

The audit was bounded. The following were **not** inspected in full and must not be treated as
covered:

- `docs/fac-1`, `docs/fac-2`, `docs/fac-3`, `docs/fac-4` (only FAC-5 was read in detail).
- `docs/cont-0` through `docs/cont-4`; `docs/notif-04` (listed as related evidence, not read in
  full for this audit).
- `docs/org-2`, `docs/org-3` (only ORG-0, ORG-1 and ORG-4 documents were read in detail).
- Full `be/compass/counseling`, `call_slips`, `referrals`, `student_support`,
  `assessment_records`, `group_sessions`, `exit_interviews`, `notifications` and
  `privacy_governance` implementations; only the academic/affiliation usage and relevant models
  were read.
- Full `be/compass/staging_seed` content; only affiliation/inventory provisioning paths were read.
- Full `be/tests` and `fe/tests` content; only file counts and targeted searches were used.
- Full frontend source; only the pages/components listed in `consumers.md` were read.
- Deployment configuration: `be/deploy`, `be/compose*.yaml`, `be/Caddyfile`, CI workflows, release
  scripts, backup/restore runbooks.
- Authentication/session/MFA internals beyond the capability/recent-MFA call sites.
- External systems: UCN SIS, Registrar systems, email transport, object storage, production
  monitoring, external reporting or spreadsheet consumers.
- Live PostgreSQL schema beyond migrations (for example, manually added triggers, extensions,
  functions not in migrations).
- Production, staging or local database contents. No row counts, distributions or PII were read.
- UAT, usability, screen-reader, load, penetration or recovery testing.

**Unknown.** Any finding that depends on the above is explicitly marked Unknown in the package.

## 5. Unknowns carried forward

1. **Unknown** — Population counts for every DQ query; no database was queried.
2. **Unknown** — Whether production schema matches migrations exactly (manual changes, trigger
   drift).
3. **Unknown** — Whether UCN/Registrar has an external authoritative source for Program,
   enrollment or graduation.
4. **Unknown** — Official term calendar, enrollment categories, verification authority and
   retention schedule.
5. **Unknown** — Whether FUP-3C exists outside this repository; no reference was found.
6. **Unknown** — Whether any Faculty academic-contact attestation implementation exists outside
   this repository; FAC-D9 says none exists in FAC-1–5, and no code matches.
7. **Unknown** — External consumers of College/Program data (spreadsheets, reports, downstream
   offices).
8. **Unknown** — Production feature-flag/monitoring/release procedures; no framework exists in the
   repository.
9. **Unknown** — Actual audit retention and access controls for affiliation history.
10. **Unknown** — Whether Students can currently request academic corrections through an
    off-system process.

## 6. Audit question coverage

| Required question | Where answered |
|---|---|
| Where academic data lives and its invariants | `current-state.md` §2–§11 |
| Who writes/reads each field across backend, frontend, tasks, seeds, reports, notifications, exports | `consumers.md` |
| Data-quality problems (duplicates, nulls, orphans, invalid combinations, year-level, inactive) | `data-quality.md` |
| Compatibility of proposed models with current data | `model-validation.md` |
| Safe affiliation migration with rollback and no destructive changes | `migration-and-rollback.md` |
| Which institutional decisions block SAR-1 and owners | `decisions.md` |
| Smallest safe SAR-1 scope | `README.md`; `migration-and-rollback.md`; `model-validation.md` |

## 7. Definition-of-done checklist

| Requirement | Status |
|---|---|
| Read proposal lines 1–986 before starting | **Verified** — read in full |
| Record exact audited SHA | **Verified** — `7afd442eed38d38ec2f18a7dc9c1715b412f5122` |
| Branch from the fetched head | **Verified** — `codex/sar-0-academic-audit` tracks `origin/integration/ux15-modernization` at the base SHA |
| No code/schema/migration/API/UI/seed/fixture/deployment changes | **Verified** by Git diff scope |
| No `makemigrations`, `migrate`, seed or destructive DB command | **Verified** — none executed |
| No PII, secrets, credentials or production data | **Verified** — aggregate-only, no database access |
| Every verified claim cited with path and line | **Verified** in the package; summary-level counts cite the command/source |
| Unverifiable items marked Unknown | **Verified** |
| No invented institutional policy; decisions assigned to UCN/GCO/Registrar/DPO/Records/IT | **Verified** — `decisions.md` |
| Proposal's old SHA/current-state claims re-verified | **Verified** — all current-state claims checked against the audit base |
| Bounded audit with uninspected paths listed | **Verified** — §4 above |
| Draft PR only; no merge/deploy/staging/production action | **Pending until the PR is opened; no merge will be performed** |
| Top 10 findings and recommended SAR-1 scope in PR body | **Prepared** — see `README.md`; to be included in the draft PR |

## 8. Residual validation limits

**Inferred.** Static source inspection is strong evidence for model shape, writers, readers and
service validation. It cannot prove:

- the population distribution or the existence of legacy bypasses;
- runtime database trigger/constraint parity;
- actual authorization grants in a deployed database (code baseline grants can differ from
  persisted overrides; see `be/compass/accounts/policy.py` and the proposal's own compatibility
  note at lines 11496–11500);
- the behavior of external systems or manual processes;
- that a future SAR-1 implementation will preserve the invariants proposed here.

Those require the authorized aggregate queries, a staging rehearsal, backup/restore evidence and
institutional UAT listed in `migration-and-rollback.md` and `decisions.md`.
