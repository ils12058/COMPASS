> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# Validation record — FUP-0

**Audit base:** `integration/ux15-modernization` at
`5224256a76c07f4503b5e3d98fea65c4ed84f2a9`, verified on 2026-11-05 with
`git rev-parse HEAD`.
**Validation type:** static, documentation-only.
**Test results claimed:** **none.** No test, lint, type check, build, migration, database, seed,
dev-server, browser or deployment command was executed. No pass/fail status is implied anywhere in this
package.

## 1. Method

The audit used four read-only techniques:

1. **Repository state verification** — `git rev-parse HEAD`; `git status --short` restricted to
   `docs/fup-0`, `be`, `fe` and `contracts`; `git status --short` overall.
2. **Static source inspection** — `rg`, `grep`, `sed -n`, `ls`, `wc` and full-file reads of the
   Follow-Up domain and its directly coupled policy, workspace, recovery, notification, Referral,
   Continuity, organization and account modules.
3. **Contract inspection** — read-only parsing of `contracts/openapi.json` to enumerate paths and
   operation IDs; comparison with the generated client's exported hooks and with the frontend imports.
4. **Document inspection** — the proposal FUP section, FAC-5, CONT-0/CONT-4 and SAR-0/3-4/5 records,
   the Follow-Up operations guide and ADR-FUP-1A.

Every material claim in the package carries **Verified**, **Inferred** or **Unknown**. "Verified" means
the cited file and line were read at this HEAD, not that the behavior was exercised.

## 2. Repository state at validation

```text
$ git rev-parse HEAD
5224256a76c07f4503b5e3d98fea65c4ed84f2a9

$ git status --short -- docs/fup-0 be fe contracts
?? docs/fup-0/

$ git status --short
?? docs/fup-0/
?? outputs/paper-screenshots/
```

- `docs/fup-0/` is the only path created by this audit; it is untracked and was not staged or committed.
- `outputs/paper-screenshots/` pre-existed and was left untouched.
- `be/`, `fe/` and `contracts/` show **no modification, deletion or addition**.
- No Git state-changing command was run: no fetch, pull, checkout, switch, stage, commit, merge, rebase,
  stash, reset, clean, tag or push.

## 3. Scope inspected

### 3.1 Backend Follow-Up domain

| File | Lines (static) | What was inspected |
|---|---:|---|
| `be/compass/guidance_followups/models.py` | 198 | Enums, fields, constraints, indexes, event and mutation models, `default_permissions=()` |
| `be/compass/guidance_followups/services.py` | 508 | Creation, list, detail, update, reassign, activity, complete, cancel, locks, events, audit |
| `be/compass/guidance_followups/policy.py` | 266 | Actor resolution, operational/confidential scope, source requirements, assignee checks |
| `be/compass/guidance_followups/api.py` | 734 | Strict schemas, 14 operations, error mapping, summary/detail projections, idempotency |
| `be/compass/guidance_followups/workspace.py` | 187 | Eligible Students/assignees, source context, reporting |
| `be/compass/guidance_followups/integration.py` | 123 | Due-soon horizon, pending work, material events, notification currentness |
| `be/compass/guidance_followups/recovery.py` | 135 | Recoverable queryset, eligibility SQL, metadata-only list |
| `be/compass/guidance_followups/replay.py` | 59 | Durable mutation and idempotency |
| `be/compass/guidance_followups/content.py` | 91 | Fernet encryption, AAD binding, keyring, rotation |
| `be/compass/guidance_followups/migrations/0001_initial.py`, `0002_guidancefollowupmutation.py` | — | Schema and constraints |
| `be/compass/guidance_followups/management/commands/rotate_guidance_followup_encryption.py` | — | Rotation entry point |
| `be/tests/test_guidance_followups.py` | 29 test functions / 33 declared cases | Coverage inventory only; not executed |

### 3.2 Directly coupled backend modules

- `be/compass/accounts/policy.py` — capabilities, role grants, Head Guidance designation, compatibility.
- `be/compass/notifications/policy.py`, `be/compass/notifications/current.py`,
  `be/config/settings.py` — event catalog and delivery flag.
- `be/compass/work_queue/services.py` — My Work/Work Queue inclusion.
- `be/compass/audit/actions.py` — Follow-Up audit action names.
- `be/compass/referrals/models.py`, `administrative_state.py`, `services.py`, `faculty_api.py`,
  `administrative_api.py`, `faculty_policy.py`, `administrative_policy.py` — source lifecycle,
  Faculty/administrative providers.
