# Agent 1 OPS-FINAL integration handoff

Updated 2026-10-17. This is an engineering handoff, not merge/deployment approval.

## Ownership and candidate chain

| Slice | PR | Base | Candidate branch |
|---|---|---|---|
| REM-1 | [256](https://github.com/ils12058/COMPASS/pull/256) | staging | feat/compass-rem-1-appointment-reminders |
| FUP-1A | [259](https://github.com/ils12058/COMPASS/pull/259) | staging | feat/compass-fup-1a-secure-foundation |
| FUP-1B/1C + scoped report | [260](https://github.com/ils12058/COMPASS/pull/260) | feat/compass-fup-1a-secure-foundation | codex/ops-final-followup-workspace |
| FUP-1D1/1D2/1E | [261](https://github.com/ils12058/COMPASS/pull/261) | codex/ops-final-followup-workspace | codex/ops-final-followup-work-notifications |

REM head `603b55a5d09d29cb074ccfe857ef09c254a284f7`. Follow-Up heads are being
updated for final verification; use the live PR head, not an earlier snapshot. Review in dependency
order. All PRs remain drafts pending complete exact-candidate validation. No staging merge is made.

Agent 1 implementation worktree: `/Users/reynantlntno/.codex/worktrees/ops-final-followups/COMPASS`.
Combined validation worktree: `/Users/reynantlntno/.codex/worktrees/ops-final-integration/COMPASS`,
branch `codex/ops-final-integration`. It reconciles REM + Follow-Ups without altering staging or
Agent 2's checkout. Service Catalog is not yet included or certified.

## Agreed Agent 2 boundary

The project owner forwarded Agent 2's confirmation from Antigravity: worktree
`/Users/reynantlntno/.codex/worktrees/ops-final-services/COMPASS`, SVC-1 branch
`feat/compass-svc-1-booking-pathways`, PR #258; downstream SVC-2–5 retain their named branches.
Agent 2's future readiness source is `docs/handoffs/AGENT-2-SVC-FINAL-HANDOFF.md` in that checkout.
Do not merge an actively changing checkout or call SVC-1 completion the completion of SVC-2–5.

- Canonical `0001_canonical_baseline.py` bytes must remain unchanged. Preserve every SHA256 in
  `be/compass/common/canonical_migrations.json`; union all explicitly reviewed additive paths.
  REM registers appointments/0002; Follow-Ups registers its new-domain 0001 and mutation-receipt 0002.
  Agent 2 explicitly registers service_catalog/0002_booking_pathways and later additions.
- Existing history guards still refuse pre-canonical history. No fake/reset/reseed is allowed.
- Fixed-date individual slots use canonical Appointment records and the REM eligibility contract.
  Group registrations are not Appointment reminders and do not create REM staff work cards.
- Group events/models use distinct `group_session.*` identities. REM uses source
  `appointment_reminder`; Follow-Ups uses `guidance_followup_event`. Never reuse occurrence UUIDs
  or event names across these domains.
- Shared infrastructure edits require deliberate reconciliation. Agent 2 agreed to domain-owned
  modules/adapters and an explicit diff/manifest before final candidate integration.

## Shared infrastructure adapter contract

`notifications/current.py` is the shared dispatcher. The combined candidate calls the source-owned
REM `reminder_notification_is_current` and FUP `followup_notification_is_current`; other existing
sources retain active-recipient behavior. `external_delivery_enabled` separately gates FUP outbound
creation/delivery. Group-session adapters should be added explicitly here, not replace either branch.

`delivery.py` checks eligibility at claim and final provider boundary, including current recipient
email and claim token/expiry. `push.py` checks source eligibility before claim and handoff. External
provider acceptance cannot be recalled, and interruption after acceptance may cause a retry.
In-app notifications use composed source SQL filters before pagination/unread counting.
Preserve current-source checks in both transports and in-app queries.

Keep independent event definitions/push allowlist/audit actions/API IDs. Consolidate OpenAPI from
the combined backend and regenerate Orval once; never hand-edit generated clients. Preserve the
closed content-free realtime registry (`followups.changed` has no extra fields).

## Runtime and migration prerequisites

All new flags stay false: `GUIDANCE_FOLLOWUPS_ENABLED`,
`GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED`, `APPOINTMENT_AUTO_REMINDERS_ENABLED`.
Provision no live key here. Follow-Ups uses independent `GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS` or
`_FILE`, web/operator only. Worker/Beat explicitly receive neither form; realtime remains keyless.
Compose now requires that reviewed web secret file before rollout, even with the feature disabled.
Retain old keys during rotation and tested backup recovery. The management rotation command has
`--dry-run` and bounded batches; protected content remains exact-record-bound and fail-closed.

Apply guarded additive migrations after verified canonical backup, synchronize capability policy,
then deploy compatible web/worker/one Beat/frontend with flags false. Perform approved synthetic
smoke tests and independently approve each outbound channel before enabling. Production rollback
normally retains additive tables/history and disables producers; reversing new tables destroys
feature history and is not an approved rollout action.

Full runbooks: `be/docs/decisions/ADR-REM-1-appointment-reminders.md`,
`be/docs/guidance-followups-workspace.md`, `be/docs/guidance-followups-operations.md`.

## Verification checkpoint

- REM frontend exact head 603b55a5: GitHub frontend targeted validation succeeded, including all
  eight Chromium/WebKit shards. Backend targeted/full regression were still running at this checkpoint.
- Follow-Up candidate: 775/775 local frontend tests, lint and typecheck passed; final build in progress.
- New browser scenarios previously passed: REM 3 per engine; FUP 8 per engine. Combined candidate
  must rerun both suites after consolidated client generation/build.
- Real PostgreSQL domain/HTTP tests cover lifecycle concurrency/idempotency, current authorization,
  source confidentiality, tampering/key failure, assignment recovery and key rotation. The Follow-Up PostgreSQL canonical upgrade/additive rollback/re-upgrade rehearsal passed
  (1 test, 390.66 seconds on the loaded local host). Final combined backend regression is in progress.
- CI foundation formatting failure and an Inventory browser timing race were identified; fixes
  are being propagated through the stack and must be checked on new heads.

No substantial Service Catalog implementation is owned by Agent 1. Final cross-feature readiness
requires Agent 2's ready exact heads, its domain review, and passing combined regression. No deadline
reminder cadence or retention duration has been invented. UAT-40 data/accounts/scenarios are untouched.

Current recommendation: **NOT READY — BLOCKERS REMAIN** until those verification gates are satisfied.
