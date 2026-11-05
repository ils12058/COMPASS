# FUP-2B + FUP-3A — next follow-up action and provisional Faculty Referral journey

**Status: Provisional — pending GCO/FAC.**
Every behavior and string in this package is provisional engineering output. D-FUP-03, D-FUP-04,
D-FUP-05 and D-FUP-07 remain **Open** in [`../fup-0/decisions.md`](../fup-0/decisions.md);
FAC-D1–D8 remain unresolved in
[`../fac-5/institutional-decisions.md`](../fac-5/institutional-decisions.md). No GCO, UCN, FAC,
privacy, records, UAT or deployment approval is claimed or implied. The code-owned provisional
providers are explicitly **not** institutional approval.

**Implementation base:** `integration/ux15-modernization` at
`9ad73c9c219aa8e4dc8ae56d7c71a9b89c35fc4a` (the FUP-1C + FUP-2A commit).
**Evidence date:** 2026-11-05.

## 1. Scope

This package records **FUP-2B** and **FUP-3A only**:

| Slice | Result |
|---|---|
| FUP-2B — create next follow-up | A completed, manageable Follow-Up shows one secondary `Create next follow-up` navigation link to the existing create page. The link carries only the readable source kind/id or the standalone Student identity. |
| FUP-3A — provisional Faculty Referral journey | The five Faculty/administrative providers are default-on through code-owned provisional policies. The canonical Student confirmation → Faculty submission → own tracking → GCO acknowledgment → administrative closure journey runs by default, with a Referral-linked staff Follow-Up proven end to end. |

Explicitly **not implemented**: FUP-1D, FUP-2C, FUP-3B, FUP-3C and FUP-4; any new Follow-Up or
Referral endpoint, model, migration, contract or generated-client change; any Faculty-facing
Follow-Up signal (status, count, due date, assignee, activity, outcome); any automatic
source-driven action; any Referral notice, email, push or external delivery (**FAC-D8 remains
inactive**); any automatic Referral closure from Follow-Up or Follow-Up mutation from Referral;
any confidentiality widening, capability change or role change; any settings, environment, database
grant, feature-flag package or `*_ENABLED` gate.

## 2. What changed

Handwritten files:

| File | Change |
|---|---|
| `be/compass/referrals/provisional_activation.py` | **New.** Fixed, code-owned provisional policies and their fixed Audit evidence for five kinds. |
| `be/compass/referrals/faculty_policy.py` | Structural/activation validation split; lookup and submission providers return the provisional policies. |
| `be/compass/referrals/administrative_policy.py` | Structural/activation validation split; acknowledgment, closure and tracking providers return the provisional policies; Faculty notice provider remains `None`. |
| `be/tests/test_fup3a_faculty_referral_journey.py` | **New.** Six tests, including the canonical end-to-end journey on the real default providers. |
| `be/tests/test_faculty_referrals.py` | Renamed the missing-provider test; fail-closed assertions unchanged. |
| `be/tests/test_referral_administration.py` | Renamed the missing-provider test; fail-closed assertions unchanged. |
| `fe/src/features/guidance-followups/followups-shared.tsx` | New pure `nextFollowupHref` helper. |
| `fe/src/features/guidance-followups/followups-detail.tsx` | `What happens next` panel and the `Create next follow-up` link on completed, manageable Follow-Ups. |
| `fe/src/features/guidance-followups/followups-help.tsx` | `Creating the next follow-up` Help section. |
| `fe/tests/guidance-followups.test.mjs` | URL-contract unit test for `nextFollowupHref`. |
| `fe/tests/guidance-followups.browser.mjs` | Completed, unavailable-source, view-only, Pending and cancelled cases; Help assertion. |
| `docs/fup-2b-3a/**` | This package. |
| `docs/fac-5/readiness.md` | Dated superseding implementation note; the original verdict is retained. |

Generated files:

