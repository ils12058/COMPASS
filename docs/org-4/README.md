# ORG-4 — Final Organization Catalog assurance

Date: 2026-10-26 (Asia/Manila). Repository: `ils12058/COMPASS`.
Verified fetched base and unchanged runtime candidate:
`d91d64c2893ac834c6b70c1e00f4a823e11478f7`.
Branch: `audit/org-4-final-integration-validation`; PR target: `integration/ux15-modernization`.
Execution: isolated worktree `/Users/reynantlntno/.codex/worktrees/org-4-final-validation/COMPASS`.
No commits followed the supplied baseline at initial fetch. Final validation implementation revision
is recorded in the final evidence handoff; the PR head also includes documentation-only evidence.

The merged Catalog can be exercised through the real authenticated application with synthetic data.
Eighteen Chromium scenarios reached all sixteen operations through Browser → Next.js → Django →
PostgreSQL, including password/TOTP login, CSRF denial, persisted identities/versions/Audit, recent-MFA
re-review after a concurrent change, and lost-response reconciliation without duplicate mutation.
This adds evidence missing from ORG-3's mocked browser selection.

The selected existing backend run passed 1,108 cases. New ORG-4 tests add operational-work races,
history isolation, policy/Inventory races, late MFA rollback and F4/F6 PDF preservation. See
[validation](validation.md) and [machine-readable evidence](evidence.json) for final unique counts.
The final disjoint selections total **1,231 passing backend cases** (1,108 + 17 + 106).
No reproduced application defect required a runtime correction. The changes are tests, an opt-in
disposable integration fixture, CI test selection registration, and this documentation package.

Engineering validation is **PARTIAL**: automated evidence is substantial, but manual accessibility,
physical-device/native-print observation, exhaustive live-response variants, actual environment
compatibility and institutional UAT are absent. Catalog identity integrity and the tested
authorization/MFA contract pass synthetic assurance. This is not an institutional security approval.
Migration/recovery remains PARTIAL; staging is BLOCKED; UAT is NOT EXECUTED; operational activation
is NOT AUTHORIZED. See [independent verdicts](final-assessment.md).

| Evidence | Document |
|---|---|
| Lineage, owners, migrations and sixteen operations | [Integration manifest](integration-manifest.md) |
| Request-to-source/constraint/test mapping | [Requirements traceability](requirements-traceability.md) |
| Independent permissions, sessions, MFA and Audit | [Security](security-and-authorization.md) |
| Identity, versions, PostgreSQL locks and race matrix | [Hierarchy/concurrency](hierarchy-and-concurrency.md) |
| Impact, routing and ongoing work | [Deactivation/work](deactivation-and-operational-work.md) |
| Inventory, F4/F6, receipts and historical outputs | [Academic policy/history](academic-policy-and-history.md) |
| Real login/UI/API/database execution | [Authenticated integration](authenticated-integration.md) |
| Recovery, browser engines and accessibility limits | [Frontend/accessibility](frontend-and-accessibility.md) |
| Additive upgrades, initialization and actual dump/restore | [Migration/recovery](migration-bootstrap-and-recovery.md) |
| Unapproved institutional choices | [Decision register](institutional-decision-register.md) |
| Twenty-two unexecuted institutional scripts | [UAT package](uat-package.md) |
| Documentation-only future cutover | [Staging readiness](staging-release-readiness.md) |

No deployment, SSH, live migration/database access, real-data inspection, institutional user grant,
institutional edit, production reset, operational activation or merge was performed. The original
checkout, staging/main and other worktrees were not edited. Dependencies were reused read-only.
