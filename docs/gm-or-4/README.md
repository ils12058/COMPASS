# GM-OR-4 — Final integrated validation

Date: 2026-10-24, Asia/Manila. Verified/fetched integration baseline: `8872db0a7325239ccab6d6f0ca3f68ffd312de8c`; no intervening commits. Isolated branch: `audit/gm-or-4-final-validation`. See [validation](validation.md) and the [distinct-case evidence](evidence/case-inventory.json) for the tested candidate, commands and results. Final PR HEAD may add documentation only; it is identified in the PR handoff rather than a self-referential commit hash.

This slice adds authenticated integration, failure-atomicity, concurrency, historical PDF and actual backup/restore tests, Good Moral CI selection registration, and this evidence package. Runtime implementation, migrations, approved-fee provider, grants, OpenAPI, generated-client ownership and printing are unchanged. Earlier GM-OR passing counts are historical context; all counts in this package come from new GM-OR-4 executions.

Engineering validation is **PARTIAL** against the entire requested assurance envelope. The executed synthetic checks pass; the 25-item coordination inventory includes explicitly limited cases, actual integration runs only in Chromium, and human/physical procedures are unexecuted. Receipt integrity is **PASS for the tested ordinary-writer, observed-identifier boundary**. Security assurance and migration/recovery readiness remain **PARTIAL**. Staging deployment is **BLOCKED**, institutional UAT is **NOT EXECUTED**, and operational activation is **NOT AUTHORIZED**. No unresolved reproduced application defect was found in these checks. See [independent verdicts and residual risks](final-assessment.md).

Operational defaults remain DORMANT, approved fee unavailable and no baseline inspector grant. Synthetic PHP 80 decisions and personal-inspection attestations are fictional test evidence, never actual physical inspections, fee approvals or Cashier reconciliation. The recovery rehearsal demonstrates that a restored ACTIVE snapshot can omit later committed receipt claims; it does not supply an approved production recovery procedure.

## Evidence package

- [Integration manifest](integration-manifest.md) and [requirements](requirements-traceability.md)
- [Security](security-and-authorization.md), [identity/concurrency](identity-and-concurrency.md), [fee/inspection policy](fee-and-verification-policy.md)
- [Authenticated integration](authenticated-integration.md), [migration/recovery](migration-and-recovery.md), [frontend/accessibility](frontend-and-accessibility.md)
- [Institutional decisions](institutional-decision-register.md), [future UAT](uat-package.md), [future staging order](staging-release-readiness.md)
- [Validation record](validation.md), [final assessment](final-assessment.md), [case inventory](evidence/case-inventory.json)

No merge, deployment, SSH, deployed-data access, live inventory/import/migration, production reset, real grants or policy activation was performed. Original checkout, staging/main and other agents' worktrees were not edited.
