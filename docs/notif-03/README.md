# NOTIF-03 — operational emails and centralized disclosure

Verified integration baseline: `6d6f3e0accbef09302f6b158295632059b9ff211`,
October 22, 2026, including merged NOTIF-01 #310 and NOTIF-02 #311. Isolated
worktree/branch: `notif-03-operational-emails/COMPASS`,
`feat/notif-03-operational-emails`. PR target is `integration/ux15-modernization`.
Staging checkpoint: `0a843dae20c01984d0fb9aa46d5eef34102ab386`; main checkpoint:
`1a9933535a0b8c0cbd7764c35f301e8402f48375`.

## Result

One optional `COMPASS_EMAIL_DISCLOSURE_POLICY` selects `minimal` (default/unknown)
or the candidate `operational_v1` bundle. The obsolete Appointment setting and
its `_FILE` form now fail startup, even when empty or the new setting also exists.
There is no alias, precedence rule or old-value fallback. Historical stored
Notifications and EmailDeliveries remain compatible; configuration compatibility
and record compatibility are separate concerns.

All seven Appointment events retain their NOTIF-02 behavior under the new selector.
Four Group Session, two Good Moral and two Call Slip events gain source-verified
minimal links and approved candidate details. All new recipients are Students
already selected by existing producers. No recipient lists or source mutations change.

Group Session version 1 omits all free-text titles, descriptions, venue/meeting
values, facilitators and rosters. It uses a generic label, exact event status and,
where provenance supports it, current/updated local schedule and mode. Good Moral
shows fixed request/status and a verified issuance date, without OR, academic,
certificate or Student identity. Call Slips stay at fixed issuance/voided status
and an authorized link; report times, destinations and Referral context are excluded.

## Architecture and compatibility

Three explicit source-owned resolvers return distinct frozen fact/row types.
Notifications admits exact event/recipient fields, builds the existing closed
portal URL and renders through existing HTML/text shells. The plan contains
explicit domain variants, not a general source serializer or payload dictionary.
Minimal new-domain plans retain typed source guards with empty detail rows so
policy/lifecycle/revision changes remain comparable immediately before SMTP.

Existing claim, lease, retry, recovery, queue, Notification/EmailDelivery IDs,
email preferences, SMTP adapter, account security, source lifecycle, Notification
Center and Push rules remain authoritative. New source checks are email-specific;
`notifications/current.py` and the Group Session shared predicate are unchanged.
No schema, migration, API contract or frontend production change is needed.

The NOTIF-02 time/value validation primitives move to a small common display module
without changing Appointment semantics. Domain-specific fields remain distinct.
Five existing operational template pairs add controlled branches; generic
event-code previews and specialized security rendering remain supported.

## Review map

- [Central policy and approval scope](centralized-disclosure-policy.md)
- [Pre-implementation source/event audit](event-recipient-matrix.md)
- [Group Session contract](group-session-email-contract.md)
- [Good Moral contract](good-moral-email-contract.md)
- [Call Slip contract](call-slip-email-contract.md)
- [Delivery/currentness](delivery-and-currentness.md)
- [Validation](validation.md), [synthetic previews/screenshots](previews.md)
- [Future configuration cutover](deployment-readiness.md), [follow-ups](followups.md)

Required NOTIF-01/02 design/delivery/privacy documents and the original Proposal #5
were reviewed. Proposal observations originally used staging; implementation follows
the newer integration source. Neither proposal text nor synthetic examples establish
institutional approval of the full bundle. Original NOTIF-02 operator instructions
now carry explicit supersession notices without rewriting implementation history.

## Changed components

| Component | Change |
| --- | --- |
| `config/settings.py`, `.env.example` | One central setting; strict obsolete-key startup rejection |
| `notifications/email_disclosure.py` | Version selection, closed admission and field sets |
| `group_sessions/email_presentation.py` | Registration/revision/cancellation participant proof and safe rows |
| `good_moral/email_presentation.py` | Assisted creation/issuance/self-access projection |
| `call_slips/email_presentation.py` | LIVE/historical/legacy and void/self-access projection |
| `common/email_presentation.py`, `appointments/email_presentation.py` | Reuse time/plain-value primitives, preserve Appointment ownership |
| `notifications/email_presentation.py` | Explicit variants, minimal/rich plans, source guards |
| `notifications/operational_email_rendering.py`, `delivery.py` | Typed event adapters and existing final comparison |
| Five operational template pairs / four partials | Event-specific Group copy, typed rows and one trusted action |
| Focused tests / existing Appointment tests / CI bundle | New source/policy coverage and central-setting replacement |
| NOTIF-02/03 docs and synthetic fixtures | Configuration cutover, decisions, evidence and future prerequisites |

## Limits

Final coordinated validation: **1,113 backend tests passed**, including 232 new
operational cases and all 113 Appointment presentation cases. CI planner: 38
passed, inventory: 173 test files. Ruff/format, Django checks, migration drift,
OpenAPI and diff checks passed. Node redirect suite: 26 passed plus three new-route
assertions. Synthetic evidence: 13 HTML/text pairs, 14 status records, 26 local
Chromium layouts and seven screenshots. Exact commands/iterations and not-run
checks are in [validation](validation.md).

Rich content remains off by default. Full-bundle institutional authorization and
separate deployment/configuration authorization are still required. SMTP remains
at-least-once; SENT means accepted handoff. Accepted mail cannot be revoked and
database checks cannot atomically include SMTP. Local Chromium is not Gmail/
Outlook evidence. No live mail, SSH, live settings, deployment, protected-branch
change or automatic merge is included.
