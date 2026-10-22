# Event facts and supersession

Source identity never changes on retry. Notification's source UUID identifies the
specific event; its target identifies the current Appointment workspace. These
are verified independently before any approved field is projected.

## Scheduled origin

Scheduled's source is the Appointment itself, including Fixed-Date Slot bookings.
It does not freeze the original time/provider. Rich initial facts require current
upcoming SCHEDULED state, current access, reminder revision 1, no revision-start
marker and no AppointmentChangeEvent history. These are the current domain's
unchanged-initial-state invariants, not a reconstruction from arbitrary timestamps.

After any known schedule/provider change, the generic Scheduled notice keeps its
qualified NOTIF-01 link where currently authorized. It does not borrow current
values as original booking facts. Terminal/past appointments suppress as before.
Missing legacy source/target references use fixed generic copy without facts/link.
No original schedule or provider is guessed, and historical rows are never edited.

## Change events

Rescheduled resolves the exact RESCHEDULED source and validates its parent,
previous/new aware positive intervals and new interval's agreement with current
state. Reassigned resolves the exact REASSIGNED source, validates distinct
previous/new provider IDs and current provider agreement. Appointment reference,
immutable Service-name snapshot and mode are canonical context, not new mutable
Notification metadata. Current provider names are explicitly labeled current
names, never immutable historical names; previous provider names are not disclosed.

Any other change with later/equal occurrence time **or** later/equal creation time
conservatively supersedes the source. Random UUID ordering is not chronology.
Conflicting/equal clocks may suppress both notices rather than invent an order.
This deliberately favors no obsolete rich mail over ambiguous history delivery.
The source's own post-change values must also match current state; a timestamp
check alone cannot turn an inconsistent row into trustworthy facts.

Example: **9 AM → 10 AM → 2 PM**. The first pending rich reschedule is suppressed.
The second uses its own 10 AM previous value and 2 PM updated value. A retry of
the first never finds the second row or rewrites 9→10 into 10→2. A subsequent
reassignment also suppresses that older reschedule's rich context.

Example: **Counselor A → B → C**. The old Student/new-provider A→B rich notice is
suppressed. The B→C Student notice names C from its verified ID/current account
label; B's historical previous-provider notice stays minimal without C, Student
details, schedule or link. A previous-provider classification stays minimal even
if that person later becomes assigned again or has another management scope.

## Cancellation and reminders

Cancellation must be the current terminal CANCELLED state with a cancellation
timestamp and valid retained schedule. It may describe a future or past cancelled
interval, without upcoming/join language or a private cancellation reason. A
reschedule/reassignment followed by cancellation cannot send an upcoming rich
change confirmation. Minimal legacy cancellation copy remains available.

Reminder sources must match actual kind (AUTO_24H/AUTO_3H/MANUAL), parent and
Student. The shared existing predicate requires active Student role, matching
Student ownership, current revision/start and upcoming SCHEDULED state. Rich
projection adds normal current record access. End/provider context is taken only
from that verified matching revision; it is not a new occurrence snapshot. No
occurrence is created by rendering or retry. Window identities, cooldown, MFA,
bulk bounds, confirmation keys, discovery and no-backfill behavior are unchanged.

## Policy/channel and historical limits

New change-event suppression is email-specific and applies to the explicitly
approved operational path. Default minimal behavior remains compatible with the
foundation. `notifications/current.py`, in-app lists/history and Push are not
globally tightened by an external disclosure policy. Existing reminder currentness
still applies to both transports independently of rich approval.

Source history is append-only through current services, not a new database
immutability constraint. Current account names can change. Legacy history can be
incomplete; the initial unchanged-state rule depends on the current supported
revision/history contract and cannot certify arbitrary out-of-band rewrites.
Equal/contradictory timestamps have no reliable sequence. These are reasons for
minimal fallback/suppression, not a generic JSON payload store. A future immutable
revision or historical-name snapshot would need a separate privacy/retention and
compatibility review; none is introduced here.
