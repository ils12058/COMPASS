# Requirements traceability

Request section numbers refer to the ORG-4 task. PASS below means the named synthetic check passed;
it does not expand its scope to institutional execution. Source-only conclusions and unexecuted
operational gates are identified. Paths below `compass/` are relative to `be/`; test names are under
`be/tests/`, except FE browser/Node selections under `fe/tests/`.

| Request | Implementation / owner | Durable constraint or boundary | Executed evidence | Result / limit |
|---|---|---|---|---|
| 1–4 Mission/base/architecture/manifest | Merged ORG-0–3; this manifest and git history | Isolated requested branch; original checkout unchanged | Fetch exact `d91d64c…`, applicable instructions/source review, lineage | PASS; no later initial-base commits |
| 5 Disposable authenticated application | `catalog_authenticated_rehearsal.py`, ordinary auth, Next rewrite | Loopback, disposable DB guard, test settings; real cookie/CSRF/TOTP | 18 authenticated scenarios, real PostgreSQL and Redis | PASS for Chromium; no real institutional actors |
| 6 All sixteen operations | Organization `api.py`, `catalog_services.py`; Catalog UI | Strict schemas, versions, shared transaction/Audit | Authenticated script exact 16-family assertion, persisted oracle after operations | PASS; small-page history via actual browser fetch too |
| 7 Independent permissions | Accounts `policy.py/services.py`, Organization gates | Dependency/eligible-role/override evaluation | Catalog services 88 cases; actual five-identity UI/API matrix | PASS; Head/unsupported/revoked variants also service/API tests |
| 8 Service/API denial | `require_catalog_manager`, session auth/CSRF | Locked persisted actor/factor/session; strict fields | Forged actor/MFA/version/parent/code, CSRF, revoked/foreign/rotated sessions; unchanged row/Audit | PASS selected cases; not every failure repeated in real UI |
| 9 Real recent MFA | Authenticator shared dialog and backend sessions | Server evidence rechecked before exit; no command replay | Actual TOTP, expired session arrangement, competing edit during MFA, deliberate re-review | PASS; setup enrollment human observation absent |
| 10 Immutable identity | Catalog services/models/API | UUID PK, stored-code uniqueness; no code/parent mutation signature | Three-entity identity/no-op/stale tests; real UI oracle | PASS supported paths; raw privileged SQL not fenced |
| 11 Hierarchy | `_active_parent`, `_activation_policy`, PROTECT FKs | Gate/ancestry locks; no cross-table status SQL trigger | Child-create/activate versus parent retire races; no cascade; referenced history | PASS supported paths |
| 12 Versions | 0003 + `_version`/`_save` | Three positive CHECKs | Populated version migration, raw zero/negative rejection, no-op/stale/Audit rollback | PASS |
| 13 Impact categories | `_impact` actual FK/subqueries | Fixed safe schema; independent counts / OR predicates | Catalog impact tests and real blocker/preview requests | PASS fixture counts; F6 text not name-matched |
| 14 Hard blockers/warnings | `_status`/`_impact` | Exclusive recount; active Student role across CURRENT/GRADUATED/FORMER | All lifecycle/blocker tests, Office/Follow-Up cases | PASS; draft/pending-GM Program warnings retained |
| 15 Advisory preview | Impact GET + status service | Version never reserves dependencies | Allowed preview→relationship insertion→exclusive blocked retirement; stale version test | PASS |
| 16 Routing/relationships | Organization `services.py/access_scope.py` | Current scope/provider-owned permissions | Organization, Accounts, operational Student and appointment suites | PASS selected routing, Head, GSS, inactive ancestry and role tests |
| 17 Pending Guidance work | Guidance Message/Follow-Up services | Shared gate before domain locks; scope permissions | New Office/Follow-Up races, completed/resolved ciphertext preservation; existing reassignment/lifecycle tests | PASS; human live-remediation acceptance absent |
| 18 Reactivation | Account Management `_admin_mutation` and Organization validator | Shared gate, invalid retained relationships refused | Concurrent account-enable/retire plus Account Management regressions | PASS synthetic; no real account enable |
| 19 Persisted academic policy | `program_policy.py`, Program, 0002 SQL function | Known enum/null shape, exact integer array CHECKs | 37 policy cases incl SQL bypass and configured/pending/unknown states | PASS; no canonical fallback |
| 20 Create/activate policy | Catalog create/status services | Complete configured active policy + ancestry | Additional DB Bachelor→Inventory→F4; pending draft and incomplete activation tests | PASS synthetic, no institutional classification approval |
| 21 Policy edits/F4 barrier | `update_program_policy` | Exclusive gate + pending-F4 refusal | Concurrent policy edits, Inventory/F4/correction races, no-op tests | PASS contract; policy owner decision open |
| 22 Current Inventory | Inventory services + selection helper | Shared gate; active ancestry/current configured membership | Inventory suites; policy/selection/submission races incl new retire→submit | PASS; pending/unknown 1–10 preserved |
| 23 Inventory history | Inventory persisted fields/ciphertext | Immutable submitted facts/reopening constraints | Real browser every-field oracle; context/documents regressions | PASS synthetic; current labels may rename |
| 24 F4 | Good Moral eligibility/lifecycle/services | Bachelor + CURRENT + Inventory + fixed Years 1–4 | Core/preparation/assisted/policy and race tests | PASS; Year 5 still excluded |
| 25 F6 | Good Moral DB degree options + saved degree text | Advisory suggestions, no whitelist | Policy/core/F6 issuance/PDF tests | PASS selected synthetic cases |
| 26 GM-OR | Good Moral receipt/verification services | Permanent identity, fee, physical inspection attribution and issuer gates | Receipt/verification/concurrency/migration suites, mocked receipt/print UI | PASS regressions; deployed ledger not activated; actual inspection absent |
| 27 Historical references/reports | Tracer, Inventory, reports, Exit, Routine, Guidance | Protected FKs and saved snapshot fields; current joins distinct | Populated migration comparisons; selected historical/report regressions | PARTIAL across all presentation formats/stakeholder acceptance |
| 28 PDF/native print | Good Moral rendering + authorized PDF routes; FE native-preview code | Saved request/template/issuer/receipt facts | Two new before/after Catalog PDF cases + six existing preservation cases; 24 mocked print scenarios/engine | PARTIAL; normalized facts/page count pass, native OS/paper not executed |
| 29 Organization upgrades | 0001→0002→0003; canonical registration | Atomic additive migration; frozen backfill | Two populated policy upgrade/failure cases, one version migration; fresh CLI | PASS synthetic; live compatibility unverified |
| 30 Initialization/adoption | Organization bootstrap/receipt | Separate advisory key, receipt shape/immutability, schema check | Fresh/populated/empty/repeat/history/rollback tests and two concurrency cases | PASS selected PostgreSQL cases |
| 31 Seeder/deploy compatibility | Staging seeder/deploy/bootstrap/new legacy alias | Receipt/schema preflight; reviewed migration allowlist unchanged | 50 seeder + 41 deployment + 5 canonical tests; restored alias preservation | PASS synthetic; no deployment script execution against host |
| 32 Backup/recovery | Native pg_dump/restore + compatible source helper | Consistent full DB/Audit point; all-table digest compare | 117 tables/514 rows exact, repeat no-op aliases, later-commit mismatch detection | PARTIAL: later events not replayed; actual image/key/media/old-process proof absent |
| 33 PostgreSQL race matrix | Existing/new Catalog tests, supported shared participants | Actual PG advisory waits/row order/atomic rollback | 38 Catalog cases + 2 initialization cases; matrix in concurrency doc | PASS listed interleavings; not exhaustive permutations |
| 34 Actual frontend authority/actions | Catalog workspace/generated operations | Backend remains final; actual login session | 18 real scenarios with 16 families and five actor classes | PASS Chromium; WebKit mocked only |
| 35 Stale/uncertain state | `catalog-editor.tsx`, Query and actor/session ownership | No mutation retry; preserved safe input/current review | Real stale/MFA/lost committed rename; 53 mocked Catalog scenarios/engine | PARTIAL real-backend variants; mocked coverage broader |
| 36 Reconciliation | Current detail + restricted history + second detail read | Actor/action/basis/version match; missing first-page event stays unconfirmed | Actual single committed PUT/lost response; mocked creation/later-edit/missing-history tests | PARTIAL real creation/interleaving variants; no backend idempotency claim |
| 37 Automated accessibility | Shared form/dialog/focus primitives and Catalog layout | DOM semantics and disabled controls | Node + Chromium/WebKit keyboard/focus/narrow/tablet/desktop/200%-text tests; two screenshot inspections | PASS selected automation; not a formal accessibility audit |
| 38 Manual accessibility | Future human UAT scripts | Actual equipment/operator evidence required | None | NOT EXECUTED; native zoom not equated with CSS scaling |
| 39 Restricted history/privacy | Exact-target service/API projection | Current capability, bounded page/basis/safe before-after | Unauthorized direct requests, target projection/paging tests, actual actor history | PASS synthetic; no global Audit browsing |
| 40 Synchronous Audit | Existing Audit transaction | Row/version/event one transaction | Four operation Audit fault variants, independent waiting writer, late MFA rollback, concurrent history read | PASS |
| 41 Default safety | Grant/dependency/MFA/schema/receipt/version/gates | No default Catalog grants or bypasses added | Baseline policies/assertions, initialized local run, source diff | PASS source/tests; actual users/config uninspected |
| 42 Institutional choices | Decision register D1–D21 | Institutional owner evidence, not software inference | Consolidated existing open decisions | OPEN; blocks operational activation |
| 43 Future cutover | Staging readiness document | Seventeen ordered separately approved steps | Documentation review only | NOT EXECUTED / BLOCKED |
| 44 Recovery plan | Recovery/readiness docs | Retain UUID/code/parents/policy/versions/receipt/Audit and later edits; compatible image | Synthetic restore plus explicit negative old-binary analysis | PARTIAL; no actual release artifact rollback |
| 45 Suites/static | validation.md, evidence.json and CI registration | Locked dependencies, unchanged baseline/allowlist, OpenAPI-generated client | Selected backend/Node/browser/static commands | PASS named executed selections; no full-repository suite claim |
| 46 Accounting | JUnit identities/JSON and artifact hashes | Reruns supersede overlap; CI separate | Reconciled evidence.json counts | PASS accounting; hosted checks reported separately |
| 47 Fix policy | Runtime unchanged | Reproduce before fix; no scope expansion | No reproduced runtime defect; harness-only corrections recorded | PASS scope |
| 48 Required documentation | Fifteen required Markdown files in this directory | Relative links/diff checks; open gates explicit | Documentation inventory and QA | PASS deliverable |
| 49 Verdicts | final-assessment.md | Eight distinct assessment categories | Evidence and limitations reviewed | PARTIAL overall, BLOCKED release, NOT EXECUTED UAT, NOT AUTHORIZED activation |
| 50 Focused PR | Requested branch→integration target | No automatic merge/deploy | PR metadata/final report | Source delivery only |
| 51 Final report/boundaries | PR/handoff/final response | No real/live actions or merge | SHA/cleanliness/file list/check state recorded at delivery | Separate from operational authorization |

The table maps requirements to evidence; it does not claim all scenarios were executed through all
layers. In particular service tests, migration fixtures, mocked browser suites, real Chromium and
source review are separate evidence classes. Manual/institutional/operational gaps remain visible.
