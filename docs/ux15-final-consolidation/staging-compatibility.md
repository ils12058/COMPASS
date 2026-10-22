# Staging Compatibility and Integration Readiness

## Ref comparison

| Ref | SHA |
| --- | --- |
| Integration | `f200e106d46474508c9efb69826e2e1948949d90` |
| Staging | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |
| Main | `1a9933535a0b8c0cbd7764c35f301e8402f48375` |
| Staging/integration merge base | `0a843dae20c01984d0fb9aa46d5eef34102ab386` |
| Staging ahead/behind integration | `0 / 18` |

The refs were fetched immediately before audit. Staging has not diverged from the merge base used
by the integration branch. No reconciliation merge or conflict resolution is required by the
current local topology. Re-fetch and compare again before any later promotion proposal.

## Complete change classification

The full local diff from `origin/staging...origin/integration/ux15-modernization` was reviewed,
not a capped GitHub file listing.

| Category | Finding |
| --- | --- |
| Frontend production source | 39 changed source files across shared form UI, the seven form experiences, Portal Shell controls, and three role Homes. No new API client or state engine. |
| Frontend config/package | `fe/package.json` changes one browser test command. No dependency or lockfile change. |
| Frontend tests | 24 test/support paths, including all UX15 form/Home regressions, Portal Shell, access/helper, and cross-role coverage. |
| API/OpenAPI/generated client | No `contracts/openapi.json` change. Generated API output is unchanged/uncommitted; Orval generation passed. |
| Backend service | No backend source changes. |
| Database/migrations | No migration, model, or schema change. |
| Authorization/configuration | No new capability, role, environment variable, feature flag, credential, or grant. Existing access helpers and backend contracts are reused. |
| CI/deployment | No workflow, deployment, container, provisioning, or environment-example change. |
| Documentation/evidence | 57 Markdown records, 26 JSON results/geometry files, and 238 screenshot/visual evidence files from the merged slices. |

The final consolidation PR adds 13 Markdown files in this package and updates one synthetic
browser test. It has no production/backend/API/configuration change.

## API/backend compatibility

UX15 consumes the existing generated client and canonical endpoints for Student Actions, Work
Queue, self and managed Appointments, Guidance Operations, announcements, and the existing form
workflows. The OpenAPI contract at staging and integration is identical. `pnpm api:generate`,
`pnpm typecheck`, and the Next production build pass; no missing generated import, route, enum,
schema, or operation was found.

No UX15 backend response or permission is assumed merely from UI copy. Backend source and the
existing endpoint/service tests were inspected for Appointment scope, Guidance Operations, Routine
Interview privacy/finalization, and Feedback/CSM idempotency. The frontend Home does not aggregate a
second work list, bypass resource routes, or broaden server authorization.

## Configuration, flags, and deployment

- No new deployment-order requirement, database migration, backend configuration, frontend
  environment variable, provider, service, or provisioning step is introduced.
- No new feature flag is required for UX15. `NEXT_PUBLIC_COMPASS_UI_TEST_MODE=1` is the existing
  local-only browser-test seam; it was used only for the isolated synthetic test build. The
  ordinary production build was separately built with the flag unset.
- Existing production `COMPASS_API_BASE_URL`/same-origin routing and session/CSRF behavior remain
  unchanged.
- `.github/workflows/deploy-staging.yml` remains unchanged and is manually dispatched from the
  current `staging` revision with an exact expected staging SHA. It was not dispatched.
- No staging host, production host, secret, credential, or real record was accessed.

## Hosted CI and branch requirements

Current workflow filters in `.github/workflows/frontend-targeted.yml` target PRs to `staging` and
`canon/compass-clean-baseline`; `integration/ux15-modernization` is excluded. Backend targeted/full
workflows likewise do not validate this frontend-only integration-targeted PR. GitHub's branch
protection endpoint returned “Branch not protected” for the integration branch on 2026-10-22;
there was no configured required-status-check list to report. The latest prior PR query also
reported no hosted checks on its feature branch.

Therefore the passing results in [validation](validation.md) are **local checks**, not hosted CI
approval. No workflow filter was altered and no workflow was manually dispatched. If hosted CI is
required before staging promotion, obtain approval for a separate validation approach. A future
staging-targeted promotion PR is the normal path through the configured PR workflows; branch
protection or required checks should be rechecked at that time.

## Safe future reconciliation

The current lineage is clean: integration is 18 commits ahead of the exact staging merge base and
0 commits behind it. After review/merge of the consolidation PR, re-fetch staging and integration,
reconfirm ancestry and rerun the complete diff inventory before proposing a separate
integration-to-staging PR. If staging moves independently, identify overlapping commits/files and
resolve through a separately reviewed merge/reconciliation proposal. Do not merge either direction
automatically, force-push, retarget this consolidation PR, or dispatch deployment from this audit.
