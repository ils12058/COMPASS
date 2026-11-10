> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-0 — Guidance Follow-Up domain and source-lifecycle audit

**Status:** documentation-only, read-only audit. No implementation, schema, seed, generated-artifact,
runtime or Git change was made.
**Audit base:** `integration/ux15-modernization` at
`5224256a76c07f4503b5e3d98fea65c4ed84f2a9` (SAR-7), 2026-11-05.
**Proposal reviewed:** *COMPASS — Guidance Follow-Up Workflow Coherence and Cross-Domain Integration*,
`/Users/reynantlntno/Downloads/COMPASS Proposals/COMPASS Development Proposal Notes - Fifteen Proposals.md`,
lines 5599–6647. That proposal was written against `staging` at `0a843dae` on 2026-10-20 and explicitly
requires re-audit before implementation (proposal lines 5607, 5616–5618, 6608).
**Claim labels:** every substantive claim below is **Verified** (static evidence with `path:line`),
**Inferred** (reasoned from verified code), or **Unknown** (evidence or command still required).
**Data handling:** no Student PII, secret, credential, production record or staging state is reproduced.
No database, migration, seed, test, dev-server or deployment command was executed.

## Why this audit exists

COMPASS already has an independent, encrypted, auditable Follow-Up domain. The open questions are not
"should we build task tracking?" but "what happens when the source record changes, when the source
Counselor is no longer available, and when one task is finished but the work is not?" Those are policy
questions with security and workflow consequences. FUP-0 establishes the verified current behavior so
GCO can approve task meanings and UAT journeys before FUP-1/FUP-2 code is written.

The proposal's own FUP-0 slice requires a "verified source/role/event/UX matrix, GCO-approved task
meanings and concrete UAT journeys" (proposal line 6367). This package supplies the verified matrix and
the proposed journeys. It does **not** supply GCO approval.

## Package map

| File | Question answered |
|---|---|
| [`current-state.md`](current-state.md) | What the domain is today: models, lifecycle, encryption, concurrency, API and UX inventory |
| [`source-lifecycle.md`](source-lifecycle.md) | What happens when a Referral, Encounter or Routine changes; exact revalidation and reconciliation gaps |
| [`access-matrix.md`](access-matrix.md) | Which actor can see, mutate, reassign or recover which task and source |
| [`ux-journeys.md`](ux-journeys.md) | Current user experience, truthful copy, proposed GCO task meanings and concrete UAT journeys |
| [`cross-proposal-readiness.md`](cross-proposal-readiness.md) | FAC, CONT and SAR readiness for FUP-3A/3B/3C, including the retired `StudentAffiliation` |
| [`decisions.md`](decisions.md) | D-FUP-01..07 with options, provisional recommendations, owners, blockers and Open status |
| [`risks.md`](risks.md) | Risk register, mitigations, rollback/review triggers |
| [`implementation-plan.md`](implementation-plan.md) | Proposed FUP-1 and FUP-2 work packages naming exact files, endpoints and tests; deferred FUP-3/4 |
| [`validation.md`](validation.md) | Method, inspected scope, evidence limits, every command not run, definition-of-done result |

## Static counts at the audit base

| Object | Count | Evidence |
|---|---:|---|
| Django models | 3 (`GuidanceFollowUp`, `GuidanceFollowUpEvent`, `GuidanceFollowUpMutation`) | `be/compass/guidance_followups/models.py:45,147,179` |
| Migrations | 2 | `be/compass/guidance_followups/migrations/0001_initial.py`, `0002_guidancefollowupmutation.py` |
| OpenAPI operations | 14 across 12 paths | `contracts/openapi.json`, operation IDs `guidanceFollowups*` |
| Capabilities | 2 (`guidance_followups.view`, `guidance_followups.manage`) | `be/compass/accounts/policy.py:142-150` |
| Follow-Up notification event types | 3 (`assigned`, `reassigned`, `due_changed`) | `be/compass/notifications/policy.py:42-44` |
| Audit actions | 6 | `be/compass/audit/actions.py:255-260` |
| Backend test functions / collected cases | 29 / 33 static | `be/tests/test_guidance_followups.py`; parametrization at `:767-775,876` |
| Frontend route pages | 5 | `fe/src/app/(portal)/portal/follow-ups/{page.tsx,new,report,reassignment,[followupId]}` |
| Frontend feature files | 10 | `fe/src/features/guidance-followups/` |

All counts are **Verified** by static inspection. "33 collected cases" is a static count of test
functions plus declared parametrization; it is not a test result. No test was run.

## Top 10 findings

