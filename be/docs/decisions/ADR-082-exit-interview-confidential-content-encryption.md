# ADR-082: Exit Interview confidential narrative and contact-content encryption

- Status: Accepted
- Date: 2026-10-06
- Scope: Existing Exit Interview direct-contact/narrative content, opportunity notes and reopen reasons

## Context

ADR-031 and ADR-075 establish a structured institutional survey, Student ownership, controlled
corrections and opportunity-based admission. Encrypting the whole response would prevent efficient
future institutional aggregation. Current search, selectors, authorization and Good Moral use
metadata, fixed survey dimensions and ratings; free text is needed only for explicit authorized
reads, edits, operational comparisons and form rendering.

The storage boundary is E0 operational metadata, E1 structured survey/report dimensions, and E2
confidential direct-contact/narrative text. Only E2 changes representation.

## Decision

Keep E0 plaintext: response UUID, Student/Academic Year/Inventory/nullable opportunity references,
status, first/last submission and creation/update timestamps; opportunity UUID, Student/year,
immutable source, status, opener/time, completion and revocation actor/time, creation/update times;
reopen UUID, response reference, actor and timestamp. Existing relations, constraints and provenance
remain authoritative.

Keep E1 plaintext: `student_name_snapshot` (historical name search), `age_snapshot`,
`civil_status_snapshot`, `course_snapshot`, `major_snapshot`, `program_completion`,
`extra_terms_count`, `delay_reasons`, `significant_learning_experiences`, `career_modes`,
`work_choices`, `study_choices`. Both Self-Assessment and College Feedback rating models retain
ordinary typed parent, `item_code`, and `rating` columns. No report needs to decrypt responses
merely to aggregate these dimensions.

Replace exactly these 13 E2 response fields with non-null/non-empty
`confidential_content_ciphertext = TextField(editable=False)`:

- `email_snapshot`, `home_address_snapshot`, `contact_number_snapshot`;
- `delay_other`, `significant_learning_other`;
- `dean_comments`, `program_chair_comments`, `faculty_comments`, `curriculum_comments`,
  `guidance_counselor_comments`, `office_staff_comments`, `facilities_comments`;
- `suggestions_recommendations`.

Replace opportunity `note` with `note_ciphertext`, and reopen `reason` with `reason_ciphertext`,
likewise non-null/non-empty. No ordinary plaintext copies remain. Empty optional text/note still
has a complete authenticated payload; a reopen reason must be non-whitespace.

### Envelopes and key isolation

Use one required independent ordered `EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS`.
The first key encrypts; all listed keys decrypt. Settings reject decoded-byte reuse with Django,
TOTP, Web Push storage and **every current/previous entry** in Routine, Shared Summary and Referral
keyrings. There is no fallback, derivation, global key registry or separate contact/note/reason key.

All three distinct envelopes authenticate integer `schema_version: 1` and exact field sets using
unchanged ADR-079 shared helpers, with UUIDs represented by `str(UUID)`:

| Envelope | Authenticated binding | Exact payload |
| --- | --- | --- |
| Response | `exit_interview_id` | All 13 named response fields, each a string |
| Opportunity | `opportunity_id`, `student_id`, `academic_year_id` | `{"note":"..."}` |
| Reopen | `exit_interview_id`, `reopen_event_id` | `{"reason":"..."}` |

Bindings live inside Fernet's authenticated plaintext, not external AAD. Tokens cannot be copied
across records, parents, Students, years or envelope families. Final UUIDs exist before encryption;
notes and correction events remain separate independently writable/rotatable rows.

The narrow adapter owns immutable projections, exact schema, limits and cross-field validation,
explicit readers/writers and sanitized errors. No model properties, descriptors, encrypted ORM
field, implicit decryption, save hook, cached plaintext or searchable/blind index is introduced.
Runtime input keeps existing trimming/full-replacement semantics. Limits remain email 320,
contact 64, address 2000, Other/note/reason 1000, comments/suggestions 4000. Email validation and
coded-choice/Other consistency remain enforced. NUL and non-UTF-8-representable strings are rejected.
Verified historical plaintext is restored exactly, without trimming or normalization.

### Disclosure and lifecycle

Existing capability, Student ownership, resource scope and state checks precede decryption.
The owner reads/edits DRAFT and reads SUBMITTED. Head sees full detail/PDF only while SUBMITTED;
a reopened DRAFT is denied before any read helper runs. GSS receives only authorized opportunity
management projections (including the bounded note); no response contact, answers, ratings,
comments, suggestions, correction reason or PDF authority. Capability revocation remains decisive.

Metadata-only response summaries/history, Student opportunity status, search and pagination use
ordinary columns without confidential decryption. Opportunity management filters and paginates
first, then decrypts only selected-page notes; lookahead rows remain unread. Good Moral's graduation
prerequisite locks/evaluates GRADUATION opportunity, SUBMITTED response and `last_submitted_at` and
stores the same provenance, without decrypting any response/note/reason or requiring the domain
keyring in the prerequisite calculation itself (application settings still require it at startup).

Creation writes contacts and empty free text into one authenticated payload. Full DRAFT replacement
verifies existing content before writing, validates normalized replacement with structured choices,
then updates ciphertext and ordinary survey/rating fields atomically. Submission validates an
explicit logical projection and preserves the token. Controlled reopen allocates/encrypts the reason
row and changes workflow metadata atomically. Opportunity OPEN retries compare verified plaintext
and retain identical tokens/timestamps; revoked reopening preserves immutable source and re-encrypts
only if the normalized note changes. No ciphertext comparison defines semantic equality.

