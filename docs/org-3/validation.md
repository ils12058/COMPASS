# ORG-3 validation

Baseline: fetched `origin/integration/ux15-modernization` =
`f9e6fb4a99ed3bdc72f7b594752a141d6ac48edd`.
Worktree: `/Users/reynantlntno/.codex/worktrees/org-3-catalog-management-ux/COMPASS`.
Branch: `feature/org-3-catalog-management-ux`. Date: 2026-10-26 (Asia/Manila).
Original checkout and ORG-0/1/2 worktrees were not modified.

## Environment and commands

Node v26.7.0, pnpm 11.19.0, Next 16.3.4, React 19.2.8, Orval 8.29.0, TypeScript 5.9.3,
Playwright 1.62.1 on local macOS. Locked offline install reused 727 packages, zero downloads.
No dependency or lockfile changed. Existing installed Chromium/WebKit runtimes were used.
Tests use synthetic data and mocked same-origin API routes; outbound services and service workers
are blocked by the shared harness. No real account, authenticator, Catalog grant or dataset was used.

Executed from `<worktree>/fe`:

```sh
CI=true pnpm install --frozen-lockfile --offline
pnpm api:generate
pnpm lint
pnpm typecheck
pnpm build
pnpm test
node --import ./tests/support/register-tsx.mjs --test tests/organization-catalog.test.mjs tests/profile-structure-composition.test.mjs tests/step-up.test.mjs
pnpm start --port 3163
```

From `<worktree>` against that local production server:

```sh
COMPASS_UI_BASE_URL=http://localhost:3163 COMPASS_UI_ARTIFACTS=/private/tmp/compass-org3-chromium-verified node fe/tests/organization-catalog.browser.mjs
COMPASS_UI_BASE_URL=http://localhost:3163 COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/private/tmp/compass-org3-webkit-verified node fe/tests/organization-catalog.browser.mjs
```

OpenAPI check only, from `<worktree>/be`, with no database migration or backend suite:

```sh
env -i PATH='/opt/homebrew/bin:/usr/bin:/bin' DJANGO_SETTINGS_MODULE=tests.settings /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python manage.py export_openapi --check --settings=tests.settings
```

The contract is current. `be/**`, `contracts/openapi.json`, deployment/migration allowlists,
workflow definitions, generated clients and baseline migrations are unchanged. Generated files are
ignored and never hand-edited. Next automatically rewrote next-env.d.ts imports while building;
its original tracked contents were restored before final typecheck/commit.

## Results and distinct counting

| Check | Observed result |
|---|---|
| Orval generation | Passed against canonical checked-in OpenAPI |
| ESLint / TypeScript / production build | Passed |
| Full Node selection | 1,016 passed; zero failed/skipped/cancelled |
| Final affected Node selection | 66 passed; zero failed/skipped/cancelled |
| Distinct Node cases | **1,021** (1,016 + 66 − 61 overlapping cases) |
| Chromium Catalog scenarios | **53 passed**, zero failures |
| WebKit Catalog scenarios | **53 passed**, zero failures |
| OpenAPI check | Current, exit 0 |
| Documentation/scope/diff checks | Nine documents, existing relative links, balanced fences; git diff --check |

The full Node selection preceded the last query/recovery refinements and five additional cases.
Final affected selection supersedes its overlapping results: 57 Catalog cases, four existing
Profile/Structure composition cases and five shared step-up cases. The other 955 full-selection
cases are unchanged. Earlier development/refinement reruns are not added to the distinct total.
No claim is made that a complete 1,021-case suite was run in one final-source invocation.

The final browser scripts exercise actual application components in the production build, with
synthetic ORG-2 request/response shapes. The full fifty-three-scenario selection passed per engine. After the final header-only layout
change, the four affected desktop-entry/narrow-phone/200%-text/tablet scenarios were rerun in each
engine with `COMPASS_UI_CHECK='01 |35 |36 |49 '`; these supersede the overlapping results and do not
add to the distinct scenario count. The same fifty-three logical scenarios across two engines are **53 Chromium and 53
WebKit scenarios**, not 106 different business cases. Suites are discovered by existing CI browser
registration and sharded once per engine. No new workflow or test bypass was added.

