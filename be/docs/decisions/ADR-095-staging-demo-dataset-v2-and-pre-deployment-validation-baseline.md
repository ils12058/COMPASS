# ADR-095: Staging demo dataset v2 and pre-deployment validation baseline

## Status

Accepted. Refines the dataset-content portions of [ADR-068](ADR-068-staging-demo-dataset-seeder.md).
ADR-068 remains the historical architecture and operational safety decision. Decisions through
ADR-094, including encrypted content, optional Routine Inventory provenance, Counselor provider
qualification, and runtime-only E-Counseling infrastructure, remain in force.

## Context

Eleven Students cannot meaningfully demonstrate pagination, College scopes, operational queues,
or report variation. Recent domain changes also left stale tests and an Availability contradiction:
the seeder preserved an institutional schedule but booked hard-coded times against it. A confidential
content cutover needs a genuinely green test baseline and representative encrypted form data first.

## Decision

Dataset v2 is a deterministic, source-controlled world of 57 Students: the original 11 recognizable
rich personas and 46 population Students. Two population Students have compact secondary Routine
stories; most have only account/profile, affiliation, and annual Inventory. Eight population
Students have a single lightweight Appointment. No runtime Faker or random population generation
is used. Identity, background answer fixtures, and orchestration are separate modules.

The lifecycle composition is 46 CURRENT, eight GRADUATED, and three FORMER. Enrollment origins span
the synchronized CCMS, CAS, CBPA, and COED catalog and eight population Programs. CURRENT Students
have 34 submitted current Inventories, eight drafts, and four missing. Drafts have early, partial,
and nearly complete depths. Ordinary support profiles outnumber special indicators. Selected
older-year Students have historical Inventories. Family, sibling, education, organization,
transportation, household, health, support, and personal narratives use the current instrument.
Exit matrices, Tracer employment paths, Routine forms, Profile, Feedback and CSM also have variety.

V1 upgrades are additive: original identities, passwords, narratives, natural keys, idempotency keys,
and scenario markers are retained. The legacy `demo-seed-v1` idempotency namespace intentionally
continues to identify the same records. Complete v1 history remains the historical completeness
boundary; missing v2 population history is entered separately through owning services, per Student,
in an atomic unit that restores the current Academic Year before commit. An established graduate
is never temporarily returned to CURRENT to manufacture missing history. Conflicting identity or
academic provenance fails closed. Existing forms, including live edits and draft progression, are
reused without template replacement. Compatible prior records are not rewritten merely for v2.

Appointments use the ordinary `list_bookable_slots` service, then normal creation. Search starts
on the desired story date and checks that day plus four following calendar days, excluding demo
non-working days and the anchor, preserving the past/future side of the anchor. It chooses the
nearest start to the desired local time with the earlier start as tie-breaker. Discovery uses
current Service configuration, selected-provider qualification, office/provider Availability,
exceptions, duration, Inventory prerequisite, and existing reservations. Terminal actions and
Appointment-backed encounters follow the selected interval. No slot produces a scenario/provider/
mode/window conflict, with no schedule replacement. Empty schedules may receive demo defaults;
existing weekly windows remain intact. The PostgreSQL advisory lock and bounded-unit recovery stay.

All eight domain keyrings are verified by encryption/decryption before synchronization or account
writes. Keys are supplied by the operator; the seeder never generates or prints them. Owning
services validate and encrypt form content. Tests check normal reads and independently persisted
ciphertext, including confidential Inventory children. No plaintext model fields are reinstated.

E-Counseling gets real eligible ONLINE Appointments but no Daily rooms, tokens, webhook receipts,
recordings, transcripts, or Spaces objects. Seeding never contacts external providers, PSGC,
Turnstile, storage, or the PDF renderer. Existing in-app notifications are useful; only seed-caused,
never-attempted email intents are removed before commit. Runtime email behavior is unchanged.
No retention period, destructive disposition approval, or institutional governance authority is
manufactured. Audit events keep actual execution time even when business records are back-entered.

The full backend suite must report zero failures and errors before this slice is considered ready.
Stale tests are corrected only against established contracts; production locking defects are fixed
with explicit row ownership. Closed typed errors and generated OpenAPI remain protected.
No deployment, key provisioning, rotation, provider provisioning, or live cutover belongs here.

## Consequences

The dataset is large enough for the default 20-row Inventory roster to paginate, for both regular
Counselors to have meaningful scopes, and for reports and encrypted projections to show varied
results. It remains cheap enough for regular backend validation, and reruns preserve operator and
Student changes. Source-controlled academic years and the supported anchor window still limit
when this particular demo world can be used; a new academic period needs a deliberate revision.
