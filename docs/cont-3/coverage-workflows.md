# Coverage workflows

## Planned coverage

An eligible original Counselor opens **Request coverage** from an existing author-owned Counseling Encounter. The route carries only Student/original-Counselor references; these are untrusted selection inputs, not permission. The backend independently checks one exact Student and historical author, current account/capabilities/affiliation and both operational/workflow policies. It returns eligible completed Encounter/finalized Routine references and currently eligible receiving Counselors. It never reads Intake, Evaluation ciphertext, Student Summary or Handoff text.

Select one receiver, a bounded purpose category, explicit start/expiry in Philippine time and up to 32 exact sources. Review recipient, scope count and expiry before submission. The existing CONT-2A request endpoint seals that exact snapshot and client intent UUID. REQUESTED/PENDING grants do not authorize professional reads. Approval/decline/cancel/revoke retain existing current-version APIs and independent authority checks; no consequential mutation retries automatically after conflict. Renewal is a new request.

My case coverage and Coverage requests show server-derived scheduled, active, expired, revoked and other decision states, with authorized historical metadata and pagination. A policy-named current Head gets Pending approvals and Coverage history. Original authors can participate in office-requested metadata only when a matching sealed workflow policy and current own-Handoff capability explicitly permit it; this does not add old-grant or office-wide body access.

## Unexpected absence

There is no general Student search or office-wide history endpoint. `ApprovedCoverageWorkflowPolicy.office_cases` names exact `(requester, Student, historical original Counselor)` triples. At most 200 explicit cases is a technical payload bound, not a professional scope rule. Configuration lists only that actor's currently eligible case references. The requester must also be a current designated Head explicitly authorized by the operational office-requester policy and have request/view/approval authority. Neither an override alone nor Acting Head status substitutes for this.

`GET .../workflow/selection` requires the exact Student and author. Candidates are restricted to that pair and the policy-approved two source kinds, ordered/paginated at 25 candidates per kind; up to 50 eligible references are returned. A lookahead controls Next without exposing total historical counts. Empty/ineligible candidates produce an accurate empty state. Page changes deliberately clear checked sources. Fields are source UUID/kind, fixed projection, historical Counselor UUID, structural date and eligibility=true. Source-owned CONT-2B lifecycle/linkage validation locks exact rows without loading ciphertext. The receiver directory is available only after the exact case/source relationship has been established, bounded to 200 active canonical Counselors with current selected-read eligibility.

The request API also enforces the workflow's exact office case and category when its digest is bound; skipping the UI does not bypass it. The absent original can be inactive. No original login, signature, Handoff, reassignment or impersonation is required. A requesting/receiving Head cannot self-approve; another currently designated, policy-named independent Head is necessary. Without a legitimate backup, the software denies approval and the institution must arrange a lawful operational procedure. No emergency or Acting Head bypass exists.

## Decisions and recipient review

The detail page identifies Student, original, receiver, requester, approver, purpose, interval, server status, version and policy reference. Confirmation shows receiver, selected scope and expiry. Approval pages fetch structural Grant/Handoff metadata only; drafts are not exposed to approvers or receivers. Head authority does not add Evaluation/Handoff body access.

The receiver opens exactly one selected record through generated CONT-2B operations. Encounter returns its six fixed fields. Evaluation renders only returned approved keys, distinguishing omitted fields, approved null ratings and legitimate empty text. No correction, Student publication, source export or reassignment action is attached. A Handoff is optional and independently gated. New work uses ordinary domain permissions and preserves the new author's identity.

Default missing/expired/unconfirmed policies display **Case coverage is unavailable**, rather than an empty successful record. Other states distinguish conflicts, denied/unconfirmed access, no sources, absent/draft/submitted Handoff and unavailable ciphertext. Some identity displays deliberately remain authorized UUID references because existing Grant metadata contains no name-directory entitlement.
