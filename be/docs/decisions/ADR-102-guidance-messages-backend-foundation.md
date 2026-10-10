# ADR-102: Guidance Messages backend foundation

Status: Accepted for backend foundation; deployment and frontend are separate reviews. Refined by
[ADR-104](ADR-104-guidance-messages-staff-operations.md) (eligible handlers, Message templates).

## Context

Guidance Messages stores durable communication; Appointment, Counseling, Referral, Call Slip,
Good Moral, Inventory and other domains remain authoritative for their own workflow facts.
It is neither a Counseling Encounter nor an E-Counseling transcript or ticketing workflow.

## Decision

A dedicated `guidance_messages` Django domain owns three UUID models: `GuidanceThread`,
`GuidanceMessage`, and `GuidanceThreadReadState`. Domain/provenance FKs use PROTECT. PostgreSQL
checks enforce family/resolution shapes and nonnegative cursors; unique constraints enforce
per-thread sequences, sender/client IDs, private read cursors, one Counseling thread per
Appointment, and at most one OPEN Office thread per Student. Messages have no editing/deletion
fields or product mutation endpoints. No empty user-created thread commits.

**OFFICE** addresses the Guidance Office institutionally. Its stored routing College comes from
the Student's current active affiliation and canonical default-Counselor resolver. A new thread
requires an eligible active default Counselor with Messages management authority; missing or
ambiguous routing fails closed. Students never submit a College, Counselor, GSS or handler ID.
Staff initiation uses the current operational Student picker, restricted to CURRENT Students in
finite handled Colleges. Routing College remains the historical thread's workload boundary.
`assigned_to` initially identifies the default Counselor, and authorized staff can transfer it
to an active Counselor or supervised GSS with current handled workload and Messages management.
Assignment is operational ownership, not ACL; stale assignments never preserve content access.

OFFICE content uses `resolve_operational_responsibility_scope` exactly as ADR-099: Counselor
explicit handled Colleges; unique Head explicit Colleges plus valid fallback Colleges; GSS
inherits only the supervisor's handled workload. GSS under Head never inherits designation-wide
authority, and Head cannot see a College handled by another active Counselor through designation.
Multiple active Heads do not create implicit fallback. Inactive accounts/organization or broken
supervision fail closed.

**COUNSELING** is exact Student ↔ Counselor participation, derived from the canonical
`COUNSELING` service Appointment. Creation accepts SCHEDULED or COMPLETED, matching the legitimate
Appointment states used by Counseling Context. CANCELLED and NO_SHOW cannot establish a new
Messages relationship. Both participants must be active in their canonical roles and the provider
must have Messages view authority. No Counseling Context time window controls durable Messages.
After creation, stored participants remain authoritative even if the Appointment is cancelled,
reassigned, or its time window expires. Historical read access still requires an active account
and its appropriate Messages capability. GSS, unrelated Counselors, IT Admin, DPO and
Head-not-provider cannot inspect content or create a relationship by organizational override.
A future E-Counseling text side-channel can reuse this one Appointment thread; join authorization
is separate. There is no Daily chat, transcript copy or Encounter note generation.

Capabilities are `guidance_messages.view_self` / `manage_self` for Student and
`guidance_messages.view` / `manage` for Counselor/GSS; each manage depends on its matching view.
IT Admin and Institutional Officer receive none; Head and DPO designations add none. Generic
capability overrides remain effective subject to these role/resource rules. Resource denial is
concealed 404; collection capability denial is 403.

Body is 1–4,000 Unicode characters of nonblank valid UTF-8 plain text, with NUL rejected. Verified
text and line breaks remain unchanged. There is no HTML/Markdown interpretation, URL expansion,
AI, embeddings, rich content, media, files, reactions, presence, typing, search, edit or delete.
Only ciphertext and schema version 1 persist, using shared `confidential_data.crypto` mechanics
and dedicated `GUIDANCE_MESSAGE_ENCRYPTION_KEYS`. The authenticated envelope binds thread UUID,
Message UUID, sequence and sender UUID. Missing keys, malformed tokens, binding/schema/payload
mismatches fail closed with domain-specific confidential-content-unavailable. No body/hash,
preview, plaintext search vector, request JSON, ciphertext or content is written to audit/logs.
The independent ordered keyring is web-only; realtime never receives it. The unprovisioned empty
keyring permits unrelated domains to run while content reads/writes fail closed. See the runtime
secret runbook for provisioning/rotation prerequisites.

