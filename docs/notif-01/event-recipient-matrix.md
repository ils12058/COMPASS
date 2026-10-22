# Audited event, recipient and currentness matrix

Baseline: integration `f268d1a5`, October 22, 2026. All **30** NotificationEvent
members are listed below. **29** permit email; Routine Interview intake is in-app
only. No Graduate Tracer, assessment, private Message-body or general Referral
event is silently inferred from the existence of those domains.

## Reading the matrix

`M` = MANDATORY_OPERATIONAL; `O` = OPTIONAL_INFORMATIONAL (preference suppresses
email only); `S` = MANDATORY_SECURITY. `I/E` = in-app + email. Push is an independent
opt-in channel with its own policy, listed separately below. Template names are
under `be/compass/notifications/templates/notifications/email/`, paired `.html/.txt`.

Classification numbers use the requested audit vocabulary: **1** specific record
link; **2** recipient-scoped destination; **3** additional source authorization
needed; **4** event-provenance review needed; **5** minimal-content-only;
**6** security-specific/excluded; **7** in-app-only; **8** deferred decisions.
Classes may overlap. **1 is activated only for Scheduled**; the remaining candidate
classes do not enable new links or source fields in this PR.

Currentness abbreviations (precise behavior, including missing/access outcomes):

- **R**: baseline `notification_is_current` checks only recipient activity. Source
  deletion, state changes or revoked source access are not checked for this family.
  Existing email remains generic; destination authorization is independent. In
  NOTIF-01 all such events other than Scheduled still use this unchanged behavior.
- **A**: Scheduled pilot additionally validates `appointment` source = Appointment
  target, upcoming SCHEDULED state, fresh actor and normal detail access. Cancelled,
  completed/no-show/past sources suppress email even if source access is now lost.
  Missing source/invalid legacy target or denied link access falls back to generic
  without source ID/details. Changes after render cancel before send.
- **F**: source Follow-Up event must be the latest material event, target match a
  PENDING Follow-Up, and fresh assignee have current manage capability/resource
  scope. Missing, completed/cancelled, superseded or access-lost events fail.
  External channel feature gate also applies. In-app list/unread suppress stale
  items independently of the external delivery switch.
- **T**: reminder occurrence must exist and match active Student, Appointment,
  upcoming SCHEDULED start and current `reminder_revision`. Missing/revised/
  cancelled/access-ineligible occurrence fails. In-app list/unread also filters it.
  This checks Student identity/role/activity, not a new rich-disclosure capability.
- **G1**: registration exists, belongs to recipient, REGISTERED; session PUBLISHED.
- **G2**: registration exists, belongs to recipient, CANCELLED.
- **G3**: session source exists and is CANCELLED; does not separately recheck the
  cancelled recipient registration relationship. Minimal only until reviewed.
- **G4**: PUBLISHED session; source schedule revision matches current schedule
  revision (legacy general `group_session_vN` compares general version); recipient
  still has REGISTERED registration. Invalid/missing/revised records fail. In-app
  rescheduled notices remain visible with qualified stale wording/current-event CTA.

All worker families check active recipient at claim; final email check now
explicitly checks activity and current email again. F/T/G guards are shared with
Push. A is email-presentation-specific; no new Push content or behavior is enabled.

## Complete catalog and actual producers

Paths in the producer column are relative to `be/compass/`.

