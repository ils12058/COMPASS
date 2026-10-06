# ADR-081: Referral confidential source-content encryption

- Status: Accepted
- Date: 2026-10-06
- Scope: Existing Referral confidential source fields and action remarks only

## Context

ADR-027 established paper-faithful Referral source records and three independently recorded
source actions. Repository audit shows reason, referrer name, status note, void reason and action
remarks are used only for authorized disclosures or source-content mutations/comparisons. They
are not population selectors, search terms, joins, aggregates, reporting dimensions or indexes.
PDF generation is an authorized disclosure, not a requirement for persistent plaintext.

Referral UUID/reference, Student/link/snapshots, referred/received dates, form revision, void
provenance, recorder, creation idempotency digests/fingerprints and timestamps remain plaintext.
Action UUID, parent, immutable action type, occurrence, recorder and creation timestamp remain
plaintext too. These support scope, search/filter/pagination, chronology, form fidelity, uniqueness,
Call Slip dependencies, history and idempotency. No encrypted metadata or new content search.

## Decision

Replace Referral `reason`, `referrer_name`, `status_note`, `void_reason` with non-null/non-empty
`confidential_content_ciphertext = TextField(editable=False)`. Replace each ReferralAction's
`remarks` with non-null/non-empty `remarks_ciphertext = TextField(editable=False)`, including empty
remarks. No ordinary plaintext copies remain in the final schema.

Use one independently managed ordered `REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` for the
Referral operational confidentiality boundary, with two distinct authenticated v1 envelopes:

```json
{"schema_version":1,"referral_id":"<Referral UUID>","payload":{"reason":"...","referrer_name":"...","status_note":"...","void_reason":"..."}}
```

```json
{"schema_version":1,"referral_id":"<Referral UUID>","referral_action_id":"<Action UUID>","action_type":"<immutable existing type>","payload":{"remarks":"..."}}
```

Actual integer version 1 and exact envelope/payload keys are required. UUIDs use `str(UUID)`.
Bindings are authenticated inside Fernet plaintext, not external AAD. Parent/action/type
transplants fail; action occurrence timestamps are not bound. Each action remains independently
writable/rotatable; actions are never nested into the Referral payload.

The narrow `compass.referrals.confidential_content` adapter owns the frozen value object, limits,
validation, bindings, explicit readers/writers, safe domain failure and rotation wrappers. Shared
mechanics delegate to unchanged ADR-079. No model properties/descriptors/save hooks, encrypted
ORM fields, implicit decryption, global keys or key registry. Final UUIDs exist before encryption.

Preserve runtime trimming: required reason/referrer and void input are stripped, optional status
and remarks stripped. Limits stay 10,000/255/1,000/1,000/4,000 respectively. Explicitly reject NUL
and non-UTF-8-representable strings. Verified historical/decrypted values are not normalized.
An active Referral requires exactly empty decrypted void reason; a voided Referral requires a
non-whitespace reason. This service/domain invariant replaces only the old plaintext DB check;
no redundant Boolean flag is introduced.

### Disclosure and lifecycle

Authorization/capabilities and current organizational scope precede resource selection/decryption.
List search/date/Student/form/void filtering and pagination run on existing metadata, then only
selected page rows decrypt to preserve `status_note`. Lookahead/outside-page rows do not decrypt.
Detail decrypts the Referral payload once and each selected action once. PDF likewise constructs
an ephemeral projection after authorized selection, then renders the unchanged historical form.
All public request/response shapes stay compatible; ciphertext/envelopes/keys never enter schemas.

Creation writes only ciphertext; exact idempotent retries return existing tokens and keep existing
fingerprints independent of randomized ciphertext. Status updates lock, read/compare plaintext,
return unchanged without rewrite on no-op, otherwise replace the full payload. Void checks linked
active/completed Call Slips first, then verifies content, updates provenance and encrypts the full
replacement in the same transaction. Actions allocate UUID before encrypting remarks and retain
metadata-only uniqueness `(referral, action_type)`.

Existing Call Slip reconciliation in Referral services explicitly decrypts existing remarks when
supplied occurrence/remarks must be compared; tokens are never compared for semantic equality.
No-input existing-action reuse remains metadata-only. Call Slip only receives the minimal error
propagation needed to return a generic 500 for unreadable source remarks instead of a 409 conflict.
Other Call Slip state/content remains unchanged. Counseling Context history needs no Referral
content decryption. Reports/analytics, population selection, notifications and Audit remain
content-free; release Audit retains only safe form/document identity.

