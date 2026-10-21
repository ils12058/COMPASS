# Proposal #15 integration and deployment safety

Inspected the latest fetched `origin/staging` source before creating or pushing the integration
branch or applying the implementation. Baseline SHA: `0a843dae20c01984d0fb9aa46d5eef34102ab386`.
Both requested branch names were absent locally and on the remote.

| Workflow | Events at the inspected baseline | Effect of the UX15 branches and PR |
| --- | --- | --- |
| `.github/workflows/deploy-staging.yml` | `workflow_dispatch` only. The job checks that the workflow ref is `refs/heads/staging` and that the dispatched workflow SHA and explicit expected SHA equal current remote staging HEAD. | Neither branch pushes nor the PR can trigger this deployment workflow. No dispatch is performed. |
| `.github/workflows/frontend-targeted.yml` | PRs targeting `staging` or `canon/compass-clean-baseline`, with frontend/contract/workflow path filters; also manual dispatch. Jobs build and test only. | A PR targeting the UX15 integration branch does not run this workflow automatically. Focused local validation is recorded instead; no manual dispatch. |
| `.github/workflows/backend-targeted.yml` | PRs targeting the same two branches, with backend/contract/CI path filters; also manual dispatch. | The integration PR is excluded. No backend or contract changes and no dispatch. |
| `.github/workflows/backend-full.yml` | Pushes to `staging` or `canon/compass-clean-baseline`; PRs targeting those branches when full-regression machinery changes; also manual dispatch. | The new branch pushes and integration PR do not match. No dispatch. |

The four files above are the complete workflow inventory at the inspected revision. There is
no push/PR/workflow-run deployment chain for these new branches in that inventory. The frontend
workflow only starts localhost services for tests and uploads test build/evidence artifacts.
`fe/vercel.json` declares a build command, not a GitHub Actions deployment trigger; it is unchanged.
The default `main` branch was also fetched and checked at
`1a9933535a0b8c0cbd7764c35f301e8402f48375`: it has the same four workflow files, manual-only
deployment, validation scoped to staging, and no `create`, `workflow_run` or
`repository_dispatch` deployment trigger. This audit is of repository-controlled workflows,
not a claim about uninspected hosting-account webhooks or settings.

## Branch ownership

- `integration/ux15-modernization` is created at the exact latest fetched staging HEAD and pushed
  without rewriting an existing branch. It contains no pilot changes until a team-approved merge.
- `feat/ux15-form-foundation` is created in a new isolated worktree from that integration branch.
  The existing pilot commit is reapplied there; frontend behavior is revalidated locally.
- The new PR targets `integration/ux15-modernization` and is ready for review. The earlier draft
  PR #296 targeting staging is superseded and closed without merging.
- Future Proposal #15 slices use the integration branch as both their source and PR target.
  Preserve existing integration commits; never reset or recreate the branch to refresh it.
- No workflow files, backend contracts, institutional form requirements or deployment settings
  change. No merge to staging/main, deployment, or deployment dispatch is part of this work.

Proposal #15 remains experimental until formal team acceptance. A review-ready PR does not
constitute acceptance, rollout authorization or permission to merge automatically.
