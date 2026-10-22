# NOTIF-02: approved rich Appointment emails

Audited integration baseline: `6f73efd981023a29fef0b0ea10ecbaacbe16212b`,
October 22, 2026. PR #310 is merged and its reviewed NOTIF-01 implementation is
present. Staging remains `0a843dae20c01984d0fb9aa46d5eef34102ab386`; main remains
`1a9933535a0b8c0cbd7764c35f301e8402f48375`. Isolated branch/worktree:
`feat/notif-02-rich-appointment-emails`,
`~/.codex/worktrees/notif-02-rich-appointment-emails/COMPASS`.

## Result and default behavior

All seven existing Appointment events can produce typed, source-owned operational
email details under the explicit `operational_v1` policy. The default setting is
`APPOINTMENT_EMAIL_DISCLOSURE_POLICY=minimal`; absent, invalid, differently cased
or unknown values remain minimal. This code version is an approval mechanism,
not institutional approval. Nothing was enabled in a deployed environment.

With the default, generic mail and already-authorized NOTIF-01 Scheduled links
retain their behavior. With explicit approval and a trusted portal origin,
Students may receive reference, Service snapshot, local schedule, current
Counselor display name and mode. Assigned Counselors receive operational fields
without Student identifiers or provider names. Former Counselors remain minimal
without record links, including when independently authorized through another
scope. No recipients or channels are added. GSS remains outside rich disclosure;
its existing scoped Scheduled pilot link is preserved.

## Architecture

The existing origin, target routes, Notification/EmailDelivery records, Mailer,
claims, retries, recovery and final presentation revalidation are reused.
Appointments owns source/type/parent checks and bounded fact projections.
Notifications selects the approval version, applies the explicit recipient field
allowlist and renders through the shared Django HTML/text engine. Only typed
detail rows and a rebuilt trusted action enter templates. No models, arbitrary
metadata dictionaries, Student identity, private reasons or confidential sources
reach rendering, logs, audit metadata or task arguments.

Scheduled facts require initial revision 1 with no change history/revision marker;
otherwise the safe NOTIF-01 qualified link remains. Change emails use their exact
source rows, suppress later/ambiguous changes, and verify current state before
using context. Cancellation uses terminal retained facts. Reminders reuse the
canonical occurrence/revision predicate, with additional kind/parent/recipient
binding and disclosure access checks. No migration or new snapshot is needed.

The final comparison uses deterministic displayed rows, source identity, current
revision/provider/interval, approval version and the validated link. It excludes
unrelated metadata, private reasons, nondisclosed names and generation time.
The validated-link snapshot also closes the foundation's origin-change comparison
gap: the actual approved destination participates in final equality, while the
renderer still rebuilds it and never trusts a supplied URL.

## Review map

- [Seven-event audit/matrix](appointment-event-matrix.md)
- [Provenance and supersession](provenance-and-supersession.md)
- [Privacy and recipient policy](privacy-and-recipient-policy.md)
- [Template design](email-template-design.md), [preview/screenshots index](screenshots.md)
- [Delivery/retry](delivery-and-retry.md), [validation](validation.md)
- [Future deployment prerequisites](deployment-readiness.md), [follow-ups](followups.md)

Reviewed prior authority: all seven required NOTIF-01 documents, Proposal #5 in
the supplied Development Proposal Notes, ADR-041/046/074, ADR-020/REM-1,
institutional-time helpers, current authorization and actual producers. Proposal
notes are discussion context; exact institutional disclosure sign-off remains
pending. NOTIF-01's design blueprint is preserved with conservative suppression
for rich change events and qualified fallback for changed initial Scheduled facts.

## Changed production files

| File | Responsibility |
| --- | --- |
| `be/compass/appointments/email_presentation.py` | Bounded source facts, exact event binding, deterministic formatting and email-only eligibility |
| `be/compass/appointments/reminders.py` | Extract existing occurrence predicate for shared use; unchanged original semantics |
| `be/compass/notifications/email_presentation.py` | Approval version, recipient fields, typed plan and link snapshot |
| `be/compass/notifications/delivery.py` | Strict approved-row adapter; existing claim/transport lifecycle unchanged |
| `be/compass/common/email.py` | Document controlled operational-context exception |
| `be/config/settings.py`, `be/.env.example` | One optional server-owned policy version, default minimal |
| Five existing `notifications/email/appointment_*` HTML/text pairs | Optional detail branches; original generic copy retained |
| Four `notifications/partials/appointment_*` HTML/text files | Shared typed detail table and authenticated action |

The test inventory adds one focused suite. No workflow triggers, frontend files,
API schema, migration, source lifecycle, reminder issuance policy, Push payload,
Notification Center, SMTP adapter, queue or preference engine change.

## Evidence and limits

Focused development tests include all seven events, approval defaults, recipient
scope, exact sequential changes, time boundaries, legacy fallback, HTML escaping,
retry stability and transaction-enabled concurrent mutations. Synthetic previews
include Student/Counselor/minimal/obsolete cases and long/missing labels. Final
validation passed 643 backend tests (including 113 new cases), 38 CI-planner tests,
Django checks, migration drift, OpenAPI parity, Ruff and formatting. Commands and
iteration results are recorded in [validation](validation.md).

SMTP remains at-least-once and SENT means provider handoff. Accepted external mail
cannot be revoked after the final read. Local HTML previews do not establish
Gmail/Outlook compatibility or institutional approval. No deployment, live mail,
live configuration, staging promotion or automatic merge is part of this PR.
