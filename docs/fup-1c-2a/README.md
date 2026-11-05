# FUP-1C + FUP-2A — list source availability and completion copy

**Status: provisional implementation — pending GCO.**
D-FUP-01, D-FUP-03 and D-FUP-07 remain **Open** in
[`../fup-0/decisions.md`](../fup-0/decisions.md). The behavior and copy in this slice are provisional
engineering defaults and proposed wording, not approved institutional language. No GCO, UCN, privacy,
records or institutional approval is claimed or implied.

**Implementation base:** `integration/ux15-modernization` at
`1e3c34c7228b6e19d1b46f1ad7f737e17ff6bf64` (the FUP-1 commit).
**Evidence date:** 2026-11-05.

## 1. Scope

This package records **FUP-1C** and **FUP-2A only**:

| Slice | Result |
|---|---|
| FUP-1C — list source availability | `source_unavailable` added to `FollowUpSummary`; muted list indicator; report explanatory copy; no report counter |
| FUP-2A — completion copy | Detail completion paragraph and Help section; copy only |

Explicitly **not implemented**: FUP-1D review gate, FUP-2B "Create next follow-up", FUP-2C lineage,
FUP-3A/B/C, any automatic source-driven action, any report aggregate or per-task report field, any
authorization change. No model, migration, service authorization, notification, seed, package or
unrelated UI change was made.

## 2. What changed

Handwritten files:

| File | Change |
|---|---|
| `be/compass/guidance_followups/policy.py` | Shared `source_is_visible` helper; `visible_source` reuses it |
| `be/compass/guidance_followups/api.py` | `source_unavailable` on `FollowUpSummary`; page-batched visibility in `_summaries`; list, recoverable, detail and receipt call sites updated |
| `be/tests/test_guidance_followups.py` | Four FUP-1C tests added |
| `fe/src/features/guidance-followups/followups-list.tsx` | Muted "Related record unavailable" line in the Status cell |
| `fe/src/features/guidance-followups/followups-report.tsx` | Workload explanatory paragraph |
| `fe/src/features/guidance-followups/followups-detail.tsx` | Completion further-action paragraph |
| `fe/src/features/guidance-followups/followups-help.tsx` | "Completion and further action" section |
| `fe/tests/guidance-followups.browser.mjs` | Mixed list fixture; list, report, completion and Help assertions |
| `docs/fup-1c-2a/**` | This package |

Generated files:

| File | Change |
|---|---|
| `contracts/openapi.json` | Only `source_unavailable` added to `FollowUpSummary` (and inherited by `FollowUpDetail`) |
| `fe/src/lib/api/generated/**` | Regenerated through Orval; the directory is gitignored (`.gitignore:23`) so it has no tracked diff |

`fe/tests/guidance-followups.test.mjs` and `followups-shared.tsx` were not changed: no pure copy
helper or shared label was introduced, and the list line is a single inline string.

## 3. Gate status

| Decision | Status in this slice |
|---|---|
| D-FUP-01 Option A (preserve and project the task; guidance only) | **Provisional — pending GCO** |
| D-FUP-03 guidance-only further-action copy (no persistence) | **Provisional — pending GCO** |
| D-FUP-07 wording | **Provisional — pending GCO**; proposed wording only |

No approval is recorded, and no decision is narrowed beyond the engineering default described in
[`decisions.md`](decisions.md).

## 4. Evidence summary

| Check | Result |
|---|---|
| Targeted backend file | `43 passed in 70.12s (0:01:10)` |
| Targeted backend + contract files | `84 passed in 137.87s (0:02:17)` |
| Contract export | `Exported OpenAPI contract: .../contracts/openapi.json` |
| Contract check | `OpenAPI contract is current: .../contracts/openapi.json` |
| Client regeneration | Orval completed; `FollowUpSummary` and `FollowUpDetail` both contain `source_unavailable` |
| Follow-Up browser suite (Chromium) | `23/23 browser checks passed` |
| Contract diff | `contracts/openapi.json \| 7 ++++++-` (6 insertions, 1 deletion; new field only) |
| Working tree | allowed files plus pre-existing `outputs/paper-screenshots/` only |

Exact commands, artifacts, evidence limits and the complete not-run list are in
[`validation.md`](validation.md).

## 5. Authority and limits

- The projection, indicator, report note and completion copy are engineering defaults for review;
  they do not record a GCO, UCN, privacy, records or institutional decision.
- The browser and backend results are engineering regression evidence, not UAT or institutional
  acceptance.
- Full regression, WebKit, `pnpm test`, lint, typecheck, build, migrations, seed and every
  runtime/data operation were not run; full regression is deferred to FUP-4.
- Changes are uncommitted. No commit, merge, push, rebase, stash or reset was performed.

## 6. Package contents

- [`implementation.md`](implementation.md) — backend semantics, batching, contract regeneration,
  exact copy and test list.
- [`decisions.md`](decisions.md) — provisional D-FUP-01/03/07 record.
- [`validation.md`](validation.md) — commands, results, not-run list and evidence limits.