- `be/compass/counseling/continuity_models.py`, `continuity_policy.py` — coverage grants and denial.
- `be/compass/organization/migrations/0001_initial.py`, `0005_delete_studentaffiliation.py` — SAR
  removal evidence.

### 3.3 Frontend

All 10 files under `fe/src/features/guidance-followups/`; the 5 route pages under
`fe/src/app/(portal)/portal/follow-ups/`; `fe/src/features/work-queue/work-queue-presentation.ts`;
`fe/tests/guidance-followups.test.mjs` (3 tests) and `fe/tests/guidance-followups.browser.mjs`
(436 lines); `fe/package.json` scripts. Source-page usage of `FollowupsContext` was inspected through
the context component's callers.

### 3.4 Contracts and generated surface

- 12 paths / 14 operations in `contracts/openapi.json`, all named `guidanceFollowups*`.
- The generated client exports for all 14 operations under
  `fe/src/lib/api/generated/guidance-followups/`.
- The schema families `FollowUpSummary`, `FollowUpDetail`, `FollowUpCreate`, `FollowUpUpdate`,
  `FollowUpReassign`, `FollowUpActivity`, `FollowUpComplete`, `FollowUpCancel`, `FollowUpHistory`,
  `SourceContext`, eligible/recoverable/report pages.

### 3.5 Documents

- Proposal FUP section, lines 5599–6647, including claims at 5607, 5748, 5752, 6227, 6325–6375,
  6412, 6417–6467, 6493–6518, 6608, 6619.
- `docs/sar-0/README.md`, `docs/sar-3-4/implementation.md`, `docs/sar-5/validation.md`.
- `docs/fac-5/readiness.md`, `docs/fac-5/institutional-decisions.md`.
- `docs/cont-0/README.md`, `docs/cont-0/source-record-policy.md`, `docs/cont-4/final-assessment.md`.
- `be/docs/guidance-followups-operations.md`,
  `be/docs/decisions/ADR-FUP-1A-secure-guidance-followups.md`.

## 4. Scope not inspected

These were **not** read in full; conclusions about them are limited to the cited interfaces:

- Full counseling Encounter and Routine Interview services, serializers, UI and tests; only the
  Follow-Up-facing source checks and models were inspected.
- Full Referral workflow beyond the status/administrative/void fields and the Follow-Up-facing
  authorization; Referral notification and reporting internals were not audited.
- Full Continuity approval/activation services; only the grant model and runtime policy denial were
  inspected.
- Full Faculty API frontend, Faculty UAT and all FAC-5 decision records; readiness is based on the
  cited blocked status and provider defaults.
- Authentication/session middleware, CSRF implementation, step-up implementation and realtime service
  internals; their Follow-Up usage was inspected at the call boundary only.
- All other frontend features and routes; only Follow-Up, Work Queue presentation and the source-context
  callers were inspected.
- Historical migrations other than the `StudentAffiliation` creation/deletion pair.
- Production/staging configuration, deployed schema, deployed feature flags and live data — **no
  access**.
- Proposal sections outside the FUP range, except where they define FAC/CONT/SAR dependencies.

## 5. Commands and suites not run

**Every item below was deliberately not executed.** The "Required at" column records where it is
expected to run, not that it ran.