Detail explicitly reads the main projection and each selected reopen reason. Authorized PDF checks
SUBMITTED, decrypts once and passes an ephemeral immutable projection into the unchanged source-form
builder/template. Saved form-local contacts/comments survive later profile changes. Release Audit
remains synchronous/fail-closed and contains only document/access metadata. Ordinary Audit,
correction notifications and email never carry text, envelopes or tokens. Demo seeding uses the same
explicit projection for its saved contact snapshots.

`ExitInterviewConfidentialContentUnavailable` exposes only typed structural UUID context and a
bounded ADR-079 reason. Authorized unreadable required content returns generic server error
`exit_interview_confidential_content_unavailable` (500). No blanks, partial detail, omitted reasons,
false not-found, automatic corrupt-token replacement or sensitive exception chaining. Unauthorized
403/404/state behavior remains unchanged and precedes all decrypt calls.

### Migration and recovery

Frozen `_exit_interview_confidential_content_v1.py` preserves migration-time key parsing, canonical
JSON, bindings/limits/validation and safe failures independently of evolving runtime/domain helpers.
Phase A `0003_encrypt_confidential_content` adds nullable ciphertext/backfills all three families,
leaving plaintext authoritative. Phase B `0004_remove_plaintext_confidential_content` atomically
locks response, opportunity, then reopen tables in deterministic order with PostgreSQL SHARE ROW
EXCLUSIVE locks before any content verification/update. It validates latest plaintext, authenticates
every present token, reconciles only missing or readable stale tokens, verifies replacements, then
removes 15 plaintext columns and enforces non-null/non-empty ciphertext.

Old code may change coded choices and Other text together after Phase A. Authenticate old token's
bindings/schema/field validation independently of today's coded choices, then validate/reconcile
latest plaintext against today's structured columns. Changed notes, contacts, comments, correction
reasons and late inserts are similarly reconciled. Present corrupt/rebound/unsupported/malformed
tokens abort the transaction, including earlier rewrites, before destruction. Business timestamps,
ratings, IDs, provenance and side effects remain untouched.

Controlled reverse uses nullable/default-compatible restored columns first, writer fencing,
verification/decryption/exact restoration of every payload, then historical field nullability/defaults.
Unreadable content aborts schema and data changes atomically; no empty fallback. Phase A reverse
drops ciphertext only after successful plaintext restoration. Full readable ordered keyrings and
coordinated downtime are required; do not start old code against the ciphertext-only schema.

### Rotation

`rotate_exit_interview_confidential_content --dry-run --batch-size 100` verifies all three families
with separate scanned/current/rotation/failure counts. Real rotation accepts batches 1–1000, locks
selected rows and uses ADR-079 primary detection/MultiFernet rotation, preserving plaintext bytes
and original Fernet timestamps. Only ciphertext columns change. Committed batches survive
interruption; rerun resumes and current-primary rows are no-ops. Failures remain unchanged, list at
most 20 safe UUID/reason contexts and cause non-success. Both dry/real modes refuse any legacy
plaintext confidential column. No automatic rotation or key deletion is introduced.

### Runtime and deferred cutover

ADR-078 inventory becomes **18**. Add required non-empty source
`exit_interview_confidential_content_encryption_keys` and exact pointer
`EXIT_INTERVIEW_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS_FILE=/run/secrets/exit_interview_confidential_content_encryption_keys`.
Only web/worker/Beat receive it because settings load eagerly; PostgreSQL/Redis/proxy do not.
Existing `0700` parent, regular/non-symlink `0444 compass:compass` source semantics remain unchanged.
The exporter cannot supply an absent new key. Repository tests use synthetic keys only.

No live cutover, live key or deployment is part of this implementation. Merges do not establish
actual host readiness. Future separately authorized cutover must inspect actual live starting
state; independently provision/escrow each absent Shared Summary, Referral and Exit Interview
keyring; verify database/rollback backups and complete ordered off-host recovery; preflight the
18-secret candidate image/manifest/environment. Stop/drain **all** old web/worker/Beat/scheduled/operator
writers and prevent restarts throughout destructive migrations and exact-SHA activation. Ordinary
workflow migration-before-service-replacement and table locking cannot bridge old-code column
compatibility. Verify actual schema, historical authorized API/PDF, metadata-only Good Moral and
all domain dry runs, build/readiness and services. Controlled reverse must match the prior schema
and immutable image/manifest/environment pair; retain keys while encrypted backups need them.
See [runtime-secrets.md](../runtime-secrets.md).

## Consequences

New rows/backups hold ciphertext only for E2; E0/E1 remain queryable. The trusted application/host
still handles authorized plaintext, and Fernet exposes approximate content length. This is not
end-to-end encryption. Key loss makes content/backups unrecoverable; old plaintext backups and any
controlled restored plaintext remain sensitive. Historical cleanup/retention is a separate operation.

ADR-031 remains authoritative for source-form semantics, lifecycle, ownership and privacy;
ADR-075/076 retain opportunity and Good Moral/GSS behavior. No frontend redesign, normal public
contract change, unrelated encryption-domain redesign, reporting/search redesign, Vault/KMS,
provider integration, background key generation or live action is introduced.
