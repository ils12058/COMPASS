# ADR-013: Curated self-activity projections over the Audit Trail

## Context

COMPASS needs readable activity history for an authenticated account without turning the
account-facing API into a general audit viewer. `audit.AuditEvent` already persists attributable
business and security evidence, including authentication events and explicit targets. Creating a
second activity table would duplicate history, complicate retention, and risk exposing audit
details that are appropriate only for authorized investigation.

## Decision

Keep `audit.AuditEvent` as the only persisted source of truth. `GET /api/v1/me/activity` and
`GET /api/v1/me/security-activity` synchronously query selected events and transform them through
explicit presenter registries. My Activity is the broader curated account feed; Security Activity
is the narrower account-security feed. Some security items intentionally overlap because the two
feeds have different user-facing purposes.

Each presenter explicitly declares its stable public type, neutral copy, allowed outcome, actor
scope, and target ownership rule. A new or removed audit action is not visible by default. Current
target checks allow self-actor events only when their account/session/MFA target belongs to the
current user, and allow the existing system-generated `account.created` event only when it targets
the current account. This keeps the selection architecture ready for future explicit
actor-versus-account target policies without introducing broad target matching.

The response contains only an audit UUID, stable type, title, description, and timestamp. Raw
metadata, target fields, actor identity, request IDs, IP addresses, user-agent values, credentials,
and security tokens are never returned. The endpoints authenticate through the existing opaque
COMPASS session and accept no user selector or audit filters. Page/page-size pagination is bounded
and ordered newest-first by `(occurred_at, id)`.

## Consequences

There is no `ActivityLog`, `ActivityEvent`, `UserActivity`, or `SecurityActivity` model, no feed
materialization job, no Redis feed cache, and no AuditEvent mutation for read state. The endpoints
are self-only and do not require a capability because viewing one's own safe account activity is an
inherent authenticated-account ability. A general Audit Viewer, audit search/export, notifications,
read/unread state, domain history, and future account-management projections remain deferred.

## BACKLOG-ACT-2 extension (2026-10-16)

My Activity now admits the explicit domain allowlist in `activity/domains.py`. Domain policies
separate Student self actions, effects on a verified owning Student, and authorized staff self
actions. They do not overload the account presenter's `actor_scope`. The original actor remains
in the Audit Trail; static descriptions distinguish "You submitted" from "Your form was returned".

Typed source-model subqueries enforce canonical ownership or current domain read scope before
the shared event query is ordered and paginated. Referral child events join their scoped parent.
Only successful USER events qualify. Missing/deleted sources, malformed IDs, mismatched targets,
revoked read authority and lost scope fail closed. No source content is fetched or decrypted.
The source authorization helpers remain owned by their domains; My Activity adds no access grant.

Students see eligible effects only for records their existing self-service read capability
allows. Staff see only their own eligible actions with current role, capability and source scope.
Head status supplies no organization-wide actor selector. IT Admin and DPO stay account-only.
Routine professional actions, encounter/evaluation events and Call Slip interview completion are
excluded, as are Student referral events. The complete evidence and deferrals are recorded in
`outputs/BACKLOG-ACT-2-Implementation-Report.md` at the repository root.

Security Activity uses its own explicit action allowlist and never consults domain policies;
session creation remains excluded. Supervised Staff, Privacy and Platform projections retain their
separate policies. The five-field response, default/max page sizes, deterministic ordering, Audit
Trail producers and persistence schema are unchanged.
