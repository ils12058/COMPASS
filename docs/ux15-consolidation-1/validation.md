# Local validation — October 22, 2026

All checks run from the isolated `feat/ux15-forms-consolidation` worktree based on
`757eb933786b8067724394c365d3a760279a1627`. Browser APIs are intercepted by the existing
localhost-only harness with synthetic records. No live backend, Student/Counselor data,
notification, deployment workflow or institutional service was used.

## Commands and results

Commands below run from `fe/` unless specified otherwise.

| Check | Executed result |
| --- | --- |
| `pnpm install --offline --frozen-lockfile` | Passed; 727 pinned packages, unchanged lockfile. |
| `pnpm api:generate` | Passed against unchanged `contracts/openapi.json`; ignored generated client, no generated changes committed. |
| `pnpm lint` | Passed; final full run after screenshot-capture instrumentation passed. Two later embedded-context test additions also passed `pnpm exec eslint tests/ux15-consolidation.browser.mjs`. |
| `pnpm typecheck` | Passed. |
| `COMPASS_API_BASE_URL=http://127.0.0.1:8000 pnpm build` | Passed; 95 static pages. Baseline build also passed; implementation rebuilt once after source changes. |
| Focused Node/component tests below | **85/85 passed**, zero failed/skipped. |
| `git diff --check` (repository root) | Passed. |

```sh
node --import ./tests/support/register-tsx.mjs --test \
  tests/form-corr-1-inventory.test.mjs \
  tests/form-corr-1-exit-interview.test.mjs \
  tests/form-ui-1b.test.mjs \
  tests/exit-interview-workflow.test.mjs \
  tests/ux15-graduate-tracer.test.mjs \
  tests/routine-inventory-decoupling.test.mjs \
  tests/routine-encounter-linking.test.mjs \
  tests/ux15-feedback-csm.test.mjs \
  tests/customer-feedback-identity.test.mjs \
  tests/feedback-access.test.mjs
pnpm start --port 3135
```

The production build's generated `next-env.d.ts` route-reference change was restored to the
tracked baseline before commit. No Next configuration, dependency, contract or generated source
change is included. The final browser checks run against the production build, not dev mode.

## Browser regression run

Each engine runs the following files once, sequentially within the engine. Chromium and WebKit
use separate processes/artifact folders. This is the six pilot suites plus the cross-form audit,
not the full frontend browser suite or backend regression suite.

| Suite | Chromium | WebKit |
| --- | --- | --- |
| `ux15-consolidation.browser.mjs` | 61/61: 59 full + 2 focused | 61/61: 59 full + 2 focused |
| `ux15-inventory.browser.mjs` | 10/10 | 10/10 |
| `ux15-exit-interview.browser.mjs` | 15/15 | 15/15 |
| `ux15-graduate-tracer.browser.mjs` | 26/26 | 26/26 |
| `ux15-routine-intake.browser.mjs` | 18/18 | 18/18 |
| `ux15-counselor-evaluation.browser.mjs` | 18/18 | 18/18 |
| `ux15-feedback-csm.browser.mjs` | 18/18 | 18/18 |
| **Distinct final cases** | **166/166** | **166/166** |

Exact invocation for each file, substituting `chromium`/`webkit` and the filename above:

```sh
COMPASS_UI_BASE_URL=http://localhost:3135 \
COMPASS_UI_BROWSER=chromium \
COMPASS_UI_ARTIFACTS=/tmp/ux15-consolidation-final/chromium \
  node tests/ux15-consolidation.browser.mjs
```

The new audit has 56 width/text combinations, two all-section Inventory target checks, one
finalized Evaluation reflow case, and two focused draft/finalized Evaluation checks through its
other existing consumer, the Counseling workspace. Existing pilots check save, validation, correction,
conditional, exact-payload, privacy/eligibility, confirmation, native keyboard, dirty-navigation,
read-only and uncertainty behavior. These are client fixture results, not live-backend claims.

## Reproductions and focused reruns

Baseline production server: `pnpm start --port 3135`, before rebuilding with the corrections.
All commands below also set `COMPASS_UI_BASE_URL=http://localhost:3135` and
`COMPASS_UI_BROWSER=chromium`.

