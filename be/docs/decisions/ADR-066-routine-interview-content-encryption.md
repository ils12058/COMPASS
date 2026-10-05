# ADR-066: Routine Interview Content Encryption at Rest

- Status: Accepted
- Date: 2026-09-28
- Scope: Application-level authenticated encryption of Routine Interview Student Intake and
  Counselor Evaluation content, with a dedicated rotatable keyring

## Context

A Routine Interview (ADR-023) holds some of the most sensitive content in COMPASS: Student answers
about coping, family, stress, and goals, the source concern choices (including
`SUICIDAL_THOUGHT_TENDENCY`), and the Counselor's ratings, special concern, and recommendations.
The API already restricts that content to the Student author and the assigned Counselor, but it was
stored as ordinary PostgreSQL columns. Anyone who could read the database directly, a dump, a
backup copy, or a replica could read it without going through COMPASS authorization.

This decision adds a second, independent layer: the content is encrypted by the application before
it reaches PostgreSQL. It is defense in depth, not a replacement for authorization, and it does not
protect content from a compromised running application host that also holds the keys.

## Decision

The reusable Fernet/keyring and bound-JSON mechanics now live in the shared confidential-data
primitive ([ADR-079](ADR-079-shared-confidential-data-cryptographic-primitive.md)). Routine's
`crypto.py` remains its thin policy adapter; this ADR continues to govern the dedicated keyring,
exact v1 envelope, section schemas, authorization, and domain rotation. The extraction changes
neither ciphertext nor frozen migration semantics.

### Encrypted content and plaintext metadata

Each section is stored as one authenticated token:

- `student_intake_ciphertext` holds the complete Student Intake:
  `coping_with_college_challenges`, `coping_remarks`, `college_experience`,
  `reason_for_choosing_institution`, `difficulties_encountered`, `stress_anxiety_causes`,
  `stress_anxiety_management`, `family_description`, `concerns`, `other_concern_specification`,
  `concerns_explanation`, `college_adjustment_and_peer_group`, `academic_goals`, and
  `career_goals`. Concern choices are content, not metadata, and are encrypted with the answers.
- `counselor_evaluation_ciphertext` holds the complete Counselor Evaluation: the six 1–10
  adjustment ratings (academic, physical, social, spiritual, financial, emotional),
  `other_adjustment`, `special_concern`, and `recommendations`. Every rating is encrypted.

The operational metadata stays as ordinary, queryable columns: `id`, `student`, `counselor`,
`inventory`, `appointment`, `counseling_encounter`, `form_revision`, `entry_mode`,
`delivery_mode`, `created_by`, `intake_submitted_at`, `evaluation_finalized_at`,
`direct_creation_key_digest`, `direct_request_fingerprint`, `created_at`, and `updated_at`.
Authorization, relationships, the assigned queue and its filters (identity search, Academic Year,
delivery mode, Intake and Evaluation status), Counseling Context, encounter matching, Overview
counts, and audit references use only this metadata and never decrypt content.

There is no search, reporting, or analytics over encrypted content, and no deterministic or
searchable encryption. A future need to aggregate ratings or concerns requires a new decision.

### Format and record binding

Tokens are Fernet tokens (AES-128-CBC with a random IV per token, authenticated with
HMAC-SHA256) produced through `MultiFernet` from the `cryptography` library already used for TOTP
secrets. COMPASS implements no cryptographic primitive, nonce handling, MAC, or key derivation.

The encrypted plaintext is deterministic JSON (sorted keys, compact separators, UTF-8, no NaN)
of a versioned envelope:

```json
{"payload": {"...": "..."}, "routine_interview_id": "<uuid>", "schema_version": 1, "section": "student_intake"}
```

`section` is `student_intake` or `counselor_evaluation`. `schema_version` versions the payload
format so later form changes can be migrated deliberately; it says nothing about keys. Only the
known section fields are serialized, as strings, integers, `null`, and lists of strings.

Fernet authenticates the token but not where it is stored, so the envelope names its record and
section. A read verifies the token, then requires exactly the envelope keys, a supported
`schema_version`, the expected Routine Interview UUID and section, and finally the section schema:
the exact field set, text as text, distinct source concern values in their stored order, and
ratings that are `null` or integers from 1 to 10. A valid token copied onto another Routine
Interview, or from one section into the other, therefore fails instead of silently becoming that
record's content.

### Keyring

`ROUTINE_INTERVIEW_ENCRYPTION_KEYS` is an ordered, comma-separated list of Fernet keys. The first
key encrypts all new content; every listed key can decrypt. It can also be supplied as
`ROUTINE_INTERVIEW_ENCRYPTION_KEYS_FILE` through the existing environment helper (ADR-007).

