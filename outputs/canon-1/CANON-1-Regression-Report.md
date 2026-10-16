# CANON-1A regression evidence

This is an in-progress infrastructure slice, not a completed CANON-1 regression cycle.
Base: d353108d1f757386b9020c4d1297e081258d2e4e. Date: 2026-10-16 (Asia/Manila).

Passing local evidence: 40 CI self-tests, backend 167-file/six-shard coverage verification,
Ruff formatting/lint, compileall, locked dependencies, fresh current-history migrations,
migration drift, Django checks, OpenAPI check, Orval generation, frontend lint/typecheck/build,
and three browser-runner unit tests. Small command outputs are retained under evidence/.

The pre-change frontend unit suite reports 763/764 passing with one failed raw API-message
boundary assertion in assisted Good Moral. It remains a visible application defect.
Full local backend and Chromium/WebKit suite runs are underway. Their results and root-cause
classifications will be appended after completion. There is no passing canonical schema, seeder,
reset rehearsal or representative end-to-end UAT claim.

Local raw working evidence is in /tmp/compass-canon-1a-evidence. Final structured failure summaries
and PR workflow links will be retained here; temporary files are not a release artifact.