`ReferralConfidentialContentUnavailable` contains Referral UUID, optional action UUID and bounded
existing action type, plus one ADR-079 failure reason. Authorized unreadable payloads fail closed
with generic `referral_confidential_content_unavailable` (500). A selected list row failure fails
the request; no blank fallback, partial detail, omitted actions, silent skipping, corruption repair
or false not-found. Errors never disclose text, token fragments, envelope or key material.

### Migration and rotation

Frozen `_referral_confidential_content_v1.py` preserves independent migration-time parsing,
canonical JSON, bindings/validation and safe failures, without evolving runtime imports.
`0003_encrypt_confidential_content` adds nullable ciphertext/backfills both tables, leaving
plaintext authoritative. `0004_remove_plaintext_confidential_content` atomically locks Referral
then ReferralAction in deterministic parent-before-action order with PostgreSQL SHARE ROW
EXCLUSIVE locks. It verifies latest plaintext and lifecycle, authenticates present tokens,
reconciles only missing or readable stale content (including old-release voids and late action
inserts), verifies replacements, removes five plaintext columns and enforces ciphertext presence.
Present malformed/tampered/rebound/unsupported tokens abort before destruction and roll back
earlier rewrites. Neither phase changes business metadata/timestamps or emits side effects.

Controlled reverse first re-adds plaintext columns temporarily nullable, restores all verified
payloads and checks exact restoration, then reinstates historical nullability/defaults and the
void-shape constraint. Unreadable ciphertext aborts schema/data changes atomically. Phase A reverse
may then remove ciphertext. The full readable ordered keyring is required for recovery.

`rotate_referral_confidential_content` verifies both envelope types with separate counts, supports
`--dry-run` and 1–1000 row batches, holds row locks for real rotation and updates ciphertext only.
ADR-079 primary-key detection/MultiFernet.rotate preserve plaintext bytes and Fernet timestamps.
Committed batches survive interruption; rerun handles remaining previous-key tokens and repeated
rotation is a no-op. Unreadable tokens stay unchanged, safe failures list at most 20 contexts and
cause non-success. Both dry and real modes refuse any legacy plaintext column. No auto rotation.

### Runtime and deferred deployment

The domain keyring is required/non-empty, with no fallback/derivation. Settings reject decoded-byte
reuse against Django, TOTP, Web Push storage and every Routine or Shared Summary keyring entry.
ADR-078 inventory becomes 17 with `referral_confidential_content_encryption_keys` and exact pointer
`REFERRAL_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/referral_confidential_content_encryption_keys`.
Web/worker/Beat receive it because settings load eagerly; PostgreSQL/Redis/proxy do not. Existing
0700 parent/0444 source-file ownership/mode semantics remain unchanged. Exporter cannot generate
or export an absent new key. Only synthetic test keys are used in this repository slice.

Live cutovers are explicitly deferred. A merge does not prove ADR-080 has deployed; eventual
cutover must inspect actual live starting state and independently provision/escrow both absent
Shared Summary and Referral keyrings, verify backups/preflight, stop/drain all old writers through
migration/activation, deploy exact staging SHA and verify historical content/schema/services.
Normal workflow migration-before-service-replacement is a compatibility boundary: table locks
cannot make old code work after column removal. Rollback also needs coordinated downtime and a
compatible previous image/manifest/env plus verified reverse migrations. The full ordered keyrings
need independently protected off-host recovery; a database backup alone cannot restore content.
See [runtime-secrets.md](../runtime-secrets.md). No live provisioning/deployment occurs here.

## Consequences

Authorized API/PDF behavior stays faithful while database rows/new backups contain ciphertext.
Application/host remains trusted and capable of decryption; this is not end-to-end encryption and
Fernet exposes approximate content length. Key loss makes encrypted data unrecoverable; old keys
must remain while retained backups need them. Historical plaintext backups remain sensitive.

No frontend, ordinary OpenAPI, other domain encryption, content reports/search/indexes, private
notes, Vault/KMS, external integration, key scheduling or live cutover is introduced. ADR-027
continues to govern functional/source semantics; only its storage representation is superseded.
