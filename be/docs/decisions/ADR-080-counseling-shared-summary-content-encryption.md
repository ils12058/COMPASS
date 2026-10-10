# ADR-080: Counseling Shared Summary content encryption

- Status: Accepted
- Date: 2026-10-06
- Scope: Only the existing Counseling Shared Summary body

## Context

ADR-025 introduced a deliberately Counselor-authored, Student-disclosable Shared Summary with
plaintext storage. Its free-text body is read after an authorized resource is selected; it is
not searched, filtered, grouped, aggregated, part of report populations or relational joins,
exported to PDF/XLSX, or copied into Audit, notifications or email. Application encryption can
protect that body without removing a current query capability.

Counseling Encounter fields remain plaintext operational metadata. Student/counselor/service,
service-name snapshot, appointment, entry/delivery mode, actual times, creator and timestamps
support authorization, search/filter/order, linkage, feedback, Routine finalization, Counseling
Context and historical correction. This decision changes none of those fields.

## Decision

Replace the Summary's persistent `content` with non-null, non-empty `content_ciphertext`
(`TextField(editable=False)`). Both draft and published bodies stay encrypted at rest. Publication
makes the body readable to its owning Student; it does not change the storage confidentiality.
There is no ordinary plaintext body column after the final migration.

`compass.counseling.shared_summary_content` owns the setting, version, binding, exact payload
schema, input rules, safe error, explicit read/write accessors and rotation wrappers. It uses
ADR-079's shared Fernet/MultiFernet mechanics, without model properties, save hooks, automatic
ORM decryption, a key registry or a generic Counseling crypto framework. The model allocates its
final UUID before the first encryption; draft edits replace the complete encrypted payload.

The dedicated ordered `COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS` is required in every environment
with no fallback/derivation. First key encrypts; every key decrypts. Settings use the shared
parser and reject byte-equivalent reuse of SECRET_KEY, TOTP, Web Push storage or **any** Routine
keyring entry. Shared cryptographic implementation does not mean shared keys. This keyring is
for deliberately Student-disclosable summaries; future counselor-only private notes require a
separate audit/design and must not automatically reuse it.

The exact v1 envelope is:

```json
{
  "schema_version": 1,
  "counseling_shared_summary_id": "<summary UUID>",
  "encounter_id": "<encounter UUID>",
  "payload": {"content": "<text>"}
}
```

Summary and Encounter UUIDs are authenticated fields inside Fernet plaintext: **authenticated
context binding**. Copying a token to either different identifier fails. Version is an actual
integer `1`; payload has exactly the `content` field. Content must be `str`, UTF-8 representable
and contain no NUL, preserving PostgreSQL's effective input boundary. Whitespace, Unicode,
multiline text, quotes and backslashes round-trip exactly. Empty/whitespace drafts are valid
and encrypted; publication still requires `content.strip()`.

### Authorization and failures

The normal API content request/response contract remains unchanged. Assigned-Counselor response
projections call the explicit reader only after the existing active role, capability and actual
Encounter relationship checks. Student selection filters owning Student and published state
before decryption; drafts/other Students remain not found. Counseling Context resolves existing
time-bounded relationship authorization, then selects Student-scoped published rows before
reading. Querysets, Encounter discovery/search, feedback and Routine lifecycle/history remain
content-unaware. No Summary response cache or body search/index is added.

Publication locks Encounter then Summary, returns already-published resources idempotently,
explicitly reads the body, requires non-whitespace content and changes publication state. Existing
Audit and generic notification/email behavior never receive the body. There are no migration or
rotation Audit events/notifications.

`CounselingSharedSummaryContentUnavailable` carries only Summary UUID, Encounter UUID and one
bounded reason: missing, undecryptable, malformed, unsupported_schema, binding_mismatch. Authorized
unreadable content returns the stable generic `counseling_shared_summary_content_unavailable` API
error (500); lists fail as a whole. No empty fallback, partial output, silent skip, token/keys/
envelope logging or automatic corruption replacement is allowed. Ordinary authorization/not-found
behavior stays separate. The shared primitive remains log-free.

### Migration, rotation and deployment

The frozen `_shared_summary_content_v1.py` deliberately retains reproducible v1 mechanics and
validation without importing evolving runtime helpers. Phase A `0004_encrypt_shared_summary_content`
adds nullable ciphertext, backfills from authoritative plaintext, and preserves identity,
relationships, publication and creation/update timestamps. Phase B
`0005_remove_plaintext_shared_summary_content` holds a PostgreSQL writer-blocking table lock in
an atomic transaction; validates every current plaintext; verifies every present token's binding,
schema and payload; reconciles missing or readable stale tokens from latest authoritative
plaintext; verifies again; and only then removes plaintext and enforces ciphertext constraints.
An unverifiable present token aborts before destruction, even if plaintext could recreate it.
A failed Phase B rolls back earlier row rewrites too.

Controlled reverse restores plaintext from verified ciphertext atomically, with no blank fallback
or output of bodies. Phase A reverse may then drop ciphertext. Both directions preserve business
metadata and side effects. The complete readable keyring is required for forward/reverse.

`rotate_counseling_shared_summary_encryption` remains domain-owned. It verifies bindings and exact
payloads, detects primary-key tokens, uses MultiFernet.rotate for previous-key tokens and retains
the original Fernet timestamp/bytes. It supports read-only `--dry-run` and 1–1000 row batches,
locks rows for real rotation, commits each batch and safely resumes after interruption. Updates
only ciphertext; metadata/Audit/notifications do not change. Corruption remains unchanged,
failures produce non-success with bounded safe UUID/reason output, and legacy plaintext schema
causes refusal for both modes. There is no automatic/key-scheduled rotation.

ADR-078's host inventory becomes 16 with the required non-empty
`counseling_shared_summary_encryption_keys` source and
`COUNSELING_SHARED_SUMMARY_ENCRYPTION_KEYS_FILE=/run/secrets/counseling_shared_summary_encryption_keys`.
Web, worker and Beat receive it because settings load eagerly; PostgreSQL, Redis and proxy do not.
The host directory stays `0700 compass:compass`, source file `0444 compass:compass`. No live key
is committed/generated by this implementation; only synthetic test keys are used. This new secret
cannot be recovered by exporting the previous 15-secret runtime: separate fresh provisioning and
independently protected off-host recovery are required before deployment.

The current workflow migrates candidate code before fully replacing old services. Removing a
column required by old code is a **deployment compatibility boundary**, not an automatically safe
rolling deployment. A separately authorized one-time cutover must provision/escrow the key, verify
backups/preflight, stop/drain old web/worker/Beat and other writers through migrations and activation,
deploy the exact staging SHA, and verify all historical Summary bodies/schema/build/services.
The table lock cannot make old code work after commit. Rollback also requires coordinated downtime,
verified reverse migration and a compatible image/manifest/environment pair. See
[runtime-secrets.md](../runtime-secrets.md) for execution gates and recovery.

## Consequences

Database rows/backups after migration hold ciphertext bodies, with no new search capability.
Loss of the keyring loses access to those bodies, so recoverable complete off-host keyrings are
mandatory and older keys must remain while retained backups need them. Historical plaintext
backups remain sensitive. The application/host remains trusted and can decrypt authorized
content; this is not end-to-end encryption.

No private notes, observations, diagnoses or case records; no E-Counseling/provider metadata,
other encrypted domains, reports/analytics, blind indexes, frontend or normal OpenAPI changes;
no KMS/Vault, live provisioning or live deployment are part of this repository slice.
