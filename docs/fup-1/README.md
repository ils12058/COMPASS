> 2026-11-10: The policy layer was removed; see [ADR-119](../../be/docs/decisions/ADR-119-remove-provisional-policy-layer.md) for current rules and reset-only delivery. This document remains historical.

# FUP-1 — source truthfulness and regression proof

**Status: provisional implementation — pending GCO.**
D-FUP-01 and D-FUP-07 remain **Open** in [`../fup-0/decisions.md`](../fup-0/decisions.md). The copy in
this slice is proposed wording, not approved institutional language. No GCO, UCN, privacy, records or
institutional approval is claimed or implied.

**Implementation base:** `integration/ux15-modernization` at
`4614b228482336c100ec5363871c4303e013cedd` (the FUP-0 audit commit on top of audit base
`5224256a76c07f4503b5e3d98fea65c4ed84f2a9`).
**Evidence date:** 2026-11-05.

## 1. Scope

This package records **FUP-1A** and **FUP-1B only**:

| Slice | Result |
|---|---|
| FUP-1A — characterization tests | Six tests added to `be/tests/test_guidance_followups.py`; all pass against unchanged production code |
| FUP-1B — detail, context and help copy | Source-unavailable detail copy, generic context-panel message and help section implemented |

FUP-1C (list/report source indicator), FUP-1D (server-enforced review gate), FUP-2 and every FUP-3
slice were **not implemented**. No review checkbox, schema, endpoint, authorization, contract,
migration, notification or generated-client change was made.

## 2. What changed

| File | Change |
|---|---|
| `be/tests/test_guidance_followups.py` | Six additive characterization tests; no production code |
| `fe/src/features/guidance-followups/followups-detail.tsx` | Proposed copy in the existing `source_unavailable` branch |
| `fe/src/features/guidance-followups/followups-context.tsx` | Pending remains `null`; context error now renders one compact generic panel message |
| `fe/src/features/guidance-followups/followups-help.tsx` | New "When a related record becomes unavailable" section |
| `fe/tests/guidance-followups.browser.mjs` | `sourceUnavailable` synthetic world; detail and context error checks; help-copy assertion |

No shared copy constant was introduced because the detail sentence, context message and help paragraph
are distinct and are not reused by list or report. `followups-shared.tsx` and
`fe/tests/guidance-followups.test.mjs` were therefore not changed.

## 3. What the behavior remains

The behavior locked by FUP-1A and described by FUP-1B is unchanged:

- a voided Referral does not close, hide or reassign its operational Follow-Up;
- the Follow-Up keeps its own status and remains independently actionable;
- a Counselor-confidential Follow-Up whose source is no longer readable is not returned by ordinary
  list, report, My Work or recovery, and its detail and mutations are not found;
- completing a Follow-Up does not change the related Referral;
- source invalidation writes no Follow-Up event, audit or material notification occurrence.

## 4. Evidence summary

| Check | Result |
|---|---|
| Targeted backend file | `39 passed in 62.44s` |
| Follow-Up browser suite (Chromium) | `21/21 browser checks passed` |
| Contract/generated-client drift | empty diff |

Exact commands and the complete not-run list are in [`validation.md`](validation.md).

## 5. Authority and limits

- D-FUP-01 Option A is implemented as a **provisional engineering default**; it is not an institutional
  decision. See [`decisions.md`](decisions.md).
- The D-FUP-07 copy is **proposed wording pending GCO**. It must not be described as approved.
- Full regression, WebKit, lint, typecheck, build, OpenAPI export, Orval regeneration and every
  runtime/data operation remain unrun; full regression is deferred to FUP-4.
- Changes are uncommitted. No commit, merge, push, rebase, stash or reset was performed.

## 6. Package contents

- [`implementation.md`](implementation.md) — exact changes, tests and exclusions.
- [`decisions.md`](decisions.md) — provisional D-FUP-01 and D-FUP-07 record.
- [`validation.md`](validation.md) — commands, results, not-run list and evidence limits.
