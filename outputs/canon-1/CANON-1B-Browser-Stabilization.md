# CANON-1B browser stabilization

Source base: `0d7fbd0a5fd0ee6d38aba091a27ffa4ed3ac4691`; reviewed 2026-10-16 (Asia/Manila).

## Inherited failure evidence

[Run 38886458758](https://github.com/ils12058/COMPASS/actions/runs/38886458758) preserved all eight
jobs but failed suites across Chromium and WebKit. Failed families included Assessment Records,
frontend consistency, Inventory corrections, assisted Good Moral, hierarchy/help/retention routes,
realtime, user copy, draft/session checks and E-Counseling call/safety/timing. The run log was read;
Chromium shard 3's server log, results and screenshots were also inspected.

Most navigation errors used a 12-second budget. Workflow warm-up requested a manual list of routes,
did not reject HTTP errors, and omitted some failing destinations (including help/retention and
several actual dynamic-route families). It proved neither complete route coverage nor hydration.

The transcription-without-storage-consent failure had a full-page skeleton and **zero API fixture
requests**, despite neighboring cases using the same workspace successfully. This points to the
page failing to become interactive; it does not prove a permission or consent defect. The context
403 failure remained on the original session when waiting for a call dock after navigation; the
screenshot still showed the valid active call, not a revoked call.

## Local development versus production observations

Focused dev-server checks passed locally on both engines for transcription and fresh downloads;
Chromium help/retention and context-denial checks also passed. Thus these CI timeouts were not
reproduced as deterministic business-rule failures. Cold dev navigation from E-Counseling to the
Routine Interview route did reproduce a timeout: the server and screenshot stayed on
`Compiling /portal/routine-interviews/[routineInterviewId]`, beyond the separated navigation budget.
It passed on the built production server on both engines with the same fixture and assertions.
This is evidence of a development compilation cause for that navigation, not proof that every
inherited timeout had the same cause.

Against the local production test build:

| Representative assertion | Chromium | WebKit |
| --- | --- | --- |
| Transcription without storage consent submits `store_transcript: false` | Pass | Pass |
| Each media click requests a fresh link, downloads exact bytes, sends no referrer | Pass | Pass |
| Scheduled-end notice does not interrupt the active call | Pass | Pass |
| Routine Interview navigation retains call dock and timing | Pass | Pass |
| Context 403 hides cached information without revoking the independently authorized call | Pass | Pass |
| Notification hint/reconnect reconciles using canonical HTTP state | Pass | Required in final CI |

No application permission, consent or download behavior was changed solely because CI timed out.
The WebKit download failure was not reproduced locally; byte-content/fresh-link/no-referrer
assertions remain required in Linux CI. Production evidence here is focused, not the complete matrix.

## Implementation

- Build one separate synthetic production application, then `next start` it in every browser job.
  The ordinary production build remains a separate check. The test artifact is not a deploy image.
- Remove the fragile manually maintained dev warm-up route list and test-only `onDemandEntries`
  configuration. The build compiles the actual route graph.
- Retain synthetic APIs and Daily mocks through a build-time, loopback-only seam. Realtime synthetic
  sockets also require loopback. Normal production defaults explicitly bake the seam off; runtime
  environment changes cannot enable it. Ordinary realtime configuration retains production `wss`.
- Block external browser HTTP requests, keep service workers blocked, preserve context/session/API
  fixtures and both engines' existing popup/download tests.
- Separate 30-second navigation from strict 12-second interactions. No global assertion timeout
  increase, arbitrary readiness sleep or retry of a failed business operation was added.
- Retain a fixture before `goto`, enabling failed-initial-navigation screenshots and context cleanup.
  Failure JSON includes suite/engine/check, current URL without query, document readiness, navigation
  history, page error fingerprints/source locations, failed-request method/path/error and API method/path history. Request
  bodies, raw error messages, authorization headers, signed query parameters and external URL paths
  are excluded at the reporting boundary, including secondary tabs. A bounded readiness probe and
  screenshot timeout prevent diagnostics from stalling failure cleanup. Server logs remain artifacts.
- Keep independent suite execution/attribution and exact-once discovery across four shards per engine.
  All 31 files remain registered; no job is optional and no assertion was removed to make CI pass.
- Retired retention bookmark cases now assert 404/no mutation controls, matching removal of the
  obsolete catch-all page. Canonical read-only oversight cases remain.

## Validation and remaining uncertainty

Local production build and focused browser comparisons passed. The initial full unit run found
four tests encoding the removed redirect/dev warm-up implementation; updated tests verify the
replacement boundary while preserving suite registration and required engines.

The PR's exact-head CI checks are the complete browser result record. This report does not claim
all inherited failures are fixed before those jobs finish. Required final validation is all 31
suites on Chromium and WebKit across eight non-optional jobs, plus frontend unit/lint/type/build.
If Linux WebKit downloads, fake-clock navigation, readiness or another assertion still fails, use
its retained diagnostics to establish the cause before a subsequent run; do not label it generic
flakiness or remove it from coverage.
