# Current state — where Student academic data lives

**Audit base:** `7afd442eed38d38ec2f18a7dc9c1715b412f5122`.
Every claim below is marked **Verified**, **Inferred** or **Unknown**. Citations refer to that SHA.

## 1. Executive summary

**Verified.** COMPASS has no Student Academic Records domain. The academic facts needed by
Guidance workflows are distributed across five places:

1. `organization.StudentAffiliation` — the Student's current College only.
2. `inventory.StudentInventory` — the Program and Year Level submitted for one Academic Year.
3. `good_moral.GoodMoralRequest` — named snapshots taken at request time.
4. `graduate_tracer.GraduateTracerResponse` — self-reported College, Program and graduation year.
5. `accounts.User.student_lifecycle_status` — `CURRENT`/`GRADUATED`/`FORMER`, independent of
   enrollment and verification.

**Verified.** The proposal's proposed `student_academics` app, models and capabilities do not
exist. A repository-wide search for `student_academics` in `be/compass` returns no matches.
`StudentAffiliation` is owned by `be/compass/organization/`, not by a Student domain.

**Inferred.** The current architecture is workable for Guidance operations, but it has no single
place that answers “what is this Student's current College, Program, Year Level, enrollment and
verification state, and what was it last term?” Each consumer answers a subset from a different
source.

## 2. Fact ownership map

| Academic fact | Current storage | Cardinality | Enforced by | History |
|---|---|---|---|---|
| Student identity | `accounts.User` | one account | unique case-insensitive email and institutional ID (`be/compass/accounts/models.py:170,218-226`) | audit only |
| Student lifecycle | `accounts.User.student_lifecycle_status` | one value | enum check (`be/compass/accounts/models.py:182-187,227-233`) | audit event on change |
| Current College | `organization.StudentAffiliation.college` | one per Student | `OneToOneField(primary_key=True)` (`be/compass/organization/models.py:199-206`) | none; audit metadata only |
| Program for a year | `inventory.StudentInventory.program` | one Inventory per Student per Academic Year | nullable FK; unique `(student, academic_year)` (`be/compass/inventory/models.py:224-230,372-375`) | per-year Inventory rows, not a current placement |
| Year Level for a year | `inventory.StudentInventory.year_level` | one per Inventory | integer 1–10 check (`be/compass/inventory/models.py:233-237,376-382`) | per-year Inventory rows |
| Academic Year | `organization.AcademicYear` | at most one current | unique label; partial unique current (`be/compass/organization/models.py:23-40`) | rows retained; no delete API |
| Term / semester | `good_moral.GoodMoralRequest.semester_snapshot` | one text value per request | canonical two-value service check, no FK (`be/compass/good_moral/models.py:42-45`; `be/compass/good_moral/services.py:788`) | snapshot only |
| Enrollment status | **none** | — | — | — |
| Academic verification | **none** | — | — | — |
| Placement effective date | **none** | — | — | — |
| Graduation | `graduate_tracer.GraduateTracerResponse` college/program/year | one response per Student per instrument version | service validation only (`be/compass/graduate_tracer/services.py:515-583`) | response revisions, not an official record |

## 3. `StudentAffiliation` — current College only

**Verified.** The model is a one-to-one current-state row:

- `student` is a `OneToOneField(..., primary_key=True)` to `User` (`be/compass/organization/models.py:199-206`). A Student cannot have two rows, and the Student's UUID is the row primary key.
- `college` is a `ForeignKey(College, on_delete=PROTECT)` (`:207-209`). No Program, Year Level,
  enrollment, verification, source, effective date, end date or campus field exists.
- `assigned_by`, `created_at`, `updated_at` are the only provenance (`:210-219`).

**Verified.** There is exactly one write path: `set_student_affiliation` (`be/compass/organization/services.py:271-303`).
It locks the active Student, the active College and the existing row; a same-College call is a
no-op; a different College updates the existing row in place; audit metadata records
`previous_college_id` and `new_college_id` (`:282-302`). No other backend code creates or updates
`StudentAffiliation` rows.

