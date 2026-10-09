# ADR-071: PWA, notification freshness, and Web Push

## Status

Accepted for this implementation slice. This decision extends, and does not rewrite, [ADR-041](ADR-041-notifications-email-delivery-foundation.md) and [ADR-046](ADR-046-notification-domain-integrations.md).

## Context

PostgreSQL `Notification` is the durable self-service record. `EmailDelivery` is independent asynchronous transport state. The existing portal bell waits up to 60 seconds to refresh. The live staging backend is a 2-vCPU, 4-GB DigitalOcean Droplet running Caddy in front of Gunicorn with two **synchronous WSGI workers**, plus PostgreSQL, Redis, Celery worker and Beat. The frontend is Next.js 16 App Router on Vercel with a same-origin `/api/v1` rewrite. The observed Caddy configuration has an ordinary reverse proxy and no dedicated streaming tier.

## Decision

### Foreground freshness

Use an 8-second, foreground-only short poll of the existing self-only canonical unread-count and Notification list queries. An open portal refreshes both on visible intervals and immediately on focus, visibility restoration and network reconnection. Background/offline tabs stop issuing requests. TanStack Query invalidation refetches only active queries; an inactive list is marked stale until opened. Logout/session loss unmounts the portal shell, stops the timer, and clears current query state through the existing auth boundary. Auth and maintenance behavior remain on the canonical API.

> Refined by [ADR-100](ADR-100-realtime-transport-foundation.md): a separate Django-free ASGI
> realtime tier now exists for content-free hints, while Gunicorn stays WSGI. This 8-second poll
> is unchanged until a later decision moves Notifications onto realtime hints.

This is bounded near-realtime polling, not a server stream. SSE would pin one of the two synchronous Gunicorn request workers per open client, making the current service unavailable with only a few tabs. WebSocket would require an ASGI deployment and new connection infrastructure. Redis is already used for tasks and caching, but no generic event bus is added. If the backend later adopts an appropriately sized ASGI/streaming tier, replace the poll with a **content-free freshness signal** and preserve canonical refetch/reconnection behavior. The 8-second interval and foreground rule must be capacity tested before a large rollout.

### Durable source and push outbox

Business events continue to create deduplicated `Notification` rows transactionally. Eligible new rows create one `PushDelivery` per active browser subscription. A post-commit Celery kick attempts delivery; Beat recovers pending or expired claims. Delivery status is `PENDING`, `PROCESSING`, `SENT`, `FAILED`, or `CANCELLED`. Transient errors retry at 60, 120, then terminate after three attempts. HTTP 404/410 retires the browser subscription. An unexpected setup/transport exception is isolated from the business transaction; it cannot roll back the Notification or existing email delivery. A narrowly scoped setup failure can mean no push outbox row; opening COMPASS still recovers the durable Notification. Web Push has at-least-attempted, not exactly-once, semantics. Duplicate device alerts are possible after a worker crash between network delivery and claim completion.

`PushSubscription` is one row per browser endpoint, not per user. It holds only ownership, enabling auth session, endpoint digest, Fernet-encrypted endpoint and browser keys, active state, and timestamps. No fingerprint or analytics identifier is collected. The endpoint is globally unique so a browser switched to another account cannot retain an old account's subscription association. Each delivery rechecks account active state, subscription active state, matching owner, and session validity before sending. A normal logout revokes the enabling session server-side, making its push subscription dormant; other devices remain enabled. The browser's OS subscription remains but receives no COMPASS sends until a user explicitly enables it again in a new session. This favors student-lab/shared-device privacy without disabling other devices. In-flight push already dispatched before revocation cannot be retracted.

Subscriptions are authenticated self-service only. Server-side endpoint validation allows HTTPS push-service hosts used by supported browsers and denies arbitrary hosts/ports to prevent SSRF. Endpoint and keys are encrypted at rest with a deployment-owned key; raw values and payload bodies are never logged. VAPID private material is backend-only. The frontend receives only the public key.

### Push policy and lock-screen text

Push eligibility and wording are code-owned in `push_policy.py`. The service worker also accepts only the approved text set and falls back to a generic message. Every push uses title `COMPASS` and destination `/portal/notifications`. It never carries record IDs, authored Notification text, target metadata, protected details, credentials, or arbitrary URLs. Opening the center and then a record invokes normal session and domain authorization.

| Event | Decision | Lock-screen text or reason |
| --- | --- | --- |
| `call_slip.issued` | PUSH | You have a new Call Slip. |
| `call_slip.voided` | PUSH | You have a Call Slip update. |
| `appointment.scheduled`, `appointment.cancelled`, `appointment.rescheduled`, `appointment.reassigned` | PUSH | You have an appointment update. |
| `good_moral.issued` | PUSH | Your Good Moral request has an update. |
| `ecounseling.consent.requested` | PUSH | You have a new request to review in COMPASS. |
| `security.password.reset`, `security.password.changed`, `security.mfa.disabled`, `security.recovery_codes.regenerated`, `security.mfa.admin_reset`, `security.account_access.changed` | PUSH | Your COMPASS account security changed. |
| `exit_interview.reopened`, `inventory.reopened`, `counseling.shared_summary.published`, `routine_interview.intake_ready` | IN_APP_ONLY | Sensitive or non-urgent context stays in authenticated COMPASS. |
| `feedback.invitation` | IN_APP_ONLY | Avoid an OS-level interruption for optional feedback. |

No current event is `POLICY_REVIEW`; the enum reserves that explicit decision for future catalog changes. Tests fail if a new event lacks a decision. Optional email remains account-level and independent of browser push.

### PWA and permission boundary

The manifest uses the existing COMPASS mark, a safe public `/` start URL, and `standalone` display. A first-party service worker caches **only** a small static offline page and uses it solely when a navigation network request fails. It never caches API responses, authenticated HTML, Counseling data, Routine Interview answers, Inventory, Referrals, Call Slips, profile or security state, or form submissions. The offline page says reconnection is required. Worker updates use no-store headers and a restricted worker CSP. HTTPS is required outside localhost.

Browser permission is requested only after the user selects Enable in Account Preferences. Browser push is device/browser specific; disabling unregisters the server endpoint and browser subscription. An ordinary iPhone/iPad Safari tab shows Add to Home Screen guidance instead of Enable. In an installed Home Screen context with actual Push API support, Enable is available. Android and desktop browsers may enable without installing. Unsupported, denied, missing and temporarily unavailable states have distinct text. A supported install prompt is optional and restrained in Preferences; there is no automatic iOS install prompt.

### Maintenance and limitations

No maintenance bypass is added. During active maintenance, normal Notification APIs can be blocked; once operation resumes, foreground canonical queries recover missed durable records. Push attempts for already committed records may occur during maintenance, but clicking still passes through normal maintenance and auth gates. Push does not confer target authorization.

Real iPhone/iPad Home Screen Web Push, Android install behavior, browser permission UX, cross-origin Vercel rewrite behavior, and production push-service delivery require staging/device validation with deployment keys. This implementation does not claim offline protected workflows, guaranteed push delivery, or sub-second streaming.
