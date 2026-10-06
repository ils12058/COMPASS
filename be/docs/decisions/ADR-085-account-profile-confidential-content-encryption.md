# ADR-085: Accounts current-profile confidential content encryption

- Status: Accepted
- Date: 2026-10-07
- Scope: Five reusable current profile values on the User aggregate

## Context and storage decision

ADR-030 owns the reusable current profile and canonical identity. Identity, authentication,
capability evaluation, account administration, organizational projections and name/email search
must remain available without confidential profile decryption. Saved Inventory, Exit Interview,
Graduate Tracer and Feedback snapshots have independent ownership and lifetimes.

Replace exactly `date_of_birth`, `civil_status`, `contact_number`, `current_address` and
`permanent_address` with `profile_confidential_content_ciphertext = TextField(editable=False)`.
The final column is non-null and database-constrained non-empty, including empty logical profiles
and every role. UUID, email, institutional ID, names, role, lifecycle, activation, password,
last login, verification, photo references/timestamps, business timestamps and capability/designation
relations remain ordinary columns. No descriptor, model property, encrypted ORM field, implicit
save/decrypt hook, plaintext cache, mirror, blind index or new profile aggregate is introduced.

## Envelope, keyring and explicit access

The unchanged ADR-079 primitive authenticates integer `schema_version: 1`, `user_id: str(UUID)`
and an exact five-key `payload`. DOB is canonical ISO calendar date or null; the other values are
strings. The dedicated immutable projection and explicit reader/writer validate exact field sets,
canonical dates, text lengths, NUL exclusion and UTF-8 representation. Historical decryption does
not trim values. Runtime PATCH trims outside text and preserves internal whitespace/newlines;
limits remain civil status 80, contact 64 and addresses 2000. Runtime DOB accepts null or a valid
non-future calendar date, with no arbitrary minimum-age rule.

`ACCOUNT_PROFILE_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` is required in every environment. First key
encrypts; all entries decrypt. Settings reject decoded-byte reuse against SECRET_KEY, TOTP,
Web Push storage and every current/previous Routine, Summary, Referral, Exit, Inventory and Tracer
entry. There is no fallback or derivation. Feedback uses another independently checked ring.

Canonical `UserManager.create_user` assigns UUID then explicitly writes the complete default
projection before its first insert. Provisioning, bootstrap admin, CSV import and demo creation use
that path. Unsaved password-validation candidates remain ordinary transient objects. Direct/bulk
fixture inserts explicitly initialize an envelope. Models do not silently repair missing content.

Active authenticated self-profile GET explicitly decrypts once. PATCH validates supplied fields,
locks the User, verifies current content, merges a true partial logical patch and compares values.
An equal patch preserves token, updated_at and Audit count. A changed patch encrypts the whole
projection once, saves ciphertext/updated_at and records only sorted changed field names.
Required unreadable GET/PATCH returns generic 500 `profile_confidential_content_unavailable`,
without blanks, regeneration, false 404, partial response or sensitive exception chaining.
The domain error contains only User UUID and a bounded ADR-079 reason.

`get_person_profile_context(loaded_user)` returns the same immutable identity/profile shape with
zero queries and no other aggregate lookup. Existing form prefill consumers use that projection.
Exit/Tracer required unreadable current context fails closed through their existing safe error
surface. Inventory form values and historical snapshots remain independently encrypted. F14
consults context only for blank address/mobile fallback; supplied contacts need no profile read.
Saved form content never references the Accounts token or changes when the current profile changes.
Authentication/password/session/email/institutional lookup, capabilities, account lists/details,
organization projections and photo PUT/DELETE never decrypt the five profile values.

## Migration and recovery

Frozen `_account_profile_confidential_content_v1.py` owns independent historical key parsing,
canonical JSON, binding/payload validation and safe errors. It imports neither the evolving domain
adapter nor ADR-079 runtime mechanics. `0007_encrypt_confidential_content` adds a nullable column
and backfills all historical values while plaintext remains authoritative; no business timestamp,
identity, security or side effect changes.

Atomic `0008_remove_plaintext_confidential_content` obtains a PostgreSQL EXCLUSIVE accounts_user
lock before any verification or destructive DDL. This also fences row-locking/security/provisioning
writers. Validate latest plaintext, authenticate each present token independently, retain equal
ones, reconcile only missing or valid stale tokens, verify replacements, then remove five plaintext
columns and require non-null/non-empty ciphertext. Late old inserts/updates are reconciled.
A corrupt, rebound, unsupported or malformed present token aborts the complete transaction,
including previous rewrites; plaintext is never used to repair an unverifiable token.

Controlled reverse acquires the same fence first, before any restored-column DDL. It temporarily
restores nullable/default-compatible columns, authenticates every token, restores exact date/text
values and verifies them, then restores original historical definitions. Unreadable content rolls
back DDL/data atomically. Reverse Phase A drops envelopes only after plaintext restoration.
Complete ordered keyrings and coordinated downtime are required.

## Rotation and deferred live cutover

`rotate_account_profile_confidential_content [--dry-run] [--batch-size 100]` verifies full binding,
schema and payload, counts current/old-key/failure rows and refuses any remaining legacy profile
column. Real batches accept 1–1000, lock rows, use ADR-079 MultiFernet.rotate, preserve plaintext bytes
and Fernet timestamps, commit individually and resume safely. Current rows are no-ops; only the
ciphertext column changes. User.updated_at, security/photo state, sessions and Audit remain unchanged.
At most 20 safe UUID/reason failures are printed, failed rows remain untouched and exit is nonzero.
No automatic key retirement, scheduled rotation or live key generation is introduced.

The repository target is 22 sources with ADR-086. Required filename is
`account_profile_confidential_content_encryption_keys`, with exact `_FILE` pointer from the runtime
example. Existing 0700 parent and regular/non-symlink 0444 compass-owned source semantics apply.
Only web/worker/beat receive the source; dependencies do not. See
[runtime-secrets.md](../runtime-secrets.md) for combined separately authorized cutover, complete
ordered off-host escrow, tested encrypted database/host rollback backup, stopped/drained old
writers, exact-SHA activation and prior-graph reverse. This implementation performs no live action.

## Consequences

New database rows/backups no longer store the five profile values in ordinary columns. Trusted
application/host access still sees authorized plaintext and Fernet exposes approximate length.
Key loss makes retained ciphertext/backups unrecoverable. Historical plaintext backups and controlled
restored plaintext remain sensitive. ADR-030 semantics, canonical queryable identity and public
contracts remain authoritative; no frontend redesign or other confidentiality boundary changes.
