# COMPASS PWA and browser notification deployment

## Backend

Apply the notifications migration before enabling Web Push. Keep the existing PostgreSQL, Redis, Celery worker and Beat topology; Beat dispatches due push deliveries every 60 seconds. No Caddy or Gunicorn streaming change is required because foreground freshness uses short requests. The DigitalOcean staging Droplet currently has two synchronous WSGI workers; capacity test the 8-second visible-client refresh rate before expanding usage.

Keep public/configuration values in the backend deployment's protected `.env`. Live staging uses
[Vault Agent file delivery](vault-live-staging.md) for `WEB_PUSH_PRIVATE_KEY_FILE` and
`WEB_PUSH_STORAGE_KEY_FILE`; preserve both existing values and the public VAPID pair during cutover.
For a new initial setup, configure these values through the appropriate secret source:

- `WEB_PUSH_ENABLED=true` only after keys and migration are ready.
- `WEB_PUSH_PUBLIC_KEY`: URL-safe base64 P-256 VAPID public key for `PushManager.subscribe`.
- `WEB_PUSH_PRIVATE_KEY`: matching URL-safe base64 raw or DER VAPID private key accepted by `pywebpush`; keep secret.
- `WEB_PUSH_CONTACT`: a monitored `mailto:` address for VAPID claims.
- `WEB_PUSH_STORAGE_KEY`: independent Fernet key for browser endpoint/key encryption at rest; keep secret and back up securely.

Create VAPID keys using a trusted Web Push/VAPID tool; verify the public/private pair in a staging test subscription before enabling users. Generate the Fernet key with `Fernet.generate_key()` from the pinned backend `cryptography` dependency. Never commit or print private key material. Preserve the storage key across redeploys and backups; losing it makes existing encrypted subscriptions unreadable. Coordinate storage-key rotation and VAPID-key rotation with a subscription migration/re-enrollment plan. The `WEB_PUSH_ENABLED=false` default leaves existing in-app/email behavior intact until infrastructure is configured.

The registration API accepts only reviewed HTTPS push-service hosts: Google FCM, Mozilla, Apple, and Microsoft WNS. Review and extend the allowlist in code if a supported browser uses a new host. Give the Celery worker outbound HTTPS access to push services. No inbound push port is needed. Never log browser endpoints, keys, or payloads.

## Frontend

Deploy `manifest.webmanifest`, `/sw.js`, `/offline.html`, and the two approved COMPASS icons together on the HTTPS frontend origin. Preserve the existing same-origin `/api/v1` rewrite and cookie/CSRF settings. The worker must be served at `/sw.js` with JavaScript MIME type, no-store cache headers and its restricted CSP. Do not add broad API runtime caching. Verify Home Screen install and push using a real iPhone/iPad; desktop emulation cannot prove Apple delivery.

## Rollout checks

1. Migrate the backend, verify worker and Beat health, then enable `WEB_PUSH_ENABLED` with protected keys.
2. Deploy the frontend and verify manifest/icons/worker routes, HTTPS, and installability.
3. Sign in with a staging account, explicitly enable on one device, create an eligible event, and confirm the durable Notification, push attempt, safe OS wording, and Notification Center navigation.
4. Sign out; verify subsequent events do not push to that session-bound device. Sign in again and explicitly re-enable. Confirm another enabled device remains active.
5. Verify an ineligible event stays in-app only, email rules remain unchanged, and a simulated offline navigation shows only the offline shell.
