# ADR-031: Exit Interview Foundation

## Context

COMPASS must digitize the existing two-page CNSC Guidance and Counseling Office Exit Interview
without turning it into a Counseling Encounter, Routine Interview, approval workflow, generic survey
engine, or Student Information System feature.

The authoritative source is the inspected two-page Exit Interview form. It is a graduating Student
exit survey consisting of general information, significant learning experiences, career plans,
15 fixed self-assessment ratings, and 26 fixed College feedback ratings across seven categories.

The source has no visible human workflow reference number, no source-entered date field, and no
confirmed official QMS code/revision.

A separate client/domain clarification establishes that initiating an Exit Interview requires a
SUBMITTED Individual Inventory for the institution's current Academic Year. This prerequisite is an
Exit Interview domain rule and is independent of Service Catalog integration.

## Decision

### Domain ownership

Create the focused `compass.exit_interviews` domain.

The domain contains only:

- `ExitInterview`
- `ExitInterviewSelfAssessmentRating`
- `ExitInterviewCollegeFeedbackRating`
- `ExitInterviewReopenEvent`

All models use `default_permissions = ()`.

There is no GenericSurvey, GenericQuestion, GenericResponse, FormField, FormAnswer, dynamic form
builder, generic rating engine, or correction-workflow framework.

### Source-backed root data

The Exit Interview root uses UUID identity and binds:

- Student
- Academic Year
- the exact submitted current-year Individual Inventory used to satisfy initiation
- DRAFT/SUBMITTED status
- form-local historical Student/source values
- typed Section I choices
- seven fixed category comment fields
- final suggestions/recommendations
- first and latest successful submission timestamps
- ordinary created/updated timestamps

There is one Exit Interview per Student per Academic Year.

No human-readable Exit Interview reference number is invented.

No source date is invented. `created_at`, `first_submitted_at`, and
`last_submitted_at` are digital operational facts.

### No FormRevision/QMS registration yet

The inspected source copy has no confirmed official controlled-form code/revision.

Although the current FormRevision model permits nullable official identity, the operational
Institutional Form Registry is a QMS metadata surface and currently requires official code/revision
for registration.

Therefore this foundation:

- does not seed an `exit_interview` FormFamily
- does not create a FormRevision with fabricated/null QMS identity
- does not add a FormRevision FK to ExitInterview
- does not add Exit Interview to the controlled-form compatibility map

A future source/QMS clarification can add a forward migration and bind legitimate historical
FormRevision identity from that point onward.

### No Service Catalog integration yet

Exit Interview is conceptually a GCO service, but the current active Service Catalog requires
provider-role and delivery-mode semantics appropriate to provider-delivered services.

This Student self-service survey has no source-backed provider, appointment, or delivery mode.

Therefore this foundation deliberately does not:

- seed or activate `EXIT_INTERVIEW`
- fabricate Counselor/GSS provider roles
- fabricate IN_PERSON/ONLINE delivery
- change generic Service Catalog rules

This does not weaken the Inventory prerequisite described below.

### Mandatory current submitted Inventory prerequisite

Exit Interview initiation requires a submitted Individual Inventory for the current Academic Year as
an explicit domain prerequisite, independently of Service Catalog configuration.

The implementation must reuse the existing:

`require_current_submitted_inventory(student)`

resolver. Exit Interview must not duplicate current-Academic-Year/Inventory-status prerequisite
logic.

On first creation, the exact returned Inventory is bound to the Exit Interview. Its
`academic_year` becomes the Exit Interview Academic Year, and its
`course_currently_enrolled` and `major` are copied once as initial form-local values.

Initiation fails when:

- no current Academic Year is configured
- no Inventory exists for the current Academic Year
- the current-year Inventory is still DRAFT
- only a prior-year submitted Inventory exists

Current Academic Year configuration uses the repository-consistent 409 response.

Once the Exit Interview exists, the bound Inventory is provenance. Later Inventory changes never
rewrite the Exit Interview, and historical Student list/detail access is not re-gated merely because
the current Academic Year changes.

### One-time Accounts profile prefill

At first creation, use `get_person_profile_context(student)` exactly once.

Initial mapping:

- Name <- current full name
- Email Address <- current account email
- Civil Status <- current profile civil status
- CP <- current profile contact number
- Home Address <- trimmed current address when present, otherwise trimmed permanent address
- Age <- derived from current profile date of birth using institution-local creation date

If date of birth is absent, the form-local age starts NULL.

