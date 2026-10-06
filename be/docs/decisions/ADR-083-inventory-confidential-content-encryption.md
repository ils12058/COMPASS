# ADR-083: Individual Inventory confidential-content encryption

- Status: Accepted
- Date: 2026-10-06
- Scope: selected Inventory source-form private content; repository implementation, live cutover deferred

## Context and decision

ADR-022 defines the annual F5 source form, ADR-037 defines controlled profiling dimensions and
ADR-055 defines scoped Counselor review/correction. Whole-Inventory encryption would force
institutional aggregation, support indicators and prerequisite checks to decrypt raw private answers.
Keep E0 workflow and E1 normalized report/support data queryable; encrypt only E2 private source
content in seven distinct bound envelopes under one Inventory keyring. StudentSupportProfile and
structured PSGC snapshots remain ordinary typed models. No frontend or logical API change.

## Exact field boundaries

### StudentInventory

Queryable columns: `id`, `student`, `academic_year`, `form_revision`, `program`, `year_level`, `submitted_at`, `first_submitted_at`, `last_submitted_at`, `full_name_snapshot`, `student_number`, `date_of_birth`, `sex`, `civil_status_category`, `current_religion_category`, `parent_statuses`, `parent_status_category`, `living_arrangement`, `boarding_exclusive`, `present_place_people_count`, `room_sharing_people_count`, `pwd_status`, `course_currently_enrolled`, `major`, `schedule_satisfied`, `course_first_choice`, `course_choice_reasons`, `interests`, `handedness`, `daily_hours_class`, `daily_hours_library`, `daily_hours_studying`, `daily_hours_rest`, `daily_hours_recreation`, `daily_hours_other`, `ideal_monthly_allowance`, `intended_work_field`, `created_at`, `updated_at`.

Encrypted logical fields (56): `nickname`, `place_of_birth`, `nationality`, `birth_order_among_siblings`, `civil_status`, `current_address`, `permanent_address`, `contact_number`, `email_address`, `languages_spoken_at_home`, `languages_most_fluent`, `religion_from_birth`, `current_religion`, `guardian_name`, `guardian_relationship`, `guardian_address`, `guardian_contact_number`, `emergency_contact_name`, `emergency_contact_number`, `friends_in_school`, `friends_outside_school`, `special_interest`, `special_skills_talents`, `hobbies_recreation`, `ambition_goal`, `characteristics`, `boarding_landlord_name`, `boarding_address`, `accidents_experienced`, `accidents_effect`, `operations_experienced`, `operations_effect`, `immunizations`, `immunization_other`, `height`, `weight`, `physical_disadvantage`, `illness_this_year`, `previous_illness`, `schedule_satisfaction_reason`, `course_choice_other`, `lowest_subjects_grades`, `highest_subjects_grades`, `inclination_performing_arts`, `inclination_sports`, `inclination_leadership`, `other_skills_hobbies`, `desired_extracurricular_activities`, `reading_preferences`, `intended_work_other`, `prior_counseling_experience`, `prior_counselor_name`, `prior_counseling_when`, `prior_counseling_where`, `current_concerns`, `current_fears`.

Ciphertext column: `confidential_content_ciphertext`.

### InventoryFamilyMember

Queryable columns: `id`, `inventory`, `kind`, `occupation_category`, `annual_income_previous_year`, `annual_income_status`.

Encrypted logical fields (14): `name`, `date_of_birth`, `place_of_birth`, `current_address`, `permanent_address`, `contact_number`, `email_address`, `educational_attainment`, `occupation`, `business_address`, `business_telephone`, `languages_spoken`, `religion_raised_with`, `current_religion`.

Ciphertext column: `confidential_content_ciphertext`.

### InventorySibling

Queryable columns: `id`, `inventory`, `sort_order`, `is_self`.

Encrypted logical fields (5): `name`, `sex`, `age`, `educational_attainment`, `occupation`.

Ciphertext column: `confidential_content_ciphertext`.

### InventoryEducationEntry

Queryable columns: `id`, `inventory`, `level`.

Encrypted logical fields (3): `school_attended_address`, `inclusive_years`, `awards_received`.

Ciphertext column: `confidential_content_ciphertext`.

### InventoryOrganizationMembership

Queryable columns: `id`, `inventory`, `scope`, `sort_order`.

Encrypted logical fields (2): `organization_name`, `position_title`.

Ciphertext column: `confidential_content_ciphertext`.

### InventoryTransportationEntry

Queryable columns: `id`, `inventory`, `mode`, `frequency_category`, `fare`.

