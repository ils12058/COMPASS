# CANON-1 seeder validation — blocked current baseline

Inspected base `d353108d1f757386b9020c4d1297e081258d2e4e` on 2026-10-16 (Asia/Manila).
The current seeder is not validated for a canonical reset. No live seed command was executed.

## Source population and safety

Existing Dataset v2 documents 57 Students: 11 rich personas and 46 population Students, plus
separate staff accounts. These are source definitions, not a successfully observed final seeded
account inventory. Expansion to 85–100 Students remains a proposal requiring owner approval.
The existing seed_demo_staging command must remain the sole seeder; no parallel seeder is added.

The code retains explicit environment allowlisting, live-staging opt-in, configured secure demo
password handling, synthetic identities/domains/narratives, concurrent-run exclusion and
idempotency guards. `demo-seed-v1` remains an intentional additive-upgrade namespace. Removal of
old-upgrade behavior belongs on the reset branch, after a successful current-contract seed.
No password/key was printed or rotated. No actual provider media or email delivery was created.

## Confirmed blocker

Full-regression CI at `8cff975e` fails in SCENARIO_ALUMNI with
`InvalidGraduateTracerInput: graduated_college is required before submission`.
The shared `_tracer_values` helper in be/compass/demo_seed/scenarios.py copies private contact
snapshots, birth date and answer fields but does not supply the canonical academic classification.
Its consumers include alumni, recent-graduate and population Graduate Tracer scenarios.
The domain submission service requires graduated college, program and a completed graduation year,
with the program belonging to the college. Weakening those rules is not a valid seeder fix.

This is a production seeder input regression. Supply deterministic, coherent canonical academic
identities and years through the existing scenarios, then rerun complete seed/rerun/safety tests.
Do not substitute arbitrary unrelated classification values merely to satisfy non-null checks.

Separate seed-preflight failures assert absolute audit-event emptiness despite the autouse
institutional-form synchronization audit. Preserve the no-new-write guarantee relative to the
initial audit baseline, and keep assertions that secrets are not read before environment refusal.
Downstream composition tests cannot establish feature coverage while their class seed setup fails.

## Evidence still required

After fixing the current blocker: fresh empty-database initialization with all four configuration
sync commands; actual account/record counts; scenario integrity and role-scope checks; encrypted
storage checks; idempotent rerun and concurrent-run exclusion; synthetic email/provider isolation;
assisted Good Moral plus durable email intent/printing/corrections/Activity/DPO coverage; and the
later consolidated-schema seed rehearsal. None are marked complete by this report.
