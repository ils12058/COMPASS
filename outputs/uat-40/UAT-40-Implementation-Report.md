# Staging Dataset v1 — 40 independent UAT participants

2026-10-17, Asia/Manila. Branch `codex/uat-40-participant-expansion`; target `staging`.

## Implementation

| New account | Synthetic identity | Existing role / lifecycle | Verified scenario |
| --- | --- | --- | --- |
| `it_admin_3` | STG-E-0014, Denise Alonzo Villanueva | IT_ADMIN; no designation/override | ITA-PLT-02: independent platform readiness review |
| `ar_25` | STG-S-0125, Felicia Balagtas | STUDENT / GRADUATED | STU-GT-03: complete a Tracer draft |
| `ar_26` | STG-S-0126, Gian Catacutan | STUDENT / GRADUATED | STU-GM-07: request graduate Good Moral |

Totals are **116 accounts: 102 Student-role and 14 staff**, retaining all 65 background Students.
All original 113 identity specifications and 91 scenario definitions are unchanged, checked against
fingerprints from staging `8684ea10e2f8cb43c9b00281ab21999b4211ddcb`. Three executable scenarios
were appended: **94 total, 91 executable and three pending**. No model, migration, dependency,
canonical authorization policy, encryption implementation or credential behavior changed.

The generated Selection Guide lists exact distinct keys for 1 Head, 3 Counselors, 2 GSS, 25 current
Students, five graduated Alumni, 3 ITSO personnel and 1 DPO. ITSO uses IT_ADMIN; Alumni use STUDENT.
Background, restricted and onboarding accounts are excluded from this allocation. The full
Assignment Template retains reserve participants. Actual evaluator assignment, mailbox ownership,
MFA enrollment and selected credential issuance remain separate owner-controlled operations.

## Focused validation

- **43 seeder tests passed**, including fresh seed/verify/report, manifest/identity uniqueness,
  exact 40-person eligibility, protected selected issuance in disposable tests, and an incremental
  113-to-116 seed preserving existing accounts, sessions, routing, encrypted records and completed
  UAT actions. A subsequent seed creates nothing.
- **213 canonical-baseline and encryption tests passed**. Two final focused assertions were
  rechecked successfully after tightening the scenario test.
- Fresh disposable local PostgreSQL: migration, seed, verify, six generated reports, then an
  idempotent seed with **zero new items** and another passing verification. Database removed.
- The exact operator transaction was rehearsed locally against the original 113-account
  population: preservation checks across **94 models**, 116-account verification and six reports
  passed. An initial rehearsal correctly refused DEBUG=true under simulated live settings;
  the successful rehearsal used DEBUG=false, matching the verified live environment.
- Ruff lint/format, whitespace checks and backend CI bundle consistency passed. No migration or
  non-seeder application-source difference exists relative to the running canonical baseline.

## Authorized additive live execution

The owner separately authorized additive live seeding before deployment, plus temporary access
from the operator's exact public IPv4 /32. The expansion PR must remain **open and unmerged**.

Running image: canonical baseline `d86ddc08285f16740848dc5880d9d2285e7dbce8`, image ID
`sha256:5042141ab5d8084208c3cc20f31b8dc999d275c71bee564a84605c14b08bb9f7`.
Updated seeder source: local commit `7f8e0c7fc5a41a1ebeaa9194e2b29f53ac6466c3`, mounted read-only
into a temporary `--rm --no-deps --pull never` container using that existing image. Running
application source and release selectors were not replaced.

Before writes, verified **479 baseline source/dependency files**, original manifest fingerprints,
the existing 113-account dataset (zero warnings), destination identity, healthy runtime, original
storage and runtime-secret metadata. The host deployment lock prevented overlap. Preliminary
operator probes stopped before seeding on HTTP-client filtering and container file permissions;
the corrected compatibility probe passed before the write container started.

One outer database transaction added **three accounts, two historical Inventories, two submitted
Exit Interviews and two Tracer responses**. Before commit it compared all prior model rows,
including credentials, sessions, encrypted content, routing and audit rows, and the complete
migration history. The only comparison exception was Academic Year `updated_at` bookkeeping
during temporary historical-year selection; year identities and final current-year selection
were preserved. New audit events were appended normally. Email/push intent sets were unchanged;
provider/SMTP/HTTP/task dispatch was blocked in the one-off process, with notification kicks
suppressed and realtime publishing disabled only for that process.

Committed result: **116 accounts, 102 Students, 14 staff; verification passed with zero warnings**.
All three new scenarios were READY. All **113 original account identities** remained unchanged.
**Zero participant credentials were issued**; all 116 accounts still have unusable passwords.
No reset, data deletion, migration, application restart, image pull, deployment or manual CI rerun
was performed. Existing PostgreSQL/Redis/Caddy volume identities, canonical network, application
container IDs/start times, secret/environment/selector metadata remained unchanged. Temporary SSH
rules were removed after each access; the original firewall rule was retained.

Six live-generated, secret-free UAT documents are retained under
`/opt/compass/operator/uat40-7f8e0c7fc5a41a1ebeaa9194e2b29f53ac6466c3-r2/reports`.
The report directory is protected with mode 0700. Repository examples under
`outputs/canon-1c/uat` are regenerated documents, never credential handoffs or evaluator assignments.
All six repository copies were downloaded from that live report run and checked against their
remote SHA-256 digests. Post-seed inspection independently confirmed the original 113 account
identity digest, zero usable passwords, one responsive worker and all four Beat jobs. Public
API and realtime readiness returned HTTP 200. The exact merged deployment database guard also
passed read-only against the expanded live dataset, with no pending forward migrations.

## Deployment handoff

Keep `staging` at **8684ea10e2f8cb43c9b00281ab21999b4211ddcb** for the already-approved normal
deployment. No deployment was dispatched by this operation. Leave this PR unmerged until that
deployment completes successfully; deploy/merge authorization is not inferred from the seed run.
The later merge installs the same updated seeder code; do not reseed or reissue credentials as a
normal deployment step.

**Observed deployment prerequisite:** from the Droplet, the default Python HTTP client received
HTTP 403 for public `/api/v1/meta`, including with the deployment's `Cache-Control: no-cache`
header. Curl and a named operator User-Agent received HTTP 200 with the correct baseline build.
`deploy.sh` at the approved staging SHA uses the default Python client for its post-rollout public
identity check; it can therefore fail after crossing the migration boundary. Resolve that HTTP
client/edge access discrepancy before dispatching the normal deployment. No edge policy,
workflow or infrastructure change was made to work around it in this seeder operation.