| # | Finding | Claim | Evidence |
|---|---|---|---|
| 1 | An **operational** Follow-Up survives Referral voiding. Its detail remains readable and mutable; only the source link becomes unavailable (`source: null`, `source_unavailable: true`). It is not hidden, cancelled, reassigned or audited as part of voiding. | **Verified** | `policy.py:162-183` (operational branch does not recheck source); `services.py:268-283`; `api.py:253-263`; `test_guidance_followups.py:252-275` (voids a Referral and asserts detail `source is None`); `referrals/services.py:896-915` (void is Referral-owned) |
| 2 | There is **no server-side source-reconciliation contract**: no review state, review endpoint, source-invalidation event, or relink operation. `source_kind`/`source_id` are immutable after creation; `update_followup` accepts only due date, category and description. | **Verified** | `services.py:288-334`; `models.py:52-55,99-106`; no `source_review`/`reconcil` symbols under `be/compass/guidance_followups` |
| 3 | A **confidential** task whose professional source stops being readable for its owner becomes an inaccessible, still-pending orphan. Detail/mutation require the live source relationship; list/report/My Work SQL mirrors it; recovery excludes confidential rows; Head designation does not bypass it. The task cannot be completed, cancelled or reassigned until source access returns. | **Verified** code path; **Inferred** operational consequence | `policy.py:162-183,186-245`; `recovery.py:49-56`; `policy.py:42-48`; `docs/cont-0/README.md:24`; `docs/cont-0/source-record-policy.md:21` |
| 4 | There is **no further-action or predecessor mechanism**. Completion is terminal; no `predecessor_followup_id`, no "next action" field, no completion payload option, no backend endpoint and no frontend control. | **Verified** | `models.py:45-94`; `services.py:391-417`; `fe/src/features/guidance-followups/followups-detail.tsx:86-89`; no `predecessor`/`next_follow` symbols under `be/compass/guidance_followups` or `fe/src/features/guidance-followups` |
| 5 | Completion and cancellation are terminal and not reversible through any normal route. `_lock_for_mutation` rejects any non-`PENDING` task; the database constraint enforces mutually exclusive terminal provenance. | **Verified** | `services.py:281-282`; `models.py:108-136`; no reopen/resume service or route |
| 6 | Head Guidance Counselors get **operational** oversight only: they may be assigned any active Student and may recover any operational orphan, but they receive no Follow-Up capability from the designation and no confidential task/source access. Their ordinary list remains assignment-scoped. | **Verified** | `accounts/policy.py:761-795` (designation grant contains no follow-up capability); `policy.py:42-48,186-210`; `recovery.py:49-64`; `test_guidance_followups.py:705-730` |
| 7 | **SAR removed `StudentAffiliation` at HEAD.** Live Follow-Up scope, assignee selection and recovery already use `student_academics`; the retired model survives only in historical organization migrations. FUP-3C's code migration is therefore already satisfied; what remains is stale proposal/SAR-0 documentation and verification. | **Verified** | `organization/migrations/0005_delete_studentaffiliation.py:13-15`; `policy.py:200-208`; `workspace.py:6-7,113-114`; `recovery.py:57-64`; `docs/sar-3-4/implementation.md:37,41`; `docs/sar-5/validation.md:265,274-275` |
| 8 | **FUP-3A is not implemented, and institutional FAC approval is still blocked.** Referral has Faculty-origin/administrative-state primitives, but no Follow-Up bridge, no FUP-specific Faculty operation, and FAC-D1–D10 remain pending with default providers `None`. | **Verified** | `be/compass/referrals/models.py:48-125,131-138`; `be/compass/referrals/administrative_state.py:7-19`; `docs/fac-5/readiness.md:8-12`; `docs/fac-5/institutional-decisions.md:1-4`; no `guidance_followup` references in `be/compass/referrals/*.py` |
| 9 | **FUP-3B is blocked.** Continuity grant models are time-bounded and revocable, but the runtime policy provider returns `None`, so `require_policy` denies; there is no Follow-Up continuity adapter, and a source **read** grant cannot satisfy the Follow-Up **manage** requirement. | **Verified** | `be/compass/counseling/continuity_policy.py:99-109`; `be/compass/counseling/continuity_models.py:49-68,87,138-141`; `docs/cont-4/final-assessment.md:7-10`; `docs/cont-0/source-record-policy.md:21` |
| 10 | Test coverage is strong for creation, confidentiality, lifecycle, idempotency, recovery and notifications, but **absent** for the post-creation source-invalidation journey: no test covers list/report/My Work/notification behavior after a Referral void, confidential source loss, Head list oversight, or further-action. The proposal's cited cross-domain test file contains no Follow-Up references. | **Verified** | `be/tests/test_guidance_followups.py:252-275` covers only detail after void; `be/tests/test_cross_domain_lifecycle_reconciliation.py` has zero Follow-Up matches; proposal line 6619 cites it |

## Proposal-vs-HEAD divergences

The proposal is not wrong for its stated baseline, but several material claims are stale at HEAD. No
proposal claim is treated as evidence without re-verification.

