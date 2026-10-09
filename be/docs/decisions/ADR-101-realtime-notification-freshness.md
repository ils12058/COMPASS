# ADR-101: Realtime Notification freshness

## Status

Accepted. First domain consumer of [ADR-100](ADR-100-realtime-transport-foundation.md).
Refines the foreground freshness policy in [ADR-071](ADR-071-pwa-notification-freshness-and-web-push.md).

## Decision

The closed public registry adds exactly one event:

```json
{"v":1,"type":"notifications.changed"}
```

It accepts **zero fields**. No Notification identifier, title, message, event code, unread count,
recipient, target, source, timestamp, or status travels through realtime. The server-derived
user channel determines the recipient; every connected tab/session of that user receives the
same hint. Other users do not receive it.

`create_notification_for_event` publishes only for a newly created row. An idempotent duplicate
that returns the existing row does not publish. `mark_my_notification_read` publishes only on
an unread-to-read transition, preserving recipient ownership, locking, and `read_at`.
`mark_all_my_notifications_read` performs one bounded bulk update in an atomic block and
publishes one hint only when its updated count is positive, with no iteration or per-row locks.
All three use `publish_to_user_on_commit`: a surrounding rollback discards the hint.

Email preferences, push subscriptions, and email/push delivery attempts or statuses do not
change the in-app list/unread state and do not publish hints. Demo seed timestamp normalization
is an operator fixture operation, not a foreground Notification producer.

HTTP and PostgreSQL remain authoritative. Redis publication is best-effort: its failures are
logged and dropped by the existing ADR-100 helper and never undo successful Notification
writes. Creation works with realtime disabled and without an open socket. There is no outbox,
replay, durable delivery, exactly-once guarantee, or ordering guarantee across reconnects.

The single portal-level `NotificationFreshness` consumes `notifications.changed` through
`useRealtimeEvent` on the existing portal socket. It invalidates only the generated base keys
for `notificationsGetUnreadCount` and `notificationsListMine`. React Query reconciles active
queries over authenticated HTTP and marks cached list pages stale according to its usual
semantics. The Bell and Center continue reading these caches; hints never patch Notification
content or arithmetic counts. Existing same-tab HTTP confirmation/invalidation stays intact.

Each advanced ready `generation` from `useRealtimeStatus` also reconciles canonical state,
including the initial ready. Repeating the same generation does not trigger a refresh. Polling
continues every **8 seconds** while disabled, idle, connecting, or reconnecting and every
**60 seconds** while live. Missing hints heal on these polls, the next ready generation, or an
immediate focus, visible-return, or online-return refresh.

Hidden documents and offline browsers issue no freshness HTTP requests. A hint received during
the socket's hidden grace period records a pending reconciliation for visible return. At most
one reconciliation runs at a time; refresh requests received during it collapse into one
trailing reconciliation after both query families settle. If it settles hidden/offline, the
pending request waits for the next foreground/online opportunity. Unmount removes the timer,
listeners, and realtime subscription and prevents a trailing refresh.

Web Push remains independent device/background delivery; it is neither replaced nor suppressed
by a foreground socket. Existing realtime flags gate the transport. No Notification-specific
flag, user-visible connection status, migration, or OpenAPI change is introduced. Guidance
Messages, presence, typing, read receipts, deployment, and enablement are outside this slice.

## Validation

Protocol tests reject every extra Notification field and verify recipient-only, multi-session
forwarding. Transaction tests exercise real commits/rollbacks and Redis failure. A deterministic
local integration test authenticates through the ordinary ticket endpoint, creates through the
Notification service, receives the fieldless hint through real Redis and the ASGI socket boundary,
and checks list/unread state and mark-read through authenticated HTTP, with another user's socket
remaining silent. Browser tests in Chromium and WebKit use synthetic HTTP/socket fixtures to
verify Bell/Center freshness, cached-page reconciliation, reconnect healing, cross-tab reads,
one socket per tab, and polling when transport is disabled/unavailable.