Age is stored only as the source-form value and is constrained to 0..150; User.age is not created.

The paper asks for Age, not DOB, so DOB is not copied into Exit Interview.

### Form-local editability and historical truth

After creation, the Exit Interview owns its copied values.

While DRAFT, the Student may correct the displayed form-local values, including name, age, civil
status, course, major, email, address, and contact number.

Those corrections do not update User, Account Profile, Inventory, StudentAffiliation, or other
records.

GET, PUT, submit, reopen, and resubmit never refresh saved form-local values from current profile or
Inventory.

### Section I exact typed structure

Academic program completion choices:

- According to schedule
- With some delay

The delay source asks for the number of extra terms. The model therefore uses one nullable positive
`extra_terms_count`; no semester/summer distinction is invented.

Delay reasons:

- Transferee
- Academic Failures
- Others (pls. specify)

OTHER requires its source-backed specification.

When completion is according to schedule, delay-specific data must be empty.

Significant learning experience choices:

- Independence
- Interpersonal Relations
- Intellectual Growth
- Spiritual Growth
- Responsibility
- Working under pressure
- Time Management
- Setting priorities
- Others, pls. specify

OTHER requires its source-backed specification.

Career Plans preserves the source's separate Work and Study checkboxes plus their subchoices.
Multiple source boxes may coexist; “no definite career plan yet” is not made artificially exclusive.

### Section II exact fixed ratings

The source contains 15 Self-Assessment items:

1. Pride and confidence in being from CNSC
2. Ability to maintain balance between academics & recreational activities
3. Awareness of the importance of holistic personal well-being
4. Ability to integrate knowledge with experience
5. Clarity of career goals
6. Self Esteem
7. Self-Awareness
8. Ability to cope with pressures
9. Ability to deal comfortably with people from different walks of life
10. Leadership
11. Communication Skills
12. Civic Mindedness
13. Initiative
14. Decision Making
15. Relationship with God

The source scale is:

- 5 Much enhanced
- 4 Enhanced
- 3 No Difference
- 2 Became Worse
- 1 I don't know

Persistence uses fixed item codes, one row per item, and rating range 1..5. Numeric zero is invalid
for Section II.

### Section III exact fixed ratings and unresolved zero

The source contains 26 College Feedback rows:

- DEAN: 5
- PROG CHAIR: 3
- FACULTY: 4
- CURRICULUM: 3
- GUIDANCE COUNSELOR: 4
- OFFICE STAFF: 4
- FACILITIES: 3

Each code has one fixed source-backed label. Category is derived from the item code rather than
persisted redundantly.

The printed legend defines:

- 5 Highly Satisfactory
- 4 Satisfactory
- 3 Average
- 2 Unsatisfactory
- 1 Very Unsatisfactory

However, every rating row visibly also includes numeric `0`, and the source provides no meaning for
that value.

Therefore Section III structurally permits 0..5, but this foundation does not assign any semantic
label to 0. It remains a source-visible value with unresolved meaning.

### Draft replacement and validation

Student draft editing uses a strict full replacement PUT rather than partial PATCH. This matches the
fixed source-form pattern and makes replacement of typed arrays/rating collections deterministic.

Server-owned fields such as Student, Academic Year, Inventory, status, timestamps, and correction
actors are never caller-controlled.

Drafts may be incomplete, but source-backed consistency applies immediately:

- unknown typed choices are rejected
- duplicate choices/item codes are rejected
- OTHER requires its corresponding text
- delay data must be consistent with the completion choice
- Work/Study subchoices require their corresponding career mode
- Section II ratings are 1..5
- Section III ratings are 0..5

The source instructs the Student to answer all items honestly/objectively. At submission, all 15
fixed Self-Assessment items and all 26 fixed College Feedback items must therefore be present exactly
once. Optional comments/text are not made artificially mandatory.

### Lifecycle

Only two states exist:

- DRAFT
- SUBMITTED

First submission:

- DRAFT -> SUBMITTED
- sets `first_submitted_at`
- sets `last_submitted_at`
- freezes Student editing
- appends safe Audit

Repeated submit while already SUBMITTED returns the unchanged record.

Authorized reopen:

- requires Head Guidance authority and a nonblank reason
- SUBMITTED -> DRAFT
- preserves all source answers/snapshots and submission timestamps
- appends an `ExitInterviewReopenEvent`
- does not re-prefill

Resubmission:

