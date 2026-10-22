# NOTIF-2 blueprint: event meaning before rich fields

This is a future design and approval checklist, not implementation or accepted
institutional disclosure policy. NOTIF-01 enables only a generic Scheduled action.
No new Appointment notification state machine, schema or snapshot is introduced.

## Existing provenance

`Appointment` stores UUID/reference, Student, Service/name snapshot, current
provider, aware starts/ends, mode, status, terminal timestamps and reminder revision.
Scheduled and Cancelled notices point to the Appointment itself. These references
do not freeze the initial scheduled time/provider or event-time display names.

`AppointmentChangeEvent` is append-only through domain services. RESCHEDULED rows
store previous/new start/end; REASSIGNED rows store previous/new provider IDs;
both have type, occurrence time and changed actor. The reason is private and must
not enter email. These fields identify *that change*, not whichever Appointment
state happens to be latest at retry time. Display names can change independently;
do not claim an immutable historical name unless provenance actually supports it.

`AppointmentReminderOccurrence` holds UUID, Appointment, recipient, kind, issued
time, issuer, revision and scheduled start. Existing currentness checks match the
live revision/start/status/Student before external transport. Revision increments
on schedule/provider change. Automatic occurrences are unique per revision/window;
manual confirmation replay/cooldown is separate. There is no rich end-time/provider
snapshot on the occurrence; enrich only after a verified matching revision.

## Per-event plan

| Event | Source / provenance | Proposed currentness predicate | Recipients / disclosure and link | Retry / fallback | Future candidate fields and required tests |
| --- | --- | --- | --- | --- | --- |
| Scheduled | `appointment`, source = target Appointment; initial fact at creation, no immutable initial revision on Notification | Upcoming SCHEDULED. For rich initial confirmation, require proof initial revision is unchanged, or reconstruct initial facts from reviewed history. Otherwise suppress rich initial confirmation; never label latest facts as the original schedule. | Student/current provider must have normal access. Former provider minimal or suppress by approved policy. Link to current authorized Appointment only. | Same Notification/Delivery. NOTIF-01 generic link may survive schedule changes with current-details qualification; stale terminal/past sources suppress; missing legacy source generic. NOTIF-2 must select a stricter per-event policy before details. | Approved Service label/reference, initial date/start/end/timezone/mode/provider. Test cancellation before send, reschedule/reassignment before first send, fixed-slot parity, legacy references, access removal and retry. |
| Rescheduled | `appointment_change_event`, exact RESCHEDULED row; target owning Appointment | Source/target/type match, source still scheduled/upcoming; determine whether this is latest relevant schedule event and whether any intervening reassignment affects disclosure. Prefer suppress superseded pending reschedules until historical-delivery wording is approved. | Student/current provider, independently authorized at send. No former provider's new protected schedule. Current Appointment link only while allowed. | Event facts come from this row on every retry. Never substitute a later row or newest live time. Missing source → approved minimal fallback or suppress; superseded → documented suppression, not SMTP retry. | Previous/new start/end in institutional zone, reference and approved Service/provider context. Test 9→10→14, later cancellation/provider change, source/target mismatch, cross-date schedules and repeated transport failure. |
| Reassigned | `appointment_change_event`, exact REASSIGNED row with previous/new provider IDs | Type/source/target match; latest relevant assignment; source still scheduled/upcoming for upcoming copy. Distinguish historical notice eligibility from current rich access. | Student: current approved provider details. New provider: own current assignment/access. Previous provider: bare historical notice or suppression pending GCO decision, no current Student/provider/schedule facts or link if access lost. | Do not reinterpret A→B as B→C. Retry rechecks current eligibility and class. Missing source/changed access downgrades or suppresses per approved policy. | Approved previous/new Counselor display labels for Student, reference, matching schedule if safe. Test A→B→C, revoked capabilities/scope, duplicate recipients, former provider with independent scope and minimal-only policy. |
| Cancelled | `appointment`, target same; cancellation timestamp/actor stored on terminal record, Notification deduplicates event | Confirm actual CANCELLED state and source/target. No upcoming language or active joining action. Lifecycle has no general reopen operation in this slice. | Student and provider at cancellation; current record access still controls any facts/link. Prior cancellation recipient ownership is insufficient. | Preserve cancellation event meaning. Missing legacy source can use existing generic cancellation notice; inaccessible recipient receives no details. Do not fabricate cancellation reason. | Approved cancelled schedule/reference/mode with explicit cancelled label; no reason. Test duplicate cancellation, old provider, source missing, already-ended schedule, retries and not-found destination. |
| Reminder 24h | `appointment_reminder`, AUTO_24H occurrence; Appointment target and revision/start snapshot | Preserve `reminder_notification_is_current`: occurrence exists, same active Student/role, upcoming SCHEDULED, matching start and revision. Add rich-disclosure access check separately. | Student only; normal record authorization required for rich facts/link. No staff copy introduced. | Existing stale-occurrence cancellation and bounded transport retry. Do not create another occurrence or backfill missed windows during retry. | Matching revision date/start/end/mode/provider/reference/Service if approved. Test cancellation, reschedule and reassign between issuance/claim/render/send, keyless worker compatibility and timezone boundary. |
| Reminder 3h | same, AUTO_3H occurrence, independent unique automatic window | Same matching-revision predicate; retain half-open lead window discovery and no retrospective backfill | Same Student-only policy/link | Same logical occurrence on retry; don't borrow AUTO_24H facts/identity | Same approved fields; test automatic/manual coexistence, per-window dedupe, superseded occurrence and exactly at window edges. |
| Manual Reminder | `appointment_reminder`, MANUAL occurrence with issuer, revision/start | Same external currentness as automatic. Issuance keeps staff capability/resource scope, recent MFA, confirmation UUID and manual cooldown. | Appointment Student only; issuer authority does not grant email detail disclosure to other recipients | Existing confirmation/batch replay, one occurrence/event; retry does not issue a new manual reminder or bypass cooldown | Same approved fields. Test single/bulk authorization/replay, automatic coexistence, concurrent manual attempts, reassign after request and inaccessible Student. |

