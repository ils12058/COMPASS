# CONT-2A — Counselor case continuity authorization foundation

Repository `ils12058/COMPASS`; starting integration SHA `1cdad9dd9378b1307140ba92a1023ed0e68a720f`, fetched and verified 2026-10-23. Isolated managed worktree `cont-2a-case-continuity-grants/COMPASS`, branch `feature/cont-2a-case-continuity-grants`; PR target `integration/ux15-modernization`. Implementation SHA and publication state are recorded on the PR.

This implements the technical foundation proposed by [CONT-0](../cont-0/README.md): one Student, one receiving Counselor, bounded operational purpose, exact selected source references, independent approval, finite interval, optimistic versions and terminal revocation. APIs expose metadata only. An `ACTIVE` effective status means the foundation's current identity/policy/time predicates hold; **it does not authorize professional source content**. No selected-source read route, bearer token, history enumeration, reassignment, Handoff body, notification event or workspace UI exists.

No institutional policy approval has been verified. `continuity_policy.get_approved_policy()` deliberately returns `None`; no environment flag or capability override can activate it. All seven operations remain unavailable by default, even after capability sync. Tests inject explicitly synthetic, short-lived approved-policy fixtures, without enabling a deployment. Activation requires signed policy evidence and a separately reviewed provider implementation; [governance](authorization-and-governance.md) identifies the missing decisions.

The five canonical capabilities are registered with **no role or designation defaults**. Active canonical Counselor identity is independently required, including for Head. Acting Head remains denied: neither expiring overrides nor supervision establish formal delegation. Existing Context, ordinary Student Session Summary, Routine, Appointment, Follow-Up, Referral, Assessment and E-Counseling authorizations remain independent. In particular, Context still uses exact providers, cross-College legitimate relationships, 24-hour pre-Appointment / uncompleted grace and seven-day post-Encounter defaults; grants do not create or extend those relationships.

Implementation record:

- [Models and database constraints](grant-model.md).
- [Actor, capability and institutional policy boundary](authorization-and-governance.md).
- [Locks, overlap, revocation and limits](concurrency-and-revocation.md).
- [Metadata APIs and audit](api-and-audit.md).
- [Executed validation](validation.md).
- [CONT-2B prerequisites](cont-2b-handoff.md).

No SSH, DigitalOcean operation, deployed database migration/reset, key provisioning, deployment or automatic merge is part of this work. Local PostgreSQL/Redis validation uses dedicated loopback processes and disposable synthetic databases. Historical CONT-0/1A/1B documents and canonical migration bytes are preserved.
