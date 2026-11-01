# Institutional review packet — FAC-D1 through FAC-D10

**Status: proposed rules for review; every institutional approval remains pending.**
Technical implementation, provisioning and passing tests grant no activation authority.
This packet consolidates the historical FAC-1/FAC-2 register and FAC-4 boundaries.
No approval reference, signature, official policy or real participant sign-off is supplied.
The authorities below are responsible roles to confirm, not named appointed approvers.

## Review agenda

UCN/QMS, GCO, institutional identity/HR, privacy/records and future SAR owners should
review the following ten decisions together. Record an actual accountable owner and
approved evidence for each; disagreement or missing evidence keeps the affected service
unavailable. Record allowed scope, effective/expiry dates, approval custody, revision and
withdrawal procedure. A later separately reviewed adapter must authenticate that evidence.
No environment switch, capability GRANT or inserted Audit row can substitute for it.

### FAC-D1 — digital form and signature authority

- Proposed rule: retain the controlled UCN-OP-GCO-01F3 Rev.1 mapping and authenticated
  Faculty authorship; the institution must decide whether this constitutes an authorized
  digital Referral Slip and whether any signature/attestation or rendering change is needed.
- Authority: UCN form/QMS authority with GCO and records/privacy review.
- Evidence: approved digital capture/retention specification, exact source mapping, signature
  rule and document disclosure decision. No typed name is treated as a digital signature.
- Contract/dependency: FAC-2 submission policy and canonical form revision; any change needs
  versioned schema/rendering review. Existing GCO paper source/PDF remains authoritative.
- Privacy: sensitive narratives remain encrypted; decide custody and permitted recipients.
- Approval: pending; no live submission provider.

### FAC-D2 — eligible Faculty identity

- Proposed rule: current authenticated single-primary-role FACULTY, active account and usable
  institutionally managed home; explicit eligible account scope. Decide temporary, dual-capacity,
  delegated and College-less cases rather than guessing a teaching roster.
- Authority: institutional identity/HR and GCO, with account-management custodian.
- Evidence: eligibility source/assignment process, allowed identity exceptions, removal rules,
  managed-home authority and periodic review. A home College is not a teaching assignment.
- Contract/dependency: FAC-1 managed affiliation and two-capability ceiling; FAC-2 provider.
- Privacy: minimum institutional account facts; no broad Student or administrative authority.
- Approval: pending; identity provisioning alone can operate without activating intake.

### FAC-D3 — exact Student confirmation and disclosure

- Proposed rule: bounded exact institutional identifier only, uniform ineligible/absent response,
  minimum display name and purpose-bound confirmation metadata; no directory/prefix search.
- Authority: GCO and privacy authority with identity-data owner.
- Evidence: approved identifier/display fields, signed-reference metadata disclosure, eligible
  Student scope, expiry/rate limits, abuse response and incident ownership.
- Contract/dependency: independent lookup provider, Redis privacy limiter and FAC-2 confirmation.
- Privacy: the signed value is not encrypted; its UUID/revision metadata needs explicit review.
  It is not a login/access token and stays in component memory.
- Approval: pending; actual provider returns None.

### FAC-D4 — Student placement and intake routing

- Proposed rule: current authoritative StudentAffiliation determines Student College; CAS
  Faculty may refer an approved CCMS Student. Missing/conflicting/retired placement fails safely
  until real triage responsibility is approved. Faculty home never selects GCO destination.
- Authority: GCO, organizational-data custodian and future SAR authority.
- Evidence: authoritative placement source, conflict/transfer handling, triage owner and scope.
- Contract/dependency: domain-owned placement resolver and current GCO resource authority;
  no second placement writer or automatic Head/home fallback.
- Privacy: saved home/Student College is historical provenance, not continuing confidential access.
- Approval: pending; current operational placement rules remain unchanged.

### FAC-D5 — GCO acknowledgment

- Proposed rule: explicit eligible Counselor/supervised GSS receipt, current Student College
  scope, actual server time/actor and synchronous Audit. Decide approved use of F3 received_at.
  Reads, PDF release and successful transport do not acknowledge.
- Authority: GCO/UCN form and operational responsibility owners.
- Evidence: receipt meaning, responsible actors/Colleges, validity, source-form mapping and
  approved Faculty wording/time disclosure. Paper dates acquire no invented acknowledgment.
- Contract/dependency: independent ACKNOWLEDGMENT provider and EXPLICIT_RECEIPT_UCN_F3_V1.
- Privacy: actual GCO actors are restricted to GCO; Faculty sees only separately approved facts.
- Approval: pending; synthetic positive fixtures only.

