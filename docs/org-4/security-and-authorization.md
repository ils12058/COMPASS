# Authorization, MFA and privacy assurance

Result: PASS for the tested synthetic contract; institutional delegate appointments and security
acceptance remain unapproved. No real user was inspected or granted authority.

Catalog and relationship authority are independent. `organization.catalog.manage` adds exactly that
capability, requires `organization.structure.view`, and is suppressed for unsupported roles even if
a malformed ORM override exists. IT Administrator and Head designation do not imply Catalog rights.
Role baselines retain their independent operational capabilities; a Catalog-only GSS fixture does
not gain StudentAffiliation, Responsibilities, Accounts or global Audit management.

The real browser rehearsal used separate Catalog-only GSS, relationship-only IT Admin, combined
IT Admin, read-only GSS and Student accounts. It checked workspace controls, relationship tabs,
direct history requests and denied mutations against persisted state. All used ordinary login and
opaque HttpOnly cookie sessions. The primary manager completed server-verified TOTP login and
later real step-up. Synthetic encrypted factors were provisioned by a test fixture; no human or
institutional enrollment/approval is implied.

## API and direct service evidence

`tests/test_catalog_services.py` has 88 selected cases. Its authority matrix covers eligible roles
without grants, unsupported roles with malformed grants, inactive actors, role/dependency change,
expired/revoked overrides, foreign/missing/revoked/expired/rotated sessions, stale actor caches,
missing/disabled factors, forged in-memory MFA evidence, mismatched Audit actors, strict fields,
CSRF, exact capability composition and protected history. Account Management/capability dependency,
identity, authentication and step-up suites provide neighboring regressions. See evidence.json for
counts by module rather than summing overlapping scenarios.

The protected service independently acquires the exclusive gate, locks/reloads the active actor,
evaluates role and current capabilities, locks active factor then session, verifies actor/session
ownership and the persisted credential digest, and requires recent MFA. It checks again before
transaction exit. The API decorator is not the only boundary. PostgreSQL races prove revocation
and MFA expiry while waiting; the new late-expiry test injects time only after a real Audit write
and proves row/version/event rollback. The latter is synthetic time injection, not elapsed real
hours or another independent-connection race.

The real same-origin integration independently exercised missing CSRF, forged MFA/actor/code/parent
fields and stale versions. It retained the exact version/event sequence after each refusal. The
browser never submits an MFA timestamp or an Audit actor with a Catalog command.

## Recent-MFA workflow

The manager edits, deliberately confirms, receives `recent_mfa_required`, preserves local input,
verifies through `/auth/mfa/totp/verify`, reloads authoritative state and confirms again. Another
properly audited synthetic manager changes the Program during verification. The browser test
asserts that verification emits no Catalog mutation, shows current data, retains the draft, then
saves only after a new review. The fixture expires the server timestamp directly to arrange the
test; it does not set it fresh or defeat TOTP replay protection. PyOTP generates a fresh real time
step for the existing supported authenticator flow.

Setup-required, account/session transitions, revoked confirmation authority and other transient
variants also pass the existing mocked Chromium/WebKit scenarios. They were not all repeated as
real browser failure races. API/service denials and browser simulations are reported separately.

## History and confidential boundaries

`get_catalog_history` requires current Catalog authority and filters exact target type/UUID,
canonical action, SUCCESS and `catalog_change=1`. It returns actor UUID, bounded basis and safe
before/after/version facts, with page_size 1–50. It never enriches actor names from Accounts or
exposes global Audit metadata, IP, user agent, Student names/answers or message/assessment contents.
Direct unauthorized HTTP requests fail even when the user can read ordinary reference structure.

The new concurrent history test uses a real independent PostgreSQL writer: uncommitted version
and event are absent from the reader; both appear after commit. Successful changes emit one event;
no-ops/stale refusals do not fake success; Audit failure and later authorization failure roll back
the row, version and event. Restricted history is administrative evidence, not cryptographic
protection against a privileged database administrator.

Impact exposes aggregate fixed categories only. Catalog grants add no operational ownership,
provider relationship, Counseling/Assessment/Inventory-answer or Good Moral confidentiality access.
Selected Guidance, Inventory, Good Moral and routing regressions retain their original permissions.