## Required event/disclosure rules

1. Keep source identity separate from navigation target. Validate event type and
   parent relationship before resolving facts; never use target alone to find an
   unrelated event row.
2. A delayed Scheduled notification after cancellation cannot claim an upcoming
   booking. The pilot suppresses such a source, without changing the general
   `notifications/current.py` dispatcher or Push behavior. NOTIF-2 should decide
   whether to share a reviewed ordinary-Appointment currentness interface across
   channels rather than silently changing all channels.
3. 9→10→14 must either suppress the first pending change or render accurately
   labeled 9→10 history with approved warning. Never render 10→14 as the first
   event. Supersession policy needs GCO approval before activation.
4. Compute event eligibility, current disclosure and current link independently.
   A former Counselor's historical reassignment notice is not current access.
   If the institution permits a minimal former-provider email, make that an
   explicit class, not a fallback rich renderer with blank fields.
5. Use `INSTITUTION_TIME_ZONE` helpers; retain aware instants, start/end and
   cross-date boundaries. Do not invent venue, room, duration or Service facts.
6. Never include change reasons, concerns, Counseling context, Referral data,
   evaluations, online room URLs/join tokens, recordings/transcripts or private
   handoff information. Default source labels are not safe HTML or URLs.
7. Stable logical event identity must survive retry even when optional detail
   projection downgrades. An email already accepted externally cannot be revoked.
8. Define safe missing-source/access-loss outcomes before enabling each event.
   Query/template defects are not transient SMTP failures. Keep logs bounded.

## Source-history decision gate

First try existing change rows/revisions and code-owned text. Initial Scheduled
facts and historical provider display names are the most obvious gaps; they do
not justify a generic Notification JSON snapshot. Document exactly which fact
cannot be reconstructed, its retention/privacy owner, compatibility for queued
rows, encryption needs and migration trade-off before adding storage. Keep any
proposal separately reviewable. Full detail tables and new snapshots are absent
from NOTIF-01.