**Verified.** `remove_student_affiliation` deletes the row and records the removed `college_id` in
audit metadata (`be/compass/organization/services.py:307-325`). There is no soft delete, tombstone
or history row.

**Verified.** Writes require the `organization.manage` capability and recent MFA
(`be/compass/organization/api.py:526-548`). Reads of the affiliation list also require
`organization.manage` (`:489`). There is no Student self-read endpoint.

**Verified.** Changing a Student's role away from `STUDENT` is blocked while an affiliation exists
(`be/compass/organization/services.py:137-162`). This prevents a current affiliation from surviving
a role change through the supported service, but it does not create history.

**Verified.** Catalog retirement treats active Student affiliations as a College/Campus blocker
(`be/compass/organization/catalog_services.py:572-590`); affiliations on inactive accounts are only
a warning. Program retirement is not blocked by Student affiliations or Inventory facts.

**Inferred.** Because transfer is an in-place update, the only surviving evidence of a prior
College is (a) the audit event metadata (IDs, not names), and (b) domain snapshots that happened to
be taken while the prior placement was current (Good Moral `college_snapshot`, historical Inventory
Program College). Any consumer that needs “the College on date X” must reconstruct it, and may be
unable to do so.

## 4. Student lifecycle is not enrollment or verification

**Verified.** `StudentLifecycleStatus` has exactly `CURRENT`, `GRADUATED`, `FORMER`
(`be/compass/accounts/models.py:61-65`). `UserManager.create_user` sets `CURRENT` only when the
resolved role is `STUDENT` (`:143-145`).

**Verified.** `is_current_student` requires an active account, role `STUDENT` and lifecycle
`CURRENT` (`be/compass/accounts/services.py:113-122`). It does not check enrollment, an academic
period, a Program or a College.

**Verified.** Role change sets lifecycle to `CURRENT` only when the new role is `STUDENT` and the
stored value is null (`be/compass/account_management/services.py:976-979`). It does not clear the
value when the role leaves `STUDENT`; only the affiliation-removal guard stands between a stale
value and a later role change.

**Verified.** `set_student_lifecycle` changes the value only for a role-`STUDENT` account and is
audited (`be/compass/account_management/services.py:1006-1042`). It does not record an effective
date, source, verification or enrollment period.

**Inferred.** `CURRENT` is a COMPASS account lifecycle marker, not proof of enrollment, and must not
be treated as a verified academic fact. The proposal states the same distinction (proposal lines
313–335).

## 5. `StudentInventory` — the only Program and Year Level source

**Verified.** `StudentInventory` belongs to one Student and one Academic Year
(`be/compass/inventory/models.py:207-230`). It stores:

- `program` — nullable FK to `Program` (`:224-230`), protected from deletion.
- `year_level` — nullable small integer, validated 1–10 (`:233-237`).
- `course_currently_enrolled` — denormalized text, forced to the Program name on save
  (`be/compass/inventory/services.py:1207-1212`; frontend `fe/src/features/inventory/editor/education-section.tsx:103-108`).
- `major`, `submitted_at`, revision and confidential content fields (`be/compass/inventory/models.py:285-291`).
- Unique `(student, academic_year)` (`:372-375`) and year-level check (`:376-382`).

**Verified.** Draft saves and submission require an active Program and its active College/Campus
ancestry (`be/compass/inventory/services.py:544-571`). On submission, Program and Year Level are
required, and Program-specific year-level policy is enforced (`:1385-1455`). Program policy is only
re-applied when the Program or Year Level changed during a draft save (`:1219-1231`).

**Verified.** There is no check that `inventory.program.college_id` equals
`StudentAffiliation.college_id`. The inventory service uses affiliation only for staff scoping
(`be/compass/inventory/services.py:432-439,1541,1612`). A Student can therefore submit a Program
owned by a different College without a domain error.

**Verified.** The inventory is a per-Academic-Year record, not a current placement. A Student may
have prior Inventories in earlier Academic Years with different Programs and Year Levels, but there
is no “current Program” row outside the selected year.

## 6. Program policy — ORG-1 fields exist and are enforced