Settings validate the keyring when any COMPASS process starts: web, worker, beat, and every
management command, including `check` and `migrate`. A missing keyring, an empty entry, anything
other than a canonical `Fernet.generate_key()` value, a repeated key, and reuse of `SECRET_KEY` or
`AUTH_TOTP_ENCRYPTION_KEY` are rejected. Errors name the setting and entry position, never a key.

The keyring is required in every environment, including local-staging, and there is no fallback or
derived key: PostgreSQL holds only ciphertext for this content, so running without a key is never
useful. Automated tests generate an ephemeral key per test process. Keys never enter PostgreSQL,
logs, API responses, the OpenAPI contract, or the frontend.

### Authorization before decryption

Content is decrypted only by the explicit accessors in `compass.routine_interviews.content`
(`read_intake`, `read_evaluation`), and only for a Routine Interview that a service has already
resolved through the Student's own relationship or the assigned Counselor relationship:

- Student paths decrypt only the Student's own Intake, never the Counselor Evaluation.
- The assigned Counselor's detail decrypts the Evaluation. It decrypts the Intake only after
  submission; a draft Intake returns `intake: null` without being decrypted.
- Other Counselors, a Head Guidance designation alone, GSS, IT Admin, and DPO are denied before any
  content is loaded or decrypted, exactly as before.

Nothing decrypts implicitly. There are no encrypted model fields or decrypting properties, so
queryset iteration, `repr()`, logging, and serialization see only ciphertext. The frontend keeps
sending and receiving the unchanged `RoutineIntakePayload` and `RoutineEvaluationPayload` over
HTTPS; the OpenAPI contract is unchanged and there is no client-side encryption.

### Validation and constraints

Services still validate before writing: supported concern values, the `OTHER` specification rule,
at least one meaningful Intake response on submission, 1–10 ratings, submission and finalization
locks, encounter matching, and current-Student restrictions. The API schema also still bounds the
ratings. Finalization first proves the stored Evaluation is readable and valid.

PostgreSQL can no longer see the ratings, so the six `routine_*_rating_range` check constraints are
removed; the API schema and the services enforce the range, and every read re-checks it. The
metadata constraints for entry mode/Appointment consistency and "finalized requires an encounter"
remain.

Both ciphertext columns are `NOT NULL` and must be non-empty. A new Routine Interview receives
encrypted empty sections when it is created, so an empty form is always an authentic encrypted
empty payload and a blank column cannot be confused with an empty form, a missing key, or a legacy
row. NUL characters, which PostgreSQL text rejected before, remain invalid input.

### Failure behavior

Decryption fails closed. A token that cannot be decrypted by any configured key, or that is
tampered with, misbound, malformed, or outside the schema, raises a domain error; COMPASS never
falls back to plaintext parsing and never returns ciphertext, a pretend-empty form, or partial
content. The API answers `500` with code `routine_interview_content_unavailable` and a generic
message, without revealing which key failed, the key order, the ciphertext, or the underlying
cryptography error. The log event `routine_interview_content_unavailable` carries only the Routine
Interview UUID, the section, and a reason category. A save never overwrites content it could not
read.

### Audit, logs, notifications, and caches

The audit policy is unchanged: `routine_interview.created`, `routine_interview.intake_submitted`,
and `routine_interview.evaluation_finalized` carry only safe identifiers and context, never answers,
concern choices, ratings, special concern, recommendations, payload JSON, ciphertext, or keys.
Migration and key rotation record no per-record audit events, because cryptographic maintenance is
not Student or Counselor activity. The Routine notification uses fixed text, direct-creation retry
state is a digest, and Routine responses are not cached in Redis or idempotency storage.

### Migration from plaintext

- `routine_interviews.0002` adds nullable ciphertext columns and, in one transaction, encrypts
  every existing row from its plaintext. Invalid legacy content, such as an unknown concern value,
  or a missing keyring aborts the migration before anything is committed. The error names only the
  Routine Interview UUID and section.
- `routine_interviews.0003`, in one transaction, first locks the table against writes and
  re-verifies every row by decrypting it and comparing it with the plaintext. Ciphertext that is
  missing or stale is re-encrypted from the still-authoritative plaintext and verified. This covers
  writes by the previous release while a deployment runs migrations. Only then does the migration
  drop the plaintext columns and rating constraints and require both ciphertext columns. Any
  failure rolls back before a plaintext column is dropped.
