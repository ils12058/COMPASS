# CANON-1 regression repair follow-up

The owner authorized repairing all exposed CI failures on 2026-10-16, superseding the earlier
CI-only review stop. Changes continue on draft PR #247; merging, deployment and live reset remain
outside authorization. The earlier failing-run evidence remains historical evidence.

## Backend changes and justification

- Graduate Tracer seeding now supplies the persona's canonical program and owning college, plus
  the story's completed graduation year (alumni 2025; recent/cohort graduates 2026). Submission
  validation stays strict. Existing composition checks now verify these relationships and years.
- An EARLY Exit Interview is intentionally an incomplete draft. The seed helper treats omitted
  college ratings as an empty list before filtering to that record's saved form contract. Complete
  submissions still require the actual supported items; no F9 identity or contract was changed.
- Full rerun testing then exposed a further production bug: anonymous Customer Feedback was
  still located by the persona's name, so reruns attempted a forbidden duplicate submission and
  reporting missed those rows. Reconciliation now selects responses from that synthetic account's
  submission audit provenance and the existing narrative match. The same helper counts records.
  Optional identity stays blank; no profile fallback, raw-response foreign key, new API association
  or real Student lookup was added. Existing credential-preservation, rerun and opportunity-rebuild
  tests exercise the fix, and composition explicitly verifies anonymous names.
- Seed preflight and transactional audit tests compare the audit count with its initial baseline,
  because the autouse institutional-form synchronization already writes its legitimate audit event.
  No-user-write, rollback, credential/refusal and secret-hygiene assertions remain.
- Exact identity expectations now include the two approved good_moral.initiate role grants (95
  total grants, 78 capabilities). The owning policy already grants initiation; no authority changes.
- OpenAPI expectations add four existing operations (graduateTracerGetClassificationOptions,
  goodMoralListEligibleStudents, goodMoralCreateAssistedCurrentStudentRequest,
  goodMoralCreateAssistedGraduateRequest), academic classification filters/context and the existing
  initiation capability. Exact operation/enumeration/query-set assertions remain.
- Good Moral fixtures use canonical 3rd Year. Blank Semester is rejected at mutation; a historical
  incomplete stored row separately exercises preparation refusal. Preparation rules stay strict.
- Graduate Tracer export audit expectations include the five existing safe academic filter keys;
  assertions excluding confidential responses and analytics remain.
- Initiated Good Moral notifications explicitly use IN_APP_ONLY in push policy. This preserves the
  previous fail-closed no-push behavior and leaves its existing mandatory email intent unchanged.

## Frontend changes and justification

- Assisted Good Moral input errors use controlled user copy rather than raw API diagnostic text.
- The issued certificate query shares one in-flight generated-client read across development
  observer replay. gcTime remains zero: an unobserved response is discarded on completion. Session
  cache clearing, detail authorization, no automatic mutation retry, frozen Blob reuse and PDF-only
  retry behavior remain intact.
- Narrow call controls retain at least 44px targets and their labels while using less horizontal
  padding/minimum width so the five essential controls fit one row at 320px.
- Devices opening explicitly focuses its invoking button, which Safari pointer clicks do not do
  automatically, so closing the dialog restores focus to the actual opener.
- WebKit uses capture-phase popstate reversal rather than cancelling Navigation API traversal,
  which left its native Back cursor out of sync after refusal. Other engines retain early
  cancellation. The native guard listeners stay mounted and consult current registrations, avoiding
  an additional effect-registration gap. A close-event test subscribes before triggering close.
- Native media attachment links are attached to the document before clicking. The regression uses
  a real loopback HTTP attachment and observes opener/popup download events, avoiding WebKit's
  routed-media limitation. It checks exact filename, bytes, fresh URL per click, no prefetch and no
  signed URL displayed. Speaker-selection tests explicitly supply the mocked browser capability;
  the separate unsupported-speaker test still verifies the system-default fallback.
- Browser fixtures select canonical Year level/Semester options. Navigation assertions omit
  aria-hidden badge decorations while retaining exact labels/order. Same-tab freshness compares
  HTTP reads from before send. Encounter corrections wait for the held intercepted request before
  asserting its exact payload. The PDF fallback listener distinguishes a deliberate named download
  from an unnamed automatic headless PDF-popup download.

## Validation

Focused seed smoke: 13 passed. Backend fixture/contract focused run initially passed 109/110; the
remaining operation-name expectation was corrected against the owning routers before full runs.
Frontend units: 767 passed, zero failures/skips. CI self-tests: 42 passed; 167 backend files have
exactly-once coverage across six planned shards. Ruff format/lint and frontend typecheck passed.
The extra PDF regression verifies permission loss during an in-flight read, cache discard, and a
fresh read after authorization is restored. Full backend and both complete 31-suite browser runs are in progress; final results will replace
this paragraph only after completion. No green result is inferred from focused runs.
