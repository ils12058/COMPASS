# ADR-030: Account Profile and Reusable Form Prefill Foundation

## Context

COMPASS repeatedly needs ordinary current person information for institutional forms, including name,
birth date, civil status, email, contact number, and address. Asking users to re-enter the same
current information for each future workflow creates unnecessary repetition.

The existing `accounts.User` model already owns the canonical current COMPASS account/person
identity:

- email
- name components and `get_full_name()`
- primary role
- designation relationships
- active state
- profile-photo object key and update timestamp

There is no existing PersonalProfile/current-profile aggregate with a distinct lifecycle that would
justify another one-to-one table.

At the same time, COMPASS already has historical and domain-specific records whose semantics must
remain independent:

- Organization owns institutional relationships/responsibility
- StudentAffiliation owns the Student's current organizational affiliation
- Individual Inventory is an annual Guidance-specific submitted record
- Referral and Call Slip preserve their own historical source snapshots
- future workflow forms will preserve their own submitted/finalized historical values

## Decision

### Extend User directly

Add exactly five reusable current personal/contact fields to the existing User aggregate:

- `date_of_birth` — nullable DateField
- `civil_status` — bounded CharField, blank string when unknown
- `contact_number` — bounded CharField, blank string when unknown
- `current_address` — TextField, blank string when unknown
- `permanent_address` — TextField, blank string when unknown

Use the existing `User.updated_at`; do not add a separate profile timestamp.

The Accounts migration is forward-only. Existing users receive NULL for date of birth and empty
strings for the four text fields.

Do not create a PersonalProfile model, role-specific profile subclasses, profile-row bootstrap,
signals, or a data migration from Individual Inventory.

### Keep the User aggregate small

Do not add Student/SIS or Guidance-specific information merely because other forms contain it.

In particular this foundation does not add course/program, major, year level, block, student number,
college, place of birth, nationality, religion, sex, family/guardian/emergency information, health
information, interests, allowance, transportation, or counseling history.

Age is derived from `date_of_birth` for the relevant future workflow reference date; age is not
stored on User.

### Current profile and historical records remain separate

User profile fields represent current reusable facts.

Individual Inventory remains an annual Guidance-specific historical/submitted record. Existing
Inventory values are not backfilled into User and User changes do not rewrite Inventory.

Referral and Call Slip source snapshots remain historical truth for those records. User profile
updates do not rewrite their snapshot fields.

Future workflow form creation may use current User profile data as initial prefill. Once a workflow
record is submitted/finalized, that workflow owns its own historical values.

If a future submitted record is reopened for correction, it must edit its existing form-local
historical data. It must not silently refresh snapshot values from the current User profile.

There is no hidden two-way synchronization between User and Inventory or future workflow forms.

### Self-service API

Expose:

- `GET /api/v1/me/profile` — `profileGetMyProfile`
- `PATCH /api/v1/me/profile` — `profileUpdateMyProfile`

These routes are authenticated owner-only self-service operations.

The response exposes:

- user_id
- email
- first_name
- middle_name
- last_name
- suffix
- full_name
- role
- date_of_birth
- civil_status
- contact_number
- current_address
- permanent_address
- safe signed profile-photo URL when available
- profile-photo update timestamp

The response does not expose the private profile-photo object key.

No generic account/profile lookup or personal-data directory is added.

### Editable fields

PATCH accepts only:

- date_of_birth
- civil_status
- contact_number
- current_address
- permanent_address

Email, name, role, designations, active state, and profile-photo object key remain outside this
endpoint.

The schema is strict and forbids extra fields. It supports true partial updates using
`exclude_unset=True`.

Date of birth may be explicitly cleared to NULL. The four string fields use empty string as the
single persisted empty representation; explicit JSON null is not part of their API contract.

### Validation

Date of birth must not be later than institution-local today. No arbitrary minimum or maximum age is
introduced.

Civil status and contact number are trimmed and bounded but deliberately have no invented enum or
Philippines-only formatting rule.

Addresses are trimmed only at their outer edges, preserve meaningful internal whitespace/newlines,
and are service-bounded to 2000 characters. No external address/contact validation service is used.

### Authorization and authentication effects

No new profile capabilities are added. Current policy counts remain unchanged.

All active authenticated primary roles can access only their own profile:

