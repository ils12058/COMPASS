# ADR-075: Explicit Exit Interview admission and graduation Good Moral

## Status

Accepted. Refines the admission and non-coupling decisions in ADR-031 and the F4
creation prerequisite in ADR-033. Their other source-form, privacy, snapshot,
issuance, historical-access, and correction decisions remain authoritative.

## Context

The source Exit Interview is a graduating Student exit survey. Baseline Student
self-service capabilities and CURRENT lifecycle alone did not establish that GCO
had instructed a particular Student to complete it. Ordinary current Students
could therefore start the workflow. The office process requires explicit GCO
admission and a submitted Exit Interview before graduation-related Good Moral.
Ordinary F4 requests and legacy graduates' F6 requests have different prerequisites.

## Decision

### Opportunity, not a global lifecycle

Add `ExitInterviewOpportunity`, with one row per Student and Academic Year.
Accounts retain CURRENT, GRADUATED, and FORMER; no GRADUATING lifecycle is introduced.
GCO's workflow authorization is not a Registrar/SIS fact and is never inferred
from free-text year level, certificate text, or a client flag.

The immutable source is GRADUATION or MANUAL. GRADUATION asserts the office's
current graduation workflow; MANUAL admits an exceptional Exit Interview without
asserting graduation or imposing a Good Moral prerequisite.

States are OPEN, COMPLETED, and REVOKED. Actor references, opening/completion/
revocation timestamps, a bounded operational note, and ordinary timestamps preserve
operational provenance. Unique Student/year and structural status/source constraints
prevent ambiguous or invalid rows. Opportunities are never deleted by these actions.

Opening the identical OPEN opportunity is idempotent. Different source or note
conflicts instead of silently changing an existing admission. A REVOKED opportunity
can be explicitly reopened with its original source; its previous transitions
remain in Audit. A COMPLETED opportunity cannot be opened or revoked through the
admission API: controlled correction uses the existing submitted response's reopen.
An already submitted legacy response also uses controlled correction, rather than
fabricating a new admission.

### Least-privilege authority and API

`exit_interviews.manage_opportunities` is granted only to the existing
HEAD_GUIDANCE_COUNSELOR designation. It requires `accounts.view` for Student
selection, and does not grant identifiable answer access. Counselors, Guidance
Services Staff, IT Admin, DPO, and Students receive no new baseline grant. Existing
`exit_interviews.view` and `exit_interviews.reopen` boundaries stay intact.

Purpose-built APIs list/search opportunities, select current Students using the
shared organizational Student lookup, open, inspect, and revoke opportunities.
An explicit Academic Year may be selected; omission selects the configured current
year and the response always returns its provenance. Notes and operational actors
are confined to the authorized operational projection.

`GET /exit-interviews/me/status` returns a typed 200 projection for missing,
open, completed, revoked, and existing workflows, including start/edit availability,
current response summary, historical presence, Inventory prerequisite, and graduation
Good Moral blocking state. An unconfigured current year is represented by null year;
historical access remains usable. Existing GET current/detail contracts keep their
record semantics. Detail adds server-owned `can_edit`.

The session's `exit_interview_workspace_available` reflects an OPEN current-year
opportunity or any owned response, behind self-view capability. Navigation consumes
this server state. Direct self URLs explain missing admission and remain read-only
where appropriate. Backend checks always control mutations.

### Admission, ongoing work, and historical compatibility

A new current response requires an active CURRENT Student, manage_self capability,
exact canonical submitted current Inventory, and OPEN opportunity for that same year.
The response records a nullable one-to-one opportunity reference. New admissions
always populate it; migrations leave every existing reference null.

For an admitted, never-submitted draft, OPEN remains necessary for edits/submission.
Revocation withdraws admission and stops those mutations while preserving the response
and its historical visibility. Reopening the same revoked opportunity can resume it.
Successful submission completes the matching OPEN opportunity in the same transaction.
There remains one response per Student/year, so completed admission cannot create a
second response.

Existing pre-opportunity drafts remain editable and submittable under their original
account/lifecycle rules with a null admission reference. No fake opportunities or
GRADUATION classifications are backfilled. Existing current response resolution
precedes fresh Inventory/admission checks, since its saved Inventory is provenance.
An explicitly opened matching opportunity may be completed when a legacy draft is
submitted, without manufacturing admission history during migration.

A Head Guidance controlled reopen changes SUBMITTED to DRAFT and remains the
correction authority. The original COMPLETED opportunity does not need replacement
or reopening. Current Students may correct and resubmit an owned reopened response,
including its historical Academic Year through existing record-addressed APIs.
Self-view and history never depend on OPEN, current Inventory, or CURRENT lifecycle.
GRADUATED and FORMER Students retain permitted historical access.

### Graduation F4 only, with saved prerequisite provenance

The original ADR-031 statement, "Good Moral is not an Exit Interview prerequisite
in either direction," is refined: Good Moral never gates Exit Interview, and Exit
Interview is not a universal Good Moral prerequisite.

For a new CURRENT Student F4 request, a GRADUATION opportunity
for the exact Inventory Academic Year requires a matching same-Student/year
SUBMITTED Exit Interview with successful submission provenance. Not started,
initial DRAFT, and reopened DRAFT all block creation with
`good_moral_exit_interview_required` and an actionable message.

MANUAL, missing, and another-year opportunities do not impose this prerequisite.
Revocation withdraws Exit Interview admission without erasing its GRADUATION source
or reclassifying the Student as an ordinary F4 applicant. A revoked graduation
workflow therefore still requires a submitted matching response; Head Guidance can
explicitly reopen admission to let the Student complete it. The revocation
confirmation explains this consequence.
Ordinary F4 keeps current submitted Inventory, active affiliation, and existing
requirements. F6 remains available to GRADUATED Students without digital Exit
Interview, current Inventory, or affiliation; paper-era graduates are not backfilled.

Graduation F4 stores the checked opportunity, exact response, and successful
submission timestamp. Later controlled corrections cannot rewrite that checked
submission time. Existing request snapshots, issuance rules, and certificates are
unchanged; there is no retroactive re-gating of existing requests. Persistent exact
creation replay remains before new prerequisites, including after a response reopen.
A new creation key must satisfy the current prerequisite.

### Transactions, Audit, and scope

Opportunity open/revoke, initial admission, response edits/submissions, controlled
reopen, and F4 creation all lock the Student row before changing/checking workflow
state. Opportunity and response row locks then protect transitions. The Student
fence handles absent opportunity rows and serializes Good Moral creation against
both submission and reopen, as well as revocation against admission/submission.
Database uniqueness is a second boundary.

Audit adds opportunity_opened, opportunity_revoked, and opportunity_completed.
Metadata includes only Academic Year ID, source, transition, and, for completion,
response ID. Notes, ratings, answers, and identifiable free text are not copied.
Existing correction notification behavior from ADR-046 stays; opening/revocation
adds no email or notification. Demo scenarios explicitly admit their intended
responses as MANUAL without inferring graduation.

## Validation

Focused coverage exercises admission and wrong-year enforcement, capability grants
and dependencies, operational APIs, privacy, unique/idempotent opening, revocation,
legacy drafts/history, completion, controlled reopen/resubmit, graduation versus
ordinary/manual F4, matching-year submission, F6, persistent replay, saved prerequisite
provenance, and races around open/admission/revoke/submit/F4/reopen. Backend OpenAPI
and generated frontend clients stay synchronized. Frontend validation preserves the
existing lint, strict types, build, and targeted UI/access checks.