**Verified.** `Program` stores `academic_classification`, `year_level_policy_status` and
`applicable_year_levels` (`be/compass/organization/models.py:116-129`). Database checks require
pending policy to have null levels and configured policy to have a supported classification plus
sorted unique levels 1–10, enforced by the SQL function `organization_valid_year_levels_v1`
(`:131-175`; migration `be/compass/organization/migrations/0002_program_policy_and_catalog_initialization.py:64,192-198`).

**Verified.** Service-level validation mirrors the database rule and rejects coercible values
(`be/compass/organization/program_policy.py:20-46`).

**Verified.** F4 eligibility requires a Bachelor's Program, a Year Level present in both the
Program's `applicable_year_levels` and the hardcoded F4 labels 1–4, and a submitted current-year
Inventory (`be/compass/good_moral/services.py:455-507`). Postgraduate and unclassified Programs are
refused.

**Inferred.** Policy completeness is institutional, not technical: Programs may legitimately remain
`PENDING_POLICY`, and ORG decisions D7–D11 still gate policy activation, expanded F4 years and
consequential edits (`docs/org-4/institutional-decision-register.md:17-21`).

## 7. Academic Year and term

**Verified.** `AcademicYear` stores a unique label and an `is_current` flag. A partial unique
constraint enforces at most one current year (`be/compass/organization/models.py:23-40`).
Creation validates a `YYYY-YYYY` consecutive label; `set_current_academic_year` is transactional and
audited; there is no delete API (`be/compass/organization/academic_years.py:33-115`).

**Verified.** “No current year” is possible at the database level; callers receive an explicit
conflict from `require_current_academic_year` (`be/compass/organization/academic_years.py:64-68`).

**Verified.** There is no `Term`, `Semester` or `Period` model. Good Moral stores
`semester_snapshot` as text limited to `First Semester`/`Second Semester`
(`be/compass/good_moral/models.py:42-45,121`; `be/compass/good_moral/services.py:788-789`).
The Graduate Tracer stores only a graduation year integer, not a term.

**Inferred.** Academic Year is a labelling/coverage key, not a calendar with dates, terms or
enrollment periods. Any SAR period model must not assume that one Academic Year maps to one or two
terms without an institutional decision.

## 8. Historical academic facts today

**Verified.** There is no dedicated academic history table. The surviving evidence is:

- Prior `StudentInventory` rows per Academic Year, including Program FK, year level, course text and
  submitted timestamps (`be/compass/inventory/models.py:207-291`).
- Finalized Good Moral snapshots: `year_level_snapshot`, `college_snapshot`, `course_snapshot`,
  `major_snapshot`, `semester_snapshot`, `degree_snapshot`, `graduation_date`
  (`be/compass/good_moral/models.py:115-124`), populated for current-student requests from the
  Inventory and affiliation (`be/compass/good_moral/services.py:818-825`).
- Graduate Tracer self-reported `graduated_college`, `graduated_program`, `graduation_year`
  (`be/compass/graduate_tracer/models.py:259-273`), with a Program/College service check on write
  (`be/compass/graduate_tracer/services.py:556-572`).
- Audit events for affiliation assignment/change/removal, Academic Year changes, Inventory events,
  Good Moral and Tracer (`be/compass/audit/actions.py:43-47,88-107`).

**Verified.** None of these is an effective-dated academic record. Program and College display
names come from the current catalog rows; there is no name snapshot on Inventory or Tracer.
Good Moral does snapshot names, but only when a request is created. Reports explicitly retain a
“recorded value” label for Year Levels above 4 (`be/compass/reports/services.py:335-344`).

**Inferred.** Point-in-time reporting is therefore partial and consumer-specific: a historical
Inventory can say which Program was selected, but not necessarily what that Program or College was
officially called at the time, whether the Student was enrolled, or whether the placement was
verified.

## 9. Account creation and CSV provisioning

**Verified.** `create_account` accepts identity, role and optional `faculty_college_id`; it creates
the User and writes only a Faculty affiliation. There is no Student College, Program or Year Level
parameter (`be/compass/account_management/services.py:668-747`).

