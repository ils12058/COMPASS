# Good Moral email contract

Both events use `good_moral_request` with source UUID equal to the GOOD_MORAL
target/request UUID. The actual request Student must still have active Student
self-access through `get_mine` and `good_moral.view_self`. The authenticated
`/portal/good-moral/{id}` page uses the existing self endpoint. No email link grants
access or bypasses login/MFA. Ownership/capability changes remove details/actions
and cancel an already-rendered plan before SMTP.

## Assisted initiation

Only the existing GCO_ASSISTED producer creates `good_moral.request_initiated`.
The email checks durable assisted origin and initiator ID. Explicit self-service
sources cannot be reinterpreted as assisted; ordinary Student self-creation still
produces no assisted event. Legacy unspecified provenance retains generic fallback
without a guessed actor or link.

Requested/Ready states can receive a truthful creation notice with current status,
never an issuance claim. Issued/cancelled initiation notices suppress as obsolete.
No new request stage, preparation mutation, payment assumption or eligibility rule
is added. Existing F4 and F6 source creation/preparation/printing remain unchanged.

## Issuance

`good_moral.issued` requires actual ISSUED state, aware nonfuture issuance timestamp,
issuer and form provenance, variant-consistent form family/template identity and
a currently supported template version. Current-student F4 supports existing
versions 1/2; graduate F6 supports version 1. Missing/inconsistent legacy proof
falls back without rich fields/action; REQUESTED/READY/CANCELLED cannot be mailed
as issued. Source provenance comes from the existing issuance transaction, not a
new receipt/certificate store or Notification metadata.

Version 1 rows are fixed request label, issued status and institution-local issuance
date. There is no canonical request reference code, so one is not invented. No
applicant/Student names, institutional IDs, contact details, academic records,
standing, certificate body, issuer name, OR number/date/amount, verification claim
or internal remarks enter the templates, subjects, preheaders or logs.

The physical Registrar dry-seal workflow is outside the recorded status. Proposal
wording alone is not independent confirmation of an instruction suitable for
email. Messages therefore direct the Student to COMPASS and available next steps;
they do not claim payment verification, certificate collection, Registrar handoff
completion or automatic dry-seal tracking.

F4/F6 regressions exercise current/graduate ownership and the existing lifecycle.
Changing excluded receipt/name fields does not alter presentation equality;
changing actual issuance provenance/date/status, owner/access, profile or URL does.
No certificate rendering, issuance, feedback opportunity, preparation or OR-integrity
feature is modified. Pending durable Notification/delivery identities are retained.