- DRAFT -> SUBMITTED
- preserves `first_submitted_at`
- advances `last_submitted_at`
- appends a resubmission Audit event

Each reopen is a separate child event containing actor/time/reason so repeated correction cycles do
not overwrite or falsify earlier provenance.

### Authorization and privacy

Capabilities:

- `exit_interviews.view_self`
- `exit_interviews.manage_self`
- `exit_interviews.view`
- `exit_interviews.reopen`

Assignments:

- Student role: view_self, manage_self
- HEAD_GUIDANCE_COUNSELOR designation: view, reopen
- ordinary Counselor: no broad Exit Interview content access
- Guidance Services Staff: no broad Exit Interview content access
- IT Admin: no Exit Interview content access
- DPO: no Exit Interview content access merely by designation

Capability names express action, not scope implementation.

Student self routes contain no arbitrary student_id selector.

Head list is a summary projection and does not bulk expose answer/rating/comment content. A Student
DRAFT is a private working response: Head Guidance may see its existing summary metadata in the review
list, but full response detail is available to Head Guidance only while the record is SUBMITTED.

Reopening returns the record to Student-private DRAFT correction state. While it remains DRAFT, Head
Guidance full detail is unavailable; after the Student resubmits, full Head review becomes available
again. The Student owner retains full DRAFT detail under the existing self-service and lifecycle rules.

Head detail remains purpose-built operational oversight. No CSV/export/analytics/staff-ranking API is
introduced.

### Audit and activity

Audit actions:

- `exit_interview.created`
- `exit_interview.submitted`
- `exit_interview.reopened`
- `exit_interview.resubmitted`

Target type is `exitinterviews.exitinterview`.

Audit metadata contains only structural facts such as Academic Year, lifecycle transition, and
optional reopen-event ID.

Audit never stores ratings, answers, comments, career choices, suggestions, address/contact,
course/major, or reopen reason.

Draft saves do not create noisy Audit events.

My Activity and Security Activity are deliberately unchanged in this slice because their current
closed-world ownership projection does not need expansion merely to implement the domain lifecycle.

### Explicit non-coupling

Creating, saving, submitting, reopening, or resubmitting an Exit Interview does not create or modify:

- Appointment
- CounselingEncounter
- RoutineInterview
- Referral
- CallSlip
- Case Record
- Good Moral record
- Service Catalog record
- FormRevision

Good Moral is not an Exit Interview prerequisite in either direction.

The original Exit Interview foundation introduced no notification/email. ADR-046 later added the
mandatory privacy-safe `exit_interview.reopened` Notification/email for a successful SUBMITTED ->
DRAFT correction reopen; ADR-046 remains authoritative for its delivery, privacy, and deduplication
semantics.

No PDF output, GeneratedDocument persistence, sentiment analysis, analytics, Graduate Tracer, Alumni
workflow, Customer Feedback/CSM model reuse, or SIS expansion is introduced.

### API

Student operations:

- POST `/api/v1/exit-interviews/me/current`
- GET `/api/v1/exit-interviews/me/current`
- PUT `/api/v1/exit-interviews/me/current`
- POST `/api/v1/exit-interviews/me/current/submit`
- GET `/api/v1/exit-interviews/me`
- GET `/api/v1/exit-interviews/me/{exit_interview_id}`

Head Guidance operations:

- GET `/api/v1/exit-interviews`
- GET `/api/v1/exit-interviews/{exit_interview_id}`
- POST `/api/v1/exit-interviews/{exit_interview_id}/reopen`

Static self routes precede UUID routes.

### Validation and CI

The targeted workflow keeps every existing regression suite and adds
`tests/test_exit_interviews.py`.

Coverage includes source enum fidelity, 15/26 fixed rating cardinality, undefined Page-2 zero,
current-year submitted Inventory prerequisite, one-time prefill, draft replacement, submission,
reopen/resubmit history, authorization/privacy, Audit safety, no domain coupling, concurrency, DB
constraints, API/OpenAPI, and policy grant counts.

No new runtime dependency is required. The full backend suite remains unnecessary by default.

## Consequences

COMPASS gains a source-faithful graduating Student Exit Interview domain with a small correction
lifecycle and defensible historical snapshots.

The explicit current submitted Inventory prerequisite is enforced through one existing canonical
resolver rather than duplicated policy logic.

The design preserves the source's unresolved rating value 0 without inventing meaning, preserves
identifiable institutional feedback behind narrow authorization, and avoids speculative Service
Catalog/QMS/SIS/generic-survey architecture.