- Student
- Counselor
- Guidance Services Staff
- IT Admin

Designations, including Head Guidance Counselor and DPO, do not create broader profile browsing
rights.

Ordinary profile edits do not require recent MFA. They do not revoke sessions, rotate credentials,
reset MFA, consume recovery/login challenges, or alter trusted-session state.

Email and name remain governed by existing account-management/security behavior.

### Existing profile photo remains authoritative

The existing User fields and `accounts.profile_photos` implementation remain unchanged.

The self-profile response resolves the existing private profile-photo reference through the current
short-lived signed-URL mechanism. It never exposes `profile_photo_object_key`.

No photo storage migration or second photo implementation is introduced.

### Accounts-owned reusable prefill context

Add `get_person_profile_context(user)`, returning the immutable
`PersonProfileContext` value object with current Accounts-owned data:

- user_id
- full_name
- email
- date_of_birth
- civil_status
- contact_number
- current_address
- permanent_address

The resolver operates only on the supplied User instance. It does not import or query Inventory,
Organization, StudentAffiliation, Referral, Call Slip, Exit Interview, Good Moral, or other domains.

A future consuming domain composes this Accounts context with its own authorized current
domain-specific context.

For example, future Exit Interview creation may combine current User name/email/date of birth/civil
status/contact/address with Student academic context, use those values only as the initial form
prefill, allow form-local review/editing, and snapshot submitted values into Exit Interview itself.

Exit Interview is not implemented by this foundation.

### Profile mutation service and concurrency

`update_my_profile` owns validation and mutation logic.

The operation uses one small database transaction, locks the authenticated User row, computes actual
changed fields, performs one User save for changed fields plus `updated_at`, and records Audit in
the same transaction.

No-op updates return successfully without writing an Audit event.

No Redis replay, persistent Idempotency-Key, ETag/version counter, optimistic-locking framework,
outbox, or job queue is introduced.

### Audit and activity

Add `profile.updated` targeting `accounts.user`.

Audit metadata contains only the sorted changed field names. It never contains birth date, civil
status, phone number, addresses, raw PATCH payload, or before/after values.

A successful profile change may appear in My Activity using generic copy only:

“Your profile information was updated.”

`profile.updated` is deliberately excluded from Security Activity because ordinary personal/contact
profile edits are not security-state changes.

### Privacy boundaries

Existing administrative account list/detail serializers remain allowlisted and do not gain the five
new profile fields.

Existing Organization person summaries remain minimal and do not gain the five profile fields.

`accounts.manage`, Counselor/GSS responsibilities, Head Guidance designation, IT Admin role, and
DPO designation do not create a generic personal-profile browsing right.

Future domain services may consume only the current data genuinely required after their own
domain-specific authorization.

### OpenAPI

Add the `profile` API tag:

“Authenticated current account personal/contact profile.”

Stable operation IDs are:

- `profileGetMyProfile`
- `profileUpdateMyProfile`

No policy capability enum changes are required.

### Validation scope

Targeted CI preserves every existing backend regression suite and adds:

- `tests/test_profiles.py`
- `tests/test_profile_photos.py`

Focused coverage verifies:

- direct User fields/defaults and absence of PersonalProfile
- no policy-count changes
- self GET/PATCH across all primary roles
- DPO remains self-only
- strict read-only identity/security/photo fields
- true partial updates and explicit nullable DOB
- conservative validation and bounded multiline addresses
- no recent MFA/session invalidation
- privacy-safe Audit metadata
- My Activity vs Security Activity separation
- Accounts-only zero-query prefill context
- existing signed photo projection with private object key withheld
- account-management and Organization serializer privacy
- Inventory/Referral/Call Slip historical records remain unchanged

The existing Inventory, Referral, Call Slip, Account Management, Organization, OpenAPI, and other
targeted suites remain in the authoritative GitHub Actions matrix.

The full backend suite remains unnecessary by default.

## Consequences

COMPASS gains one small reusable source for current personal/contact prefill without becoming a
Student Information System or generic form engine.

Users can maintain ordinary current profile information themselves. Future form domains can reuse it
as initial prefill while continuing to own their submitted historical truth.

No duplicate profile lifecycle, generic personal-data directory, hidden synchronization, or
historical rewrite is introduced.
