# Configuration cutover — documentation only

No setting was changed in a deployed environment.

`COMPASS_EMAIL_DISCLOSURE_POLICY` is the sole operational disclosure selector.
Default/missing `minimal`, empty, unknown, differently cased or invalid runtime types
cannot activate rich fields. Only exact `operational_v1` selects the code-owned
candidate bundles for **all seven Appointment, four Group Session, two Good Moral
and two Call Slip events**. No per-domain setting, compatibility alias, hidden
precedence, approval flag or user preference selects richer fields.

Both `APPOINTMENT_EMAIL_DISCLOSURE_POLICY` and
`APPOINTMENT_EMAIL_DISCLOSURE_POLICY_FILE` must be absent. Presence, including an
empty string or coexistence with the central selector, fails startup with the
bounded replacement instruction before ordinary parsing. Do not read the old
file or print its contents. Original NOTIF-02 docs are historical and explicitly
superseded by NOTIF-03; they are not current operator instructions.

`COMPASS_PORTAL_ORIGIN` remains optional and server-owned. Use only the separately
approved canonical HTTPS origin in live staging. Reject credentials, unexpected
paths/query/fragment, unsafe schemes, malformed authority and request-derived Host.
Only explicitly supported local-loopback origins in local-staging allow HTTP.
Missing/invalid origin keeps generic email with no new operational details/link.
No operational URL includes auth tokens or meeting credentials.

## Prerequisites for a separately authorized operation

1. GCO/UCN approves the complete four-family event/recipient/field/copy bundle,
   external-mailbox exposure and stale-event behavior. Appointment-only approval
   cannot authorize the expanded bundle. Excluded Group title/venue/facilitators,
   Call Slip reporting time/destination, Good Moral payment/seal facts remain excluded.
2. Review source queue age/provenance and the exact backend/frontend commits.
3. Remove both obsolete keys from all backend and worker environments before startup.
   Select `minimal` initially; verify worker consistency and canonical HTTPS origin.
4. Separately authorize deployment and synthetic SMTP/client verification. Use only
   controlled safe recipients; exercise authorization/MFA/retry/cancellation/legacy
   scenarios before selecting the institutionally approved profile.
5. Keep every worker on a consistent binary, central profile and origin. Final
   pre-SMTP comparison cancels a rendered plan whose policy/origin/access/facts change.

## Downgrade and binary rollback

A policy downgrade uses the central `minimal` value consistently across workers.
It retains generic copy and currently supported minimal authorized links. Already
cancelled deliveries stay cancelled: no automatic replay, source rewrite or reissue.
Accepted email cannot be recalled; SMTP remains at-least-once, SENT means handoff.
A binary rollback before NOTIF-03 needs a coordinated operator configuration change;
never run mixed old/new workers while assuming the selectors are interchangeable.
No database migration or durable queue conversion is part of these slices.
