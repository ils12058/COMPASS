# ADR-049: Account Identity and Security Hardening

## Status

Accepted for implementation on the Account Identity & Security Hardening slice.

## Context

COMPASS has three identity concepts with different lifecycles and trust properties:

- the User UUID is the immutable internal database identity;
- the UCN Institutional ID is the institution-issued human identifier;
- email is the current authentication, contact, and recovery address.

Historically, Account Management treated email as an ordinary editable identity field and bulk account provisioning classified existing accounts by email alone. StudentInventory also stores the official F5 "Student No." without a canonical User-level institutional identifier.

These concerns need to be hardened without replacing UUID primary keys, changing the current email login identifier, introducing a generic identity provider, or redesigning the Notification domain.

## Decision

### Canonical Institutional ID

User.institutional_id is the canonical current UCN-issued identifier.

It is stored as text, remains nullable for legacy migration compatibility, trims surrounding whitespace, applies conservative uppercase canonical casing, and does not parse, strip, or infer structure from punctuation or numeric-looking values.

A PostgreSQL case-insensitive unique constraint on Lower(institutional_id) is the final race-safe guard when the value is populated. Multiple legacy null values remain valid.

Existing users are not backfilled from email, UUID, names, organization relationships, or historical Inventory data.

### Provisioning and correction

New accounts provisioned through Account Management single-create and CSV flows require an Institutional ID.

Account Management list/detail/create responses expose it, and search matches Institutional ID, email, and supported names.

Institutional ID is read-only in self-service Profile and can be corrected only through Account Management with the existing accounts.manage and recent-MFA gates. Audit metadata records only structural field names, never identifier values.

### CSV dual-identity semantics

CSV provisioning requires both institutional_id and email.

Dry-run and commit use the same classification semantics:

- both identifiers resolve to the same active account and canonical role/name identity matches: SKIP;
- either identifier resolves separately, only one resolves, or they resolve to different users: CONFLICT;
- neither resolves: CREATE.

The importer never merges identities and never silently replaces either identifier.

### Inventory Student Number snapshot

StudentInventory.student_number remains the historical annual F5 snapshot.

A newly created annual Inventory initializes that field from the current User.institutional_id when available. While the Inventory remains a draft, replacement/submission treats the canonical User ID as server-owned when populated. Submission snapshots the then-current canonical ID.

A submitted Inventory remains immutable, so later Institutional ID corrections do not rewrite historical Student Number values. Legacy users with null canonical IDs and legacy Inventories with existing Student Numbers remain readable without backfill.

### Verified email change

Email is security-sensitive because it is the current login identifier, contact address, and recovery address.

Generic Account Management identity PATCH no longer accepts email.

Email change uses a purpose-built EmailChangeRequest plus the existing hash-only EmailOTPChallenge infrastructure with a dedicated EMAIL_CHANGE purpose. The old User.email remains authoritative until the proposed new mailbox successfully proves possession.

Only one active pending email change may exist per account; a newer request deterministically cancels the previous pending request.

### Step-up and mailbox proofs

The proofs remain deliberately distinct:

- recent TOTP-backed MFA proves strong recent authentication;
- a SECURITY_CHALLENGE OTP to the current verified mailbox is the fallback authorization for self-service users who are not governed by TOTP;
- an EMAIL_CHANGE OTP proves possession of the proposed new mailbox.

An account with an active TOTP factor must have recent MFA for request and confirmation. A role whose policy requires MFA cannot substitute current-email OTP for required TOTP. A non-TOTP, non-MFA-required self-service user must prove control of the current verified mailbox before the new-mailbox challenge is staged.

Administrative initiation requires accounts.manage plus recent MFA, but it only stages the proposed address. It does not mark the mailbox verified or directly change User.email.

### Confirmation and authentication state

Confirmation locks the User, the active pending change, and its new-mailbox OTP challenge in one transaction. It re-checks current-email snapshot consistency, request expiry, OTP binding/consumption, and email uniqueness before committing.

After successful confirmation:

- User.email changes to the verified proposed address;
- email_verified_at is set to the confirmation time;
- the OTP and request are consumed/confirmed;
- AuthSessions, TrustedSessions, LoginChallenges, and obsolete email-security challenges are invalidated;
- the browser is expected to re-authenticate using the new email.

The current session is not preserved as an exception because the login identity itself changed.

### Previous-address security alert

The pending email-change record keeps current_email_snapshot. A dedicated retryable authentication security task sends the mandatory "sign-in email changed" alert to that explicit previous destination after commit.

The alert contains no OTP, secret, or new-address value. It does not require approval from the old mailbox. Durable request state records delivery attempts and completion without putting the old/new address into audit metadata.

### Sensitive, defensive, and ordinary actions

Existing recent-MFA protection remains in place for administrative account/security mutations, TOTP disable, and recovery-code regeneration.

Defensive actions such as logout and session/trusted-session revocation do not gain a new step-up requirement.

Ordinary profile edits remain ordinary profile edits and do not gain OTP/MFA requirements.

No account hard-delete endpoint is introduced; account lifecycle remains disable/enable based.

## Consequences

- UUID, Institutional ID, and email retain separate meanings and lifecycles.
- Newly provisioned identities are stronger and bulk import fails closed on ambiguous identity matches.
- Email can no longer be silently replaced by an administrator or committed before new-mailbox verification.
- Identity changes invalidate reusable authentication state and produce privacy-safe structural audit events.
- Historical controlled-form Student Numbers remain stable after submission.
- No generic workflow engine, generic identity provider, duplicate Notification table, or frontend work is added.

## Validation policy

During this development period, validation is limited to lightweight static/migration/OpenAPI gates and directly affected tests.

The canonical .github/workflows/backend-targeted.yml is not modified on the feature branch. A disposable temp/ci-account-identity-security-hardening branch may carry one workflow-only narrowing commit for manual GitHub Actions validation. That temporary commit is never merged back.

The full backend suite remains deferred until explicit authorization, release-candidate/defense readiness, or an exceptional shared-primitive risk that narrow validation cannot reasonably cover.
