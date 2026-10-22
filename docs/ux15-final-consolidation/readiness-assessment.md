# UX15 Readiness Assessment

## Recommendation

**GO — Milestone B: staging-promotion proposal may be prepared for separate review and approval.**

This recommendation applies only after this consolidation PR receives normal review and is merged
to `integration/ux15-modernization`. It means the verified integration branch is suitable to be
considered for the next controlled promotion proposal. It is not approval to merge this PR, approve
a future staging PR, execute a deployment, accept UX15 institutionally, or release to production.

## Evidence supporting the recommendation

- The current integration tree contains all twelve UX15 PRs (#297–#308) at the verified
  `f200e106` head.
- Staging is the exact merge base (`0a843dae`); the fetched topology is 0 commits behind and 18
  ahead, with no independently moved staging files to reconcile.
- The full staging-to-integration diff contains no backend, OpenAPI, generated-client, database,
  migration, authorization-grant, workflow, deployment, or environment-example change.
- API generation, lint, typecheck, ordinary production build, 862 Node/component tests, and the 13
  selected browser suites (295 checks per engine) pass.
- No confirmed product blocker/high-severity defect remains. One synthetic WebKit reload test
  timing issue was fixed and its complete suite now passes in both engines.
- Existing staging deployment remains manual and exact-SHA gated; it was not invoked.

## Conditions before any staging deployment/UAT

1. Review and merge the single consolidation PR to the requested integration branch; do not merge
   automatically.
2. Re-fetch staging and integration immediately before preparing a separate promotion PR. Confirm
   the base and rerun the full local diff inventory if either moved.
3. Use the normal staging-targeted PR workflow or another separately approved hosted validation
   approach if hosted checks are required. Integration-targeted PR workflows currently do not
   trigger for this branch; local results are not hosted CI approval.
4. Obtain separate approval for any staging promotion and deployment. Use the current staging SHA
   and existing manual exact-SHA deployment workflow. This audit itself did not deploy or modify
   staging.
5. After an approved staging deployment, execute the blank role/capability/data-safe UAT matrix,
   including actual browser zoom, screen-reader, physical-device, account/scope revocation, and
   staged backend checks. Record only real observed outcomes.

If staging diverges, if a backend contract/configuration difference appears, or if UAT reveals a
confidentiality, authorization, duplicate-submission, or critical accessibility issue, stop the
promotion path and reassess. These are future verification conditions, not known present defects.

## Four milestones remain separate

| Milestone | State at this audit |
| --- | --- |
| **A — Code integration** | The twelve UX15 slices are on integration. This final audit branch/PR is validated but is not yet merged; Milestone A for the final consolidation completes only after its review and merge. |
| **B — Staging promotion readiness** | **GO to propose** a separate reviewed integration-to-staging step after Milestone A and a fresh ref check. No staging PR was created here. |
| **C — Staging deployment and institutional UAT** | Not started. No deployment, live staging test, or stakeholder acceptance occurred. |
| **D — Production readiness** | Not assessed or approved. Milestone A/B evidence cannot establish production readiness. |

## Explicit limits

No hosted CI run was claimed. The automated browser harness is synthetic and local. Backend source
and existing test coverage were inspected, but no backend test database or live staging service was
used. Manual accessibility checks, UAT, deployment authorization, and production approval remain
separate requirements.
