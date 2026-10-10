# ADR-079: Shared confidential-data cryptographic primitive

- Status: Accepted
- Date: 2026-10-05
- Scope: Backend implementation extraction; Routine Interview remains the only content consumer

## Context

ADR-066 established explicit encryption of Routine Interview Student Intake and Counselor
Evaluation. Its reusable mechanics were embedded in Routine's crypto module, which settings
also imported for generic key validation. Future confidential-content designs need these proven
mechanics without importing Routine models, sections, settings policy, or payload schemas.

## Decision

Use the plain Python package `compass.confidential_data`, without Django app registration,
models, services, or endpoints. Its `crypto.py` owns canonical Fernet key validation, ordered
MultiFernet assembly, deterministic JSON serialization, flat versioned envelopes, authentication
and context verification, primary-key detection, and `MultiFernet.rotate`. Its `errors.py`
provides `ConfidentialDataUnavailable`, with only `missing`, `undecryptable`, `malformed`,
`unsupported_schema`, or `binding_mismatch` as a reason. It never logs or embeds confidential
inputs in errors. Invalid caller context/keyring configuration raises safe `ValueError`;
rotation retains the library's content-free `InvalidToken` failure.

The caller supplies an ordered keyring, an actual integer schema version, a mapping of non-empty
string binding keys to string values, and a JSON-safe payload mapping. `schema_version` and
`payload` are reserved binding keys. Encryption uses the first key; decryption tries the ordered
keyring and returns only a dictionary payload after checking the exact envelope key set, actual
integer version, expected version and every expected binding value. Invalid tokens, encoding,
JSON, envelope structure and non-finite JSON values fail closed. Domain field validation and
authorization remain the caller's responsibility.

The envelope is `{ "schema_version": version, **binding, "payload": dict(payload) }`.
Serialization remains `json.dumps(..., sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False).encode("utf-8")`. Fernet authenticates the binding inside
this plaintext envelope. This is **authenticated context binding**, not external AAD; Fernet
does not expose an associated-data API. Fernet/MultiFernet and their randomized tokens remain
unchanged. No algorithm replacement or cryptographic primitive is implemented here.

### Routine compatibility and ownership

`compass.routine_interviews.crypto` stays the public Routine boundary. It supplies
`ROUTINE_INTERVIEW_ENCRYPTION_KEYS`, `RoutineContentSection`, UUID string formatting and the
schema version, and translates generic decryption errors to `RoutineContentUnavailable` with
the existing safe UUID/section/reason. Small `parse_keyring` and `keyring_reuses_secret`
compatibility wrappers preserve current imports. Settings imports generic helpers directly;
missing/invalid/duplicate keys and reuse of `SECRET_KEY` or `AUTH_TOTP_ENCRYPTION_KEY` still
fail startup safely.

The exact Routine v1 envelope key set stays `schema_version`, `routine_interview_id`, `section`,
`payload`. Version stays `1`; sections stay `student_intake` and `counselor_evaluation`; UUIDs
stay `str(UUID)`. Payload representation and serialization options remain identical. Stable
synthetic pre-extraction ciphertext and both directions against frozen migration v1 semantics
verify compatibility without using live keys or content.

Routine `content.py` still owns section fields, canonical defaults, read/write accessors and
field/schema validation. Its service layer still authorizes before decryption. Routine's
rotation command stays domain-owned: row selection, locks, batching, validation, dry runs,
failure reporting, timestamps, audit policy and legacy-column safeguards do not move. Generic
rotation preserves plaintext bytes and the original Fernet timestamp; it does not itself
validate a domain binding or payload.

Historical `_routine_content_v1.py`, `0002_encrypt_routine_content.py` and
`0003_remove_plaintext_routine_content.py` remain frozen and do not import this evolving shared
implementation. Their intentional duplication preserves migration reproducibility.

### Keys and future use

Shared implementation does not mean a shared key. Routine keeps its dedicated, unchanged
ordered keyring and existing `routine_interview_encryption_keys` secret file under ADR-078.
There is no global confidential-data key, new secret, key generation/rotation/reordering,
ciphertext rewrite, runtime-secret inventory change or live cutover in this extraction.

> Reuse of the shared primitive does not authorize encryption of a field.

Each future domain must first assess plaintext needs for search, filtering, aggregation,
reporting, workflow eligibility, deduplication, exports, PDF generation, notifications and
integrations. A separate design and audit must establish the exact encrypted fields, domain
binding, payload policy and independently managed keyring before encryption is introduced.
Counseling, Referral, Inventory, Exit Interview and every other domain remain unchanged here.

## Consequences

The mechanics can be audited in one small, Django-independent module while Routine's policy
remains explicit. Existing ciphertext remains readable without migration. No model/database
migration, API/OpenAPI change, frontend change, runtime provisioning or live data access is
required. ADR-066 remains authoritative for Routine policy; ADR-078 remains authoritative for
runtime-secret delivery and recovery. The original server/host trust boundary and Fernet length
disclosure limitations still apply; this does not introduce end-to-end encryption or key management.
