# ADR-025: Counseling Shared Summary

## Context

COMPASS needs a narrow post-session communication that an assigned Counselor deliberately chooses
to disclose to the Student after a real Counseling interaction. Existing domains already separate
the annual Individual Inventory, Student-authored Routine Interview Intake, private assigned-Counselor
Routine Interview Evaluation, Appointment scheduling, completed Counseling Encounters, and the
E-Counseling/Daily provider boundary.

A Shared Summary must not collapse those boundaries. It is not a Counselor Evaluation, generic or
psychotherapy note, Case Record, transcript, recording, Daily telemetry, or automatically generated
session recap. In particular, private Routine Interview recommendations, special concerns, ratings,
and Student Intake content are never copied into it automatically.

## Decision

Add `CounselingSharedSummary` to the existing `compass.counseling` domain. Each record has a UUID,
a one-to-one `PROTECT` relationship to one completed `CounselingEncounter`, plain-text `content`, a
nullable `published_at`, and normal creation/update timestamps. The Encounter remains authoritative
for Student, assigned Counselor, delivery mode, and historical interaction context; no redundant
Counselor or publication-actor field is stored on the Summary.

The record is optional and exists only after a Counseling Encounter already exists. There is no
provisional Appointment-backed draft and no requirement that every Encounter receive a Summary.
Both IN_PERSON and ONLINE Encounters use the same model and service path. Daily rooms, meeting
telemetry, recording, and transcription are irrelevant to Shared Summary ownership.

State is derived rather than modeled as an enum. `published_at IS NULL` means draft;
`published_at IS NOT NULL` means published. Draft content may be empty while being edited. Publishing
is an explicit assigned-Counselor action, requires non-whitespace content, sets a server-authoritative
publication timestamp, and makes the text readable by the Encounter Student. Ordinary editing is
locked after publication. Repeated publication is idempotent and returns the already-published
resource without emitting another Audit event. Correction, versioning, superseding, deletion, and
Student acknowledgement are deferred.

Authorization requires both capability and resource relationship. Students receive only
`shared_summaries.view_self`; Counselors receive `shared_summaries.view_assigned` and
`shared_summaries.manage_assigned`. Capability alone never bypasses the Encounter relationship.
Head Guidance receives no designation-wide Shared Summary access; a Head who is the actual assigned
Counselor uses ordinary Counselor access. Guidance Services Staff, IT Admin, and DPO receive no
Shared Summary content capability by default.

Counselor endpoints are Encounter-nested. Student endpoints are self-facing under
`/counseling/me/shared-summaries` because Students do not otherwise receive general internal
Counseling Encounter access. Student reads return only published Summaries belonging to that Student
and expose only the deliberately published content plus small safe session context. Drafts and other
Students' records behave as not found.

Draft writes and publication lock the parent Counseling Encounter before the Shared Summary. This
provides a coordination point even for first-time draft creation while the database one-to-one
constraint remains the final uniqueness backstop. No Shared Summary response is stored in Redis.

Publication records exactly one `counseling.shared_summary.published` Audit event in the same
PostgreSQL transaction as the state change. The Summary UUID is the Audit target and metadata contains
only the Counseling Encounter UUID. Shared Summary text, excerpts, keywords, Routine content,
transcripts, and provider data are not copied into Audit. Draft saves are not audited.

Published historical Summaries remain readable to their Student even if the assigned Counselor later
becomes inactive. Current provider eligibility, Academic Year changes, affiliation changes, or
Service configuration changes do not rewrite or hide an already-published historical disclosure.

## Consequences

COMPASS gains a small, explicit, human-authored Counselor-to-Student disclosure without creating a
second counseling service, a generic notes platform, or an E-Counseling-specific record. The feature
has no frontend, AI generation, recording/transcription dependency, notifications, Student comments,
read receipts, rich text, attachments, Case Records, Referral, Call Slip, delete operation, or
published-summary correction workflow in this foundation.