| Event code | Policy / channels | Producer | Source type: source_id meaning | Recipients | Target type: target_id meaning / destination | Currentness | Template | Class / content / link readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `guidance_followup.assigned` | M I/E | `guidance_followups/integration.py:event_committed_intent` | `guidance_followup_event`: CREATED event UUID | Current assigned staff only | GUIDANCE_FOLLOW_UP: Follow-Up UUID → `/portal/follow-ups/{id}` | F | `guidance_followup` | 3,5,8 / B; minimal update only; source access required before future link |
| `guidance_followup.reassigned` | M I/E | same, REASSIGNED branch | `guidance_followup_event`: reassignment event UUID | New/current assignee; old assignee gets cache-eviction hint, not a new Notification | GUIDANCE_FOLLOW_UP: Follow-Up UUID | F | `guidance_followup` | 3,5,8 / B; no Student/reason/due detail |
| `guidance_followup.due_changed` | M I/E | same, material UPDATED branch | `guidance_followup_event`: changed-due event UUID | Current assigned staff | GUIDANCE_FOLLOW_UP: Follow-Up UUID | F | `guidance_followup` | 3,4,5,8 / B; date projection still deferred |
| `call_slip.issued` | M I/E | `call_slips/services.py:_create_new_call_slip_locked`, only notify_student=true | `call_slip`: slip UUID | Slip Student | CALL_SLIP: slip UUID → `/portal/call-slips/{id}` | R | `call_slip_issued` | 3,5,8 / B; require live provenance/current ownership/state for future link; no Referral narrative |
| `appointment.scheduled` | M I/E | `appointments/services.py:create_student_appointment`; `service_catalog/fixed_slots_services.py:book_fixed_slot` | `appointment`: canonical Appointment UUID for either pathway | Student + assigned provider at creation | APPOINTMENT: same Appointment UUID → `/portal/appointments/{id}` | baseline R; pilot A | `appointment_scheduled` | **1 activated**, 4 for future rich facts / B; generic copy + approved action only |
| `appointment.cancelled` | M I/E | `appointments/services.py:cancel_appointment`, first transition | `appointment`: Appointment UUID | Student + provider at cancellation | APPOINTMENT: Appointment UUID | R | `appointment_cancelled` | 3,4,8 / B; cancellation state/time/recipient review before detail/link expansion |
| `appointment.rescheduled` | M I/E | `appointments/services.py:reschedule_appointment` | `appointment_change_event`: exact RESCHEDULED event UUID | Student + current provider | APPOINTMENT: owning Appointment UUID | R | `appointment_rescheduled` | 3,4,8 / B now; future A fields from specific old/new event only |
| `appointment.reassigned` | M I/E | `appointments/services.py:reassign_appointment` | `appointment_change_event`: exact REASSIGNED event UUID | Student + previous provider + new provider | APPOINTMENT: owning Appointment UUID | R | `appointment_reassigned` | 3,4,5,8 / B; former provider must not gain current record facts/link from notice ownership |
| `appointment.reminder_24h` | M I/E | `appointments/reminders.py:dispatch_due_reminders` → `_issue_locked` | `appointment_reminder`: AUTO_24H occurrence UUID | Appointment Student only | APPOINTMENT: occurrence's Appointment UUID | T | `appointment_reminder` | 3,4,8 / B now; future approved A needs matching occurrence revision |
| `appointment.reminder_3h` | M I/E | same, AUTO_3H | `appointment_reminder`: AUTO_3H occurrence UUID | Appointment Student only | APPOINTMENT: Appointment UUID | T | `appointment_reminder` | 3,4,8 / same safeguards, distinct automatic window |
| `appointment.reminder_manual` | M I/E | `appointments/reminders.py:issue_manual_reminder` / `issue_bulk_reminders` → `_issue_locked` | `appointment_reminder`: MANUAL occurrence UUID | Appointment Student only; issuer receives no reminder Notification | APPOINTMENT: Appointment UUID | T | `appointment_reminder` | 3,4,8 / B; capability/resource scope/recent-MFA and confirmation key govern issuance |
| `group_session.registered` | M I/E | `group_sessions/services.py:register_student` | `group_session_registration`: registration UUID | Registered Student | GROUP_SESSION: session UUID → `/portal/group-sessions/{id}` | G1 | `group_session_update` | 3,8 / B; future public title/time only after field/visibility review |
| `group_session.registration_cancelled` | M I/E | `group_sessions/services.py:cancel_student_registration` | `group_session_registration`: registration UUID | Cancelling Student | GROUP_SESSION: session UUID | G2 | `group_session_update` | 3,4,8 / B; cancelled-registration visibility needs explicit link review |
| `group_session.cancelled` | M I/E | `group_sessions/services.py:cancel_group_session` | `group_session`: session UUID | Students in active registrations at cancellation | GROUP_SESSION: session UUID | G3 | `group_session_update` | 3,4,8 / B; strengthen current recipient ownership/visibility for future detail disclosure |
| `group_session.rescheduled` | M I/E | `group_sessions/services.py:update_group_session` schedule-change branch | `group_session_schedule_v{revision}`: session UUID (legacy `group_session_v{version}` supported) | Students registered at change | GROUP_SESSION: session UUID | G4 | `group_session_update` | 3,4,8 / B; no old/new time snapshot in Notification; future provenance review |
| `call_slip.voided` | M I/E | `call_slips/services.py:void_call_slip` if void_notifies_student | `call_slip`: slip UUID | Slip Student only when proven live-notification intent permits | CALL_SLIP: slip UUID | R | `call_slip_voided` | 3,4,5,8 / B; LEGACY_UNKNOWN/back-entry suppression preserved |
| `good_moral.request_initiated` | M I/E | `good_moral/services.py:_notify_assisted_creation` GCO_ASSISTED only | `good_moral_request`: request UUID | Request Student | GOOD_MORAL: request UUID → `/portal/good-moral/{id}` | R | `good_moral_request_initiated` | 3,5,8 / B; no receipt, payment, academic or certificate fields |
| `good_moral.issued` | M I/E | `good_moral/services.py:issue_request` first issuance | `good_moral_request`: request UUID | Request Student | GOOD_MORAL: request UUID | R | `good_moral_issued` | 3,8 / B; future issuance-only status/date requires approval and current ownership |
| `exit_interview.reopened` | M I/E | `exit_interviews/services.py:reopen_for_correction` | `exit_interview_reopen_event`: correction event UUID, **not** interview UUID | Interview Student | EXIT_INTERVIEW: interview UUID → `/portal/exit-interviews/{id}` | R | `exit_interview_reopened` | 3,4,5,8 / B; no answers, reason or correction targets; lifecycle gate before future link |
| `inventory.reopened` | M I/E | `inventory/services.py:reopen_inventory_for_correction` | `inventory_reopen_event`: reopen event UUID | Inventory Student | INVENTORY: inventory UUID; route ignores ID → `/portal/inventory/current` | R | `inventory_reopened` | 2,3,4,5,8 / B; current year may differ from historical reopened inventory |
| `counseling.shared_summary.published` | M I/E | `counseling/shared_summaries.py:publish_assigned_shared_summary` first publication | `counseling_shared_summary`: summary UUID | Encounter Student | COUNSELING_SHARED_SUMMARY: summary UUID → `/portal/counseling/summaries/{id}` | R | `counseling_shared_summary_published` | 3,5,8 / B; no summary content, narrative or clinical material; published/current owner check needed |
| `routine_interview.intake_ready` | M I only | `routine_interviews/services.py:create_direct` | `routine_interview`: interview UUID | Interview Student | ROUTINE_INTERVIEW: interview UUID → `/portal/routine-interviews/{id}` | R (no email) | none | 7 / B; no email activation |
| `ecounseling.consent.requested` | M I/E | `ecounseling/media.py:request_consents`, only newly created scopes | `ecounseling_consent`: first newly created consent UUID in command | Appointment Student | E_COUNSELING: **Appointment UUID** → `/portal/e-counseling/{id}` | R | `ecounseling_consent_requested` | 3,4,5,8 / B; no join/recording/transcript credentials; current consent/session access required |
| `feedback.invitation` | O I/E | `good_moral/services.py:issue_request`; `counseling/services.py:_create_row` | `feedback_opportunity`: opportunity UUID from completed service | Service Student | FEEDBACK: opportunity UUID → `/portal/feedback?opportunity={id}` (legacy missing ID → recipient list) | R | `feedback_invitation` | 2,3,8 / B; current opportunity ownership/eligibility needed; no answers or source narratives |
| `security.password.reset` | S I/E | `authentication/password_access.py` successful reset, initial setup excluded | `audit_event`: successful reset AuditEvent UUID | Affected account | ACCOUNT_SECURITY: recipient User UUID; in-app `/portal/account/security` | R | `security_password_reset` | 6 / C; no ordinary operational link or reset token |
| `security.password.changed` | S I/E | `authentication/password_change.py` successful change | `audit_event`: successful change AuditEvent UUID | Affected account | ACCOUNT_SECURITY: affected User UUID | R | `security_password_changed` | 6 / C; established security copy only |
| `security.mfa.disabled` | S I/E | `authentication/mfa.py:disable_totp` successful disable | `audit_event`: disable AuditEvent UUID | Affected account | ACCOUNT_SECURITY: affected User UUID | R | `security_mfa_disabled` | 6 / C; no secret or recovery values |
| `security.recovery_codes.regenerated` | S I/E | `authentication/mfa.py:regenerate_recovery_codes` | `audit_event`: regeneration AuditEvent UUID | Affected account | ACCOUNT_SECURITY: affected User UUID | R | `security_recovery_codes_regenerated` | 6 / C; never actual recovery codes |
| `security.mfa.admin_reset` | S I/E | `account_management/services.py` administrative MFA reset → security helper | `audit_event`: successful admin reset AuditEvent UUID | Reset account | ACCOUNT_SECURITY: affected User UUID | R | `security_mfa_admin_reset` | 6 / C; no administrator rationale or credentials |
| `security.account_access.changed` | S I/E | `account_management/services.py` actual activity/role/designation/capability changes → `_create_account_security_notification` | `audit_event`: successful access-change AuditEvent UUID | Affected account | ACCOUNT_SECURITY: affected User UUID | R | `security_account_access_changed` | 6 / C; inactive account cancellation still applies; no capability/reason payload |

