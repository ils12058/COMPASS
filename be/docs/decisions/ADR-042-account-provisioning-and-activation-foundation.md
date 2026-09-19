# ADR-042: Account Provisioning, Institutional Identity, and Email Activation

- Status: Accepted
- Date: 2026-09-19
- Scope: institutional officer identity, designation compatibility, CSV account provisioning, and email ownership verification

## Context

COMPASS models every account with exactly one required primary Role while institutional
Designations are separate many-to-many appointments.

Before this change, the canonical primary roles were IT Administrator, Counselor, Guidance
Services Staff, and Student. This created an identity problem for a university-level officer such
as a Data Protection Officer: assigning IT_ADMIN solely because the account required a primary role
would falsely imply platform-administration authority.

The account-management service already provided a serialized administrative mutation boundary,
recent-MFA enforcement, per-account audit, role-transition validation, and unusable-password account
creation. Password setup/recovery already used email OTP with hash-only persistence.

This ADR extends those existing seams rather than creating approval workflows, an import engine, or
a separate activation subsystem.

## Primary role and institutional designation

Add canonical primary role:

- `INSTITUTIONAL_OFFICER`

It represents an authenticated institutional account that does not naturally belong to the
operational IT Admin, Counselor, Guidance Services Staff, or Student roles.

The role has an empty baseline capability grant. Ordinary authenticated self-service profile,
password, and MFA behavior does not require broad operational capabilities.

In particular, INSTITUTIONAL_OFFICER does not imply:

- account administration
- organization administration
- Guidance scope
- counseling/referral/call-slip access
- report access
- Head Guidance authority
- platform administration

Designations remain separate institutional appointments. COMPASS records that an appointment
exists; it does not make the institutional appointment.

## Fail-closed designation compatibility

Designation/Role compatibility is code-owned:

| Designation | Allowed primary Role |
| --- | --- |
| `HEAD_GUIDANCE_COUNSELOR` | `COUNSELOR` |
| `DPO` | `INSTITUTIONAL_OFFICER` |

Every canonical Designation must have a compatibility definition and every referenced Role must be
canonical. Unknown combinations fail closed.

Normal Account Management services reject incompatible assignment and reject a Role change that
would invalidate an existing Designation. They never silently remove the Designation.

The existing Head Guidance routing fallback remains explicitly
`COUNSELOR + HEAD_GUIDANCE_COUNSELOR`. DPO and INSTITUTIONAL_OFFICER status do not create GCO
routing scope.

No database-editable compatibility table is introduced.

## High-trust designation recording authority

Add code-owned capability:

- `institutional_designations.manage`

The canonical IT_ADMIN Role receives this capability.

Designation assignment and removal require all of:

- active authenticated actor
- effective `accounts.manage`
- effective `institutional_designations.manage`
- recent MFA
- existing self-target protection
- compatibility validation where assigning
- synchronous audit

DPO receives no capabilities from the DPO Designation and specifically does not receive designation
management authority by virtue of being DPO.

Existing designation assignment/removal audit action codes remain authoritative.

## CSV account provisioning

Account Management gains one narrow multipart endpoint for CSV provisioning:

`POST /api/v1/accounts/imports/csv?dry_run=true|false`

This is not a generic ETL, import-job, approval, or background-processing subsystem. The uploaded CSV
is parsed in memory and is not persisted by COMPASS.

### Contract

Required columns:

- `email`
- `first_name`
- `last_name`
- `role`

Optional columns:

- `middle_name`
- `suffix`

The first slice deliberately rejects every other header. In particular, CSV cannot assign:

- password or temporary password
- Designation
- capability override
- MFA state
- email verification state
- arbitrary active/disabled state
- organizational affiliation
- counselor responsibility
- staff supervision
- confidential/profile data

High-trust DPO and Head Guidance appointments therefore cannot be assigned through CSV.

### Bounds and parsing

CSV uses Python's standard-library `csv` parser.

Accepted text encoding is UTF-8, including UTF-8 BOM. Input is bounded to:

- maximum 1 MiB
- maximum 1,000 nonblank account rows

COMPASS rejects unsupported encoding, NUL input, malformed rows, missing/duplicate/unknown headers,
blank or invalid required values, invalid email, noncanonical Role, and duplicate normalized email
within the same file.

No CSV row or raw file content is logged.

### Dry-run and commit

Both modes parse and validate the submitted file independently and require effective
`accounts.manage` plus recent MFA.

`dry_run=true`:

- performs no account writes
- emits no mutation audit
- returns a bounded CREATE / SKIP / CONFLICT / INVALID report

`dry_run=false`:

- reparses and revalidates the entire file
- serializes with the existing account-management mutex
- locks existing matching accounts while rechecking conflicts
- performs zero writes when any invalid/conflicting row exists
- creates all CREATE rows in one transaction

