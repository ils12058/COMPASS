# ADR-035: Graduate Tracer Survey foundation

- Status: Accepted
- Date: 2026-09-18
- Scope: `compass.graduate_tracer`

## Context

COMPASS needs a focused backend foundation for the supplied five-page Commission on Higher
Education Graduate Tracer Survey (GTS). The supplied questionnaire was inspected directly and is
the source authority for COMPASS Graduate Tracer instrument schema version 1. This ADR does not
claim that the supplied PDF is the latest or current nationwide CHED revision.

The questionnaire contains graduate identity, education, training, professional examination,
employment, first-job, earnings, curriculum-relevance, competency, and free-text curriculum
feedback data. It also contains historical wording and an internally inconsistent first-job
question-number sequence. The final appendix asks the respondent for other graduates' names,
addresses, and contact numbers.

## Decision

Create one fixed `compass.graduate_tracer` domain. Reuse the existing `STUDENT` User identity;
do not introduce an ALUMNI role or duplicate alumni identity. Participation mutation eligibility is
an active STUDENT whose `student_lifecycle_status` is `GRADUATED`. CURRENT and FORMER
students cannot initiate, edit, or submit GTS data. If the lifecycle later changes, an existing
response remains owned by the same User UUID and remains owner-readable; mutation still requires
current GRADUATED eligibility.

Graduate Tracer does not require a current Academic Year, Individual Inventory,
StudentAffiliation, College, Appointment, Counseling Encounter, Exit Interview, Good Moral,
Feedback, CSM, or Service Catalog record. In particular, it does not call the current-student
Inventory prerequisite.

Use one `GraduateTracerResponse` root aggregate plus source-specific repeatable
`GraduateTracerEducation`, `GraduateTracerProfessionalExam`, and
`GraduateTracerTraining` child rows. Do not create a generic survey/question/answer engine,
campaign engine, Registrar integration, or alumni profile.

The response lifecycle is only `DRAFT -> SUBMITTED`. There is one response per Student and
instrument schema version. Schema version 1 is server-controlled by
`instrument_schema_version = 1`. The blank Institution Code and Control code printed on the
source are not collected or invented. GTS is not registered as an Institutional Forms
FormFamily/FormRevision because the supplied source provides no confirmed COMPASS/UCN/CNSC QMS
identity.

## Source fidelity decisions

General information preserves the supplied civil-status options, Male/Female sex options,
Region 1 through Region 12 plus NCR, CAR, ARMM, and CARAGA, and City/Municipality residence
location. Historical labels such as ARMM are retained for schema version 1 rather than silently
modernized.

The Q12 baccalaureate education table, Q13 professional examinations, and Q15a training/advance
study table are repeatable child rows. Professional-exam rating remains bounded text because the
source does not define one universal rating type.

Q14 has fourteen checkbox reasons displayed in separate Undergraduate/AB/BS and
Graduate/MS/MA/PhD columns. The printed "Others, please specify" is one shared free-text line
below the table and has no separate checkbox in either column. Therefore schema version 1 keeps
two independent fourteen-value reason lists and one shared `degree_other_reason`; it does not
invent two OTHER checkboxes or two column-specific other fields.

The employment source keeps Yes, No, and Never Employed distinct. Branch-specific answers are
cleared when a full DRAFT replacement makes them inapplicable. The source's fixed employment
status, business-line, place-of-work, job-level, salary, first-job-source, and competency choices
are retained as schema-v1 values rather than modernized master data.

The supplied source duplicates question number 24, shows question 25, refers to questions 26 and
27, and then visibly presents question 27 without a visible question 26. Internal fields therefore
use semantic names rather than question-number identities. No missing question is invented.
Reasons for accepting/changing a job are kept conditionally optional where the numbering and
branch sequence are ambiguous.

