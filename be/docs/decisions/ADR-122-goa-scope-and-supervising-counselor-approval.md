# ADR-122: Guidance Office Assistant scope and supervising-Counselor approval

- Status: Accepted
- Date: 2026-11-21

## Context

During the Guidance and Counseling Office (GCO) demonstration and evaluation, the Head Guidance
Counselor clarified two boundaries for the Guidance Office Assistant (`GUIDANCE_OFFICE_ASSISTANT`,
GOA) role:

1. A GOA performs office support work only and has no role in counseling cases or counseling
   continuity (case coverage, case transfers, or counselor handoffs).
2. Actions that a GOA prepares on a Counselor's behalf, or that students and the campus community see
   as official GCO issuances or publications, require approval from the GOA's active supervising
   Counselor (`StaffSupervision`).

## Decision

### 1. Remove counseling continuity from the GOA

- Remove `counseling.continuity.view` and `counseling.continuity.request` from the default role
  grants of `GUIDANCE_OFFICE_ASSISTANT` in `compass/accounts/policy.py` and from `STAFF_CAPABILITIES`
  in `compass/organization/counselor_about.py`.
- Prohibit capability overrides from granting `counseling.continuity.view`,
  `counseling.continuity.request`, `counseling.handoff.view`, or `counseling.handoff.manage` to any
  account whose primary role is `GUIDANCE_OFFICE_ASSISTANT`, and prune any existing role grants for
  those capabilities during `sync_identity_policy`.
- Deny `GUIDANCE_OFFICE_ASSISTANT` across all backend counseling continuity and handoff services and
  endpoints (`continuity_rules.py`, `case_continuity_rules.py`, `case_coverage_*.py`,
  `case_transfer_*.py`, `case_handoff_api.py`, and `continuity_services.py`), and remove GOA access
  from all frontend continuity routes, navigation links, and work-queue continuity filters.
- Preserve existing historical records: coverage and transfer requests previously prepared by a GOA
  retain their `prepared_by` / `requested_by` references and `office_preparation_reason`. Any
  pending requests prepared before this change remain reviewable and decidable by Counselors and the
  Head Guidance Counselor, while the GOA no longer has access to view or act on them.
- When a Counselor is absent and cannot prepare their own request, the Head Guidance Counselor
  prepares office-initiated coverage requests (`is_office_requester`) with a distinct Counselor or
  Head reviewer providing independent decision authority.
- Keep Guidance Follow-Ups visibility enforcement unchanged: a GOA with `follow_ups.manage` can only
  access `OPERATIONAL` follow-ups and is denied access to `COUNSELOR_CONFIDENTIAL` follow-ups.

### 2. Supervising-Counselor approval for GOA-prepared Call Slips

- Counselors continue to issue Call Slips directly in `ACTIVE` state.
- When a GOA creates a Call Slip (standalone or linked to a Referral), it requires an active
  supervising Counselor (`StaffSupervision`) and starts in `PENDING_APPROVAL` (`approval_status =
  PENDING_APPROVAL`) with the supervising Counselor recorded as `issued_by`.
- While a Call Slip is in `PENDING_APPROVAL` or `RETURNED`:
  - It is invisible to the student across student list, detail, PDF download, active Call Slip
    counts, student actions, and student activity projections.
  - No student notification is sent, and the official Call Slip PDF printout is blocked until
    approved.
- The supervising Counselor sees waiting Call Slip requests in their work queue (`/api/v1/work`,
  `CALL_SLIP_APPROVAL`) and on Overview, and receives an in-app notification and a content-free
  email (`CALL_SLIP_APPROVAL_REQUESTED`: *"A Call Slip is waiting for your approval."*) linking to
  `/portal/call-slips/<id>`.
- The supervising Counselor decides under row lock with audit logging:
  - **Approve (`CALL_SLIP_APPROVED`):** transitions the Call Slip to `ACTIVE`, sets
    `approval_status = ISSUED`, records `approved_by`, `approved_at`, `issued_by`, and
    `issued_by_name_snapshot` as the approving Counselor, and dispatches the student notification
    (`CALL_SLIP_ISSUED`) when `issuance_mode == LIVE`. The Call Slip printout template is unchanged
    and displays the approving Counselor as the issuing Counselor.
  - **Return (`CALL_SLIP_RETURNED`):** transitions the Call Slip to `RETURNED` with a required note
    to the GOA (`return_note`, `returned_by`, `returned_at`) and notifies the GOA in-app.
- When a Call Slip is `RETURNED`, the preparing GOA can edit and resubmit it
  (`CALL_SLIP_RESUBMITTED`) to the current active supervising Counselor, or withdraw it
  (`CALL_SLIP_WITHDRAWN`, transitioning to `VOIDED`).
- If the GOA's active supervising Counselor changes in `StaffSupervision` while a Call Slip is
  waiting in `PENDING_APPROVAL`, the pending request moves to the new supervising Counselor.

### 3. Supervising-Counselor approval for GOA-prepared Announcements and Resources

- Counselors and the Head Guidance Counselor continue to publish and edit Announcements and
  Resources directly.
- A GOA can create and edit drafts (`DRAFT`), but cannot publish directly and cannot edit or archive
  already-published (`PUBLISHED`) or waiting (`PENDING_APPROVAL`) items.
- Instead of publishing directly, a GOA submits a complete draft for approval
  (`ANNOUNCEMENT_SUBMITTED_FOR_APPROVAL` / `RESOURCE_SUBMITTED_FOR_APPROVAL`), which transitions the
  item to `PENDING_APPROVAL`, records `prepared_by` and `submitted_for_approval_at`, places an item
  in the active supervising Counselor's work queue (`ANNOUNCEMENT_APPROVAL` / `RESOURCE_APPROVAL`),
  and sends an in-app notification (`ANNOUNCEMENT_APPROVAL_REQUESTED` /
  `RESOURCE_APPROVAL_REQUESTED`).
- The GOA's active supervising Counselor (or the Head Guidance Counselor) can:
  - **Approve and publish (`ANNOUNCEMENT_PUBLISHED` / `RESOURCE_PUBLISHED`):** transitions the item
    to `PUBLISHED`, records the approving Counselor as `published_by` at `published_at`, and retains
    `prepared_by`.
  - **Return for changes (`ANNOUNCEMENT_RETURNED` / `RESOURCE_RETURNED`):** transitions the item
    back to `DRAFT` with a required `return_note` (`returned_by`, `returned_at`) and notifies the
    GOA in-app so the GOA can revise and resubmit.

### 4. Actions that intentionally remain without new approval

The following operational office duties remain within the GOA's direct authority without a new
approval step:

- Appointment intake and operational appointment handling;
- Referral receipt and operational encoding;
- Good Moral Certificate request preparation and receipt verification (certificate issuance itself
  already requires an authorized Counselor);
- Exit Interview opportunity administration;
- Operational Guidance Follow-Ups (`FollowUpVisibility.OPERATIONAL`); and
- Office Guidance Messages.

All of these operational actions remain audit-logged and visible to the GOA's active supervising
Counselor (and the Head Guidance Counselor) through `activity.supervised_staff.view`.
