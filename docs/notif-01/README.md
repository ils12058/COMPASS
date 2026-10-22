# NOTIF-01: secure email links and presentation foundation

## Verified baseline and authority

Audited on October 22, 2026. Repository: `ils12058/COMPASS`.

| Ref | Fetched SHA |
| --- | --- |
| `integration/ux15-modernization` | `f268d1a5369c24c9fe94ca07c294f1052642e00f` |
| `staging` | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |
| `main` | `1a9933535a0b8c0cbd7764c35f301e8402f48375` |

Integration HEAD is the merge of UX15 final consolidation PR #309. The isolated
worktree is `~/.codex/worktrees/notif-01-secure-email-foundation/COMPASS`, branch
`feat/notif-01-secure-email-foundation`, based exactly on the fetched integration
HEAD. The primary checkout and protected refs were not edited.

The user-supplied NOTIF-01 specification authorizes NOTIF-0/1 only. Proposal #5
in *COMPASS Development Proposal Notes - Fifteen Proposals.md*, supplied from the
user's Downloads directory, is discussion context. Its proposed rich Appointment
copy and institutional disclosure policies are not approval to implement NOTIF-2.

## Audit findings

There are **30 active catalog events: 29 email-enabled and one in-app-only**.
Actual producers, sources, recipients, templates and currentness are inventoried
in [the matrix](event-recipient-matrix.md). Notification intent and EmailDelivery
remain the durable owners; Celery's ID-only post-commit kick and Beat recovery
use PostgreSQL state. Claims, bounded retries and transport statuses already exist.

The October 20 proposal's principal findings still hold on integration. A source
diff from current staging to the audited integration HEAD has no `be/` or
`contracts/` changes. UX15 changes frontend experience, not the delivery system.
There is no verified, dedicated frontend email-origin configuration. The frontend
already supports safe login return and MFA. Inventory and Feedback routes are
recipient-scoped; not every target is an ID route. Security links require a
separate policy.

Baseline currentness dispatch covers reminder occurrences, Follow-Up events and
Group Sessions. Ordinary Appointment scheduled/cancelled/change events otherwise
only check recipient activity. Reassignment notifies the former Counselor too;
Notification ownership cannot establish current source access. Change events
preserve old/new schedule/provider IDs; scheduled/cancelled notifications use the
mutable Appointment as source. These gaps prohibit blindly rendering live facts
under historical event labels.

Reviewed decisions: ADR-041, ADR-046, ADR-074, ADR-020, ADR-REM-1, ADR-FUP-1A,
ADR-012, ADR-049, ADR-071 and ADR-091, alongside the current implementations.
ADR-074's historical 18-event count, colored-shell description and blanket no-link
rule describe its original slice. Current tests/templates own the newer white
shell. This slice narrows the no-link rule only for a validated operational action;
all generic previews and security templates keep the original restrictions.

## Implemented foundation

- `COMPASS_PORTAL_ORIGIN`: optional backend configuration, validated when building
  a link. Missing or invalid configuration keeps safe generic email functional.
- Closed typed target-to-route builder: canonical UUIDs, explicit recipient-scoped
  routes, bounded Feedback query, no arbitrary URLs or security target support.
- Immutable email presentation plan: event, bounded reason, recipient class and
  closed target. No source text, details table, model object or arbitrary context.
- Appointments-owned eligibility: current account, normal detail authorization,
  participant/staff class and upcoming scheduled source state.
- One activated event: `appointment.scheduled`, with fixed generic copy and a
  **View Appointment in COMPASS** link in HTML/text. Its historical wording is
  qualified by a reminder to review current details.
- Rendering and final revalidation inside the existing claim lifecycle. A
  changed presentation/account after rendering cancels before transport. An
  authorized, no-longer-upcoming scheduled source is suppressed; this also applies
  after source access has been lost. Missing sources/legacy references fall back.

See [links](deep-link-contract.md), [presentation](presentation-contract.md),
[delivery](delivery-integration.md), and [Appointment design](appointment-event-design.md).

## Production files changed

| File under repository root | Responsibility |
| --- | --- |
| `be/config/settings.py`, `be/.env.example` | Optional origin setting and operator example |
| `be/compass/notifications/email_links.py` | Origin validation and closed routes |
| `be/compass/notifications/email_presentation.py` | Event allowlist and safe rendering plan |
| `be/compass/appointments/email_presentation.py` | Domain-owned eligibility without detail disclosure |
| `be/compass/notifications/delivery.py` | Controlled adapter, cancellation and final revalidation |
| `be/compass/notifications/templates/notifications/email/appointment_scheduled.html`, `.txt` | Optional single action and current-details qualification |
| `be/compass/common/email.py` | Clarify the controlled-link context exception |
| `be/compass/common/json_logging.py` | Allow a bounded presentation reason code |

The backend test bundle registry adds the two new suites. No workflow filter was
changed. Frontend changes are tests only; existing login, MFA, portal guards,
Notification Center and record authorization are reused.

## Preserved boundaries and evidence

No schema, migration, OpenAPI, channel policy, recipient selection, push payload,
queue, notification table, source fact snapshot, SMTP adapter or tracking change.
Generic previews still render by event code without a Notification. No confidential
source text enters templates or logs. Current endpoint authorization independently
decides every opened record. SMTP remains at-least-once; SENT means handoff only.

Exact commands, test counts and limits are in [validation](validation.md).
[Follow-ups](followups.md) preserve NOTIF-2/3/4, institutional decisions and future
operator prerequisites. Automated tests are not institutional privacy approval or
production readiness. No deployment, live configuration, real email or automatic
merge is part of this work.
