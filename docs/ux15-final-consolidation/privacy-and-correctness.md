# Privacy, Authorization, and Data Correctness

## Frontend boundaries

| Area | Integrated behavior and evidence | Remaining limit |
| --- | --- | --- |
| Student Home | Uses canonical Student Actions and existing self-service helpers. Unexpected professional summary sections are suppressed. Current versus Graduated/Former eligibility remains domain-owned. Browser and unit fixtures cover no unauthorized professional content and lifecycle variants. | Synthetic fixtures do not prove server authorization. |
| Counselor and Head | Counselor agenda uses the self Appointment projection only when `appointments.view_self` permits it. Head keeps the Counselor self-work scope; oversight destinations require existing workspace/capability rules. Purpose, counseling narratives, Evaluation text, Assessment findings, referral reasons, and Message bodies are excluded from Home previews. | No live account/scope-revocation exercise was performed. |
| GSS | Backend identity stays `GUIDANCE_SERVICES_STAFF`. Managed Appointments are requested only when the existing `appointments.manage` helper permits it. Routine Evaluation and Counselor issuance are not presented as GSS actions. Operations metrics remain the backend's scoped projection; null is not changed to zero. | Browser tests inspect request gating and fixture presentation, not deployed College/supervision enforcement. |
| Other roles | Existing Overview remains for IT Administrator, Institutional Officer, and other roles. Synthetic non-regression checks cover IT Admin and Institutional Officer. | DPO-designated Institutional Officer behavior remains a human UAT scenario. |
| Account and scope changes | Existing session/query ownership discards old-account data. Browser tests switch synthetic Counselor/GSS accounts to Student and verify private projections disappear. 401/403 paths hide cached private data; transient failures retain labeled last-confirmed data. | Dynamic server authorization and every scope-revocation timing are not proven by browser fixtures. |
| Confidential forms | Student Inventory, Exit Interview, Tracer, and Intake visibility/editability follow existing lifecycle and resource helpers. Counselor Evaluation stays professional and is not surfaced in Student or GSS previews. | No real confidential record, production key, or live backend was used. |
| Submission safety | Intake has fresh canonical status reconciliation and no automatic duplicate POST. Feedback/CSM preserve exact intent on supported retry and never infer the accepted body from an opportunity flag. Evaluation finalization remains separate and becomes read-only only after confirmation. | Real network/database races and deployed idempotency storage were not exercised. |

## Backend contract and source review

The staging and integration `contracts/openapi.json` files are identical. Existing operations and
capabilities cover the UX15 reads and mutations; Orval generation completed successfully, and
strict typecheck/build resolved the generated request/response types without a new endpoint or
schema. The canonical work, self/managed Appointment, Guidance Operations, form, and submission
paths are owned by the existing generated API client.

Backend source review checked the existing Appointment capability and scope enforcement in
`be/compass/appointments/api.py`, `access.py`, and `services.py`; role/capability and scoped
projections for Guidance Operations; Routine Interview Student-draft versus Counselor-Evaluation
privacy and finalization; and Feedback/CSM ownership, optional identity, one-time submission,
transaction/idempotency behavior. No backend source or contract was changed.

Relevant existing negative/backend test coverage includes:

- `be/tests/test_appointment_management_scope.py` — Head/self/provider and GSS scope, revoked
  capability, resource list/get/action boundaries.
- `be/tests/test_guidance_operations.py` — role/capability absence, stale actors, Head/GSS scope,
  source failure, null/zero semantics, and content-minimized wire contract.
- `be/tests/test_routine_interviews.py` — Student draft privacy, Counselor Evaluation lifecycle,
  authorization and finalization.
- `be/tests/test_feedback.py` — Student ownership, optional identity, separate Feedback/CSM
  payloads, one-time submission and idempotency boundaries.
- `be/tests/test_inventory.py` and `be/tests/test_exit_interviews.py` — lifecycle/ownership and
  confidential form behavior.

These backend test files were inspected but **not run** in this frontend-only consolidation. The
backend test settings require local PostgreSQL and Redis test services; no backend files changed
and no backend CI workflow was dispatched. This audit therefore establishes source/contract
compatibility, not a live server authorization result. Any staging or production permissions must
be verified through the normal approved backend tests and environment-specific UAT.

## Submission and ownership invariants

- A Home projection is a read-only view, not a second work aggregator or authorization policy.
- A visible link is not evidence that a server will authorize the resource; the owning API remains
  authoritative.
- No head override, cross-Counselor access, emergency access, case-continuity workflow, or GSS role
  migration was added.
- No secret, credential, real Student response, or production/staging record was accessed.
- UI confirmation follows server confirmation. Uncertain states remain explicit; the interface
  never manufactures success or silently repeats consequential mutations.
