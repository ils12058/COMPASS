# OPS-FINAL — Agent 1 readiness report

Verification checkpoint: 2026-10-17. **NOT READY — BLOCKERS REMAIN**.
This report distinguishes implemented behavior, executable evidence, and outstanding gates.
No staging merge, deployment, live secret operation, UAT reset or outbound enablement was performed.

## Implementation and integration status

| Requirement | Implementation | Verified evidence | Integration |
|---|---|---|---|
| REM-1 | Automatic 24h/3h discovery, manual/bulk preview, canonical staff roles, durable occurrence/replay, Student-only delivery, stale suppression, generated-client UI | 33 final reminder/canonical checks; earlier 56 delivery regression checks; new browser checks 3 per engine; frontend CI all eight shards on 603b55a5 | REM/FUP combined build/browser checks passed; full CI pending |
| FUP-1A | Secure independent domain, source policies, classification, bound encryption, lifecycle/audit, PostgreSQL locking | Foundation 37 focused checks; later 28 domain/HTTP checks, including concurrent lifecycle, MFA, recovery and rotation | #259 precedes #260/#261 |
| FUP-1B | List/filter/sort/pagination, scoped selectors, frozen create retries, detail/actions/history, conflict review, retained MFA | 775 frontend checks, lint/typecheck/build; 8 new browser checks per engine on final Follow-Up build | Workspace #260 and dependent #261 |
| FUP-1C | Canonical Encounter/Referral/Routine contextual creation and links, source revalidation, independent lifecycle | Source policy/domain tests and canonical Encounter browser scenario | E-Counseling uses Encounter; no media identities |
| FUP-1D1 | Current assigned PENDING My Work projection, scoped safe cards, confirmed-time overdue, freshness/removal | Work queue checks passed in combined PostgreSQL regression; dedicated frontend tests | Existing work kinds preserved; no Reminder staff task |
| FUP-1D2 | Staff assignment/reassignment/due-change events, transactional durable intents, source/recipient revalidation, separate outbound flag | Domain/transport checks passed; full CI pending | Distinct REM/FUP source adapters composed; Service/Group adapter pending Agent 2 |
| FUP-1E | Scoped on-screen counts, operational-only owner recovery, key rotation, runtime isolation, browser/accessibility checks, docs | Head/GSS/capability recovery tests; rotation/tampering tests; runtime/contract tests; PostgreSQL rehearsal | No confidential administrative bypass or invented institutional cadence/retention |

## Focused PR chain

