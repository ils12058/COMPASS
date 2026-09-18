# ADR-034: Customer Feedback and Client Satisfaction Measurement foundation

## Status

Accepted for the Feedback foundation.

## Context

The supplied `Customer feedback.pdf` was visually inspected page by page. It contains two distinct
feedback instruments that share one source file but do not share one questionnaire schema or one
controlled-form identity.

Page 1 is the Guidance, Testing and Admission Office Customer Feedback Form. Its confirmed
controlled identity is `CNSC-OP-GTA-01F14`, Revision `0`, Page 1 of 1. The historical `GTA`
segment remains part of the QMS identity even though the current office context is the Guidance and
Counseling Office. The source does not establish that this form has been withdrawn.

Page 2 is the Client Satisfaction Measurement (CSM), headed “HELP US SERVE YOU BETTER!”. It contains
client type, sex, age, region of residence, service availed, Citizen's Charter questions CC1-CC3,
service-quality dimensions SQD0-SQD8, optional suggestions, and optional email. The supplied source
does not establish a controlled QMS code or revision for this instrument.

## Decision

### One Feedback domain, two fixed aggregates

Create one `compass.feedback` application with two explicit response aggregates:

- `CustomerFeedbackResponse` for the controlled F14 Customer Feedback Form; and
- `ClientSatisfactionResponse` for the fixed CSM schema version 1.

The two instruments remain technically separate. COMPASS does not introduce a generic survey
builder, configurable question table, campaign engine, or generic `FeedbackResponse` containing
unrelated nullable fields.

### Controlled Customer Feedback Form

Institutional Forms registers the confirmed family/revision:

- family key: `customer_feedback`
- official code: `CNSC-OP-GTA-01F14`
- official revision: `0`
- internal schema version: `1`
- initial status: `ACTIVE`

Schema version 1 is listed in `SUPPORTED_SCHEMA_VERSIONS`. Every F14 submission calls
`require_active_supported_form_revision("customer_feedback")` and freezes that exact
`FormRevision` on the response. The controlled code is not rewritten to a GCO or UCN code.

The fixed F14 model preserves the source service selections, Guidance Counselor contact question,
Student Assistant / Clerk-Personnel fallback, office visit count, six personnel ratings, transaction
duration, five office/environment ratings, overall customer-experience satisfaction, additional
feedback, future-service improvement text, and identifying/contact fields. The Excellent through
Poor scale is kept separate from the CSM SQD scale.

The paper source visibly contains “Signature over Printed Name.” This foundation does not represent
a COMPASS login as a handwritten, legal, cryptographic, or third-party electronic signature. No
signature image, PKI, or e-signature provider is introduced. Authenticated session provenance is
retained in the normal Audit Trail, while the response saves the respondent-name snapshot requested
by the source form.

For the initial digital channel, the authenticated Student's current Accounts profile may supply a
one-time fallback for name, address, and mobile number when the submitted source field is blank.
The saved response contains response-local snapshots only; later Profile changes do not rewrite it.
`course/year` remains bounded F14-local text and does not create Registrar or enrollment semantics.

### Client Satisfaction Measurement

CSM is not registered in Institutional Forms because its controlled QMS identity is not established
by the supplied source. It is not assigned F14 or any invented GCO, UCN, or CSM code.

`ClientSatisfactionResponse` stores a server-controlled `instrument_schema_version = 1`. This is a
COMPASS interpretation version only, not a QMS `FormRevision` or document-template version.

Schema version 1 stores the source client types Citizen, Business, and Government (Employee or
another agency); source sex choices Male and Female; respondent-supplied age; bounded region and
service-availed text; CC1-CC3; explicit SQD0-SQD8; optional suggestions; optional respondent-supplied
email; and server-controlled submission time. N/A is a real SQD value, represented explicitly as
zero rather than null or omission.

For the COMPASS digital channel, the core CSM answers are required to produce a complete submitted
response. This is a COMPASS schema-version rule; the source explicitly labels only suggestions and
email as optional. CC1 answer 4 requires N/A for both CC2 and CC3, while CC1 answers 1-3 require
substantive CC2 and CC3 answers.

### Authentication, identity, and lifecycle

Both initial submission endpoints require an authenticated active account whose primary role is
`STUDENT`, with the instrument-specific submission capability. Student lifecycle is not an
eligibility gate: CURRENT, GRADUATED, and FORMER Students may submit. Neither instrument requires a
current Academic Year, Individual Inventory, StudentAffiliation, Appointment, Counseling Encounter,
Good Moral request, Referral, Call Slip, or Exit Interview.

F14 is identifiable by source design because it requests name, course/year, address, and mobile
number. It does not retain a live User foreign key; its saved identifying values are response-local
snapshots and the normal Audit Trail separately records the authenticated actor.

CSM is data-minimized. It stores no User/Student foreign key, name, student number, lifecycle,
Inventory, Academic Year, affiliation, College, or account email. Authentication authorizes the
channel but does not become a response field. Optional CSM email is supplied voluntarily by the
respondent and is never automatically copied from `User.email`.

### Service and workflow separation

F14 service selections and CSM `service_availed` are source fields, not Service Catalog foreign
keys. The F14 source includes GTA-era Admission and Testing services, so binding those choices to the
current COMPASS catalog would change source meaning. Neither instrument creates or depends on an
Appointment or Counseling record.

Both responses are one-shot and final on successful POST. Multiple submissions are allowed because
they may represent different visits or transactions. No status workflow, reopen/edit endpoint,
delete endpoint, uniqueness-by-user rule, or human reference number is added.

### Authorization and operational review

Students receive the narrow submission capabilities:

- `feedback.submit_customer_feedback`
- `feedback.submit_csm`

Head Guidance receives the raw-review capabilities through the
`HEAD_GUIDANCE_COUNSELOR` designation:

- `feedback.view_customer_feedback`
- `feedback.view_csm`

Ordinary Counselors, Guidance Services Staff, IT Admin, and the DPO designation receive no raw
Feedback content access by default. Read APIs are summary/detail separated so list responses avoid
unnecessary long free text and optional CSM email.

### Audit and privacy

Submission events are synchronously audited with the authenticated actor in the existing Audit Trail.
F14 Audit metadata contains only controlled-form provenance. CSM Audit metadata contains only its
instrument schema version. Questionnaire answers, demographics, identifying/contact snapshots,
ratings, optional email, and free text are not copied into Audit metadata.

### API and deferred work

The Feedback API exposes Student POST endpoints and Head Guidance read-only list/detail endpoints for
both instruments. No Student self-history is introduced because neither aggregate stores a live
respondent User relationship.

This foundation does not add a public/anonymous endpoint, QR/token intake, paper-encoding workflow,
analytics/dashboard calculations, PDF generation, exports, AI/sentiment/risk automation,
feedback-to-case/referral automation, notifications, or Service Catalog coupling. Those require
separate evidence and design decisions.
