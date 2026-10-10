# ADR-086: Customer Feedback and CSM private prose/contact encryption

- Status: Accepted
- Date: 2026-10-07
- Scope: Selected private content in the existing two Feedback response aggregates

## Context and storage split

ADR-034 retains separate controlled F14 Customer Feedback and internal CSM aggregates, opportunity
admission, one-shot submissions, Head-only raw review and existing capability policies. Institutional
survey dimensions remain efficiently queryable without decrypting private content.

Customer Feedback retains UUID, controlled revision relation, submitted_at, services_received,
talked/accommodation codes, visit count, transaction duration, all twelve typed ratings and
course_year_snapshot. `respondent_name_snapshot` remains plaintext for historical Head name search.
Replace exactly `other_service`, `additional_feedback`, `future_service_improvement`,
`address_snapshot`, `mobile_number_snapshot` with required non-empty
`confidential_content_ciphertext = TextField(editable=False)`.

CSM retains UUID, instrument_schema_version=1, client type, sex, age 0–150, region, service_availed,
conditional CC1–CC3, SQD0–SQD8 including N/A=0, and submitted_at. Replace exactly `suggestions` and
optional `email` with a required non-empty confidential_content_ciphertext column. CSM has no User
foreign key and never copies account email. No encrypted ORM fields, model properties/descriptors,
implicit decryption/save hooks, plaintext caches/mirrors or searchable indexes are introduced.

## Two envelope families, one independent Feedback ring

Use required `FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`; the first key encrypts and all entries
decrypt. Reject decoded-byte reuse with SECRET_KEY, TOTP, Web Push storage and every current/previous
Routine, Summary, Referral, Exit, Inventory, Tracer and Account Profile key. No fallback/derivation.
Accounts owns its independent ring; neither aggregate refers to Account ciphertext.

Unchanged ADR-079 canonical bound JSON authenticates actual integer schema_version=1:

| Family | Exact authenticated binding | Exact payload |
| --- | --- | --- |
| F14 | customer_feedback_response_id, form_revision_id (str UUIDs) | five named F14 strings |
| CSM | client_satisfaction_response_id (str UUID), instrument_schema_version (canonical decimal string `"1"`) | suggestions and email strings |

The primitive accepts string bindings. CSM's ordinary schema column and envelope schema_version
remain actual integers; the binding uses their canonical decimal representation without modifying
ADR-079. Copying tokens across rows/revisions/instruments/families is rejected. Allocate final UUIDs
before encryption. Immutable domain projections enforce exact fields, text types, lengths, NUL and
UTF-8 validity. Historical values are restored without normalization. Limits remain Other 255,
private prose/suggestions **4000** (the existing effective service limit), address 2000, mobile 64,
email 320 with explicit optional validate_email. OTHER semantics and accommodation/CC rules remain
logical submission validation before encryption; stale migration tokens are authenticated separately
from latest coded choices before reconciliation.

## Submission, snapshots and authorized review

Existing Student ownership, capability, opportunity availability, revision and state checks precede
private operations. Under opportunity/Student locks, normalize logical request values, allocate row,
encrypt selected private values, insert and mark opportunity/audit atomically. Empty optional values
still have full valid envelopes. Respondent-name fallback uses canonical plaintext full name.
Only blank address/mobile invokes Accounts context; if both are supplied, profile decryption is
unnecessary. Blank fallback uses current address then permanent address, and current contact. An
unreadable required profile context fails closed with generic 500 feedback_confidential_content_unavailable
without row/marker changes. Saved F14 contacts are independently encrypted one-time historical
snapshots; later profile updates do not rewrite responses. No new audit answer/snapshot/token/email
content or notification/email/export/PDF pipeline is introduced.

Existing feedback.view_customer_feedback and feedback.view_csm checks precede selection/decryption.
Student, ordinary Counselor, GSS, Admin, Institutional Officer and DPO have no raw response access.
Head list/search/filter/pagination selects only queryable metadata without decryption. Detail decrypts
only the selected authorized row and retains the existing logical API shape. Revoked capabilities
remain decisive. Required unreadable detail returns generic 500 feedback_confidential_content_unavailable,
without blanks, partial output, false 404, repair or sensitive chaining. Domain error context is
only bounded family, response UUID and ADR-079 reason. Synthetic demo dedup/count filters by metadata
and compares explicit ephemeral projections; there is no plaintext SQL filter or new index.

## Independent historical migrations and recovery

Frozen `_feedback_confidential_content_v1.py` independently owns historical parsing, JSON, bindings,
validation and bounded errors, without evolving runtime adapter/primitive imports.
`0003_encrypt_confidential_content` adds two nullable columns and backfills all seven private values,
leaving plaintext authoritative. Atomic `0004_remove_plaintext_confidential_content` locks Customer
Feedback then CSM in deterministic order with PostgreSQL EXCLUSIVE locks **before** verification/DDL.
It validates latest plaintext, authenticates every present token, retains equal tokens and reconciles
only missing or valid stale ones, including late old inserts/edits, verifies again, removes seven
columns and enforces both required non-empty envelopes. Present corrupt/binding/schema/payload
failures abort the entire transaction, including previous rewrites. UUIDs, revision links, ratings,
dimensions and submitted_at remain unchanged; no audit/notification/email side effects.

Reverse executes writer fencing first, before restoring columns. Temporary nullable/default-compatible
columns allow exact verified restoration of both families, then original definitions including
CSM EmailField(max_length=320) are restored. Any unreadable row aborts all schema/data restoration
atomically. Phase A reverse removes tokens only after successful plaintext restoration. Complete
readable ordered rings and stopped writers are mandatory.

## Rotation, runtime and consequences

`rotate_feedback_confidential_content [--dry-run] [--batch-size 100]` verifies both families and
reports separate scanned/current/rotation/failure counts. Both modes refuse legacy plaintext columns.
Real 1–1000 row-locked transactional batches use ADR-079 MultiFernet.rotate, preserving original
plaintext bytes/token timestamps and every business field. Committed batches survive interruption;
reruns leave primary-key rows untouched. Only ciphertext changes. Failed rows remain unchanged,
at most 20 structural failure contexts are listed and the command exits nonzero.

With ADR-085 the final inventory is 22. The required filename/pointer are
`feedback_confidential_content_encryption_keys` and
`FEEDBACK_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/feedback_confidential_content_encryption_keys`.
Existing 0700 parent/regular 0444 compass-owned source semantics apply. Only web/worker/beat receive
it. Combined separately authorized deferred cutover, complete off-host ordered keyring escrow,
verified encrypted database/host rollback backup, drained old writers, exact-SHA activation,
seven-domain verification and controlled prior-graph reverse are in
[runtime-secrets.md](../runtime-secrets.md). No live action/key generation/deployment occurs here.

Trusted application/host access still handles authorized plaintext; this is not end-to-end encryption.
Fernet exposes approximate length. Key loss makes retained encrypted backups unrecoverable and old
plaintext backups remain sensitive. ADR-034 source/lifecycle/disclosure semantics remain authoritative.
No frontend/normal OpenAPI change, analysis endpoint, export/PDF, unrelated crypto redesign or excluded
administrative reason encryption is introduced.
