# Delivery and source-currentness integration

The existing Notification/EmailDelivery pipeline remains the durable owner.
Business producers, ID-only Celery kicks, claim locks/tokens/leases, Beat recovery,
email preferences, retry/backoff/attempt limits and SMTP adapter are unchanged.
No new queue, status, schema, recipient list, serialized source store or task exists.

After claim, Notifications dispatches explicit event families to their domain-owned
resolvers. Each verifies exact source/type/target and current self-authorization.
The central code-owned profile admits the domain's typed row vocabulary; it does
not discover arbitrary models/fields from `source_type`. The rendering plan has
explicit Appointment/Group Session/Good Moral/Call Slip fact variants. Mixing
variants, wrong binding/class, untyped rows, duplicate/unapproved fields, unavailable
origin snapshots or unapproved rich profiles fails safely before transport.

New minimal-mode links retain frozen source guards but no display rows. Rich
plans add only the exact approved event/recipient rows. The trusted URL is rebuilt
with NOTIF-01's origin/closed-route builder and compared with the validated snapshot.
Code-owned headings, actions and templates are selected internally; no caller
supplies free-form subjects, template names or source dictionaries to rendering.
HTML autoescape stays on; literal text escaping is disabled only in the bounded
typed text-row partial. No tracker or embedded remote resource is introduced.

## Pre-SMTP comparison

The existing final transaction locks the claimed delivery and checks token/status/
lease, current account activity/email and baseline currentness, then re-resolves
the full email presentation. Relevant source identity, participant/owner proof,
status/provenance, interval/revision, disclosed rows, effective policy and actual
trusted URL must compare equal. A safety/meaning change cancels the rendered
attempt. Generation time, unrelated metadata and excluded private fields do not
enter equality. Separate committed-transaction worker tests cover all three new
domains; NOTIF-02's Appointment concurrency tests remain included.

| Condition | Existing outcome |
| --- | --- |
| Approved eligible source | SENT after accepted handoff |
| Minimal policy + eligible source | Same durable delivery, safe link without new rows |
| Missing/invalid/incomplete legacy source or denied action | Generic no-data/no-link fallback, unless baseline currentness already cancels |
| Obsolete lifecycle/superseded source | CANCELLED / `source_ineligible` |
| Source/recipient/profile/origin change after rendering | CANCELLED / `source_or_recipient_changed` |
| Resolution/render/revalidation exception | FAILED / existing `template_error`, bounded phase reason |
| SMTP exception or zero return | Existing bounded retry / transport failure code |

Original Group Session shared currentness can reject a missing/stale source during
claim before fallback resolution. No new shared predicate change is made to force
delivery of such messages. Conversely, email-specific participant/provenance rules
can be stricter without deleting Notification Center history or changing Push.
Stored Notification/delivery/source UUIDs are never rewritten by rendering/retry.

## Limits and privacy

Retries project the same event, never the latest different event or a new issuance.
Duplicate claims still skip. Cancelled deliveries remain cancelled after a policy
downgrade. Logs retain bounded event/delivery/Notification IDs, attempt/status/
failure/presentation codes; no new body, address, source value, URL, model repr or
raw exception text is emitted. Fact/row value/URL fields stay excluded from reprs.

SMTP is effectively at-least-once across acceptance/crash/recovery. SENT records
transport handoff, not reading or final inbox receipt. A database check cannot
atomically include SMTP, and accepted external mail cannot be recalled. No claim
of exactly-once delivery or complete elimination of the final read-to-send race.