| Command / suite | Why it was not run | Required at |
|---|---|---|
| `pytest` (any selection) | FUP-0 is documentation-only; no test execution permitted | FUP-1 targeted, FUP-4 full |
| `pytest be/tests/test_guidance_followups.py` | Same | FUP-1 |
| `python manage.py test` | Not the repository runner; prohibited | Not planned |
| `pnpm test` (`node --test tests/*.test.mjs`) | No frontend test execution permitted | FUP-1 targeted, FUP-4 full |
| `pnpm test:ui` / `node tests/run-browser-regressions.mjs` | No browser execution permitted | FUP-4 |
| `node tests/guidance-followups.browser.mjs` (Chromium and WebKit) | No browser execution permitted | FUP-1 targeted, FUP-4 full |
| Playwright runner (`fe` declares `playwright` 1.62.1) | No browser execution permitted | FUP-4 as configured |
| `pnpm lint` | No lint execution permitted | FUP-1/FUP-4 |
| `pnpm typecheck` | No type-check execution permitted | FUP-1/FUP-4 |
| `pnpm build` | No build execution permitted | FUP-4 |
| `pnpm validate` (Orval + lint + typecheck + build) | No generated-artifact or build execution permitted | FUP-4, or any contract-changing slice |
| `pnpm api:generate` (Orval) | No generated-client change permitted | Only a contract-changing slice |
| OpenAPI export/check script | Not run; `contracts/openapi.json` was read only | Any contract-changing slice, FUP-4 |
| `ruff check` / `ruff format` | No lint execution permitted | FUP-1/FUP-4 as configured |
| `python manage.py check` | No Django runtime permitted | FUP-1/FUP-4 |
| `python manage.py makemigrations --check` | No schema command permitted | Any migration-changing slice |
| `python manage.py migrate` | No database command permitted | Deployment/migration slice, not FUP-0 |
| `python manage.py shell` / Django shell | No runtime or data command permitted | Never for this audit |
| Any ORM/database query (`psql`, Django ORM, SQL) | No database access permitted; no PII access | Authorized reporting only, outside FUP-0 |
| Seed command / fixture load | No data mutation permitted | Never for this audit |
| `next dev` / Django `runserver` | No dev server permitted | Manual validation only when authorized |
| Manual browser walkthrough of any journey | No browser/UI execution permitted | FUP-4 UAT |
| Coverage run | No test execution permitted | FUP-4 if configured |
| `git fetch`, `pull`, `checkout`, `switch`, `add`, `commit`, `merge`, `rebase`, `stash`, `reset`, `clean`, `tag`, `push` | No Git state change permitted | Only on explicit authorization, outside FUP-0 |
| Any deployment, migration or environment command (staging/production) | No environment access permitted | Release process, not FUP-0 |

**Read-only commands that were used:** `git rev-parse`, `git status --short`, `rg`, `grep`, `sed -n`,
`ls`, `wc`, and file reads. A read-only Python snippet parsed `contracts/openapi.json` to enumerate
paths; it imported no application module and touched no database.

## 6. Evidence limits

1. **Static only.** Every "Verified" claim is a code/contract/document fact at HEAD. No runtime
   behavior, race, network, notification delivery, encryption round-trip or browser rendering was
   exercised.
2. **Single base.** Line numbers are valid only at `5224256a`. Any later commit requires re-checking
   every citation.
3. **Test count is static.** "29 test functions / 33 declared cases" counts `def test_` and
   `@pytest.mark.parametrize` declarations; pytest was not run, so collection, skips, failures and
   database-specific outcomes are **Unknown**.
4. **No data.** Task volume, source-loss frequency, orphan count, notification volume and data quality
   are **Unknown**. No production or staging access was used.
5. **No institutional approval.** All decisions are **Open**; provisional recommendations are audit
   proposals, not policy.
6. **No PII or secrets.** No Student record, credential, key, ciphertext or production identifier is
   reproduced. Test fixtures cited are synthetic.
7. **UAT is proposed.** All 20 journeys in [`ux-journeys.md`](ux-journeys.md) are unexecuted. The
   proposal's 45 UAT scenarios (lines 6417–6467) are unexecuted at HEAD.
8. **Deployment state is Unknown.** Whether the deployed staging schema matches this integration branch,
   and whether the notification flag is enabled in any environment, was not checked.
9. **Frontend rendering is unverified.** Copy, responsive behavior, focus order and screen-reader
   behavior were reasoned from source, not observed.
10. **The proposal was not treated as evidence.** Its stale claims are listed in
    [`README.md`](README.md) D1–D8.

## 7. Audit questions A–L

