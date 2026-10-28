# Seven-event audit and implementation policy

Audited before rich-field implementation on October 22, 2026, integration
`6f73efd981023a29fef0b0ea10ecbaacbe16212b` (merged NOTIF-01 PR #310).
Source/target relationships below are verified against actual producers, models,
authorization and reminder services. No source snapshot or new recipient is needed.

## Verified event sources

| Event | Actual producer | Source identity / parent / target | Recipients | Provenance available and missing |
| --- | --- | --- | --- | --- |
| `appointment.scheduled` | `appointments/services.py:create_student_appointment`, `service_catalog/fixed_slots_services.py:book_fixed_slot` | `appointment`, canonical Appointment UUID; APPOINTMENT target must equal source | Student + provider at booking | Current reference, immutable Service-name snapshot, start/end/provider/mode, initial reminder revision. No independently frozen initial schedule/provider; only enrich revision 1 with no change history/revision-start marker. |
| `appointment.rescheduled` | `appointments/services.py:reschedule_appointment` | `appointment_change_event`, exact RESCHEDULED UUID; event.appointment must equal APPOINTMENT target | Student + provider at change | Exact previous/new start/end, occurred_at, created_at. Provider display names and Service/mode context are not event snapshots. Never substitute another row or latest schedule for this event. |
| `appointment.reassigned` | `appointments/services.py:reassign_appointment` | `appointment_change_event`, exact REASSIGNED UUID; parent must equal APPOINTMENT target | Student + previous provider + new provider | Exact previous/new provider IDs and times. No historical display-name snapshot or event schedule snapshot. Only latest unambiguous change can use verified unchanged current schedule. |
| `appointment.cancelled` | `appointments/services.py:cancel_appointment`, first transition | `appointment`, source = APPOINTMENT target | Student + provider at cancellation | Terminal CANCELLED state/timestamp and retained final schedule/provider/mode. No cancellation-reason disclosure. No post-cancellation scheduling mutation is supported. |
| `appointment.reminder_24h` | `appointments/reminders.py:dispatch_due_reminders` → `_issue_locked` | `appointment_reminder`, AUTO_24H occurrence UUID; occurrence.appointment = APPOINTMENT target | Student only | Revision/start snapshot and recipient, issuer/issuance time; no complete provider/end snapshot. Enrich only when kind/parent/Student/revision/start/current state match. |
| `appointment.reminder_3h` | same, independent AUTO_3H window | `appointment_reminder`, AUTO_3H occurrence UUID; same parent contract | Student only | Same facts; independent occurrence/window identity retained. |
| `appointment.reminder_manual` | manual single/bulk reminder services → `_issue_locked` | `appointment_reminder`, MANUAL occurrence UUID; same parent contract | Student only | Same facts. Existing staff scope, recent MFA, confirmation/replay, cooldown and bulk bounds remain authoritative. |

## Implemented field and currentness policy

One versioned external-disclosure setting defaults to minimal. Only an exact
approved operational policy value permits source facts. Invalid/missing values
are minimal. Existing generic templates and NOTIF-01 Scheduled links must remain
available with the default. Approval is institutional/operator-owned, not a user
preference or frontend flag. GSS receives no new Notification and no rich fields.

| Event | Approved current Student / assigned Counselor | Rich currentness / suppression | Fallback and retry |
| --- | --- | --- | --- |
| Scheduled | Reference, Service snapshot, date/time, mode; Student additionally current provider name. Counselor gets no Student identifiers. | Upcoming SCHEDULED, current domain access. Initial revision 1, no changes and no revision-start marker required for original facts. | Changed initial facts → qualified generic Scheduled link using NOTIF-01 eligibility. Terminal/past → suppress as NOTIF-01. Missing source → legacy generic. Retry never reconstructs a guessed original. |
| Rescheduled | Exact previous/new date/time, reference, Service/mode; Student may see current assigned provider only when no later change. | Correct source type/parent/type; valid positive aware intervals; new interval equals current. Any later/ambiguous change, or terminal/past state, suppresses approved-path email. | Missing/incomplete legacy source → generic without facts/link. Denied access → minimal. Same source UUID on retry; 9→10 never becomes 10→14. |
| Reassigned | Reference, Service/mode and unchanged verified schedule; Student gets new/current Counselor only. | Correct source type/parent/type and provider IDs; latest unambiguous change; new provider equals current, source upcoming. | Previous provider always minimal without facts/link, even with unrelated management access. Other superseded notices suppress. Missing legacy source → generic. A→B never becomes B→C. |
| Cancelled | Reference, Service, retained cancelled date/time/mode; no private reason or Student identifiers. | Must actually be CANCELLED with valid retained interval/timestamp; normal current access for facts/link. No upcoming wording or joining action. | Missing/incomplete legacy source or access loss → minimal. Same terminal event meaning on retry. |
| 24h reminder | Reference, Service, verified revision date/time/mode, current Counselor for Student only | Existing reminder predicate plus exact event kind/parent/current access; preserve revision/start, active Student and upcoming state checks. | Stale occurrence suppresses through existing worker/currentness or email guard. No extra occurrence, window backfill or new staff recipient. |
| 3h reminder | Same Student fields | Same independent revision/window checks | Retry preserves the same AUTO_3H occurrence; does not borrow 24h identity. |
| Manual reminder | Same Student fields | Same occurrence checks; issuance policy unchanged | Retry does not reissue, reset cooldown or replay a staff mutation. |

Link eligibility and detailed disclosure are independent of later endpoint access.
The existing validated origin/closed APPOINTMENT route is reused; missing or
invalid origin gives minimal fallback. No new details are disclosed without both
the approved policy and a safe authenticated record destination. New email-only
guards do not change Notification Center history or Push currentness/payloads.

Supersession must not rely on random UUID ordering. Existing change timestamps
are not a durable revision number: equal/conflicting timestamp order is ambiguous
and must suppress conservatively. The source row's own schedule/provider facts
must also agree with the current Appointment before any approved detail is used.

All seven events retain Notification/EmailDelivery IDs, claim leases, backoff,
recovery and SMTP at-least-once semantics. Final presentation comparison must
contain only deterministic disclosure values and source identity/revision guards,
not generation time, database reprs or arbitrary mutable source fields.
