# Faculty authorization, privacy and institutional decisions

## Authority matrix

| Actor/state | Exact confirmation | New submission | Own projection | GCO/clinical APIs |
| --- | --- | --- | --- | --- |
| Active Faculty, usable managed home, required capabilities, explicit current approved evidence and actual session | Only under approved lookup scope/rate bounds | Only under approved digital form, eligibility and matching lookup policy | Immutable submitter ownership and approved projection/scope | Denied |
| Faculty with own-read only | Denied | Denied | Allowed only if remaining policy/session/home predicates pass | Denied |
| Faculty with stale role/activity/session, missing or inactive home | Denied | Denied | Denied | Denied |
| Any other role, including malformed Faculty capability GRANTs | Denied | Denied | Denied | Existing owning-domain rules unchanged |
| No installed institutional policy provider | Denied | Denied | Denied | Existing GCO behavior unchanged |

The role ceiling permits exactly `referrals.submit_self` and
`referrals.view_submitted_self`; it grants no broad `referrals.view/manage` or other
business capabilities. Submission requires own-read as a dependency, so revoking
own-read also suppresses submission. No role/designation, raw override, shared
College, notification or confirmation value replaces source-domain authorization.

## Approval contract — deliberately no live activation

`get_approved_lookup_policy()` and `get_approved_submission_policy()` return `None`.
There is no settings/environment switch, activation endpoint, automatic seed or
command that converts technical readiness into institutional approval.

A future separately reviewed provider must resolve verified institutional evidence,
effective dates, explicit eligible Faculty UUIDs, permitted Student College UUIDs,
the exact disclosure/capture contract and a matching successful Audit decision.
Both frozen policy objects bind their content digest to an existing
`referral.faculty.policy.recorded` event with `decision=APPROVED`, policy kind,
version and evidence reference. Submission additionally binds the exact lookup
policy digest and distinct eligibility/own-projection evidence. An Audit row alone
does not install a provider; a provider without matching approval Audit is denied.

The provider is an institutional trust boundary, not a document-signature verifier:
this slice does not claim that an arbitrary evidence string authenticates a real
GCO/UCN decision. The future adapter and approval-recording custody must be reviewed
after the decisions below are actually made. Tests create only isolated synthetic
Audit/policy fixtures and patch the provider in that test process.

## Exact confirmation contract

Only a complete normalized institutional identifier is accepted: trim and existing
case normalization, maximum 64 characters. There is no name/prefix/substring query,
pagination, account directory, contact information, lifecycle label, academic
history or Guidance record lookup. One eligible exact identity returns only the
approved display name and a bounded confirmation reference. Nonexistent, inactive,
wrong-role, out-of-policy, unplaced and retired-placement Students return the same
negative DTO with no distinguishing reason.

The existing Redis limiter counts every approved lookup attempt by authenticated
actor and trusted server-derived client IP. Limits/window are part of the approved
lookup policy; no production rate is guessed here. Keys hash the subject and never
contain the submitted Student identifier. Redis failure always denies this privacy
operation, even if another service's generic limiter is configured fail-open. 429
reports Retry-After; 503 reports temporary unavailability without Student facts.

The confirmation is a Django-signed, versioned purpose-specific value bound to the
Faculty UUID, Student UUID, current Faculty home version, Student identity revision,
placement revision, lookup-policy digest and server issuance time. The approved
deadline is at most the technical 15-minute upper bound. It is signed, **not
encrypted**; its bounded UUID/revision metadata is part of the proposed disclosure
contract and needs privacy approval too. It contains no reason, name or contact data.
It cannot authenticate a user or grant access without the actual current session.

New submission rechecks current Student eligibility/placement, actor, actual session,
managed home, policy, signature and deadline. Edited/expired/foreign-actor references
fail uniformly. The value lives only in the FAC-3 form's memory: never a URL, log,
analytics, persistent browser storage or an Audit metadata field.

## Institutional decision register

| ID | Still required | Current safe behavior / owner |
| --- | --- | --- |
| FAC-D1 | Digital F3 authority, exact capture mapping, signature requirement and source PDF treatment | UCN/QMS and GCO; no submission provider installed; no typed-name-as-signature claim |
| FAC-D2 | Eligible Faculty, dual-capacity personnel and affiliation requirements | UCN identity/HR and GCO; implemented contract requires explicit Faculty IDs and active managed home |
| FAC-D3 | Exact identifier, display-name disclosure, signed reference metadata, expiry/rates and abuse handling | GCO/privacy; confirmation provider absent and endpoint denied |
| FAC-D4 | Missing/conflicting placement and actual triage ownership | GCO/SAR; unresolved fails safely, no Faculty-home or Head fallback |
| FAC-D5 | Actual acknowledgment actor, transition, received-at meaning and Faculty wording | FAC-4/GCO; submission leaves receipt unset |
| FAC-D6 | Administrative closure criteria and actual event/actor | FAC-4/GCO; no closure field or inferred clinical outcome |
| FAC-D7 | Own list/detail fields, exceptional void visibility, historical read eligibility and retention | GCO/privacy; separate approved projection evidence; voided records omitted/404 pending safe contract |
| FAC-D8 | Whether any Faculty/GCO/Student notifications are appropriate and what they disclose | NOTIF and GCO/privacy; none emitted automatically |
| FAC-D9 | Academic contact self-attestation wording, values and evidence limitations | GCO; no contact-basis field, roster or verification claim introduced |
| FAC-D10 | Student transfer/SAR historical record access and routing treatment | GCO/SAR; current GCO scope unchanged, saved College is provenance only |

Technical tests cannot satisfy these institutional decisions. No institutional
approval, privacy sign-off, UAT or live deployment authority is claimed.
