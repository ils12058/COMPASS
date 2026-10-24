# Authenticated integration

Evidence labels: **REAL-BROWSER** = Chromium→actual Next production build→Django live HTTP server→disposable PostgreSQL; **API-PG** = Django HTTP test client using persisted opaque session/real CSRF→PostgreSQL; **PG** = actual database/service/independent connections; **MOCK-UI** = intercepted browser contract; **STATIC** = source/contract/type checks; **MANUAL** = human observation. These labels are not interchangeable.

## Environment and bootstrap

Dedicated loopback PostgreSQL 17.11 and Redis were initialized under `/tmp/gm-or-4/synthetic-*` on nondefault free ports. No deployment `.env`, real credentials, deployed hostname, Student/payment record or SSH was used. Python executes from the existing Python 3.13 dependency runtime with a clean environment and `DJANGO_SETTINGS_MODULE=tests.settings`; encryption keys are ephemeral. The original checkout's interpreter is reused read-only; no checkout source/dependency tree is edited there.

New fixture `actors` synchronizes synthetic identity/form definitions, creates eligible F4 Inventory/affiliation and synthetic Student/GSS/Counselor accounts, explicitly grants only the fictional inspector and imports/activates only the disposable ledger. The provider patch exists only inside pytest. It cannot enter a deployed setting. Opaque sessions are persisted by `create_auth_session` and supplied as HttpOnly browser cookies. The application authenticates every request normally; password/MFA login itself is outside this domain test.

For the opt-in browser tests, build Next with `COMPASS_API_BASE_URL=http://localhost:8764`, serve on loopback 3164, set `CSRF_TRUSTED_ORIGINS` to include `http://localhost:3164`, and run pytest with `--liveserver=localhost:8764` plus `COMPASS_GM_REAL_FRONTEND_URL=http://localhost:3164`. The fixture rejects a non-loopback frontend URL, blocks non-loopback browser requests and blocks service workers. It never mocks/fulfills API responses. Generated clients, normal transport/CSRF, normal API authorization, PostgreSQL triggers and real PDF renderer remain in use.

## REAL-BROWSER: F4 and F6

Each case creates a receipt-free Student request via browser fetch, loads the real Student guidance and GSS detail, records number/date/80.00 through the actual editor, queries committed reservation ownership and proves saving created no inspection. It opens an initially unchecked personal attestation, records through the real action and checks original server actor. It prepares, replaces the receipt in the actual editor, confirms old inspection invalidation and old reservation retention, deliberately reinspects with an unchecked new confirmation and prepares again. A separate Counselor session issues. PostgreSQL checks exact current inspection provenance, one issuance Audit and one feedback opportunity. The authorized real PDF endpoint returns PDF bytes, and owned Student detail returns ISSUED without restricted internals. Inspection invokes no instrumented print call.

Two distinct REAL-BROWSER scenarios are counted once, separately from the mocked Chromium scenarios. Only Chromium has actual backend integration evidence; WebKit backend integration is NOT EXECUTED.

## API-PG

Two complete F4/F6 cases additionally compare request/revision/identity bindings, original verifier/time/Decimal fee, notification existence, exact committed issuance replay with unchanged persisted facts, other-Student detail/PDF denial, and normalized actual owned PDF text. Nineteen denial cases are enumerated in [security](security-and-authorization.md). Three outcome-failure cases fail feedback, issuance notification and feedback invitation separately; the entire issuance/Audit/outcome transaction rolls back, then deliberate retry/replay produces exactly one outcome.

The backend client is real Django request/session/CSRF/database integration, but not a TCP browser round trip. Only the two REAL-BROWSER cases establish that stronger path. Simulated physical inspections, ephemeral grants and fictional fees do not constitute institutional execution or policy authorization.