There is no persisted pending import batch.

### Existing-account semantics

Normalized email is authoritative.

- CREATE: no existing account
- SKIP: active existing account has the same Role and same normalized name identity
- CONFLICT: existing account is disabled, has a different Role, or has different normalized name identity

CSV never silently updates, renames, reactivates, disables, or changes the Role of an existing
account.

Re-importing an identical clean file is therefore idempotent and becomes SKIP-heavy.

Every created account uses the normal User manager:

- normalized canonical email
- requested canonical primary Role
- unusable password
- active account
- `email_verified_at = NULL`
- normal Student lifecycle initialization

Each actual account creation retains the normal `account.created` audit. A successful committed
batch also records one `account.csv_imported` summary containing only aggregate counts.

## Account enablement, email ownership, and password state

Three account states remain distinct:

- `is_active`: institution/platform enablement
- `email_verified_at`: proof that the holder demonstrated control of the currently registered email
- `has_usable_password()`: whether a COMPASS password is configured

No redundant persisted `email_verified` boolean is added. APIs derive that boolean from
`email_verified_at`.

Existing/legacy accounts are not backfilled as verified. Existing login behavior remains unchanged:
a legacy active account with a usable password may continue to authenticate even when
`email_verified_at` is null.

The bootstrap `create_it_admin` command also does not mark email verified because creating an
account does not prove mailbox ownership.

## Password access as activation proof

The existing anonymous password-access endpoints and response shape remain authoritative.

Request behavior is now:

- active account without a usable password -> `EMAIL_VERIFICATION` OTP
- active account with a usable password -> `RECOVERY` OTP
- unknown or disabled account -> enumeration-safe decoy behavior with no real delivery

Confirmation accepts only those two password-access purposes and revalidates state under the existing
user/challenge row locks.

For EMAIL_VERIFICATION, the account must still be active, the challenge must belong to the current
user/current canonical email, and the user must still have no usable password.

For RECOVERY, the account must still be active, the challenge must belong to the current user/current
canonical email, and the user must still have a usable password.

This prevents a stale initial-setup verification challenge from becoming a later password-reset
mechanism.

After password policy succeeds, one transaction:

1. sets/replaces the password
2. sets `email_verified_at` to the same transaction timestamp if it is null
3. consumes the OTP
4. revokes reusable authentication state through existing primitives
5. invalidates outstanding password-access OTPs for both verification and recovery purposes
6. records the existing initial-password or password-reset audit action

Password-policy failure does not consume a valid OTP. Confirmation does not automatically sign the
user in.

If an already-verified account completes recovery, its existing verification timestamp is preserved.

## Email changes and reverification

When Account Management changes the registered email, the same account mutation clears
`email_verified_at`.

Existing session, trusted-session, login-challenge, and email-security invalidation is preserved and
now includes outstanding EMAIL_VERIFICATION challenges in addition to recovery/security challenges.

The prior email's verification timestamp never survives an email change.

There is no administrator endpoint to mark an email verified. Verification represents demonstrated
mailbox control, not an administrator assertion.

## Account Management visibility

Safe administrative account summary/list output includes:

- active state
- password configured
- derived email verified state

Account detail additionally includes:

- `email_verified_at`
- existing MFA-enabled state

Account listing may filter by derived email verification state.

Credential material, password hashes, OTP state/codes, session tokens, and authentication secrets
remain excluded.

## Role-transition compatibility

Adding INSTITUTIONAL_OFFICER does not change the existing Organization, Availability, or Appointment
relationship blockers.

Moving an operational Counselor, Guidance Services Staff member, or Student to Institutional Officer
must first resolve any relationship state that the existing validators already protect. Provider
Availability and active/future Appointment blockers likewise remain authoritative.

No relationship row is automatically deleted and no GCO scope is inferred from
INSTITUTIONAL_OFFICER or DPO.

The generated OpenAPI contract remains committed source and exact-head CI must validate the
contract together with the implementation before merge.

## OTP boundary

Email OTP remains the dedicated security flow introduced before the durable Notification system.
Plaintext OTP remains transient and the database stores only its password hash.

Password-access OTP is not routed through Notification or EmailDelivery. ADR-041's security boundary
remains intact.

## Deferred work

This ADR deliberately does not add:

- DPO privacy-governance feature set
- COP modeling
- Student organizational-affiliation import
- SIS/HR synchronization
- invitation links
- administrator-selected temporary passwords
- custom onboarding workflow
- generic import framework
- automatic Designation assignment from CSV
- frontend work
- system-health/maintenance/dashboard work
- custom backup/restore

Future domain onboarding may build on this foundation only through explicit capabilities and
domain-specific invariants, not by turning this slice into a generic workflow engine.
