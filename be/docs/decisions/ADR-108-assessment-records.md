# ADR-108: Assessment Records

- Status: Accepted
- Date: 2026-10-10
- Scope: Small institutional recordkeeping domain; no deployment or live provisioning

## Decision

`assessment_records` records results already produced by Guidance-administered or recognized
assessments. It does not administer tests, score, infer, diagnose, rank, recommend interventions,
or generate interpretations. Interpretation is authorized human-authored source content.

Two models suffice: an institution-managed `AssessmentType` catalog and repeatable longitudinal
`StudentAssessmentRecord` facts. Records are independent of Student Support, Individual Inventory,
Academic Year, Appointments, Counseling, Routine Interviews, Referrals and Graduate Tracer
professional-exam responses. There is no workflow status, approval lifecycle, attachment, export,
Notification, My work item, Student action, Guidance operations metric or Reports analytics.

Catalog names reject blank/control-character input, collapse surrounding/repeated whitespace and
are unique case-insensitively across active and inactive rows. Head Guidance with manage authority
can create, rename, describe, deactivate and reactivate types. Referenced types use PROTECT.
Inactive types remain visible on historical records; new records and type corrections to a
different type require an active type. Ordinary corrections may keep the existing inactive type.

## Confidentiality and source fidelity

Plaintext is limited to UUID, Student FK, Assessment Type FK, administered calendar date,
recorded-by FK and creation/update timestamps. A future administered date is rejected using the
institutional calendar; historical dates remain valid. Provenance and Student ownership stay
immutable. Corrections update facts and append structural Audit Events.

The first migration already contains only `confidential_content_ciphertext`, with a nonempty
database constraint. There are never plaintext score, result, interpretation or remarks columns;
there is no legacy data backfill or plaintext-to-ciphertext migration. The exact version-1 payload
is four strings: `score` (500 characters), `result` (4000), `interpretation` (8000), `remarks` (4000).
At least one must contain meaningful nonblank content. NUL, invalid Unicode and excess length
fail safely. Source text, including score/rating scale and whitespace, is preserved.

ADR-079's shared Fernet mechanics encrypt the exact JSON payload under an independent ordered
`ASSESSMENT_RECORD_CONFIDENTIAL_CONTENT_ENCRYPTION_KEYS` keyring. The authenticated envelope is
bound to canonical `assessment_record_id`, `student_id` and `assessment_type_id` strings and schema
version 1. Copying ciphertext between any of these identities fails closed. No existing domain or
security key is reused. SQL filtering and aggregation by encrypted result values are intentionally
unavailable; future analytics requires a separate privacy and source-fidelity design.

Explicit domain helpers validate input, write/read content, detect primary-key tokens and rewrap
verified envelopes. ORM reads never implicitly decrypt. Structural list/search/filter/order queries
do not select the result column or decrypt content. Detail authorizes first, then decrypts exactly
the authorized result. Safe unavailable reasons are only missing, undecryptable, malformed,
unsupported_schema and binding_mismatch; errors, logs and API responses never include ciphertext
or submitted values. PATCH locks the selected record, validates/decrypts its existing envelope,
applies corrections and encrypts the complete payload. A type change rebinds within the same
transaction; corrupt existing content cannot be silently replaced. No-op corrections do not change
timestamps, ciphertext or audits.

## Authority

`assessment_records.manage` depends on `assessment_records.view`. Both are granted through the
HEAD_GUIDANCE_COUNSELOR designation only, never any baseline role. All operations require a current
active canonical COUNSELOR plus effective capability. GSS, Students, IT Admin and DPO/Institutional
Officers stay denied even with unusual grants. Technical/governance authority creates no content
access. Head authority is institution-wide explicitly within this domain (ADR-099).

An ordinary Counselor with an exceptional explicit grant receives only Students within current
active handled College/Campus responsibility. Out-of-scope resources are concealed as 404.
Catalog mutations additionally require the actor's own Head designation. New-record selection
uses the narrow operational Student helper: active CURRENT Students only. Historical records
remain readable when a Student becomes GRADUATED, FORMER or inactive, within current authorized
scope. There is no Student self-service/disclosure route.

## Audit, rotation and runtime

Record create/update and type create/update/deactivate/reactivate use canonical synchronous Audit
Events in the mutation transaction. Record metadata contains only the Assessment Type UUID; type
metadata is empty. No confidential values or special per-read surveillance are introduced.

`rotate_assessment_record_confidential_content` verifies binding/payload before even treating a
primary token as current. Dry-run writes nothing. Real runs lock bounded batches, rotate only old
tokens with MultiFernet.rotate, preserve provenance/business timestamps, cap safe failure reports
at twenty UUID/reason pairs and exit nonzero for unreadable rows. It is rerunnable and committed
batches survive interruption. It does not emit audit, confidential content, keys or ciphertext.

Runtime source `assessment_record_confidential_content_encryption_keys` brings the repository
inventory from 23 to 24 sources. Web alone receives the mount; worker/beat clear its setting/path,
and realtime receives no content key. Empty keyless non-web settings may boot, while confidential
access fails closed. Malformed/duplicate keys and cross-domain/security reuse fail startup safely.
Live preflight requires the nonempty file with existing ownership/mode/pointer rules; web startup
validates its keyring. Operators must provision and protect this independent key before any later
deployment, retain recovery keys, apply the initial schema and run normal sync_identity_policy.
This slice generates no real key, accesses no Droplet secret directory and performs no deployment.

## Deferred governance

No hard delete, archive/void state, Student reassignment, automated purge or retention duration is
invented. Assessment Records are not registered with ADR-072's retention executor. Disposition,
controlled correction of erroneous ownership, graduate backfill, Student disclosure, attachments
and analytics require separate institutional governance decisions.
