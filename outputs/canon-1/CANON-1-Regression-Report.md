# CANON-1A regression evidence and failure classification

Base: `d353108d1f757386b9020c4d1297e081258d2e4e`. Date: 2026-10-16 (Asia/Manila).
This is the first infrastructure checkpoint, not completion of the milestone.

## Passing checks

- 42 CI selector/deployment-guard self-tests, including an AST guard that every actual current
  Django model declaration selects the full suite (Graduate Tracer participation.py is a model).
- 167 backend files bundled and covered exactly once across six full shards, including split parts.
- Ruff format/lint, frozen dependency/lock checks, compileall, fresh current-history PostgreSQL 17
  migrate, migration drift, Django system checks and OpenAPI verification.
- Locked Orval generation, frontend ESLint, TypeScript and production build.
- 31 focused frontend registration/feature checks. Three historical tests asserted the old shell
  chain; they now assert discovered membership, once-per-engine shard coverage, actual matrix
  invocation and the original route compilation requirements. No feature assertions were removed.

## Frontend complete CI execution

[Run 38859892026](https://github.com/ils12058/COMPASS/actions/runs/38859892026), head `8cff975e`:
all eight browser jobs executed; all 31 suites ran once on Chromium and once on WebKit.
Each engine passed 26 suites and failed five. There were 25 failed individual browser cases.
[Structured results and every failed case](evidence/ci-frontend-8cff975e.json).
The build/lint/typecheck job passed. The initial unit job failed on one application assertion and
three old shell-chain assertions; the latter are fixed and verified locally in the follow-up.

The reviewed local full unit rerun is **766 passed / 767, zero skipped**, retaining the assisted
Good Moral raw-message-boundary failure. [Result](evidence/frontend-unit-reviewed.json).

| Failure family | Classification and evidence | Required next action |
| --- | --- | --- |
| Assisted Good Moral raw API message | Real frontend boundary violation: source calls readApiErrorMessage for a form error; user-copy.test identifies the source. | Map the approved error code to controlled user copy; preserve validation and input. |
| Guidance Operations navigation labels (both engines) | Stale selector: allTextContents concatenates visible badge counts with My work. Portal label/badge rendering is expected current behavior. | Assert the stable label/order and accessible badge semantics independently. |
| Good Moral unconfirmed request (both engines) | Fixture violates current form input contract: the test calls fill on Year level and Semester, now select controls with canonical options. | Use canonical select values and retain uncertain-result/idempotency assertions. |
| Counseling correction (Chromium) | Test synchronization race: expected PATCH is undefined, rather than a wrong payload. The assertion follows a pending button before the intercepted request is observed. | Wait for the actual intercepted request, then retain the exact changed-fields/seconds assertion. |
| Good Moral duplicate PDF reads and missing first-error state (both engines) | Development-runtime query/mount behavior, not evidence of production breakage. All five corresponding cases pass against the built production server after readiness. The current component has gcTime=0 and a development Strict Mode mount can repeat a fetch. | Isolate and test the development lifecycle without weakening no-reissue, release-audit or PDF reuse invariants. |
| Good Moral native PDF popup (WebKit) | Browser-specific unresolved behavior; source opens directly from user action. A native viewer/headless interaction must be separated from confirmed issuance. | Reproduce focused popup behavior and preserve authorization, object URL cleanup and user-activation assertions. |
| E-Counseling narrowPhone call controls (Chromium, height 129px) | Responsive production-regression candidate: violates the existing one-row control requirement. No authorization/consent code is implicated by this assertion. | Inspect screenshot and layout at 320px; preserve accessible control targets and call lifecycle. |
| E-Counseling device selection and fresh download (WebKit) | Browser/environment integration failures: selectOption/download-event timeout with synthetic Daily/media. Root cause is not established by a timeout. | Reproduce with engine-specific mocked device/download behavior; do not remove WebKit checks. |
| Draft/back navigation (WebKit) | Browser/test-isolation candidate: waitForURL timeout in the service unsaved-draft check, also seen locally. | Trace guard decision and URL navigation before classifying product behavior. |
| Same-tab send refresh count (WebKit) | Test timing/count observation candidate: the expected new HTTP summary may already occur before the test records its baseline, after confirmed send. Current read-count assertion alone does not prove a missing invalidation. | Record the request before send/navigation and retain canonical HTTP freshness assertions. |

Unresolved classifications are explicit; no production fix or changed business rule is inferred from
an unexplained browser timeout. These cases remain registered and failing for CANON-1B.

## Backend evidence

The duplicate local serial run was deliberately interrupted once all six independent GitHub shards
were running, to reduce contention with browser work. It completed **480 passes and four failures**
in 905 seconds; this is not a full-suite result. [Partial report](evidence/local-backend-partial.json).

| Confirmed local failure | Classification | Evidence / next fix |
| --- | --- | --- |
| Accounts policy role count | Stale test expectation | Test expects 93 role grants; current policy explicitly grants good_moral.initiate to Counselor and GSS, producing 95. Capability definitions remain 78. Update verified canonical grant assertions, not policy. |
| Accounts effective Counselor capabilities | Stale exact-set expectation | good_moral.initiate is present in current policy and absent from the expected set. Preserve designation and override tests. |
| Audit rollback event count | Test isolation / fixture mismatch | Autouse synchronized_institutional_forms records an initial configuration audit event; the test asserts absolute zero after rolling back only its own event. Assert the pre-operation audit baseline. |
| Policy-sync audit failure rollback | Test isolation / fixture mismatch | Same pre-existing forms-sync audit event; Role rollback assertion passes. Preserve atomic rollback and failure propagation. |

The complete targeted run [38859891949](https://github.com/ils12058/COMPASS/actions/runs/38859891949)
executed six shards: **1,278 passed, seven failed, zero errors/skipped**.
[Report](evidence/ci-backend-targeted-8cff975e.json). Besides the two audit failures above:

- Graduate Tracer XLSX release audit: the expected safe context omits five current academic-filter
  keys (college/program IDs/codes and graduation year). Classification: stale exact metadata
  expectation; verify the safe allowlist before updating, never remove release auditing.
- OpenAPI operation set: 355 current operations versus the expected 351. The four supported
  additions are graduateTracerListClassificationOptions, goodMoralListStudentOptions,
  goodMoralCreateCurrentStudentRequest and goodMoralCreateGraduateRequest.
- OpenAPI list filters and report context: expected fields omit the current college, program and
  graduation year additions. Classification: stale contract expectations, verified against current
  exported schema and owning routers; strict fields and authorization must remain.
- OpenAPI capability enum: good_moral.initiate is absent from the old expected enum. Classification:
  stale canonical policy expectation, not justification to remove the capability.

The complete [backend full run 38859891816](https://github.com/ils12058/COMPASS/actions/runs/38859891816)
at `8cff975e` recorded **4,648 passed, 41 failed, 22 errored, zero skipped** across all six shards.
Plan and static/contract jobs passed; all six test jobs failed on application/fixture cases and the
aggregator correctly failed. [Every unsuccessful case](evidence/ci-backend-full-8cff975e.json).
There are 4,711 unique JUnit case IDs, matching local collected function/parameter counts without
missing or extra functions. Parameter IDs that contain generated UUIDs or ephemeral test keys
cannot be compared literally across processes. [Coverage evidence](evidence/full-node-coverage.json).

| Root-cause family | Unsuccessful cases | Classification |
| --- | ---: | --- |
| Seeder alumni Graduate Tracer classification and downstream seed setup | 31 | Production seeder input regression; required college/program/year omitted. |
| Pre-existing institutional-form audit in audit/seed preflight tests | 22 | Test fixture isolation mismatch, including 16 keyring preflight parameter cases. Preserve no-new-write checks. |
| Current OpenAPI operations/filters/context/capability | 4 | Stale explicit contract expectations. |
| Current assisted Good Moral capability/grants | 2 | Stale identity-policy expectations. |
| Good Moral preparation year-level/semester values | 2 | Fixtures violate strict current input contracts (Third and blank semester). Preserve strict validation. |
| Graduate Tracer release filter metadata | 1 | Stale safe metadata expectation. |
| Initiated Good Moral notification absent from PUSH_POLICY | 1 | Production configuration omission. The fallback returns no push; add an explicit reviewed decision without inventing a new notification channel. |

No encryption or migration-order failure was observed in this six-shard plan. The source-level
privacy migration-test cleanup hazard (restoring an intermediate state rather than all leaf nodes)
remains a follow-up reproduction target; it is not counted as an observed failure here.

All 167 files now have JUnit-derived timings, replacing the 36 missing historical observations.
[Provenance](evidence/duration-provenance.json). The rebalanced plan and all 42 CI self-tests pass.
These timings describe the failing baseline: successful seeder scenarios can take longer after
repair and must be remeasured. The final follow-up also includes model/branch wiring guards and
adapted frontend registration assertions; its new exact-head remote validation is distinct from
this completed reference run and is not represented as green.

## Limits and safety

The local all-suite browser runs were partial duplicates and stopped after complete CI evidence
was available. They include load-sensitive navigation timeouts and are not substituted for the
complete CI matrix. A first production diagnostic attempt started before server readiness and
received connection refusals; after an explicit readiness check, the same five printing cases passed.
The focused production diagnostic is not a full end-to-end printing acceptance test.

Current-history schema introspection contains 98 tables, 981 columns, 557 constraints and 429
indexes; no canonical schema comparison has yet occurred. No successful canonical seeder,
reset rehearsal or full role-based UAT result is claimed. Live infrastructure is unchanged.
