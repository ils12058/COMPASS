# FAC-5 verified baseline and change boundaries

Starting integration SHA: `d9971e892bd432d766567084dba2492746953306`, fetched
on 2026-11-01. Branch: `codex/fac-5-integration-assurance`; target is integration.
FAC-1 #348 (`1778359f`), FAC-2 #349 (`1a8f9aa3`), FAC-3 #350 (`e10671e2`) and
FAC-4 #351 (`d9971e89`) are merged. The FAC-4 implementation head `2aed08ac` and its
integration squash have identical trees. No staging/main, deployment or activation
change is authorized by this slice.

Reviewed FAC-1 identity/provisioning/contracts, FAC-2 intake/encryption/placement/
policy/idempotency/migrations, FAC-3 portal/cache/recovery/validation/handoff, FAC-4
administration/disclosure/notification/void/locking/migrations and release handoff;
current canonical manifest, CI workflows/planners, frontend AGENTS/UX15/SIMPLIFY
rules and the owning code/tests. Referral ADRs 027/081/113 and Notification ADRs
041/046 remain authoritative within their current later contract boundaries.
Historical documents describe their original slice; current code and FAC-4 own the
three-state model and two-capability Faculty ceiling.

## Hosted comparison and local reproduction

FAC-4 baseline: backend run 41252323738 and frontend run 41252325881, exact head
`2aed08ac`. All four backend failures also occur in FAC-3 run 41249274723. Browser
failures match FAC-3 run 41249277319. Baseline static/build/unit checks passed.
Some hosted browser jobs were cancelled; cancellation cause is not established.
The workflow already has `fail-fast: false`: the prior FAC-4 PR's attribution to
matrix fail-fast was incorrect. No complete hosted baseline pass is inferred.

The four backend cases were reproduced unchanged locally: four failures in 26.95s.
The privacy request's eight queries were profiled: maintenance configuration,
authenticated session plus User, three effective-capability sources, a separate
lazy Role read, notice page and bounded open-revision prefetch. Joining User.Role
in the existing session lookup removes the redundant read while retaining every
authorization source and the unchanged seven-query budget. No row/query values or
session credentials are committed as profiling evidence.

Correct synthetic browser build reproduced the current owning failures in Chromium:
E-Counseling Call 39/40, information hierarchy 17/18, UX-P2A 1/6 and user copy 40/44.
An initial local call run used a normal build without the fake-provider seam; those
results are excluded. The corrected build matches CI's loopback-only UI test mode.
CSM in the failing code is **Client Satisfaction Measurement**, not a separate
Counselor Shared Message feature; no messaging workflow is changed.

## Bounded implementation decisions

- Eager-load authenticated User.Role; retain actual session, capability and policy checks.
- Lock only the Counseling Encounter in synthetic summary regeneration's joined query;
  preserve dataset exclusion, approval checks, ciphertext and publication transaction.
- Recognize only the typed, single Case Coverage grant revocation in the source inventory;
  assert its canonical model binding and reject any extra/unknown writer. AuthSession
  revocation still has its one socket-close-after-commit primitive.
- Replace destructive postbaseline reversal with an owned disposable PostgreSQL forward
  upgrade, original-column/ciphertext comparison, failed-transaction rollback and idempotent
  forward recovery. No historical migration or irreversible guard is edited.
- Keep call identity/status information but group it compactly, bringing the narrow call
  stage above the existing half-screen assertion without hiding controls or changing consent.
- Align obsolete tests with the accepted 44px labeled control contract, accessible icon Help,
  current Save Progress label and canonical uncertain Feedback/CSM status recovery. Preserve
  resource links, keyboard/focus, read-only/no-mutation and no-automatic-retry assertions.
- Expand Faculty/GCO checks to all requested widths and 200% text. Fix genuine newly exposed
  Referral action-rail and long status wrapping with available-width/container sizing.
- Add integrated actual-session/CSRF cross-College lifecycle and direct confidential/API
  boundary tests. Positive policy evidence stays in isolated synthetic fixtures.

No migration, Faculty capability, production policy provider, live Notification producer,
Student academic writer, signature/attestation rule or external delivery is added.