| Run / exact test selection | Result and reason |
| --- | --- |
| Initial `node tests/ux15-consolidation.browser.mjs`, before adding all enlarged widths/strict sheet/target assertions | 35/35 passed. Coarse viewport-edge checks missed internal Evaluation spill. |
| `COMPASS_UI_CHECK='(1440\|768\|390)px 200%' node tests/ux15-consolidation.browser.mjs` | 21/21 passed, adding 200% text at the other three widths. Combined baseline inventory: 56 distinct layout cases. |
| `COMPASS_UI_CHECK='^(exit 390px\|evaluation 320px 200%)' node tests/ux15-consolidation.browser.mjs` | 1/3 passed after strengthening checks: Exit default-text labels 36px and editable Evaluation 267/254px failed; Exit enlarged-text case passed. These are expected reproductions against the baseline. |
| `COMPASS_UI_CHECK='^inventory all choice' node tests/ux15-consolidation.browser.mjs` | First 0/2 run included shell fieldsets and was too broad. Corrected selector scopes to the Inventory editor; second 0/2 reproduces actual smaller Family choices (32/40px). No production fix was based on the unscoped result. |
| `COMPASS_UI_CHECK='^inventory all choice targets 320px'` with before capture enabled | First capture attempt hit duplicate visible-text/option matching; scoped to the actual checkbox. Second run captures baseline then intentionally fails its smaller Family targets (0/1). |
| `COMPASS_UI_CHECK='^finalized' node tests/ux15-consolidation.browser.mjs` | 0/1 baseline reproduction: finalized Evaluation 287/254px, addressed in its existing read-only renderer. |
| After rebuild: `COMPASS_UI_CHECK='^(exit 390px$\|evaluation 320px 200%\|inventory all choice\|finalized)' node tests/ux15-consolidation.browser.mjs` | **5/5 passed**. Directly affected cases only; produces after captures. |
| `COMPASS_UI_CHECK='^intake 320px 200%' node tests/ux15-consolidation.browser.mjs` with after capture enabled | **1/1 passed**; screenshot-only rerun to retain the deferred shell overflow evidence. No production change/rebuild. |
| `COMPASS_UI_CHECK='^Counseling workspace Evaluation' node tests/ux15-consolidation.browser.mjs` in each engine, artifacts `/tmp/ux15-consolidation-embedded/chromium` and `/tmp/ux15-consolidation-embedded/webkit` | **2/2 passed per engine**. Added after source review identified the existing renderer's second entry point. Focused additions only, not a broad rerun. These two distinct cases are included in the final 61/166 counts. |

For capture runs, the additional environment is:

```sh
COMPASS_UI_ARTIFACTS=/tmp/ux15-consolidation-focused \
COMPASS_UX15_CONSOLIDATION_PHASE=after \
COMPASS_UX15_CONSOLIDATION_CAPTURE=/Users/reynantlntno/.codex/worktrees/ux15-forms-consolidation/COMPASS/docs/ux15-consolidation-1/screenshots \
  node tests/ux15-consolidation.browser.mjs
```

Baseline selections use `COMPASS_UX15_CONSOLIDATION_PHASE=before` and distinct `/tmp` artifact
folders. The full paths and exact result/measurement inventory are recorded in the evidence
files [suite-results.json](evidence/suite-results.json) and [audit-metrics.json](evidence/audit-metrics.json).
Repeated/capture checks are **not** added to distinct final scenario
totals. There is no broad rerun loop for unrelated failures.

## CI, safety and limits

Inspected all four `.github/workflows/` files on the fetched integration baseline. The targeted
frontend/backend PR branch filters exclude `integration/ux15-modernization`; backend-full also
uses protected-baseline branches. Staging deployment is `workflow_dispatch` only with current
staging/ref/SHA checks. No CI definition edit or manual dispatch. Local passing tests are not
GitHub-hosted CI approval. Hosted PR checks are reported separately at handoff.

The full frontend/backend suites, manual screen readers, physical devices, browser zoom,
GCO UAT and live-backend concurrency/security testing were not run. At 320px/200% text the
global header still makes the page 417px wide; only the form sheets pass independent reflow.
Routine Intake generic uncertain submission still has advisory refresh copy, not canonical
reconciliation. Feedback's exact-intent retry remains limited to its existing retained-intent
branches. No production-readiness or WCAG conformance claim follows from these results.
