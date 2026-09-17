# ADR-023: Interaction-specific Routine Interview

## Context

COMPASS needs a Routine Interview record without conflating four different concepts: the annual
Individual Inventory baseline, an Appointment reservation, the interaction-specific Routine
Interview form, and the Counseling Encounter that records what actually occurred.

The supplied historical two-page Routine Interview scan was inspected directly. Page 1 contains
student/header context, the source nature-of-visit choices `Called-in`, `Walk-in`, and `Referred`,
and Questions 1–3. Page 2 continues Questions 4–7, including the source concern checkboxes, and then
explicitly marks `GUIDANCE COUNSELLOR'S / COORDINATOR EVALUATION` with `NO WRITING BEYOND THIS
POINT`. That visual boundary is treated as a privacy and authorship boundary: Questions 1–7 are the
Student Intake; the following section is the assigned Counselor Evaluation.

The source evaluation has six established 1–10 adjustment ratings: academic, physical, social,
spiritual, financial, and emotional. Its `Others` line is represented conservatively as optional
text rather than inventing a seventh numeric rating. The source scan does not visibly establish a
reliable controlled-document code or revision, so COMPASS must not manufacture one.

## Decision

### Domain boundaries

`RoutineInterview` is one explicit typed domain record containing two grouped sections: Student
Intake and Counselor Evaluation. It is not a generic form/question/answer engine, annual profile,
Counseling Encounter, Case Record, Referral, Call Slip, generic note system, or E-Counseling
workspace.

The record binds the submitted current-year `StudentInventory` that governed creation. That
Inventory FK is historical context; an Academic Year switch after creation does not re-resolve or
rewrite an existing Routine Interview. Inventory owns current-year/submitted resolution through a
single prerequisite resolver.

Appointment-backed creation stores a one-to-one Appointment link, derives Student, Counselor,
Counseling Service context and delivery mode from that Appointment, and records `APPOINTMENT` as a
COMPASS digital workflow mode. `APPOINTMENT` is deliberately not represented as if it were a
checkbox printed on the historical source form. Direct creation supports only `WALK_IN`,
`CALLED_IN`, and `REFERRED` and never creates a fake Appointment.

A Routine Interview may exist before a Counseling Encounter because the latter represents the
completed real interaction. Counseling Encounter remains independently recordable without a Routine
Interview, including urgent `WALK_IN` occurrences for a Student who has no current Inventory.
Routine Interview therefore does not become a truth gate for occurrence recording.

### Controlled-form identity

The minimal Form Registry adds only family key `routine_interview`, title `Routine Interview Form`,
and application compatibility `routine_interview -> {1}`. No official Routine Interview revision is
seeded because the source does not establish one. `RoutineInterview.form_revision` is nullable.
Creation snapshots the active compatible revision when one exists; otherwise it proceeds with
`NULL`. A future QMS-confirmed revision affects new records only and does not silently rewrite
historical `NULL` records.

### Student Intake and privacy

Student Intake fields map explicitly to source Questions 1–7. Source checkbox concerns use a closed
typed array, including the highly sensitive `SUICIDAL_THOUGHT_TENDENCY` source choice. No diagnosis,
risk score, prediction, automated escalation, notification, or AI interpretation is inferred from
that answer.

A Student may read and replace their own Intake while it is a draft. The assigned Counselor may
know safe Routine/Intake status while the Intake is a draft but does not receive draft answer
content. After Student submission, the assigned Counselor may read the submitted Intake. Submission
locks the Intake and records a server-authoritative timestamp.

Draft validation and submission validation are intentionally distinct. `OTHER` may be selected with
an empty specification while drafting; removing `OTHER` clears stale specification text; submission
requires its specification. COMPASS does not invent a required-answer matrix or percentage-complete
state. Submission requires structural validity, confirmed conditional rules, and at least one
intentional Student response or concern.

### Counselor Evaluation and authorization

The six source ratings are nullable while drafting and constrained to 1–10 whenever supplied.
`other_adjustment`, `special_concern`, and `recommendations` remain explicit source-oriented fields.
No additional psychotherapy/progress/SOAP notes, diagnosis, or treatment plan is introduced.

Student responses never include Counselor Evaluation fields. Only the actual assigned Counselor may
read or mutate the Counselor side of a Routine Interview. Capabilities are necessary but never
replace the resource relationship. Students receive `routine_interviews.view_self` and
`routine_interviews.manage_self`; Counselors receive `routine_interviews.view_assigned` and
`routine_interviews.manage_assigned`. Head Guidance receives no extra blanket Routine-content
capability from the designation itself. GSS, IT Admin, and DPO receive no Routine-content capability
by default. A Head who is actually the assigned Counselor uses ordinary assigned-Counselor access.

This reflects the effective current policy: Academic Year configuration authority is supplied by the
Head designation; Routine Interview services do not require ordinary Counselors to hold
`academic_years.view` because historical Academic Year context comes from the bound Inventory.

### Encounter matching and finalization

Counselor Evaluation may be saved only after Intake submission and locks after finalization.
Finalization requires a completed matching Counseling Encounter. Identity and delivery mode must
match. Appointment-backed Routine Interviews additionally require an Encounter whose
`entry_mode == APPOINTMENT` and whose Appointment is exactly the same Appointment. Direct Routine
Interviews require an Encounter with no Appointment and with the same `WALK_IN`, `CALLED_IN`, or
`REFERRED` entry mode. These service checks deliberately close the pre-existing one-way Counseling
model constraint that merely says APPOINTMENT entry mode requires an Appointment link.

### Retry, concurrency, and audit

Appointment-backed ensure relies on PostgreSQL one-to-one uniqueness and transaction locking; full
Routine responses are not placed in Redis. Direct creation has no natural Appointment key, so it
requires an `Idempotency-Key`. Instead of Redis response-body replay, COMPASS persists only an
actor-scoped SHA-256 digest of the key plus the request fingerprint on the created Routine Interview.
The raw key and confidential Intake/Evaluation content are never persisted in that retry token.
Repeating the same request returns the same Routine UUID; reusing the key for different request
content is rejected. This avoids a post-commit Redis-completion window that could otherwise create
permanent duplicate drafts.

Student Intake replacement/submission and Counselor Evaluation replacement/finalization use
transactions and row locks. Safe Audit actions are `routine_interview.created`,
`routine_interview.intake_submitted`, and `routine_interview.evaluation_finalized`. Audit metadata
contains only safe identifiers/context and never Student answers, concern choices, suicidal-thought
selection, Counselor special concern, recommendations, or free-text contents. Draft autosaves are
not audited.

## Consequences

The Routine Interview remains understandable and source-faithful while enforcing the paper's
Student/Counselor boundary digitally. No delete/reopen/correction engine is introduced. No Routine
content is projected into generic Activity/Security Activity feeds.

E-Counseling/Daily.co, recording/transcription/consent, Shared Summary, Referral, Call Slip,
Case Records, Good Moral, Exit Interview, Customer Feedback/CSM, semester/term/SIS concepts,
printing/signatures, institutional branding/profile, generic forms, and automated clinical/risk
workflows remain separate future foundations.
