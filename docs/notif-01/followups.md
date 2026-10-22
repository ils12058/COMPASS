# Follow-ups and approval boundaries

## NOTIF-2: rich Appointment emails, separately reviewed

Use [the event blueprint](appointment-event-design.md). Add explicit field/recipient
allowlists and event-as-occurred projections owned by Appointments. Resolve the
initial Scheduled provenance gap, superseded changes, previous-provider treatment,
revision-aware reminders and retry meaning before activating detail tables. Reuse
this origin/route/presentation and durable delivery foundation. Do not introduce a
snapshot table unless a precise source-history gap justifies it.

## NOTIF-3: additional operational events

Implement one source family at a time after its matrix gates are satisfied.
Group Sessions needs registration/visibility and public-field approval; Good Moral
needs request access plus minimal issuance facts without OR/payment data; Call
Slips needs live-issuance/void provenance and minimal content; confidential domains
remain minimal. Route-builder support is not event activation or authorization.

## NOTIF-4: cross-channel regression

Exercise Notification Center navigation/read state, reminder/follow-up suppression,
push privacy, account switching, session expiration, MFA setup/restart, historical
links and inaccessible records. Keep one canonical HTTP notification authority and
content-free realtime hints; do not add a second freshness manager.

## GCO/UCN decisions still pending

- Whether exact Appointment date/time, Service and Counselor names are appropriate
  in external Student mail, including forwarded/shared inbox risks.
- Which Student identifiers may be disclosed to currently authorized staff.
- Former Counselor notice versus suppression after access loss.
- Suppression versus clearly labeled historical delivery for superseded changes.
- Safe Group Session titles, venue/facilitator facts; Call Slip/Follow-Up fields.
- Good Moral next-step wording (including Registrar dry sealing) and branding/copy
  sign-off, with OR/payment facts excluded.
- Email retention/address-change policy and broader event-specific disclosure.

These are proposed institutional communication decisions, not inferred approval.
The pilot discloses no source fields beyond an authorized record UUID in its link.

## Future operator and manual verification prerequisites

Verify the canonical external portal origin and configure `COMPASS_PORTAL_ORIGIN`
in the approved worker environment. Missing/invalid origin deliberately keeps
generic mail, so configuration activation must be explicitly verified. Confirm
HTTPS, login/MFA continuation, endpoint authorization and controlled synthetic
destinations before any approved staging mail smoke test. No hostname, secret,
SSH connection, DigitalOcean/Vercel environment change or deployment is performed
by this slice.

Check actual Gmail/Outlook/mobile clients, long links, styling removed, text-only
mail and accessibility manually. Browser automation here tests COMPASS routing,
not external mail clients or real-device acceptance. Mandatory-MFA setup
continuation has synthetic coverage in both engines. Refresh/restart while
mid-challenge deserves separate coverage; the current flow is in-memory and a
reload loses continuation state.

Keep PR target `integration/ux15-modernization`. Do not promote to staging, dispatch
deployment workflows or merge automatically. Hosted CI filters currently exclude
the integration target; do not change filters merely to obtain checks.