Encrypted logical fields (1): `frequency`.

Ciphertext column: `confidential_content_ciphertext`.

### InventoryReopenEvent

Queryable columns: `id`, `inventory`, `reopened_by`, `reopened_at`.

Encrypted logical fields (1): `reason`.

Ciphertext column: `reason_ciphertext`.

InventoryGeographicLocation is unchanged: UUID/parent/kind, explicit `not_specified` and all
region/province/city-municipality/barangay PSGC codes and saved names. StudentSupportProfile remains
unchanged: Inventory relation, four-Ps/Indigenous Peoples/mother-life/father-life statuses and timestamps.
Queryable historical name/Student-number snapshots remain source-form identity, not private search
indexes. Search uses canonical User identity, never raw confidential content or ciphertext.

## Seven exact v1 envelope schemas and one keyring

Every authenticated JSON envelope has exactly integer `schema_version: 1`, its binding below and
`payload` with exactly its encrypted logical fields above. UUIDs use `str(UUID)`; sort order uses
canonical decimal strings because ADR-079 bindings use strings. Choice values, nullable bool/date/age
and immunization arrays retain types; dates use canonical ISO calendar dates. Projections are frozen,
with immutable immunization tuples and an immutable UUID-to-child projection map.

| Family | Authenticated binding (envelope key → stored attribute) |
| --- | --- |
| StudentInventory | `inventory_id` → `pk` |
| InventoryFamilyMember | `inventory_id` → `inventory_id`, `family_member_id` → `pk`, `kind` → `kind` |
| InventorySibling | `inventory_id` → `inventory_id`, `sibling_id` → `pk`, `sort_order` → `sort_order` |
| InventoryEducationEntry | `inventory_id` → `inventory_id`, `education_entry_id` → `pk`, `level` → `level` |
| InventoryOrganizationMembership | `inventory_id` → `inventory_id`, `organization_membership_id` → `pk`, `scope` → `scope`, `sort_order` → `sort_order` |
| InventoryTransportationEntry | `inventory_id` → `inventory_id`, `transportation_entry_id` → `pk`, `mode` → `mode` |
| InventoryReopenEvent | `inventory_id` → `inventory_id`, `reopen_event_id` → `pk` |

Sibling/organization sort order is safe to bind because draft replacement deletes/recreates rows with
new UUIDs rather than mutating ordering in place. Never reorder/transfer an existing ciphertext row
without an explicit authorized rewrite. Other mutable workflow/report values are deliberately absent
from authenticated binding. Parent and semantic child discriminators remain bound.

`INVENTORY_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` is required in every environment. First key
writes; all ordered keys read. Generic `_FILE` resolves its host source
`inventory_confidential_content_encryption_keys`. Settings reject empty/noncanonical/duplicate keys
and decoded-byte reuse with Django SECRET_KEY, TOTP, Web Push storage, and **every** current/previous
entry in Routine Interview, Shared Summary, Referral and Exit Interview keyrings. No derivation,
fallback or per-child keyring. Runtime mechanics use unchanged ADR-079; migration mechanics are
frozen independently of evolving runtime code.

Each ciphertext column is non-null/non-empty. Even an empty new root form has a complete authenticated
payload. Private field limits match source CharField/EmailField limits (implicit email max 254), while
unbounded TextFields remain unbounded; reopen reasons retain 1000. Reject NUL, lone surrogates,
wrong bool/int/date/array/enum/string types, invalid email and unknown/missing fields. Preserve exact
Unicode/newlines/whitespace in stored logical content (existing normalization/trim semantics still
apply where the original domain requires them). Keep prior-false detail clearing rules, boarding
conditions, Other requirements, NOT_SPECIFIED/fixed-label normalization and submission completeness.

## Explicit reads, authorization and disclosure

Models have no plaintext properties, transparent encrypted fields, `save()` crypto, descriptors,
plaintext caches, blind indexes or deterministic encryption. Assign UUIDs before encryption/save or
bulk child creation. Service draft replacement verifies existing private tokens before changing any
row, splits public/private values explicitly, validates combined logical input and persists tokens.
Submission checks Program/Year Level before private reads and preserves idempotency.

Owner routes authenticate/capability-check and scope by Student ID before projection; unauthorized
history/PDF cannot decrypt. Active scoped Counselors require `inventory.view` **and currently
submitted_at != NULL** before raw detail/PDF. Never-submitted and reopened correction drafts are
denied before crypto. Organizational scope stays current for historical records. Counselor reopen
returns history metadata and writes an encrypted append-only reason after lifecycle/scope validation;
it does not read the reopened raw form. Reopen notifications remain reason-free.