**Verified.** CSV headers are exactly `institutional_id,email,first_name,last_name,role` plus
optional `middle_name,suffix,faculty_college_id`; no academic columns are accepted
(`be/compass/account_management/csv_import.py:37-39`). Commit creates Students through the same
`UserManager`, so they begin with lifecycle `CURRENT` and no affiliation.

**Verified.** The frontend create-account form has no academic fields and states that new Student
accounts start with current status (`fe/src/features/accounts/create/create-account.tsx:35-44,244`).
The import template documents only identity and `faculty_college_id`
(`fe/src/features/accounts/import/import-accounts.tsx:23,174`).

**Inferred.** A provisioned Student cannot route to a Counselor, appear in operational College
scope, or complete current-student Good Moral until an administrator separately sets an
affiliation. This is a deliberate separation today, but it means provisioning and academic
placement are not atomic.

## 10. Proposed SAR capabilities are absent

**Verified.** The canonical role/capability policy has no `student_academics.*` capability
(`be/compass/accounts/policy.py:608-760`). Existing roles are `FACULTY`, `IT_ADMIN`, `COUNSELOR`,
`GUIDANCE_SERVICES_STAFF`, `STUDENT`, `INSTITUTIONAL_OFFICER`; designations are
`HEAD_GUIDANCE_COUNSELOR` and `DPO` (`be/compass/accounts/policy.py:20-76`). There is no Registrar
role.

**Verified.** Affiliation management is an `organization.manage` responsibility; IT_ADMIN receives
it by baseline grant (`be/compass/accounts/policy.py:617-626`). No capability currently separates
“read academic profile”, “manage placement” and “verify academic fact”.

**Inferred.** SAR-1 cannot reuse an existing Registrar capability or role; verification authority
must be represented through a new capability grant, a designation, or an approved process outside
COMPASS. This is an institutional decision, not a code assumption.

## 11. Invariant strength

| Invariant | Strength | Evidence |
|---|---|---|
| One affiliation per Student | Database | primary key `OneToOneField` (`be/compass/organization/models.py:199-206`) |
| One Inventory per Student per Academic Year | Database | unique constraint (`be/compass/inventory/models.py:372-375`) |
| Program belongs to an existing College | Database FK | `Program.college` (`be/compass/organization/models.py:111`) |
| Year Level 1–10 | Database check | `be/compass/inventory/models.py:376-382` |
| Program policy shape | Database check + service | `be/compass/organization/models.py:131-175`; `be/compass/organization/program_policy.py:20-46` |
| Selected Program is active and has active ancestry | Service | `be/compass/inventory/services.py:544-571` |
| Inventory Program College equals affiliation College | **Not enforced** | no check in inventory or organization |
| Tracer Program belongs to Tracer College | Service only, not database | `be/compass/graduate_tracer/services.py:556-572` |
| Academic Year label shape and one current | Service + partial unique | `be/compass/organization/academic_years.py:33-115`; `be/compass/organization/models.py:32-39` |
| Student lifecycle matches role/active status over time | **Not enforced** | role change does not clear lifecycle (`be/compass/account_management/services.py:976-979`) |
| Placement verification and source | **Not modeled** | no fields |
| Placement effective dating | **Not modeled** | no fields |
| Historical College/Program after transfer | **Not modeled** | in-place update/delete; audit IDs only |

## 12. Open questions raised by current state

1. **Unknown** — Which office, if any, currently verifies a Student's Program or College outside
   COMPASS? The proposal names this as decision 1 but the repository contains no implemented
   authority.
2. **Unknown** — Whether UCN treats the affiliation College as an academic placement, a Guidance
   service placement, or both. FAC-D4 describes it as operational placement; the proposal treats it
   as academic placement.
3. **Unknown** — Whether a Student may have a Program without an affiliation College, or a College
   without a Program, in institutional practice. The proposed profile allows both nulls.
4. **Unknown** — The official term calendar and enrollment categories. No current model supplies
   either.
5. **Unknown** — Population-level counts for every data-quality check in `data-quality.md`; no
   database was queried.