| File | Change |
|---|---|
| `contracts/openapi.json` | **None.** No API shape or operation changed. |
| `fe/src/lib/api/generated/**` | **None.** Not regenerated and not hand-edited. |

## 3. Gate status

| Decision | Status in this slice |
|---|---|
| D-FUP-03 — meaning and persistence of "further action" | **Provisional — pending GCO.** UI-only navigation to the existing create form; no disposition, predecessor/successor link, automatic creation or persistence. |
| D-FUP-04 — who may initiate a next Follow-Up | **Provisional — pending GCO.** The existing create authorization is unchanged; the link grants no authority and does not preselect an assignee. |
| D-FUP-05 — completion never closes a Referral; voiding never silently closes a Follow-Up | **Provisional — pending GCO.** Both invariants are affirmed and proven in the journey test; no automatic action was added. |
| D-FUP-07 — GCO sign-off of meanings and UAT journeys | **Provisional — pending GCO.** The new strings are proposed wording, not approved language. |
| FAC-D1–FAC-D7 | **Provisional — pending FAC.** Code-owned provisional providers exist; every institutional question remains open. |
| FAC-D8 — notifications | **Inactive.** `get_approved_faculty_notice_policy()` still returns `None`; no producer, catalog entry, channel or delivery was added. |

## 4. Evidence summary

| Check | Result |
|---|---|
| Targeted backend files | `135 passed in 89.15s` |
| Follow-Up + Referral focused files | `test_faculty_referrals.py` 59, `test_referral_administration.py` 27, `test_guidance_followups.py` 43, `test_fup3a_faculty_referral_journey.py` 6 |
| Frontend unit | 4 passed, 0 failed |
| Follow-Up browser suite | 28/28 checks passed |
| Faculty Referrals browser suite | 35/35 checks passed |
| Referral Administration browser suite | 108/108 checks passed |
| Faculty Foundation browser suite | 11/11 checks passed |
| Typecheck | Passed (`tsc --noEmit`) |
| Lint | Passed after escaping one apostrophe; first run failed one `react/no-unescaped-entities` error |
| Contract check | `OpenAPI contract is current` |
| Contract/generated diff | None |
| Whitespace hygiene | `git diff --check` exit 0 |

Exact commands, first-run failures, the local smoke-check side effect, evidence limits and the
complete not-run list are in [`validation.md`](validation.md).

## 5. Authority and limits

- The provisional providers are code-owned defaults with truthful `PROVISIONAL` evidence. They do
  not record an institutional decision, approval, signature or UAT result.
- The five fixed Audit events are append-only. A future approved implementation must add separate
  approved evidence; it cannot relabel, edit or delete the provisional rows.
- No setting, environment variable, database grant or request input enables the provisional path;
  changing `be/compass/referrals/provisional_activation.py` is the only mechanism.
- The browser suites use synthetic HTTP fixtures. The backend journey test uses a test database
  and the real default providers, with only the Redis confirmation limiter replaced by an
  in-memory synthetic limiter.
- No manual UI session, live backend, seed, staging or production environment is represented.
- The only notifications observed in the journey are the existing in-app Follow-Up assignment
  notices produced by the Follow-Up domain when staff are assigned. There are no Referral-targeted
  or Referral-sourced notices and no `EmailDelivery`. This nuance is recorded in
  [`validation.md`](validation.md) §4.3 and [`implementation.md`](implementation.md) §2.8.
- Changes are uncommitted. No commit, merge, push, rebase, stash or reset was performed.

## 6. Package contents

- [`implementation.md`](implementation.md) — exact frontend URL contract and copy, provisional
  provider wiring, evidence model, scope/window semantics, journey proof and exclusions.
- [`decisions.md`](decisions.md) — provisional D-FUP-03/04/05/07 and FAC-D1–D8 record.
- [`validation.md`](validation.md) — commands, results, first-run failures, artifacts, not-run list
  and evidence limits.
