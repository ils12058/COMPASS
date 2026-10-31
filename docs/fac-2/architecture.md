# FAC-2 architecture and migration decisions

## One canonical record, separate authorization

`referrals.services.persist_referral` owns the shared encrypted insert and synchronous
`referral.created` Audit event inside an atomic block. Both entry services use the
existing annual allocator, canonical form resolver and confidential-content writer.
GCO operational identity/scope validation stays in `create_referral`; Faculty identity,
policy and confirmation validation stay in `faculty_services.submit_referral`.

The Faculty path adds a transactional `referral.faculty.submitted` Audit event bound
to the exact approved policy digest/event. Neither event contains the reason,
confirmation value, course text, contact details or internal actions. Audit failure
rolls back the insert, ciphertext and reference-counter allocation together.

GCO creation's original actor/key digest remains byte-for-byte compatible. Faculty
uses the same digest helper and unique `creation_key_digest` field with a Faculty
channel namespace; fingerprints use the canonical server request-fingerprint helper.
The locked current actor serializes same-actor retries. Same key/changed body is a
409 conflict; exact replay returns the same persisted allowlisted result without
counter advancement, provenance rewriting or duplicate Audit. Current role,
capability, session, home eligibility and own-disclosure policy are required even on
replay. An old confirmation may resolve an already committed replay after expiry or
home transfer; it cannot authorize a new submission.

## Additive schema

`referrals.0002_referral_faculty_home_college_and_more` adds:

| Field | Meaning |
| --- | --- |
| `submission_channel` | `LEGACY_UNSPECIFIED`, `GCO_RECORDED`, or `FACULTY_PORTAL` |
| `submitted_by` | Protected FK to the authenticated originating Faculty account |
| `submitted_at` | Server timestamp for the digital submission |
| `faculty_home_college` | Protected home College UUID at submission; provenance only |
| `student_college_at_submission` | Protected placement College UUID at submission; historical provenance only |
| `submission_policy_digest`, `submission_policy_event` | Exact approved policy and matching append-only Audit decision |

A database default also labels writes from compatible pre-FAC schema clients as
`LEGACY_UNSPECIFIED` when they omit the new columns; it invents no digital origin.
Existing rows acquire only `LEGACY_UNSPECIFIED`; their original fields, timestamps,
relationships, encryption and references are unchanged. There is no name matching,
Faculty owner backfill, invented paper provenance or invented approval event. Newly
encoded GCO records explicitly use `GCO_RECORDED` with all Faculty provenance null.
Faculty inserts have complete origin provenance and `recorded_by=None`, preserving
the GCO-encoder meaning. Referrer printed name remains encrypted source content.

CHECK constraints reject partial or cross-channel origin facts. A PostgreSQL update
trigger prevents changing the origin tuple for all records and also protects the
Faculty submission's Student, source-name/course snapshots, date, form revision,
reference and creation digest/fingerprint. The existing confidential-envelope field
remains writable by existing GCO status/void services, which retain reason/referrer
while updating their own encrypted fields. No new correction authority is introduced.

The migration refuses reversal when any Faculty-origin record exists: destroying
authenticated provenance is not an operational rollback. Roll forward with compatible
code. Empty/pre-activation schema reversal is available for disposable rehearsals.
Historical Organization migration fixtures explicitly pin Referral at its pre-FAC
schema while exercising old Organization; otherwise the new real dependency would
incorrectly pull current Organization fields into an old-schema test state.

## Locking and current authority

Faculty operations take the cooperative shared catalog gate first, then current
actor/Student account rows in UUID order, the actual session, and the managed home
relationship. Student placement writers already lock the Student account and take
that gate. Authority/lifecycle/affiliation mutations therefore serialize with intake.
Queries and writes use database state, not cached request/session projections.

The canonical form row is locked with PostgreSQL `FOR NO KEY UPDATE`. It blocks
revision synchronization while remaining compatible with GCO's FK key-share lock,
avoiding a form/counter lock inversion. Both writers share one annual counter.
Approval/session/confirmation eligibility is checked again after counter contention.
References use the Philippine institutional date; caller-provided timestamps are not
accepted by the Faculty schema. `received_at` stays null; no action/task is created.

These protections coordinate supported writers. They are not a claim that a database
superuser, old unrestricted binary or arbitrary SQL is fenced by the catalog gate.
Audit retains its existing application-level append-only boundary; no new claim of
database-level Audit tamper-proofing is made.

## SAR and operational scope

`faculty_placement.resolve_student_placement` is the sole new Student placement read
adapter. Today it validates active Student identity plus active StudentAffiliation
College/Campus and returns a stable College UUID with a revision binding. It writes
no academic facts. SAR may replace this adapter in a separately reviewed migration.

CAS Faculty can confirm/submit for an approved CCMS Student: no equality comparison
between home and Student College exists. Missing/retired placement produces the same
non-disclosing unavailable result as other ineligible Student confirmation. There
is no Faculty-home routing or Head fallback. Existing GCO list/detail/document scope
continues to follow its current Student College-based rules; the new saved Student
College is provenance, not a silent rewrite of those rules. Scope after future SAR
transfers remains a separately governed decision.

## Form mapping

The exact active identity is `UCN-OP-GCO-01F3`, Revision 1, internal schema 1 (ADR-113).
Student name comes from the current authenticated-confirmed account; Course/Yr & Blk
is declared form text; reason uses the existing bound encrypted envelope; referrer
printed name comes from Faculty identity; date comes from institutional server time.
The GCO portion (receipt date/time, actions, remarks, status) is never accepted from
Faculty. A printed name does not represent an approved digital signature. Digital
capture and any signature rule still require the explicit approval described in the
policy register. The source template and all legacy PDF renderers are unchanged.