API `_inventory` reads one explicit root/child projection after selection; `_correction` reads only the
latest pending reason. Owner status preserves its existing correction-message contract by decrypting
only that reason. Roster, pagination/filter/search and owner/Counselor history metadata never decrypt.
Counseling context consumes the same authorized Inventory mapper after its existing scope/state gates.
The pure PDF context builder requires an explicit projection and has no crypto. Submitted PDF entry
reads each root/child token once before rendering the unchanged fixed three-page F5 layout; saved
snapshots stay authoritative and existing fit/wrap/truncation rules remain. Privacy release auditing
occurs only after successful render and remains a release gate.

Unreadable authorized content returns generic HTTP 500 `inventory_confidential_content_unavailable`.
No blanks, partial detail, dropped children or silent corruption repair. Domain errors carry only
Inventory UUID, family/row UUID and bounded ADR-079 reason. API/errors/audit/notification/rotation
output never contain plaintext, ciphertext, keys or decrypt-library details. Existing structural
inventory.created/submitted/resubmitted/reopened audit actions remain unchanged.

Student Profiling service/API/PDF/XLSX aggregate only E0/E1; Student Support reads typed normalized
fields; Routine candidates/prerequisite and other Inventory prerequisites inspect submission metadata.
These operate with Inventory keys/decrypt unavailable. No dependent-domain crypto is redesigned.

## Two-phase migration and controlled reverse

`0006_encrypt_confidential_content` adds seven nullable transition token columns and backfills v1
with plaintext still authoritative. `_inventory_confidential_content_v1.py` owns frozen keyring,
JSON/payload limits/types, binding and combined logical consistency; it never imports runtime adapters.
It preserves legitimate legacy NULL normalized controls and their exact raw values, empty/partial
forms, submitted snapshots and reopened drafts; submission-only completeness is not imposed on drafts.

`0007_remove_plaintext_confidential_content` atomically fences **all seven tables** in deterministic
root → family → sibling → education → organization → transport → reopen order using PostgreSQL
SHARE ROW EXCLUSIVE locks **before any verification/update**. Validate latest plaintext; every present
token must authenticate exact original binding/schema/payload without evaluating stale payload against
new normalized controls. Equal tokens remain byte-identical; missing or valid stale tokens are
rewritten to latest logical content and verified. Late child replacement/creation and reasons are
included with their actual UUIDs; deletions remain deleted. A corrupt present token aborts all earlier
reconciliation and DDL atomically. Then remove exactly 82 private columns and enforce seven token
constraints. No timestamps, IDs, report dimensions, audit or notification changes.

Reverse requires stopped writers and complete readable keyring: temporarily restore nullable/default-
compatible plaintext columns, fence all seven tables, authenticate/decrypt/restore every exact value,
verify, then reinstate historical field definitions/constraints. Corrupt reverse aborts atomically
without blank/partial plaintext. Phase A drops tokens only after successful plaintext restoration.
Backups and restored plaintext remain sensitive; key escrow is independent of database/Droplet backups.
Table locks are a fence for concurrent writers, not compatibility for old code after column removal;
maintenance downtime and prevented old-process restart remain required operational gates.

## Rotation and runtime delivery

`rotate_inventory_confidential_content --dry-run --batch-size 100` verifies/counts seven families;
real rotation authenticates each exact payload/binding, row-locks 1–1000 row batches, rewraps only
previous-key tokens through ADR-079 MultiFernet.rotate and commits batches. Preserve exact authenticated
bytes and token timestamps, all business data/timestamps and side effects. Resumption skips current
rows. Both modes refuse any selected legacy plaintext column. List at most 20 structural failures,
leave failed rows untouched and exit nonzero. Never remove older keys while dependent backups remain.

Runtime inventory is 19. Web/worker/Beat receive the Inventory file; PostgreSQL only its existing
password, Redis only its existing password and proxy none. Parent mode remains 0700 and regular
read-only sources 0444. Test keys are synthetic/ephemeral only. No live key, deployment, migration or
host configuration is part of this repository change. See `docs/runtime-secrets.md` ADR-083 combined
Summary/Referral/Exit/Inventory runbook for actual-starting-state discovery, absent independent-key
provisioning, protected escrow/verified rollback, stopped writers, exact-SHA activation, all four
migration/rotation checks, privacy smoke tests and schema-compatible rollback. Live cutover requires
separate authorization; merge alone cannot establish live readiness.
