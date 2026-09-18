# ADR-027: Referral Foundation

## Context

The Guidance and Counseling Office uses the historical controlled one-page Referral Slip
`CNSC-OP-GTA-01F9`, Revision 1. Its source fields distinguish the referring person's information
from the Guidance/Coordinator portion and provide exactly three Action Taken rows. Referral intake is
institutional office truth, but it is not proof that Counseling occurred and is not an Appointment,
Routine Interview, Call Slip, Case Record, or generic workflow instance.

The controlled code remains historical QMS identity. The institution's later branding change does not
authorize COMPASS to rename `CNSC-OP-GTA-01F9` or replace `GTA` with `GCO`.

A follow-up client clarification establishes that the second Date/Time pair on the source Referral
Slip represents when Guidance/GCO actually received the Referral.

## Decision

### Referral is a distinct source record

`Referral` is a dedicated `compass.referrals` domain record. It references a real active COMPASS
Student but snapshots the Student display name and the paper `Course/Yr & Blk` value so historical
rendering does not depend on mutable current identity/context. `referrer_name` is the source
"Signature over Printed Name" identity and remains distinct from the authenticated `recorded_by`
account that encoded the record.

No faculty role, Program/Year/Block SIS domain, counselor-assignment field, diagnosis, severity,
risk category, generic workflow engine, print generator, delete policy, or correction/version engine
is introduced by this foundation.

### Source chronology

Referral chronology has three intentionally separate meanings:

1. `referred_on` is the source Date signed/made by the referring person.
2. `received_at` is the timezone-aware operational timestamp when Guidance/GCO actually received
   the Referral.
3. `created_at` is when COMPASS persisted/encoded the digital Referral record.

The source can therefore be back-entered after receipt. `received_at` is optional because current
repository workflow does not prove that every encoded Referral is received at the same instant. If it
is omitted, COMPASS stores `NULL`; it does not silently copy `created_at`. When supplied,
`received_at` must be timezone-aware, cannot be future-dated, and its institution-local date cannot
precede `referred_on`.

Action Taken timestamps are stored as one timezone-aware `occurred_at`, combining the paper's
separate Date and Time columns into one digital occurrence. An action cannot precede known receipt;
when receipt is unknown it cannot precede the source Referral date.

### Controlled form revision

The Institutional Form Registry contains family `referral_slip` with supported internal schema
version 1. Migration `institutional_forms/0004_referral_slip_family.py` bootstraps the exact active
QMS revision:

- official code: `CNSC-OP-GTA-01F9`
- official revision: `1`
- internal schema version: `1`

Creation requires the current active *supported* Referral Slip revision and snapshots it through a
`PROTECT` foreign key. A future active QMS revision affects new Referrals only.

### Human reference

Referral has a UUID API/database identity and an immutable human-facing reference
`REF-YYYY-NNNNNN`. `YYYY` is the calendar year of COMPASS creation/issuance in the configured
institutional timezone, not Academic Year, `referred_on`, or `received_at`. The six-digit sequence
starts at 000001 and uses an independent `ReferralReferenceCounter` with transaction locking and a
maximum of 999999. Appointment and Referral counters never share sequence state.

The historical paper label "Student Reference No." maps to `Referral.reference_code`; it is not a
Student account number and possession of it grants no authorization.

### Persistent creation idempotency

Create requires `Idempotency-Key`. COMPASS stores only an actor-scoped SHA-256 digest plus request
fingerprint on the Referral; the raw key and response body are not persisted or placed into Redis.
`received_at` participates naturally in the request fingerprint. Same actor/key and same request
returns the same Referral and REF code; the same key with a different request conflicts.

Creation locks the authenticated actor row before idempotency lookup and reference allocation. This
small serialization rule prevents concurrent retries by the same actor from allocating multiple
references without creating a generic idempotency subsystem.

### Scoped Guidance authorization

Capabilities are `referrals.view` and `referrals.manage`, granted to Counselor and Guidance
Services Staff roles only. Capability is necessary but not sufficient.

Referral defines a resource-scope rule using current Organization relationships:

- Head Guidance Counselor: institution-wide Referral scope.
- ordinary Counselor: Students currently affiliated with colleges assigned to that Counselor.
- Guidance Services Staff: scope inherited from the currently supervising Counselor.
- Student, IT Admin, and DPO: no Referral-content capability by default.

The domain deliberately does not reuse `effective_responsibility_colleges()` as an authorization
decision because that Organization helper documents itself as routing/default responsibility only.
Referral evaluates the same authoritative Organization relationships in its own access rule.

No `assigned_counselor` field is added to the source Referral.

### Source actions and status

The source has exactly three Action Taken rows, modeled by `ReferralAction`:

- `CALL_PARENT_GUARDIAN`
- `SEND_PARENT_NOTIFICATION_LETTER`
- `SEND_CALL_SLIP_INTERVIEW_PERMIT`

Each Referral may contain at most one row of each action type. Recording an action records only that
the source action happened; it does not place a call, send SMS/email, generate a parent letter,
create a Call Slip, create an Appointment, or create a Counseling Encounter.

The source `STATUS:` line remains free text as `status_note`. COMPASS does not invent OPEN,
PENDING, RESOLVED, CLOSED, or any other lifecycle enum. The narrow status mutation cannot alter
Referral source identity or chronology.

### Downstream independence

Creating a Referral does not require Individual Inventory, Academic Year, Routine Interview,
Appointment, or Counseling Encounter. It creates none of those records and creates no Call Slip or
Case Record.

Existing `CounselingEntryMode.REFERRED` remains independently recordable and does not require a
Referral FK in this foundation. Downstream Referral/Call Slip/Appointment/Counseling linkage is
deferred until those routing semantics are explicitly established.

### Audit and privacy

Successful create, status, and action mutations synchronously append `referral.created`,
`referral.status_updated`, and `referral.action_recorded` inside the same database transaction as
their business mutation. Audit metadata is restricted to safe operational identifiers such as the
REF code, controlled-form identity, and action type. It never includes the Referral reason,
referrer name, Student name snapshot, Course/Yr & Blk snapshot, action remarks, status text, or full
request payload.

Referral content is not projected into My Activity or Security Activity.

### API and deployment

The v1 API exposes operational Guidance-only create, list, detail, status-note mutation, and
source-action recording under `/api/v1/referrals`. There is no Student self-service Referral API.

Identity policy changes remain code-controlled and deployments must run:

`python manage.py sync_identity_policy`

The targeted GitHub Actions matrix remains read-only and retains all existing regression tests while
adding the focused Referral suite. The full backend suite is not required by default.

## Consequences

COMPASS can encode paper Referrals faithfully, including delayed encoding after actual GCO receipt,
without inventing downstream business truth. Historical source identity and QMS metadata remain
stable, access stays constrained by current operational scope, and human reference allocation is
auditable and concurrency-safe.

Call Slip issuance, parent-letter generation, printing, Referral-to-Counseling linkage, retention,
deletion, corrections, and any future operational Referral state machine remain separate work.