Coverage includes Catalog-only, relationship-only and read-only entry; Student denial; independent
relationship route guards; all entity creation/rename/status/impact/history operations; Program
policy and noncontiguous levels; normalized duplicates; inactive/missing parents; no-ops; blockers,
warnings and preserved counts; activation and pending F4 refusal; paging; stale versions/previews;
MFA setup/verify without replay; interrupted committed rename/creation and unconfirmed writes;
saved-but-refresh-failed; revoked capability; actor/session transitions; dirty discard; keyboard,
focus containment/return, narrow phone, tablet and 200% text scaling; existing Responsibilities
(including Staff Supervision surface) and Student affiliations routes. A commit-between-detail-and-
history scenario verifies a second detail read before committed-state feedback.

All sixteen generated operations are exercised: creation/name/status/impact/history for Campus,
College and Program, plus complete Program policy update. Other existing Organization list/detail
operations remain. No Accounts/global Audit read enriches history, and Catalog-only impact exposes
no unauthorized remediation links.

## Evidence files and corrections

Local logs: `/private/tmp/compass-org3-{orval,node-final,node-layout,lint-layout,typecheck-restored,build-layout}.log`.
Final browser JSON/screenshots are under the two `*-verified/organization-catalog/` directories in
the commands above, with the final header-layout refinements in corresponding `*-layout/organization-catalog/` directories. These are machine-local evidence, not repository artifacts or live-state proof.
The task-owned production server is stopped after validation.

Development corrections:

- Initial Node run: three failures from old fixtures/assumptions. The composition provider lacked
  the now-used session UUID; the old read-only assertion prohibited even browse controls; an old
  command-palette assertion excluded authorized staff reference browsing. Fixtures/assertions were
  updated for the explicit ORG-3 contract. Existing operational authority remains independent.
- An initial Chromium focus check toggled an already-open Actions disclosure closed; the helper
  now opens it only when needed. Later assertions awaited dialog disappearance but ran before focus
  restoration's animation frame. They now wait for the focus invariant. Both engines pass actual
  containment/Escape/return checks; no timeout or assertion was weakened.
- Screenshot review found the page title/actions were cramped at 200% text size beside the expanded
  dock even though no horizontal overflow occurred. A Structure-local container query now stacks
  the header by available width; the browser assertion also checks heading wrapping and reaches
  the confirmation control at enlarged text size.
- Review improved duplicate-code field association, failure-safe cached reference presentation,
  fallback heading focus, timeout uncertainty, and accurate latest-record feedback. A second read
  after matching history closes the commit-between-reads race. Focused tests and final browser
  selection exercise the refinements.

Incidental shell path errors while authoring were corrected before affected files were written;
they are not passing application checks. No known selected failure remains.

## Hosted CI and limits

The integration target is not selected by the existing staging/canonical-targeted PR workflows.
Hosted checks/runs are inspected at the final PR head and reported in the PR/handoff. An absent
check is not CI-green; no workflow is dispatched. Local browser runs are mocked API evidence,
not real authenticated Django/PostgreSQL integration or real institutional UAT.

No backend regression suite, real certificate PDF rendering, populated migration rehearsal,
concurrency race suite, actual authenticator setup, screen-reader session, native browser-menu
zoom, physical-device QA, deployed-state inspection, old-writer inventory, production backup/recovery
or institutional policy approval was run in ORG-3. Those remain ORG-4/separate operational gates.
Existing ORG-1/2 evidence is historical context and is not added to these counts.

No merge, deployment, SSH, live migration, real-data inspection, actual Catalog grant,
institutional edit or academic-policy activation occurred. The source PR is the delivery boundary.
