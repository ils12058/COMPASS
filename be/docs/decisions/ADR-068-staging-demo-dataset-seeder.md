# ADR-068: Staging demo dataset seeder

- Status: Accepted
- Date: 2026-09-28
- Scope: The `seed_demo_staging` operator command, its environment boundary, and the seed-only
  writes it is allowed to make

## Context

Staging demonstrations need a believable, internally consistent COMPASS world: accounts in every
role, Students in different cohorts and lifecycle states, and records across every workflow that
agree with each other and with the calendar. Hand-entered data drifts, and random fixture data
produces impossible timelines. Most workflows also act only on the current Academic Year, stamp
wall-clock time, and queue email, all of which are correct for real use and wrong for bulk
back-entry.

## Decision

- A source-controlled, deterministic dataset (`compass/demo_seed`, dataset version 1) is applied by
  the `seed_demo_staging` management command. There is no API, UI, middleware, or model flag, and
  no production code branches on seeded data.
- The command runs only when `APP_ENV` is in the explicit allowlist `{local-staging, live-staging}`
  **and** `DEMO_SEEDING_ENABLED` is true (default true locally, false on live staging). The opt-in
  never widens the allowlist. The shared password comes only from `DEMO_ACCOUNT_PASSWORD`
  (or `_FILE`) at run time and is validated with the normal password policy.
- Canonical configuration is reconciled by calling the existing synchronizers' Python functions;
  `sync_identity_policy`'s logic moved into `compass.accounts.bootstrap` for that purpose with no
  change in command behavior.
- Records are created through domain services as the acting persona. Historical Academic Years are
  entered by making each one current inside a single transaction, so the ordinary current-year
  services apply and no other session observes the switch.
- Seed-only writes are limited to: account provisioning through the User manager with SYSTEM audit
  (Account Management requires an MFA step-up session), mirrored designation/lifecycle/disable
  changes, an allowlist of business timestamp columns moved onto the demo timeline, and removal of
  the uncommitted, never-attempted email deliveries that seeding itself caused. Audit events are
  never rewritten; each run's events share one request ID.
- Reruns are create-if-missing only. The command never deletes or resets data; conflicting real
  data fails closed before business records are written.

## Consequences

- Staging can be made presentation-ready with one command and rerun safely.
- Demo records exercise the same invariants as real records and remain readable through the
  normal services and API.
- Seeded audit history is truthful about when it was recorded, while domain records carry the
  synthetic narrative dates.
- Generic operational Guidance Student pickers require CURRENT lifecycle even for institution-wide
  actors. Graduated and former demo accounts stay active for their lifecycle-specific workflows.
- A demo reset workflow remains a separate, future decision.
