# ADR-FUP-1A — Secure Shared Guidance Follow-Up foundation

Date: 2026-10-17
Status: Implementation proposal; institutionally gated / NOT an approved rollout.

## Ownership and non-goals

`compass.guidance_followups` owns a single Follow-Up lifecycle and immutable history.
No source-domain Appointment, Counseling Encounter, Referral, Routine Interview, Task, Work
Queue, Notification or Counseling Context lifecycle is mutated or invented. Every follow-up
is optional. No My Work or frontend modules are modified in this PR.

`GuidanceFollowUp` stores a Student, required assignee, optional paired typed source
reference, server-enforced visibility, category, due time, PENDING/COMPLETED/CANCELLED
status, encrypted content, actors/timestamps and optimistic revision. OVERDUE is derived
using a timezone-aware instant; institutional scheduling fields follow ADR-097.
`GuidanceFollowUpEvent` is a strictly typed append-only history with a unique
Follow-Up/revision pair. No arbitrary metadata payload or plaintext is recorded.

## Source matrix

| Source | Eligibility / current access | Visibility |
| --- | --- | --- |
| Standalone Student | Active Student, current operational College scope | OPERATIONAL |
| Counseling Encounter | Same Student, exact assigned Counselor, counseling view/manage | COUNSELOR_CONFIDENTIAL |
| Routine Interview | Same Student, exact assigned Counselor and actionable parent | COUNSELOR_CONFIDENTIAL |
| Referral | Same Student, live Referral and scoped `referrals.view/manage` | OPERATIONAL |
| E-Counseling | Link through canonical Counseling Encounter only | COUNSELOR_CONFIDENTIAL |

Unknown sources, raw Appointments, Student Support, Guidance Messages, Daily media and
group registrations are not allowed. Source IDs are not returned in summary pages and
are included in detail only after independent source authorization. Source policy is
evaluated on each read, not inherited through Follow-Up assignment.

## Authorization

The registered identity-policy capabilities are `guidance_followups.view` and
`guidance_followups.manage` (manage requires view). Baseline candidates are
COUNSELOR and GUIDANCE_SERVICES_STAFF. These code-owned grants **do not run a DB
synchronization by migration**. They become effective only through the existing
explicit `sync_identity_policy` operational step, after institutional approval.

GSS handles operational items only within live supervision and College scope.
Counselor-confidential records require exact source relationship and Counselor role;
Head, IT Admin, DPO, Student and unrelated Counselors cannot gain content through
designation, assignment or capability override. No global 'list all' route exists.
A lost supervision, role, College or capability boundary removes ongoing access. Recovery
of an inaccessible pending record must use a separate reviewed, audited authority and
must not auto-reassign a confidential record to Head or IT.

Mutations require recent MFA through the existing step-up middleware conventions.
Read/list requests still require active, current server-side domain capability and
resource authorization.

## Crypto and deployment

The new `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS` domain reuses versioned bound-json
envelopes in `compass.confidential_data.crypto`. Descriptions, outcomes and activity/
cancellation remarks are bound to the Follow-Up UUID and section; event content is also
bound to its exact event UUID. No plaintext appears in structural list responses,
Audit metadata, realtime, email, push, or persistent work projections.

The optional keyring is validated when supplied and rejects reusing another domain's
key. Missing keys fail closed on confidential read or write; they are **not** replaced
by an existing domain key or plaintext fallback. Web alone will need access to the
new keyring when the rollout is authorized; worker, Beat and realtime stay keyless.
The default `GUIDANCE_FOLLOWUPS_ENABLED=false` disables all HTTP endpoints, including
reads, pending a staged approval and verified key provisioning. No runtime environment,
host secrets, infrastructure, UAT accounts, or dataset are changed by this PR.

Key rotation must be a separately reviewed or included bounded management command
that validates every envelope before re-encryption, has dry-run and interrupted-rerun
safety, and retains older keys until all records have been rotated and verified.

## Concurrency and audit

Create locks the authenticated actor row and persists an actor/key digest and raw
request fingerprint in PostgreSQL; Redis replay is not the authority. Different
content under the same key returns 409. Every mutation revalidates current actor,
resource scope, terminal state and expected revision under a row-level PostgreSQL
lock. Each successful mutation and its safe domain-history event and synchronous
Audit event commit inside one transaction. Stale updates return 409. Completion and
cancellation cannot be repeated to generate extra events.

`FollowUp` is not a case file. No source content, protected diagnosis, document,
media or referral narratives are duplicated.

## Migration, rollback, and institutional decisions

`guidance_followups.0001_initial` adds independent tables and indexes only. It does
not modify the canonical baseline or alter preexisting source rows. Rollback of the
application should first disable the feature; dropping tables containing new audited
content should be treated as a destructive operation requiring an approved data plan.

Still requires GCO/DPO/Records approval: allowed categories and GSS coordination
boundaries, confidentiality classes, retention/hold/disposition policy, reassignment
recovery, key provisioning/rotation, and live-staging enablement. Do not invent a
retention period or seed synthetic follow-ups by migration.

## Parallel ownership

REM-1 #256 owns Appointment models, Notification event/transport, audit actions and
settings. FUP-1A's minimal integration overlaps only `audit/actions.py` and
`config/settings.py`, to be reconciled against merged staging before integration.
SVC-1 #258 owns Service Catalog and its API contract; this branch adds Follow-Up
OpenAPI endpoints, so `contracts/openapi.json` will require coordinated regeneration.
UAT-40 #257 is merged; seeder allocation and UAT report files are untouched.

FUP-1B can consume GET/POST/PATCH/POST lifecycle endpoints and typed errors,
but no frontend implementation is present. Future My Work and Notification changes
must be in isolated follow-up PRs.

## OPS-FINAL foundation repair

The audit target is `guidancefollowups.guidancefollowup`, consistent with the existing lowercase
letters/digits dotted target grammar. An invalid target previously rolled back every successful
creation; PostgreSQL lifecycle tests now execute the authoritative transaction. Lists and detail
also reject deactivated or non-Student recipients. Create retries check their durable replay before
rejecting a due date that has since passed. Threaded tests close their PostgreSQL connections.

The common migration registry pins all applied canonical migration bytes and explicitly registers
`guidance_followups.0001_initial` as a schema-only new-domain addition. It preserves the existing
pre-canonical history refusal and asserts a single graph leaf and no model/schema drift. REM-1's
independent registry entry must be retained when combining branches. This does not authorize a
staging reset, fake history, rewriting an applied baseline, or a deployment.

Verification during foundation repair: Ruff format/lint and 37 PostgreSQL-backed tests across the
Follow-Up lifecycle/security suite, canonical migration suite, capability dependencies and step-up
policy passed locally. Candidate commit and remote full-regression evidence are recorded in the
OPS-FINAL handoff; downstream workspace/notifications are separate dependent implementation slices.
