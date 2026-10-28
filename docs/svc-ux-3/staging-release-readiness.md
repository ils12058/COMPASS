# Staging release readiness

**Readiness: BLOCKED.** This branch is an engineering validation PR targeting `integration/ux15-modernization`; it is not authorization to deploy or activate the workflow.

Before any separately approved staging release:

1. Review the exact PR head and hosted checks after they finish; this handoff does not assert hosted CI success.
2. Resolve or formally accept the remaining automated Feedback/CSM test expectation debt and run the relevant regression suite.
3. Complete real flexible and Group Session browser-to-backend coverage or explicitly accept that evidence gap.
4. Have GCO/product/policy owners resolve the decision register items that affect current terminology, fixed-only Inventory policy, discovery, and notifications.
5. Complete the UAT package with authorized actors; obtain separate release/operator approval.
6. Confirm deployment migration/artifact procedure and a tested rollback path under the actual staging release process.

No staging/production deployment, SSH, live migration, environment change, data reset, or institutional account/Service edit occurred in this task. No live data was accessed.
