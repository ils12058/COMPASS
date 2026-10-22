# NOTIF-03 source audit and implementation decisions

Completed before implementation, October 22, 2026, on integration
`6d6f3e0accbef09302f6b158295632059b9ff211` (merged PRs #310 and #311).
Actual producers, models, currentness, API self-access and frontend detail routes
were read. Stored Notification data does not require a schema change.

| Event | Producer / exact source | Target / recipient | Email currentness and provenance | Candidate rich fields / action |
| --- | --- | --- | --- | --- |
| `group_session.registered` | `register_student`; `group_session_registration`, registration UUID | GROUP_SESSION parent UUID; exact registration Student | Source type/parent/Student/status REGISTERED; PUBLISHED and upcoming; Student self-view capability. Registration has no schedule snapshot: label disclosed schedule as current verified context. | Fixed Group Session label, registration-confirmed status, current date/time/mode; authenticated session link |
| `group_session.registration_cancelled` | `cancel_student_registration`; same registration source | Same parent and owner | CANCELLED registration with timestamp, no later registration superseding cancellation; published/cancelled session remains readable through own registration. Do not promise active registration/attendance. | Fixed label and cancelled-registration status only; own historical session link |
| `group_session.cancelled` | `cancel_group_session`; `group_session`, session UUID | Same target; Students registered at cancellation | CANCELLED/timestamp; bind recipient to a cancelled registration with the same cancellation timestamp and earlier registration time. Existing generic currentness lacks this binding. Never assume Notification ownership proves participation. | Fixed label and session-cancelled status only; verified participant's retained record link |
| `group_session.rescheduled` | `update_group_session`; `group_session_schedule_v{schedule_revision}`, session UUID; legacy `group_session_v{version}` | Same target; currently registered Student | Match exact supported revision and current PUBLISHED upcoming session; current owned registration and self-view authority. Legacy general-version match permits minimal link only, no certified schedule details. Superseded revisions suppress. No old schedule snapshot exists. | Fixed label, rescheduled status, verified updated date/time/mode for current schedule revision; session link |
| `good_moral.request_initiated` | `_notify_assisted_creation`, GCO_ASSISTED only; `good_moral_request`, request UUID | GOOD_MORAL same UUID; request Student | Exact source/target/owner; current `good_moral.view_self` via `get_mine`; assisted initiation and initiator required. REQUESTED/READY remain meaningful creation notices with current-status wording. Already issued/cancelled initiation is obsolete and suppressed. Self-service produces no new event. | Fixed request label, office-assisted initiation and current status; request link |
| `good_moral.issued` | first `issue_request`; same request source | Same target and owner; F4 or F6 | Actual ISSUED state and complete persisted issuance provenance; valid aware issuance time. Never infer issuance from READY. Source currentness/authorization checked again before SMTP. | Fixed certificate-issued status and institutional-local issuance date; request link |
| `call_slip.issued` | `_create_new_call_slip_locked`, notify_student true; `call_slip`, slip UUID | CALL_SLIP same UUID; slip Student | Actual LIVE provenance, active not voided/completed; current self-role/activity/capability plus `get_my_call_slip`. HISTORICAL/LEGACY_UNKNOWN cannot become fresh live issuance. | Fixed issuance status only; exact slip link. No report time/destination pending explicit field approval. |
| `call_slip.voided` | `void_call_slip` if `void_notifies_student`; same slip source | Same target and owner | Actual void timestamp and existing notification-intent rule. HISTORICAL suppresses. LEGACY_UNKNOWN preserves existing minimal void notice/link, but no new rich provenance claim. | Fixed voided status for LIVE; legacy minimal; own voided record link. No private reason/report instruction. |

## Privacy and source access findings

Group title/description/venue and meeting URL are free text with no public-email
approval marker; the one venue field mixes physical destinations and meeting
credentials. Version 1 deliberately uses a fixed generic label and omits **all**
titles, venue values, facilitators, roster and reasons. Cancellation records retain
Student detail-route access because the API allows a prior owned registration;
it hides online venue from inactive registrants. Email never receives that venue.

Good Moral has no request reference code, so no pseudo-reference is invented.
Issuance persists timestamp, issuer, form revision and template identity. F4/F6
creation/preparation/printing rules remain unchanged. Receipt, applicant, academic,
certificate body and review details are excluded. Registrar/dry-seal instructions
are not independently confirmed here; next steps direct the Student to COMPASS.

Call Slip self-detail remains readable after voiding. Its domain getter checks
active Student ownership, while API separately checks `call_slips.view_self`;
email must enforce both. Durable issuance mode separates LIVE/HISTORICAL/unknown;
the existing void rule permits unknown legacy but excludes historical entries.
No Referral content, destination, Student identifiers, report time or notes enter
the candidate bundle. No producer or recipient list needs to change.

## Adopted policy and delivery integration

The new `COMPASS_EMAIL_DISCLOSURE_POLICY`, minimal by default, replaces the old
Appointment setting without alias. Obsolete plain or `_FILE` environment keys,
including empty values, fail startup with a bounded replacement instruction.
The central operational_v1 candidate scope is explicitly all four families; prior
Appointment-only authorization, if any, cannot authorize the expanded profile.
No deployed activation occurs. New minimal-mode links require the same verified
domain eligibility as rich fields, a trusted origin and closed UUID route.

Missing source/invalid legacy provenance uses generic no-detail/no-link fallback,
unless the existing cross-channel Group Session currentness already cancels it
at claim time. Unauthorized ownership gets no data/link; obsolete lifecycle and
superseded events suppress email. Current policy/facts/source guards and actual
validated URL participate in final deterministic presentation equality. Existing
claim, retry, transport, Notification Center and Push behavior remain authoritative;
new restrictions belong to email, not `notifications/current.py`.