Function names above identify the audited producer or logical workflow; exact
Notification calls and the current catalog are authoritative. Failed login/MFA
attempts are audit/security facts, not Notification/email producers. Email OTP
and the old-address email-change alert are separate security mechanisms outside
these 30 catalog events and remain untouched.

## Missing source, access changes and sensitivity policy

For each **R** row, deletion/lost source access is currently not consulted by
the email worker: it sends existing minimal fixed copy while the account remains
active. A record click is independently protected. These rows are not approved
for new source facts or links; NOTIF-3 must add owning-domain checks. For F/T/G,
failed predicates cancel pending external delivery using existing state. A's
fallback/suppression is deliberately specified above and in the delivery contract.
No row authorizes clinical/sensitive content by merely naming an operational tier.

Future candidates for **Tier A** are only Appointment schedule/reference/Service/
mode/current provider and approved public Group Session title/schedule, with
recipient/event authorization and institutional review. Good Moral, Call Slip,
Follow-Up, Inventory, Exit Interview, summary and E-Counseling rows remain Tier B
unless a separate, explicit field policy is approved. Security is Tier C. Good
Moral OR/payment facts, confidential narratives, answers, scores and all tokens
are excluded regardless of tier.

## Independent Push policy and seed producers

PUSH is allowed for Follow-Ups, Call Slip issued/voided, all seven Appointment
events, all four Group Session events, Good Moral issued, E-Counseling consent and
the six security events. Delivery requires opt-in subscription/session eligibility
and uses the existing generic lock-screen body. Good Moral initiated, Exit
Interview reopened, Inventory reopened, summary published, Routine Interview
intake ready and Feedback have no Push body. The new email presentation is never
passed to Push.

`staging_seed/workflows.py` invokes canonical services, timestamps retained in-app
notifications and removes never-attempted external seed intents through its
existing safety helpers. Scenario modules also locate/read those Notifications.
They do not define additional event families, and this slice neither runs the
seeder nor resends historical Notifications. Fixed-slot booking is a genuine
second Scheduled producer using the same canonical Appointment source/target;
there is no slot-specific email or duplicate logical event.
