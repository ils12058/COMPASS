# RA-1: Case-session reassignment follows the case-transfer approval

**Status:** draft PR into `staging`. Not merged or deployed.
**Base:** `2b2411dd` (`staging` after SAR-8).
**Date:** 2026-11-14.
**Decision:** on 14 November 2026 the owner agreed to apply the case-transfer rules to Appointment reassignment, but only for sessions that belong to an Active case.

## 1. The gap

**Reassign Counselor** moves one scheduled Appointment to another Counselor. Before RA-1, it never looked at counseling cases:
- A session linked to an Active case could move to a Counselor who has no access to the case. The case stayed with its owner.
- An Encounter the new Counselor records cannot join another Counselor's case (`lock_case_for_recording` accepts only the Counselor's own Active case), so the case history split.
- A Counselor could hand their case session to a colleague, who only received a notification.
- There was no Head involvement, although a case transfer requires independent Head authorization.

A Student can still cancel their own Appointment after the notification (`appointments.manage_self`). RA-1 does not change that.

## 2. Rules

| Appointment | Move to | Result |
|---|---|---|
| Not linked to an Active case | Any eligible Counselor | Direct reassignment, unchanged |
| Linked to an Active case | The case's own Counselor | Direct reassignment: it restores continuity |
| Linked to an Active case | Anyone else | A **request**. `POST /appointments/{id}/reassign` refuses with `409 case_continuity_reassignment_request_required`. |

A request follows `authorization_route`, the same function a case transfer uses:

| Route | When | Effect |
|---|---|---|
| `INDEPENDENT_HEAD` | An independent current Head exists (not the requester, not the receiver) | The request is `PENDING`. Eligible Heads get an in-app notice and a Work Queue item (`CASE_REASSIGNMENT_APPROVAL`, due at the session start). The Appointment stays with its Counselor until a Head approves. |
| `DIRECT_OUTGOING_HEAD` | The case owner is the Head and asks | Applied at once and recorded with its route |
| `OWNER_TO_HEAD` | Single-Head rule: the owner gives the session to the only Head | Applied at once, flagged as not independent |
| none | No independent approver | Refused with `case_continuity_no_independent_approver`. The office can still reschedule or cancel. |

**Further rules:**
- The requester must manage the Appointment, give a reason, and confirm that the case stays with its Counselor (`acknowledged`).
- Only one pending request per Appointment, enforced by a database constraint.
- **Approval:**
  - Only an independent current Head with `counseling.continuity.approve` may decide, never the requester or the receiver.
  - Approval re-checks every reassignment rule: scheduled, before start, no Routine Interview, Encounter or E-Counseling room, eligibility, availability and overlaps.
  - It then applies the move through the same code path as a direct reassignment.
- **Currency:**
  - A request no longer applies if, after it was made, the Appointment time, Counselor or status changed, the session started, the case link or owner changed, or the route changed.
  - Approving such a request saves it as `EXPIRED` and returns `409 case_continuity_reassignment_expired`. Nothing moves.
- **Decline and withdraw:** a Head may decline with an optional note. The requester may withdraw.
- **Privacy:** responses and notices name people and the Appointment only. No case narrative, notes or handoff content. The receiving Counselor sees "Part of <owner>'s counseling case. Case records stay with <owner>."

## 3. Changes

### Backend
- **Model and migration:** `counseling/case_reassignment_models.py`, with additive migration `counseling/0011_case_appointment_reassignment`. It is pinned in `canonical_migrations.json` and `deploy/staging/additive-migrations.json`.
- **Services:** `counseling/case_reassignment_services.py` handles the request, decision, currency check, view rules and Work Queue rows.
- **Appointments refactor:** `appointments/services.py` splits reassignment into `_validate_reassignment` and `_apply_reassignment`, shared by the direct and the approved paths. The direct path calls `require_plain_reassignment`.
- **API** (`counseling/case_reassignment_api.py`):
  - `GET /counseling/appointments/{id}/reassignment`
  - `POST /counseling/appointments/{id}/reassignment-requests`
  - `GET /counseling/appointment-reassignments/{id}`
  - `POST /counseling/appointment-reassignments/{id}/decision`
- **Audit:**
  - New `counseling.case_reassignment.{requested,approved,declined,withdrawn,expired}`.
  - `appointment.reassigned` now carries `case_reassignment_id` and `case_route` when applicable.
- **Notifications:** in-app `counseling.case_reassignment.review` and `.decided`, with target `APPOINTMENT_REASSIGNMENT`.
- **Policy:** no new capability. Approval reuses `counseling.continuity.approve`.

### Frontend
- **Appointment page:**
  - A case-session notice, and a pending-request notice linked to the request in place of the Reassign button.
  - In the Reassign dialog: the case warning, the acknowledgement checkbox, and **Request reassignment** for case sessions.
- **Review page:** `/portal/counseling/reassignments/[id]` lets a Head approve or decline, or the requester withdraw.
- **Notification and Work Queue destinations:** both lead to the review page.
- **Refusal messages:** a bounded code-to-message map. The user-copy rule forbids showing raw backend text.

## 4. Verification

| Check | Result |
|---|---|
| `test_ra1_case_reassignment.py` | 9 passed |
| Affected backend suites (OpenAPI, notifications, canonical baseline, Work Queue, CW-2/CW-3, appointment lifecycle and scope, finish concurrency, provider qualification) | 205 passed |
| `makemigrations --check`, `export_openapi --check`, ruff, `backend_ci.py verify` | clean |
| Frontend `typecheck`, `lint` (0 errors), `pnpm test` | 1,326 / 1,326 |
| `ra1-case-reassignment.browser.mjs` (new) | 5/5 Chromium, 5/5 WebKit |
| `ui-information-hierarchy`, `appointment-picker`, `guidance-messages-contextual`, `portal-navigation-attention`, `simplify-3b-queues`, `ux-p1`, `work-queue` | all pass in both engines |

CI on the pull request is the full run.

## 5. Deploy notes

- Run the normal staging deploy. It applies the additive migration `counseling/0011`.
- No capability or identity-policy change, so `sync_identity_policy` is not required.