- Both migrations use frozen version-1 helpers instead of evolving application code, leave
  `updated_at` and the workflow timestamps unchanged, and never print content. They are reversible
  for a controlled rollback; reversing `0003` decrypts the content back into restored plaintext
  columns and needs the same keyring.

### Rotation and verification

`python manage.py rotate_routine_interview_encryption` verifies every token against the configured
keyring. It leaves tokens already encrypted under the primary key unchanged and re-encrypts older
ones with `MultiFernet.rotate`, which keeps the exact plaintext. It works in bounded, row-locked
batches (`--batch-size`, default 100) and updates only the ciphertext columns, so timestamps do not
change and no audit events are recorded. Finished batches stay committed, so the command is safe to
interrupt and repeat. `--dry-run` writes nothing and is the post-migration verification. Output is
counts only: records scanned, payloads verified and re-encrypted per section, payloads already
under the primary key, unreadable payloads, and remaining legacy plaintext columns. A token no
configured key can read is reported by Routine Interview UUID and section, left unchanged, and makes
the command exit non-zero. The command never prints plaintext, ciphertext, or keys. Configuration
changes never rotate anything by themselves.

## Operations

### First deployment containing 0002 and 0003

1. Generate a key outside the repository with
   `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.
   Store it in the deployment secret store, and escrow a copy away from the database host and its
   backups. Content encrypted under a lost key cannot be recovered, including from backups.
2. For current live-staging, follow ADR-078 and [the runtime-secret runbook](../runtime-secrets.md):
   store the exact ordered keyring in the protected host file and set
   `ROUTINE_INTERVIEW_ENCRYPTION_KEYS_FILE=/run/secrets/routine_interview_encryption_keys` in
   the deployment-owned `.env` (mode 600). Compose grants it to `web`, `worker`, and `beat`.
   Direct environment values remain supported for local staging. Changing delivery does not
   generate, rotate or reorder keys.
3. Take and verify a PostgreSQL backup. The deployment workflow does not take one. That backup
   still contains plaintext Routine content, so protect it and expire it under the retention
   policy.
4. Preview the plan. `showmigrations routine_interviews` should list only `0002` and `0003` as
   pending. Where practical, rehearse on a restored copy of the backup: run `migrate`, then
   `rotate_routine_interview_encryption --dry-run`.
5. Consider maintenance mode for the deployment. After `0003` commits, the previous release cannot
   serve Routine Interview requests until the new containers replace it.
6. Dispatch "Deploy staging backend". Its first step, `manage.py check`, fails without a valid
   keyring, so `migrate` never runs without one.
7. Verify with `rotate_routine_interview_encryption --dry-run`. Expect the Routine Interview row
   count as records scanned, `Unreadable payloads: 0`, and `Legacy plaintext columns: none`.

### Key rotation and retirement

1. Generate `K2` and configure the ordered keyring as `K2,K1`. Current live-staging replaces the
   protected `routine_interview_encryption_keys` host file atomically (ADR-078); local-staging
   may use `ROUTINE_INTERVIEW_ENCRYPTION_KEYS=K2,K1`. Recreate or redeploy `web`, `worker`, and
   `beat` so file bind mounts see the replacement. New writes use `K2`; content under `K1` stays
   readable.
2. Run `rotate_routine_interview_encryption --dry-run`, then the command itself. Repeat until it
   reports nothing left to re-encrypt and no unreadable payloads. Re-run it if any process was
   still writing under `K1`.
3. A successful live rotation does not mean `K1` can be destroyed. Database backups taken before
   the rotation still hold ciphertext under `K1`. Keep `K1` in secure storage, out of the live
   keyring if desired, until every such backup has expired or been re-protected. Only then destroy
   it.

## Threat model and limitations

This layer protects Routine content in database files, dumps, backups, and replicas. It also
protects it from anyone with database access but not the keyring. It does not protect content from
the running application or a compromised host that holds the keyring, or from an operator who has
both the database and the keys. COMPASS decrypts content server-side for authorized users, so this
is not end-to-end or client-side encryption.

Fernet does not hide the approximate length of each section, and the plaintext metadata still shows
who is involved, when, the entry and delivery modes, and workflow status. Backups taken before the
migration contain plaintext. Losing every copy of a key permanently loses the content encrypted
under it.

## Consequences

Routine content is no longer readable through direct database access alone, while the workflows,
API contract, frontend, queues, and privacy boundaries stay the same. Every environment needs one
more deployment-owned secret, with escrow and a retention-aware retirement procedure. Database-level
rating checks and any SQL-level search or reporting over content are given up deliberately. No
general key-management service, KMS, per-field encryption framework, background re-encryption, or
key table is introduced, and TOTP encryption keeps its own separate key.