### FAC-D6 — administrative closure

- Proposed rule: explicit authorized closure after acknowledgment and review of approved
  administrative obligations; independent Call Slips/Follow-Ups retain their lifecycles.
  The institution must decide whether obligations must be mechanically satisfied, retained
  pending, or classified, and whether any minimal confidential classification is necessary.
- Authority: GCO with privacy/records and UCN process owners.
- Evidence: actual completion criteria, closer eligibility, attestation wording, linked-task
  exceptions, audit/retention and approved Faculty meaning. Clinical resolution is not implied.
- Contract/dependency: independent CLOSURE provider. Current test proposal is
  ADMINISTRATIVE_REVIEW_RETAIN_LINKS_V1 with strict explicit review; it is not adopted policy.
- Privacy: no confidential closure narrative is captured or disclosed without a new contract.
- Approval: pending; actual provider returns None.

### FAC-D7 — tracking, exceptions and retention

- Proposed rule: immutable submitter owns only approved minimal reference/time/Student-name
  and actual Submitted/Received/Administratively Closed facts. Decide timestamp disclosure,
  retention, account changes and void communication. Keep void omit/404 until approved.
- Authority: GCO, privacy and records authority.
- Evidence: exact field/exception allowlist, retention/custody, continued eligibility after
  role/home/account changes, historical read rules and any separate Faculty PDF authority.
- Contract/dependency: independent three-stage disclosure provider, FAC-2 own-read policy;
  unavailable disclosure refuses affected reads rather than fabricating Submitted.
- Privacy: no reason readback, GCO actors, Actions, Call Slips, Follow-Ups, contacts or clinical facts.
- Approval: pending; no approved Faculty PDF or exceptional lifecycle is invented.

### FAC-D8 — Notifications

- Proposed rule: no automatic Referral notices until event/recipient/channel disclosure is
  approved. Candidate Faculty events are actual receipt/closure to the current eligible
  authenticated submitter. Any GCO recipient must follow actual responsibility and scope.
  No automatic Student notice is authorized.
- Authority: GCO/privacy/records plus Notification operations/security owner.
- Evidence: appropriate events/recipients, minimum external content, channels, trusted origins,
  retention, currentness and delivery deduplication/withdrawal semantics.
- Contract/dependency: existing Notification catalog/current-recipient/idempotency/deep-link
  framework. FAC-4 supplies only an inactive candidate intent, not a producer or send authority.
- Privacy: minimum reference, actual event/time and authenticated safe route; never narratives,
  confirmation values, internal activities or clinical outcomes. Links grant no access.
- Approval: pending; no live catalog/producer/delivery change.

### FAC-D9 — academic-contact attestation

- Proposed rule: capture no academic-contact attestation until the institution decides whether
  it is needed and exactly what it proves. A Faculty statement cannot establish enrollment,
  current teaching, roster membership or academic verification.
- Authority: GCO and academic/identity authority with privacy review.
- Evidence: approved need, wording/value set, permitted use, evidence limitations and retention.
- Contract/dependency: separate reviewed form/policy revision if approved; absent from FAC-1–5.
- Privacy: avoid unnecessary Student relationship data and misleading verification labels.
- Approval: pending; no contact-basis field or verification claim is implemented.

### FAC-D10 — transfer and SAR integration

- Proposed rule: preserve immutable original provenance; current GCO scope follows the current
  approved placement relationship. Decide historical access/transfer custody and eventual SAR
  authority before replacing that resolver. No silent historical ownership/routing rewrite.
- Authority: GCO, SAR/academic records custodian and privacy/records authority.
- Evidence: transfer access/custody matrix, historical disclosure/retention rules, SAR authority,
  migration/reconciliation and supported conflict recovery.
- Contract/dependency: separate SAR integration and reviewed placement-adapter migration;
  current StudentAffiliation remains the only operative placement source.
- Privacy: a saved College never grants access to clinical or other retained records.
- Approval: pending; FAC-5 performs no transfer or SAR activation.

## Decision record template for the actual authority

Use the decision ID, accountable institutional owner, proposed rule accepted/modified/rejected,
actual evidence reference and custody location, approved scope/validity, privacy/records review,
contract version, exceptions, withdrawal/review date and resulting implementation ticket.
Leave actual names, references and signatures blank until supplied by authorized officials.
Approve policy and review its adapter separately from technical/UAT/release sign-off.