| PR | Base | Exact head at checkpoint | Changed files | Dependency and CI |
|---|---|---|---:|---|
| [#256](https://github.com/ils12058/COMPASS/pull/256) | staging | b4902ce7eee9a7d00c1737f7eaf522c0b347f331 | 27 | Independent REM; frontend CI passed on 603b55a5; email heading failure repaired in latest head; fresh CI pending |
| [#259](https://github.com/ils12058/COMPASS/pull/259) | staging | 8e6acbfb3df3c5b449759fa5e1b515a42528e083 | 24 | Foundation; fresh CI pending after formatting and two browser race repairs |
| [#260](https://github.com/ils12058/COMPASS/pull/260) | feat/compass-fup-1a-secure-foundation | 1a8edb39f3f25761c7b47d805eb0a1960978981b | 24 | After #259; exact-head manual workflows dispatched |
| [#261](https://github.com/ils12058/COMPASS/pull/261) | codex/ops-final-followup-workspace | 7dac089db51b7cf1f96da14432646d3c61015bbc | 56 | After #260; adjacent work/notifications/hardening share occurrence and recovery contracts; exact-head workflows dispatched |

All remain draft. Retarget stacked bases only after predecessor integration, preserving review history.
Do not squash a predecessor underneath dependents without reconciling their ancestry.
Combined code candidate: `3914be81945d37b0eb09c549790698bb557ec676`, branch
`codex/ops-final-integration`, worktree
`/Users/reynantlntno/.codex/worktrees/ops-final-integration/COMPASS`.

## Exact-candidate automated evidence

Follow-Up code stack 77cbd8d5 (production sources match the final successful build; subsequent
foundation propagation changes only test synchronization): lint/typecheck/build passed, 775/775
unit/component checks, 8/8 new browser checks in Chromium and 8/8 WebKit. The affected existing
Inventory pending/failure check passed after synchronizing on actual request receipt.

Combined production candidate (latest code 3914be81): Ruff formatting (762 files), Ruff lint and Python compilation passed;
Django system checks passed; no model migration drift. The first migration consistency command
warned that the unused default compass_test database did not exist; fresh disposable test database
setup and the subsequent real upgrade test execute actual migrations, without suppressing history.
Canonical upgrade/additive rollback/re-upgrade rehearsal passed in real PostgreSQL (1 test, 75.51s).
It checks pinned canonical history, preserved Appointment fields/IDs and row counts, reminder revision
initialization when present, and Service flexible-pathway backfill when included in a future candidate.
Reversal is tested only in disposable fixtures; production application rollback retains feature data.

Combined local results:
- The broad PostgreSQL/security/transport/work/contract run completed with 200 passes and 65 failures,
  all confined to `test_runtime_secrets.py`. The fixture omitted the required synthetic Follow-Up
  file and seven explicit counts still expected 24. The fixture/counts were repaired without changing
  production guards. All 91 runtime/Compose checks then passed, including five additional checks.
- Both domains' transactional email templates now use the branded shell; all 110 email checks passed.
- All 38 OpenAPI contract checks passed independently. No generated route/operation was lost.
- Consolidated Orval generation, frontend lint/typecheck/production build passed. Against that same
  build, Reminder 3/3 and Follow-Up 8/8 scenarios passed in each Chromium and WebKit engine.
- Existing Inventory and E-Counseling pending/failure browser races were synchronized on actual
  mocked request receipt; both affected scenarios passed. These are test-only changes.
- Final Ruff lint/format passed. No unexplained local test failure remains. This does not mean the
  complete six-shard backend/full-browser CI has passed; exact-head CI is still queued/running.

The broad run predates only the email-template repairs and runtime-fixture changes. Affected suites
were rerun on their corrected combined tree. Later changes propagate test synchronization and docs;
frontend product sources match the verified build. The combined upgrade rehearsal predates only
those template/fixture/test changes; migration and domain model bytes are unchanged.

The following table retains historical run evidence. Older failures/cancellations are not passes;
consult each PR's latest head checks and the final branch workflow runs for superseding results.

| Candidate | Backend targeted | Backend full | Frontend |
|---|---|---|---|
| REM historical 603b55a5 | [run](https://github.com/ils12058/COMPASS/actions/runs/38997712195) | [run](https://github.com/ils12058/COMPASS/actions/runs/38997712180) | [passed run](https://github.com/ils12058/COMPASS/actions/runs/38997712202) |
| Foundation historical 3cbb478f | [run](https://github.com/ils12058/COMPASS/actions/runs/38998472426) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998472451) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998472433) |
| Workspace historical a942cc92 | [run](https://github.com/ils12058/COMPASS/actions/runs/38998714076) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998720853) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998717771) |
| Work/notifications historical 77cbd8d5 | [run](https://github.com/ils12058/COMPASS/actions/runs/38998724150) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998736226) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998730372) |
| Combined historical 6770b90e | Combined domain checks local | [superseded/cancelled run](https://github.com/ils12058/COMPASS/actions/runs/38998815664) | [run](https://github.com/ils12058/COMPASS/actions/runs/38998819954) |

## Cross-agent conflict and compatibility report

The owner supplied Agent 2's Antigravity branch/worktree and confirmed the shared contract.
Latest observed SVC-1 committed head is `33fe0117d694ba675b8214b2be3aec978a91e93e`, PR #258;
Agent 2 has moved to `feat/compass-svc-2-fixed-slots` with active uncommitted slot models/services/migration. It is **not certified as a
compatible final candidate**. SVC-2–5 ready heads and Agent 2's final handoff are still unavailable.
No Agent 2 branch, working file or commit was changed by Agent 1.

Resolved REM/FUP conflicts deliberately in the isolated candidate:
- Union explicit additive migration registry entries; original canonical SHA256 pins unchanged.
- Compose `notifications/current.py` source checks and SQL in-app/unread scopes, preserving both.
- Preserve claim/current-recipient validation in email and push; generic source-change cancellation.
- Union API operation IDs and regenerate consolidated OpenAPI/Orval; preserve all source routes.
- Keep independent event definitions, push allowlists, audit actions, settings and task registration.
- Keep both CI domain bundles and the real PostgreSQL upgrade rehearsal in test selection.

Agent 2 confirmed fixed-date individual bookings use canonical Appointments; Group Sessions use
separate `group_session.*` models/events. Final tests must prove relevant Appointment reminders work
without treating group registrations as reminders, and preserve Service eligibility/qualification.
The SVC-1 additive migration intentionally backfills flexible pathways for already bookable Services;
that reviewed data operation must preserve canonical Service/Appointment rows. Later migration graph,
shared delivery adapters, realtime events, OpenAPI and generated clients require final reconciliation.
The complete Service Catalog cross-feature gate cannot pass before its owner supplies ready work.

## Operational inventory and order

| Setting/secret | Consumers | Default/readiness |
|---|---|---|
| GUIDANCE_FOLLOWUPS_ENABLED | Web plus shared worker settings | false; approved workspace rollout |
| GUIDANCE_FOLLOWUP_ENCRYPTION_KEYS / _FILE | Web/operator only | Independent ordered keyring, new primary first; provision by owner |
| GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED | Web and email/push delivery workers | false; approved destinations and integrations |
| APPOINTMENT_AUTO_REMINDERS_ENABLED | Web/worker/one Beat | false; separately approved Student Reminder rollout |
| Existing SMTP, WEB_PUSH_*, Redis/Celery | Existing runtime consumers | Verify approved destinations, device/session opt-in and delivery integration |

Follow-Up content keys remain absent from worker/Beat (both environment forms explicitly cleared)
and realtime. Compose requires the reviewed web secret file before rollout even with feature disabled.
No live key is created. Key rotation/backup/recovery and exact-envelope failure are documented in
`be/docs/guidance-followups-operations.md`; rotation only rewrites ciphertext wrapping in bounded,
resumable batches after complete bound-content validation. Retain all required historical keys.

After explicit approvals: (1) select reviewed compatible heads and pass gates; (2) verify canonical
DB and separately secured keyring backups; (3) provision web secret/approved environment with flags
false; (4) review guarded migration plan and apply registered additions in dependency order;
(5) synchronize role/capability policy explicitly; (6) deploy compatible web/worker/one Beat/frontend;
(7) smoke synthetic role/source denial, retry/conflict/reassignment/recovery, My Work disappearance,
report scope, keyless-worker validation and task registration; (8) verify approved SMTP/opt-in push
and stale cancellation; (9) approve and enable each dispatch feature independently. No UAT reseed.

Rollback disables producers/feature/outbound flags first and retains schema, ciphertext, receipts and
history while reverting compatible application images. Reversing feature tables destroys their
history and requires a separately approved recovery plan. Restore only compatible canonical backups
with corresponding keys; never fake migration history or reset UAT data.

## Remaining gates and policy

- Finish exact-head CI and repair any newly exposed reproducible failure. The observed REM HTML
  heading, FUP text footer and runtime-fixture failures are repaired and affected checks pass.
- Full regression CI remains pending; the combined local build/browser/domain/transport/contract
  and migration evidence below has completed.
- Obtain Agent 2's ready SVC-1–5 exact heads and domain review; reconcile and validate the final candidate.
- Owner approvals and documented secret/runtime provisioning remain operational prerequisites.
- No institutional deadline cadence, retention duration, broad analytics or confidential admin bypass
  was invented. These require separate policy if requested; they are not silently implemented.

Recommendation remains **NOT READY — BLOCKERS REMAIN** until engineering and integration gates pass.
