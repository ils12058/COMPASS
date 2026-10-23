# Future staging sequence — BLOCKED, no deployment performed

Repository-owned workflows, deployment planner, local/staging Compose, settings, runtime inventory and CONT-1B/3 runbooks were inspected. No SSH, Droplet connection, DigitalOcean secret/API access, remote database probe, deployed data classification or live source-file check occurred. The current staging filesystem/mount state is unknown. A repository contract check does not establish the actual environment satisfies it.

| Order | Separately authorized operator action / required evidence | Stop condition |
| --- | --- | --- |
| 1 | Verify reviewed PR/candidate SHA, upstream integration drift, backend image digest/build identity, frontend revision and required hosted checks | Wrong/unreviewed SHA, unresolved security failure or missing release authorization |
| 2 | Record approved scope, institutional decision references, deployment authorization, operators/window and rollback owner | D01–D18 unresolved for proposed active sharing; deployment authorization absent |
| 3 | Classify exact existing staging Summary/related delivery scope and other retained records without assuming the environment disposable | Unknown/retained data cannot use synthetic disposal route |
| 4 | Back up and restore-rehearse consistent schema/data/identity policy, old/new keys, images/frontend, consumer versions, manifests and queue/delivery state | No protected recovery proof/keys or unresolved processing claims |
| 5 | Select/rehearse guarded CONT-1B cutover: approved exact disposable scope plus known-fixture regeneration, or separately verified retained conversion | Remaining legacy rows, changed scope/digest, unsupported converter, missing explicit scoped approval |
| 6 | Prepare independent canonical Summary/Routine and web-only Handoff key custody/recovery through authorized secret process | Missing key, reuse, unverified escrow or no custody authority |
| 7 | Verify runtime inventory, exact pointer/owner/mode, source regular-file status and mounts; new Handoff source file must exist even for optional empty ring | Missing declared source/mount or direct/file conflict; no fallback |
| 8 | Enter approved maintenance; fence old web/browser traffic, producers, workers, Beat and realtime consumers; drain/reconcile affected deliveries without blanket broker purge | Mixed old/new consumers, unfenced deliveries or lost unrelated work |
| 9 | Verify immutable baseline/registered additive graph; run approved cutover before guarded Summary migration; apply canonical migration order through Counseling 0004 | Pre-canonical history, hash mismatch, retained legacy rows or migration failure |
| 10 | Run normal identity-policy synchronization after capability migration; separately govern exact no-default continuity/Handoff capability assignments | Legacy capability collision, unsupported actor/delegation or broad default grant |
| 11 | Release exact compatible backend image with validated secret mounts and startup/system checks while traffic remains fenced | Missing required ring/schema or build mismatch |
| 12 | Release matching generated-contract frontend; ensure existing clients refresh and stale sessions/queries revalidate | Old endpoints/bindings/client state or incompatible frontend |
| 13 | Verify genuine operational/disclosure/workflow providers against approved evidence and transactionally visible publication/invalidation fence | **Currently BLOCKED: providers all None; none is authorized by CONT-4** |
| 14 | Under separately authorized synthetic accounts, smoke unsupported roles, self-approval, exact Student/scope, missing policies/rings, no-store, source revisions, expiry/revoke and Student Summary separation | Unexpected disclosure or unresolved 401/403/404/409/503 behavior |
| 15 | Smoke approved field-only Evaluation/no Intake, exact submitted Handoff, safe Audit commit/failure and no accidental notification/delivery; verify worker/Beat remain without Handoff custody | Unapproved field/audience, absent Audit or unwanted delivery |
| 16 | Complete institutional UAT/retention/monitoring and explicitly authorize traffic/activation; otherwise retain reviewed forward-denied state | UAT not passed, missing sign-off, role/contention/mount/backup evidence absent |

The above is preparation only. A future inert deployment, if separately approved, must explicitly preserve default denial and still satisfy schema/secret/cutover compatibility. It cannot be labeled confidential-sharing activation.

## Exact secret metadata preflight

Future authorized host command, never executed here:

```sh
python3 be/deploy/runtime-secrets/check-runtime-secrets.py \
  --secrets-dir /opt/compass/secrets --env-file /opt/compass/.env --owner compass
```

Run the repository-owned script from the approved checkout/path layout. It checks known names/pointers and file metadata without reading secret contents. The repository requires a 0700 owner-controlled directory and 0444 owner-matched regular source files, no symlinks. Required rings must be nonempty; optional Handoff may be empty but not missing. Confirm `/run/secrets/counselor_handoff_summary_encryption_keys` is web-only, with worker/Beat direct and `_FILE` settings empty. Parser/separation and actual container readiness need protected operator checks; do not print values or assume Compose rendering verifies existence on the Droplet.

## Failure and consistent rollback

Before mutation, abort and keep the existing consistent version. After Summary contract/ciphertext/capability cutover, old code is incompatible: keep maintenance and reconcile/resume or restore the reviewed complete recovery unit. Do not switch just the image/frontend or discard new Audit evidence.

After Handoff documents exist, reversing 0004 destroys retained ciphertext and is unsafe. Prefer separately reviewed forward denial/revocation/provider withdrawal with policy-fenced publication, preserved records/keys/Audit and content-free monitoring. If restoration is necessary, stop all affected consumers and restore compatible schema/data, identity policy, backend/frontend, protected keys/mounts and notification/delivery state from a verified point. Reconcile events after the snapshot without deleting historical Audit to force consistency. Actual restore/live cutover requires separate authorization.

Remaining blockers: real provider implementation/verification, D01–D18, exact staging data classification and Summary cutover decision, independent custody/recovery, required Handoff source file, actual runtime roles/mounts, compatible consumer/image/frontend rollout, production contention/monitoring and institutional UAT. Staging deployment readiness **BLOCKED**; confidential sharing **NOT AUTHORIZED**.
