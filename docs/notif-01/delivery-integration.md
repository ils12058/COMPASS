# Durable delivery integration

## Existing lifecycle retained

Business transactions create one Notification per recipient/event/source and its
one-to-one EmailDelivery. Optional-email preference is applied by the existing
producer; mandatory policies are unchanged. An ID-only `on_commit` callback
requests Celery delivery. Failed enqueue leaves recoverable PENDING state. Beat
scans due retries and expired claims. No new dispatcher, queue, polling loop,
table, recipient snapshot or source-content store exists.

Claiming still locks only EmailDelivery, checks status/due date/lease, recipient
activity and the existing currentness dispatcher, increments attempt count and
records a random claim token/expiry. Competing unexpired claims skip. Terminal
updates require the matching claim token. Recipient address is resolved from
the current canonical account at claim time, not persisted in a body snapshot.

After claim, the worker loads the actual Notification and resolves a typed plan
through approved source IDs. It renders using the catalog and controlled adapter.
Immediately before Mailer, a fresh delivery/account read rechecks claim ownership,
expiry, recipient activity, unchanged current email and source currentness, then
re-resolves presentation eligibility against fresh capabilities and resource scope.
A changed plan cancels the attempt with existing `source_or_recipient_changed`.
Inactive accounts are now explicitly rechecked at this final boundary as well as
at claim. No source facts are cached in Notifications or forwarded to templates.

Scheduled pilot eligibility is email-specific: `notifications/current.py` and
Push behavior remain unchanged. It suppresses a Scheduled source that is no
longer scheduled/upcoming, including when its former recipient lost access.
Invalid/missing legacy references use generic copy. A newly changed authorization
after rendering cancels rather than sending the already-rendered link.

## Outcomes and retry classification

| Condition | Result |
| --- | --- |
| Other supported catalog event / no approved presentation | Existing generic or specialized fixed template |
| Optional origin absent/invalid | Generic email; no link, no transport retry |
| Missing/invalid/mismatched target or missing legacy source | Generic email; no invented URL or details |
| Current recipient cannot receive a link | Existing minimal email; no protected facts or UUID |
| Scheduled source is cancelled/completed/no-show/past | CANCELLED, `source_ineligible` |
| Reminder/Follow-Up/Group Session no longer current | Existing claim/final currentness cancellation |
| Account/email/lease/source/presentation changes after render | CANCELLED, `source_or_recipient_changed` |
| Unexpected resolver error | FAILED, existing `template_error`; diagnostic `resolution_error` |
| Template error | FAILED, `template_error`; no retry |
| Unexpected final source-revalidation error | FAILED, `template_error`; diagnostic `revalidation_error` |
| Unknown event without a catalog template | Existing terminal `template_error`; no fabricated copy |
| SMTP raises | Existing bounded exponential retry, `transport_error` |
| Mailer returns zero | Existing retry, `send_returned_zero` |
| Successful provider handoff | SENT, clear claim/retry state |

The failure/status/API vocabularies and maximum attempts stay unchanged. Optional
presentation outcomes have their own reason codes, not additional delivery states.
Unexpected source failures use the established nonretryable rendering phase rather
than being mislabeled as SMTP failures. Operator APIs may normalize cancellation
codes they do not expose to `unknown_failure`, as before; no new API enum is added.
Preference changes after queuing keep existing behavior; this slice does not add
a new preference-recheck mechanism.

## Logging and transport limits

Only bounded reason/stage codes join existing delivery IDs, event code, attempt,
status and correlation ID. `JsonFormatter` permits `presentation_reason` only
through its existing identifier/code filter. It rejects prose, URLs and structured
payloads. Resolver/template/provider exception text, source records, addresses,
bodies and complete deep-link context are never logged by the new path.

Database checks cannot atomically commit an external SMTP send. Access/account
changes after the last read can race with provider submission; accepted mail
cannot be revoked. Claims prevent ordinary concurrent sends, but a crash after
SMTP acceptance and before recording SENT may lead to a retry/duplicate. This is
the pre-existing at-least-once guarantee, not exactly-once delivery. SENT does not
prove inbox receipt, opening or reading. Tests use local memory/mock transport;
there is no real-recipient or live SMTP proof in this PR.