All writes use HTTP and database transactions. Sender `FOR NO KEY UPDATE` row locking before thread locking serializes
persistent `(sender, client_message_id)` replay even across threads; the unique constraint remains
a final guard. These participant locks permit foreign-key key-share checks, preventing crossed
Student/Counselor creation deadlocks without weakening send serialization. Same sender/ID/thread returns the original immutable Message, including after
resolution; reuse against another thread conflicts. Changed retry body is not stored or compared
via a plaintext hash. Thread locking allocates sequence and updates `last_sequence` and
`last_message_at` atomically. Failed encryption/rollback leaves no Message, consumed sequence,
orphan read state, success audit or hint. Creation locks Student (OFFICE) or Appointment
(COUNSELING), and creation plus first send is one transaction. Opening an existing eligible OPEN
thread with a fresh client ID sends that submitted Message into the same thread. Retrying the
original create ID returns its original thread/Message. There is no generic Redis response replay.

Only OPEN / RESOLVED exist. Current scoped OFFICE staff or exact COUNSELING Counselor may resolve
or reopen; Students cannot. RESOLVED rejects new sends. A resolved Office concern permits a new
OPEN thread. Reopening conflicts if another OPEN Office thread exists. Status changes record
resolution provenance and never edit Message history.

Read state is private per actor, monotonically advances through a committed sequence, and cannot
exceed the thread cursor. Responses include only the actor's own cursor and unread count, excluding
self-authored Messages. There are no peer cursors, Seen/Read by indicators or social read receipts.
Directory responses contain minimal safe identity/structural facts and require no decryption or
plaintext preview. Message history is bounded to 50, before-sequence based, and returned in
chronological order with `has_older`; directory/options use bounded pages and `has_next` without
invented totals. Responses containing authorized confidential data use `no-store, private`.
Recipient options show Guidance Office and only canonical eligible Counseling Appointment anchors;
there is no arbitrary Counselor/GSS directory. Options pages advance through bounded Appointment
candidates and omit providers whose capability has been revoked, so a page may be sparse.

The sole new public hint is `{"v":1,"type":"messages.thread_changed","thread_id":"<UUID>"}`.
The closed shared registry rejects missing/malformed UUID or additional fields and the standalone
service revalidates it. Commit-time recipient calculation applies current Messages authorization:
COUNSELING exact Student/Counselor, OFFICE Student plus valid responsible Counselors/Heads and
supervised GSS for the stored College. Candidates are routing-related, never a global staff
broadcast. Private read updates hint only the reader's own user channel/all sessions. PostgreSQL
and HTTP are authoritative; Redis failures/disabled realtime never undo creation, send, status,
assignment or read state. Hints are lossy, with no outbox or durable realtime delivery promise.

Stable audit actions: `guidance_messages.thread.created`, `.message.sent`, `.thread.assigned`,
`.thread.resolved`, `.thread.reopened`; structural IDs/sequence/kind and assignment provenance only.
Audits commit atomically with mutations. Private read changes do not create noisy audit events.

## Boundaries and consequences

No frontend Messages workspace/navigation, contextual entry buttons, Notification records/events,
large seed dataset, workflow hooks, or deployment are added. OpenAPI/generated client validation
prepares the next phase without inventing UI. ADR-072's closed retention executor is unchanged.
A future `GUIDANCE_MESSAGE_THREAD` category needs adopted institutional duration/trigger/treatment,
holds, approval, executor and verification tests. This foundation preserves creation/resolution
timestamps, immutable provenance and encrypted content; it does not add retention rules,
disposition, deletion placeholders or speculative statuses.

PostgreSQL concurrency tests include 20/32 duplicate attempts and distinct concurrent sends; no
global ordering across threads is claimed. Local real DB/Redis/ASGI socket + authenticated HTTP
proof complements policy/constraint/encryption/API regression tests. This does not prove a live
secret/deployment configuration, guarantee realtime delivery, or authorize raw content oversight.

## Subsequent decision

[ADR-105](ADR-105-guidance-work-queue-and-messages-operations.md) adds the read-only Guidance
staff Work Queue and Messages operational hardening. This decision remains the historical
foundation; ADR-105 defines the current host-key gate, template version requirement and shared
Guidance actionable projection.