| ID | Question | Where answered | Status |
|---|---|---|---|
| A | Model and lifecycle | [`current-state.md`](current-state.md) §§2–5; `models.py:45-144`; `services.py:268-463` | Answered |
| B | Sources and confidentiality | [`current-state.md`](current-state.md) §§3, 5; [`source-lifecycle.md`](source-lifecycle.md); [`access-matrix.md`](access-matrix.md) | Answered |
| C | Roles, capabilities and scope | [`access-matrix.md`](access-matrix.md); `accounts/policy.py:142-150,654-701,761-795`; `guidance_followups/policy.py:18-245` | Answered |
| D | Creation and mutation safeguards | [`current-state.md`](current-state.md) §§4, 6; `services.py:127-208,268-463`; `replay.py`; `content.py` | Answered |
| E | Source-reconciliation gap | [`source-lifecycle.md`](source-lifecycle.md); [`README.md`](README.md) findings 1–3; `policy.py:162-183`; `services.py:288-334` | Answered — gap proven |
| F | Completion / further-action gap | [`current-state.md`](current-state.md) §5; [`ux-journeys.md`](ux-journeys.md) UAT-FUP-16; [`decisions.md`](decisions.md) D-FUP-03 | Answered — gap proven |
| G | Workspace, reporting and notifications | [`current-state.md`](current-state.md) §§7–8; [`ux-journeys.md`](ux-journeys.md); `workspace.py:150-187`; `integration.py:47-93` | Answered |
| H | Recovery | [`access-matrix.md`](access-matrix.md) §6; [`current-state.md`](current-state.md) §9; `recovery.py:49-135` | Answered |
| I | Academic scope / SAR | [`cross-proposal-readiness.md`](cross-proposal-readiness.md) §4; [`README.md`](README.md) finding 7; `organization/migrations/0005_delete_studentaffiliation.py:13-15` | Answered — code migration complete |
| J | Cross-proposal readiness (FAC/CONT/SAR) | [`cross-proposal-readiness.md`](cross-proposal-readiness.md) | Answered per slice |
| K | Test inventory | [`current-state.md`](current-state.md) §10; [`README.md`](README.md) counts; §6 above | Answered — inventory only, none executed |
| L | API / frontend surface and OpenAPI consistency | [`current-state.md`](current-state.md) §§7, 11–12; [`ux-journeys.md`](ux-journeys.md); 12 paths / 14 operations | Answered — static consistency only |

## 8. Definition-of-done checklist

| Requirement | Result | Evidence |
|---|---|---|
| A–L answered with claim labels and evidence | **Met** | §7; findings and documents carry labels |
| Proposal-vs-HEAD divergence table, including `StudentAffiliation` | **Met** | [`README.md`](README.md) D1–D8 and the explicit SAR answer |
| Source-invalidation gap proven or disproven | **Met — proven** | [`source-lifecycle.md`](source-lifecycle.md); findings 1–3, 10 |
| Further-action gap proven or disproven | **Met — proven** | [`current-state.md`](current-state.md) §5; finding 4 |
| FAC/CONT/SAR readiness per slice | **Met** | [`cross-proposal-readiness.md`](cross-proposal-readiness.md) |
| Decision register with options, owners, blocking impact | **Met** | [`decisions.md`](decisions.md) D-FUP-01..07, all **Open** |
| FUP-1/FUP-2 plan with exact files, components, endpoints, tests; full regression deferred to FUP-4 | **Met** | [`implementation-plan.md`](implementation-plan.md) |
| Validation lists every command not run, including all suites | **Met** | §5 |
| No application, schema, seed, generated-artifact or Git change | **Met** | §2: only `?? docs/fup-0/`; pre-existing untracked output untouched |
| No test result claimed | **Met** | Header and §6; no pass/fail statement exists in the package |

## 9. Re-verification recipe (read-only)

A reviewer can reproduce the key facts without changing state:

```bash
git rev-parse HEAD
git status --short -- docs/fup-0 be fe contracts
rg -n "StudentAffiliation" be/compass be/tests
rg -n "guidance_followups" be/compass/accounts/policy.py be/compass/notifications/policy.py
rg -n "GUIDANCE_FOLLOWUP_NOTIFICATIONS_ENABLED" be
rg -n "source_unavailable|source_kind|source_id" be/compass/guidance_followups fe/src/features/guidance-followups
rg -n "def test_" be/tests/test_guidance_followups.py
rg -n "guidanceFollowups" contracts/openapi.json | head
```

Expected static results at this HEAD: `StudentAffiliation` only in historical organization migrations and
documentation; the two capabilities in `accounts/policy.py`; the flag default `False`; 29 test functions;
14 operation IDs. If any result differs, the audit is stale and must be repeated.

## 10. Change manifest

Created (untracked, documentation only):

- `docs/fup-0/README.md`
- `docs/fup-0/current-state.md`
- `docs/fup-0/source-lifecycle.md`
- `docs/fup-0/access-matrix.md`
- `docs/fup-0/ux-journeys.md`
- `docs/fup-0/cross-proposal-readiness.md`
- `docs/fup-0/decisions.md`
- `docs/fup-0/risks.md`
- `docs/fup-0/implementation-plan.md`
- `docs/fup-0/validation.md`

No commit, branch, tag or remote operation was performed. No file outside `docs/fup-0/` was created or
modified by this audit.
