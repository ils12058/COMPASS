# NOTIF-04 — cross-channel integration and security readiness

Audited October 23, 2026, against freshly fetched integration
`f0b05dcf6a2a80e22193144891d23fee5865bdad` (merged #310, #311, #312).
Source: `test/notif-04-cross-channel-hardening`; target: `integration/ux15-modernization`.

Email informs. In-app notifications guide. COMPASS records provide the full details.

The audit reconciles 30 catalog events, 29 email-enabled events and 15 operational
candidate presentations. Existing Notification/EmailDelivery, recipient/channel
policy, claim/lease/retry/recovery, Celery, Mailer, source-owned currentness, Push,
HTTP Notification Center and authentication/authorization remain authoritative.

The sole production correction preserves a validated record destination when MFA
verification or required authenticator setup reloads and requires restarted login.
Only `next` travels in the URL; challenge metadata, authenticator secrets, recovery
codes, credentials and sessions stay out of storage and URLs. Reload still requires
a fresh password challenge. Normal uninterrupted MFA continues through the existing
in-memory flow. No new authentication persistence or backend API is introduced.

New tests join all 15 events under both policies to real Notification list/read,
locmem transport and Push policy; exercise actual protected APIs for nine actor
cases, registration ownership and retained history; and check backend/frontend
route parity. Browser scenarios use actual React/Next pages with intercepted
synthetic APIs. Backend API tests independently enforce real domain authorization;
these are complementary layers, not a live browser-to-backend/SMTP acceptance test.

Read [findings](findings-and-disposition.md), [event matrix](event-channel-matrix.md),
[validation](validation.md), [cross-channel results](cross-channel-validation.md),
[UAT](uat-matrix.md), [configuration](configuration-cutover.md),
[readiness](readiness-assessment.md) and [remaining follow-ups](remaining-followups.md).
[Manifest](integration-manifest.md) records the dependency chain.
[Accessibility](accessibility-and-responsive.md) and [email clients](email-client-readiness.md)
separate local evidence from manual acceptance.

The original Proposal #5 in the user's `COMPASS Development Proposal Notes - Fifteen
Proposals.md` was reviewed as design context, alongside the completed NOTIF-01/02/03
contracts, validation, previews and follow-ups. Its illustrative fields are not
additional authorization; the narrower NOTIF-03 versioned field bundle controls.

No staging/main update, deployment, deployment workflow dispatch, SSH, Vercel,
live configuration, institutional recipient data or real outbound mail is included.
The PR is for review only and must not be automatically merged.
