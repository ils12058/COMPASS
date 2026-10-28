# Delivery, retries and consistency

The existing `EmailDelivery` pipeline remains the only queue. No new task,
recipient, status, payload store or transport is added. Claims still lock the
delivery row, enforce eligibility, capture recipient email and issue the existing
lease/token. Duplicate tasks and expired-claim recovery retain their existing
behavior. The original reminder currentness check remains active at claim time.

After claim, the worker resolves the source-owned plan. Under `minimal`, existing
generic mail and qualified Scheduled links are unchanged. Under `operational_v1`,
the seven Appointment event sources are checked before typed approved facts can
be rendered. Missing/invalid/incomplete provenance yields minimal mail without
untrusted detail/link; stale or superseded rich sources cancel. Missing/stale
reminder occurrences can already be cancelled by the original claim predicate,
before fallback rendering, as before this change.

## Final transport boundary

After rendering and immediately before `Mailer.send`, the existing transaction
locks the claimed delivery and verifies token/status/lease, recipient activity and
email, original cross-channel currentness, then re-resolves the email plan. Plan
equality includes disclosed values, source UUID, event/target identity, recipient
class, current revision/provider/interval, disclosure version and validated link.
The renderer independently rebuilds the URL; it never trusts a supplied URL.

The validated-link snapshot is a bounded correctness fix to NOTIF-01: replacing
one approved origin with another after rendering now changes plan equality and
cancels the old destination. Previously the target alone could compare equal.
Unrelated metadata, generation time, private reasons and nondisclosed provider
names are excluded from the comparison. Account email changes are checked through
the existing claim snapshot rather than included in template data.

Existing bounded classifications are reused:

| Condition | Existing outcome/code |
| --- | --- |
| Stale/superseded source plan | CANCELLED / `source_ineligible` |
| Source, recipient, policy or URL changes after rendering | CANCELLED / `source_or_recipient_changed` |
| Source resolution/render/revalidation exception | FAILED / `template_error`, with bounded phase reason |
| SMTP exception | Existing retry/backoff / `transport_error` |
| Transport returns zero | Existing retry/backoff / `send_returned_zero` |
| Successful handoff | SENT |

Retries retain Notification, EmailDelivery and source IDs. They re-resolve that
source and never issue another reminder or convert an earlier change into a later
event. Stable retries can send the same approved facts; a superseded retry
cancels. Cooldowns, reminder windows/revisions, auto/manual coexistence, bulk
issuance, staff authority/MFA and existing idempotency are unchanged. Cancellation
is terminal for that delivery; a later rollback does not silently revive it.

## Limits and diagnostics

SMTP remains effectively at-least-once when acceptance precedes a process crash.
SENT records accepted transport handoff, not reading or final mailbox receipt.
External accepted mail cannot be revoked. Database reads and SMTP cannot be one
atomic operation; mutations after the final read remain a transport-boundary race.
The implementation narrows that interval without claiming exactly-once delivery.

Logs retain bounded delivery/Notification IDs, event, attempt, status, failure and
presentation reason. Fact values, raw source objects, bodies, email addresses,
URLs and raw exception messages are not added to logs/reprs/audit metadata.
Transaction-enabled tests exercise worker-thread rendering while a separate
committed database mutation changes schedule, role or reminder revision. Existing
claim, retry, duplicate-task and transport-error regression tests also pass.

Email-only supersession/disclosure rules do not change Notification Center history
or browser Push. The sole shared reminder extraction preserves its old predicate;
channel regression tests verify that separation.