Because the source routes NO answers from the first-job branch toward that ambiguous later
job-history section, schema-v1 normalization preserves supplied `reasons_for_changing_job` and
its OTHER companion for EMPLOYED respondents rather than discarding them solely because
`first_job_after_college` or `first_job_related_to_course` is false. This preservation does not
make job-change reasons mandatory and does not assert that the missing printed question 26 has
been conclusively reconstructed.

Both "How long did you stay in your first job?" and "How long did it take you to land your first
job?" visibly include "3 years to less than 4 years" in the supplied page. Schema version 1
therefore permits that bucket for both semantic fields.

The final appendix requesting other graduates' names, full addresses, and contact numbers is
deliberately excluded. It is third-party personal data tied to a historical cohort request and is
not the authenticated respondent's own graduate outcome record.

## Profile prefill and historical snapshots

Creating the DRAFT performs a one-time convenience prefill from the existing Accounts profile
where semantics are clear:

- full name -> response-local name snapshot
- permanent address -> response-local permanent-address snapshot
- account email -> response-local email snapshot
- generic profile contact number -> Telephone or Contact Number(s) snapshot
- date of birth -> response-local birth date
- civil status -> prefilled only when it maps to one of the supplied closed source options

The generic profile contact number is not copied into the separate GTS Mobile Number field because
the current profile does not establish that it specifically represents a mobile number. The
Student may correct all GTS-local draft values without mutating Accounts/Profile. Later Profile,
email, lifecycle, or other-domain changes never rewrite the response. SUBMITTED values are
immutable.

## API and authorization

Use six focused operations:

- POST `/api/v1/graduate-tracer/me` to ensure/create the schema-v1 DRAFT and perform one-time
  prefill
- GET `/api/v1/graduate-tracer/me` to read the owner's existing DRAFT or SUBMITTED response
- PUT `/api/v1/graduate-tracer/me` for deterministic full replacement of an existing DRAFT,
  including repeatable rows
- POST `/api/v1/graduate-tracer/me/submit` for final source-aware validation and submission
- GET `/api/v1/graduate-tracer/responses` for paginated Head Guidance access to SUBMITTED rows
- GET `/api/v1/graduate-tracer/responses/{response_id}` for Head Guidance submitted detail

No delete, reopen, Head edit, impersonation, or Student-controlled status/schema fields are added.

Capabilities are narrow:

- STUDENT: `graduate_tracer.view_self`, `graduate_tracer.manage_self`
- HEAD_GUIDANCE_COUNSELOR designation: `graduate_tracer.view`

Ordinary Counselor, Guidance Services Staff, IT_ADMIN, and DPO receive no raw GTS content access
by default.

## Draft and submission validation

DRAFT save allows incomplete root answers but validates supplied source choices and meaningful
repeatable rows. PUT replacement is deterministic and transactionally replaces child rows, so
repeated saves do not append duplicates. Employment branch replacement clears now-inapplicable
answers.

Submission performs completeness and branch validation in the service layer rather than encoding
the full questionnaire as giant database checks. Schema-v1 completeness requires core respondent
classification, at least one meaningful baccalaureate education row, employment state, and the
applicable employment branch. Because the printed source does not mark every contact blank as
required, permanent address, email, telephone, and mobile are not independently made mandatory
solely by digital implementation. OTHER-dependent fields are validated when the corresponding
source option exists. Q14's one shared other line is preserved without inventing checkbox
semantics.

SUBMITTED is immutable. Repeat submission returns the already-submitted response without creating
a second successful submission audit event.

## Audit and privacy

Audit records only structural metadata such as instrument schema version and lifecycle transition.
It does not copy names, addresses, contact information, DOB, demographics, education, exams,
training, employment, occupation, business line, salary, reasons, competencies, or free-text
suggestions.

No reports, employability analytics, dashboards, exports, AI classification/scoring, PDF
generation, notification/email campaign, generic campaign infrastructure, or third-party alumni
contact collection is included in this foundation.
