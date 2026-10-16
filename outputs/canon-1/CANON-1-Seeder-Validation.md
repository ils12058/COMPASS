# CANON-1 current-contract seeder repair

Base d353108d1f757386b9020c4d1297e081258d2e4e, repaired 2026-10-16 (Asia/Manila).
No live seed command was executed. This validates the existing migration/schema path; canonical
replacement migrations and reset rehearsal remain separate work.

## Population and safety

Existing Dataset v2 defines 57 Students (11 rich personas, 46 population Students), plus staff.
The existing seed_demo_staging command remains the only seeder. No population expansion or new
seeder was introduced. Environment allowlisting, live-staging opt-in, operator-controlled demo
password/domain, advisory exclusion, idempotency, encrypted storage and synthetic isolation remain.
The additive demo-seed-v1 upgrade namespace is retained until reviewed reset-only cleanup.

## Repaired causes

The former SCENARIO_ALUMNI failure omitted required Graduate Tracer academic classification.
The shared scenario helper now resolves the persona's actual canonical program and owning college,
and every caller supplies its story's completed graduation year (alumni 2025, recent/cohort 2026).
The strict domain validation is unchanged. Composition checks verify these relationships and years.

After that blocker was removed, an EARLY population Exit Interview draft exposed a KeyError:
its intentionally partial narrative omits college ratings. The helper now filters an empty list
for that draft; complete submissions still require the saved F9 contract's actual supported items.
No form identity, revision, service validation or schema was changed.

Full rerun testing also exposed an obsolete Customer Feedback name lookup after optional identity
stopped prefilling. It attempted duplicate submission and undercounted anonymous responses. The
helper now bounds lookup to the synthetic account's submission audit provenance, course/year and
existing confidential narrative match; reporting uses that helper too. Names remain anonymous.
No feedback API, encryption, review masking or raw-response model association was changed.

Preflight tests preserve the initial institutional-form audit baseline while checking no new audit
or account writes, because canonical form synchronization already created a legitimate event.

## Evidence

The complete 13-case SeededDemoDatasetTests smoke run passes on isolated local PostgreSQL after
both production fixes. It exercises coherent histories, relationships, role/lifecycle separation,
normal API reads, encrypted boundaries, workflow projections, forms and notifications. Full seed,
rerun, upgrade, concurrency, refusal, secret-hygiene and external-isolation coverage is included in
the running complete backend regression; its final result is pending.

The later canonical-schema rehearsal, reset-only seeder modernization, assisted Good Moral scenario
expansion and operator rebuild remain unfinished milestone work. No runtime keyring/credential was
read, printed or rotated; test keyrings are ephemeral.
