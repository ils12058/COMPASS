# Real authenticated local integration

**18 scenarios PASS; all 16 operation families observed.** This is distinct from the 53 mocked
ORG-3 Catalog scenarios per engine. Real chain: headless Chromium → production Next 16.3.4 on
`http://localhost:3164` → same-origin rewrite to Django on `127.0.0.1:8164` → disposable PostgreSQL
17.11 on `127.0.0.1:56649`, DB `compass_org4_browser`. Local Redis on 56650 supplies actual rate
limits/cache/idempotency. No production dependency, real account, SMTP, S3 or provider was used.
Non-loopback browser destinations are blocked; service workers are blocked, not application APIs.

## Fixture and oracle

`be/tests/catalog_authenticated_rehearsal.py` requires explicit disposable opt-in, tests.settings,
loopback/nondefault PostgreSQL port, a `compass_org4_*` DB and state outside the repository. Its
prepare action refuses existing users/Catalog data. A fresh state file is mode 0600 and contains
ephemeral synthetic passwords/keyrings. It is never committed or printed. Preparation adopts an
explicitly empty synthetic Catalog, syncs identity/forms, provisions encrypted active TOTP factors,
and submits a real encrypted Inventory through existing services. Preparation writes are transactional.

`fe/tests/organization-catalog.authenticated.mjs` uses ordinary login form/password, login challenge,
server TOTP verification, opaque HttpOnly session cookie and canonical CSRF bootstrap. It does not
inject authenticated cookies or browser-managed tokens. Fresh time steps use PyOTP and retain
server replay protection. Read-only oracle subprocesses independently inspect persisted Catalog
rows, versions and Audit metadata, and compare every submitted Inventory field with its original.

The only test arrangements after preparation are an expired persisted MFA timestamp and a competing
audited edit via the protected Catalog service. Neither is a test-only HTTP endpoint. The competing
actor is synthetic service-level authority; the principal browser actor authenticates normally.
No authenticator/authentication implementation or production persistence was added.

## Executed scenarios and persisted evidence

| Scenario group | Observation |
|---|---|
| 1 Login/entry | Actual Catalog-only GSS password/TOTP/session, Catalog controls and no relationship capability/tab |
| 2–7 Entity create/rename/history | Three creations and three renames through actual forms; UUID/code/parents preserved, versions 1→2, exact actor/event; actual target history plus two pages at page_size=1 |
| 8 Complete policy/no-op | Noncontiguous [1,3,5], Bachelor→Master change, version 3; identical direct authenticated submission does not increment/append |
| 9 Denied requests | Missing CSRF 403; extra MFA/actor/code/parent fields 422; stale version 409; unchanged version/event sequence |
| 10 Impact/status | Real active-child refusal, Program→College→Campus retirements, reverse ancestry activation, database status and exact versions/events |
| 11 MFA re-review | Expire primary session, receive real refusal, change target during MFA, verify real fresh TOTP, assert no Catalog replay, retain input, deliberately review/confirm current version |
| 12 Lost response | Playwright forwards the PUT to actual Django, waits for its committed 200 then aborts delivery; current row and actor/basis/version history confirm it; exactly one mutation |
| 13 Submitted history | Real rename/policy/retirement of Inventory-linked Program; all Inventory fields/ciphertext remain unchanged |
| 14–17 Other actors | Relationship-only, combined, read-only and Student ordinary sessions; independent tabs/actions and direct restricted-history/unauthorized-edit responses |
| 18 Coverage assertion | Exact set of 16 successful operation families from real HTTP responses, no fabricated bodies |

Campus/College/Program creation, rename, activation/deactivation and policy use UI confirmations.
Impact/history are loaded by actual UI components; small-page pagination is additionally exercised
through authenticated same-origin browser fetches. Status families run both directions. The oracle
asserts the full creation-through-version sequence and actual actor UUID; it does not infer success
from response status or optimistic UI.

## Reproduction

Use the clean environment prefix and build in [validation](validation.md). Start a task-owned
PostgreSQL/Redis and create a fresh DB; never point this helper at deployed data. From `be/`:

```sh
python tests/catalog_authenticated_rehearsal.py prepare "$COMPASS_ORG4_STATE"
python tests/catalog_authenticated_rehearsal.py serve "$COMPASS_ORG4_STATE"
```

The second command is a separate local process; start Next on 3164, with the build's API rewrite
target set to `http://127.0.0.1:8164`. From `fe/`, under the same synthetic clean environment:

```sh
pnpm start --port 3164
node tests/organization-catalog.authenticated.mjs
```

The browser command requires COMPASS_ORG4_PYTHON, COMPASS_ORG4_STATE, COMPASS_ORG4_DISPOSABLE=1,
COMPASS_UI_BASE_URL and COMPASS_UI_ARTIFACTS. Secrets are passed only through the private fixture
state and inherited test environment. Ordinary CI mocked-browser discovery does not automatically
run this opt-in live-backend harness.

Local evidence root: `/private/tmp/compass-org4.I9H5cI/`; final `authenticated-results.json` and
`authenticated.log`, backend request paths/statuses in `django.log`, private fixture `auth-state.json`.
The committed evidence.json includes counts and hashes, not credentials/keyrings/raw private rows.

## Boundaries and development corrections

Initial harness preparation missed the command's explicit positional --adopt flag and the active
Institutional Forms prerequisite. These fixture errors were fixed; subsequent failed preparation
rolls back fixture writes. Early browser attempts used two incorrect accessible action labels and
did not reset the workspace's deliberate post-save Campus filter before selecting another Campus.
Selectors/navigation were corrected to actual source behavior; fresh disposable baseline restores
preceded reruns. No production assertion or safeguard was weakened. Only the final complete
18-scenario run is counted; aborted attempts and their successful prefixes are not added.

Only Chromium ran this real backend harness. The WebKit evidence is mocked API execution. Real
negative variants such as interrupted creation, missing first-page reconciliation evidence, account
switch mid-edit and failed refresh remain represented by service/API tests plus mocked component
scenarios, not separately claimed as real end-to-end runs. Physical-device, screen-reader, native
zoom/print and institutionally appointed operator execution remain NOT EXECUTED.
