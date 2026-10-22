# Trusted email link contract

## Origin ownership

`COMPASS_PORTAL_ORIGIN` is a dedicated server-owned setting, default `""`. The
builder reads no request and has no Host/Origin/Forwarded, ALLOWED_HOSTS, CORS,
CSRF, callback or external meeting-link fallback. Environment-file ownership is
the trust boundary: syntactic DNS validation does not prove domain ownership.
No deployed hostname is guessed, provisioned or hardcoded here.

`validated_portal_origin(value, app_env=...)` accepts canonical lowercase ASCII
DNS HTTPS origins. Live ports are absent or exactly `443`. A single trailing `/`
is normalized away. DNS labels are bounded and cannot begin/end with `-`; the
final label must be alphabetic, length 2–63. Bare labels, IP literals in live,
`.localhost`, uppercase/noncanonical authority, Unicode, percent-encoding,
trailing DNS dots, empty/leading-zero ports and unknown environment names fail.
Punycode ASCII labels can be configured; Unicode hostname input cannot.

In **local-staging only**, explicitly configured `localhost`, `127.0.0.1`, or
`[::1]` may use HTTP or HTTPS and a canonical port 1–65535. DEBUG does not grant
this exception. Other HTTP names and nonloopback IPs remain unavailable.

All origins reject credentials (including empty userinfo), query/fragment
delimiters even when empty, application paths, extra slash paths, traversal,
backslashes, whitespace/control characters and unsafe schemes. No arbitrary
origin path is appended to a route.

Missing/invalid configuration produces `origin_missing`/`origin_invalid`, with
no URL. These are safe generic presentation outcomes, not SMTP failures and not
application startup failures. Rollback to blank configuration removes new email
links while preserving generic email. Already sent messages cannot be recalled.

## Closed route vocabulary

`NotificationEmailTarget` holds only a target type and optional ID. String IDs
must be canonical hyphenated UUID shapes (case is normalized), or UUID objects.
No URL, path, fragment, user-authored label or arbitrary query input is accepted.
An invalid supplied ID is rejected even for a recipient-scoped destination.

| Type | Relative route | ID meaning |
| --- | --- | --- |
| APPOINTMENT | `/portal/appointments/{id}` | Appointment |
| GROUP_SESSION | `/portal/group-sessions/{id}` | Session, not registration |
| GROUP_SESSION without ID | `/portal/group-sessions/my` | Explicit recipient-scoped fallback |
| GOOD_MORAL | `/portal/good-moral/{id}` | Request |
| CALL_SLIP | `/portal/call-slips/{id}` | Slip |
| GUIDANCE_FOLLOW_UP | `/portal/follow-ups/{id}` | Follow-Up, not event |
| ROUTINE_INTERVIEW | `/portal/routine-interviews/{id}` | Interview |
| EXIT_INTERVIEW | `/portal/exit-interviews/{id}` | Interview, not reopen event |
| COUNSELING_SHARED_SUMMARY | `/portal/counseling/summaries/{id}` | Published summary |
| E_COUNSELING | `/portal/e-counseling/{id}` | Appointment, never room/join token |
| INVENTORY | `/portal/inventory/current` | Recipient's current self-service record; supplied UUID is not put in URL |
| FEEDBACK | `/portal/feedback?opportunity={id}` or `/portal/feedback` | Feedback opportunity only |
| ACCOUNT_SECURITY, unknown | unavailable | Excluded from ordinary email links |

Route support alone does **not** activate an email event. Only Scheduled has an
email resolver in this slice. `NotificationEmailLink` returns an explicit reason
and a URL or `None`; `target_invalid` differs from `target_unsupported`. Sensitive
IDs/URLs are excluded from representations. No synthetic `/portal` substitute is
invented for an invalid record target.

## Authentication and destination access

The email points directly to the record, without auth credentials or a login
token. `PortalBoundary` first checks the canonical session. A confirmed 401
clears account cache and navigates to `loginPathForPortal(currentPath)`. The login
server page validates `next` through `safePortalDestination`. Only same-origin
`/portal` or `/portal/...` destinations survive. Absolute URLs, protocol-relative
input, backslashes, nonportal/login paths and traversal out of portal fall back.
Encoded absolute destinations are never decoded into a second redirect URL.
Opaque encoded segments that remain inside `/portal/` are ordinary local paths,
which may return not-found; they never become an external navigation.

Password success returns to the safe path. Existing MFA verification stores it
only in the in-memory AuthFlowProvider, then restores it after verification.
Mandatory setup carries the same path through setup, recovery-code acknowledgment
and a fresh sign-in. No session, CSRF, trusted-browser or recent-MFA policy changes.

After login, Appointment detail queries its normal authenticated endpoint. An
unauthorized UUID produces the existing `appointment_not_found`/unavailable state,
with no source data. The link never grants permission. Browser fixtures prove
password, ordinary MFA, logged-in, denial, session-expiry and mandatory-setup
continuation, including recovery-code acknowledgment and a fresh MFA sign-in.
Refreshing midway through MFA loses the in-memory flow and asks the user to
restart; this existing limitation is documented for follow-up.

## Security proof and operator prerequisite

Negative tests cover hostile request headers, request query, origin credentials,
paths/ports/schemes, encoded traversal, malformed IDs, external/protocol-relative
targets, injection strings and secret-bearing queries. Cross-source tests verify
that backend record routes still occur in the frontend mapping and actual pages.
HTML links and plain-text URLs must agree and use the configured origin exactly.

Before any future deployment, an authorized operator must verify ownership of the
actual external frontend origin, confirm HTTPS and ingress routing, explicitly
set it in the **email worker's effective environment**, and validate browser
login/record access and approved synthetic mail destinations. Compose already
uses environment files; no live configuration or deployment is changed here.
Test origins use the reserved `.example` namespace only.