| # | Proposal claim | HEAD evidence | Disposition |
|---|---|---|---|
| D1 | "The current Follow-Up policy, eligible-assignee selection and recovery contain direct uses of `StudentAffiliation`" (line 5748; repeated at 6227). | `policy.py:200-208`, `workspace.py:6-7,113-114`, `recovery.py:57-64` use `student_academics`; `StudentAffiliation` appears only in `organization/migrations/0001` and `0005` (`docs/sar-5/validation.md:265`). | **Stale claim.** The proposal was correct at `0a843dae`; SAR-2A/3/4 changed the code before this audit. |
| D2 | "Current production/staging academic scope remains based on the existing affiliation relationship" (line 5748). | HEAD is an integration branch after SAR-7; no live `StudentAffiliation` code remains. Deployed staging state is **Unknown** (no deployment access). | **Baseline divergence.** Do not repeat the claim for HEAD; verify deployment separately. |
| D3 | FUP-3C is listed as an academic-scope migration prerequisite (proposal lines 6372, 6353, 6412). | The code migration is already done; the remaining FUP-3C work is documentation reconciliation and regression evidence, not a new consumer migration. | **Scope reduction.** Reclassify FUP-3C as verification-only at HEAD. |
| D4 | The proposal cites `be/tests/test_cross_domain_lifecycle_reconciliation.py` as cross-domain lifecycle evidence (line 6619). | The file exists but contains **no** `followup`/`FollowUp` reference (static `rg`). | **Evidence gap.** Do not cite it as Follow-Up cross-domain coverage. |
| D5 | "Selected source-invalidity cases" are already tested (line 5752). | The only post-creation invalidity test is `test_referral_source_keeps_operational_scope` (`:252-275`), which asserts detail source absence only. List, report, My Work, notification, recovery and confidential source loss are untested. | **Overstatement.** Treat as partial coverage. |
| D6 | Reference branch is `staging` at `0a843dae` (line 5607, 6608). | Audit base is `integration/ux15-modernization` at `5224256a`; SAR and FAC-5 work has since merged. | **Baseline divergence.** All claims here are re-verified at `5224256a`. |
| D7 | The proposal's 22 open decisions and 45 UAT scenarios are numbered 1–22 and 1–45 (lines 6493–6518, 6417–6467). | No current code or approved policy adopts them. The seeded D-FUP-01..07 are a narrower FUP-0 set; the remaining proposal decisions remain unadopted. | **Proposal artifact, not current behavior.** |
| D8 | The proposal treats "FUP-1 source reconciliation and FUP-2 completion UX" as implementable before CONT (lines 6368-6375, 6325-6355). | Code inspection agrees for operational tasks. Confidential source loss cannot be solved there without CONT and a separate task-coverage policy. | **Partially confirmed.** Split operational and confidential scope explicitly. |

**Did SAR remove `StudentAffiliation`?** **Verified yes at HEAD.** The model is deleted by
`be/compass/organization/migrations/0005_delete_studentaffiliation.py:13-15`, and no live
`be/compass` module references it (`docs/sar-5/validation.md:265,274-275`; re-run static search in
`validation.md`). Historical migrations still contain the name. The proposal's staging-era claim and
`docs/sar-0/README.md:37-38,55-58` describe the pre-SAR baseline and are not HEAD truth.

## Recommended smallest safe FUP-1 scope

**Recommendation, not adopted policy.** The smallest useful FUP-1 is a **projection-and-copy slice with
no schema change and no cross-domain write**, conditional on D-FUP-01 and D-FUP-07.

1. Keep the three canonical statuses and the existing model. Do not add a source-review state until
   GCO decides whether review must be mandatory (D-FUP-01).
2. Make source availability truthful everywhere the task is already authorized: expose the existing
   `source_unavailable` fact consistently (detail already has it; the list/report need a safe,
   non-leaking indicator only if GCO approves), and replace the current silent context-panel
   disappearance with an approved, non-leaking explanation where the source page is still readable.
3. Add server-side tests for the **existing** behavior: Referral void after creation, list/report/My
   Work/notification inclusion, operational mutation after void, and the confidential-source-loss
   orphan. Do not change authorization semantics without D-FUP-01.
4. Do not add a new endpoint, source-review flag, automatic cancellation, relinking, or Head bypass.
5. Defer FUP-2 further-action to D-FUP-03/D-FUP-04; defer FUP-3A/3B to FAC/CONT; treat FUP-3C as
   verification-only.

**Why this is smallest:** it removes the most misleading user-visible state (a broken or silently
missing source) without inventing persistence or delegation. It does not resolve the confidential
orphan or decide whether review is mandatory; those are institutional decisions, not code defaults.

## What FUP-0 did not do

- No `be/`, `fe/`, `contracts/openapi.json`, generated-client, migration, seed, fixture or dependency
  change.
- No test, lint, build, OpenAPI export, Orval regeneration, `manage.py`, Django shell, database query,
  seed, dev server or browser run.
- No `git fetch`, checkout, stage, commit, merge, rebase, stash, reset or push; the pre-existing
  untracked `outputs/paper-screenshots/` directory was left untouched.
- No staging or production access; no deployed-state claim.
- No GCO, UCN, privacy or legal approval; every proposed rule remains **Pending**.
- No population-level analysis. Source-loss frequency, actual task volumes, and live data quality are
  **Unknown** and require an authorized read-only query outside this audit.
