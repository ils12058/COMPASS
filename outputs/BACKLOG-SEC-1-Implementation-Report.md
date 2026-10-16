# BACKLOG-SEC-1 — Security Activity cleanup

Date: October 16, 2026 (Asia/Manila)

## Baseline and isolation

- Fetched and verified `origin/staging`: `bea790e6c04a3ea6b7d69ce651e88d5ba3b724e2`.
- Branch: `feat/backlog-security-activity-cleanup`.
- Worktree: `/Users/reynantlntno/Projects/COMPASS-BACKLOG-SECURITY`.
- Inspected worktrees and branches before creation. Other workstreams were left untouched.
- Dedicated local PostgreSQL on port 55471, database `compass_agent_d_security` (pytest owns its `test_` database); frontend on 3147. Browser API traffic uses synthetic intercepted fixtures.

## Change and security boundary

Removed only `AUTH_SESSION_CREATED` (`auth.session.created`, formerly “New session created”) from `SECURITY_ACTIVITY_PRESENTERS`. Ordinary successful sign-in remains represented by `AUTH_LOGIN_SUCCESS` (“Signed in to COMPASS”).

All other presenters and their copy are unchanged after review: sign-out, session revocation, attributable denied sign-in, password setup/reset, authenticator enrollment/disablement, recovery-code regeneration/use, trusted-browser addition/removal, and account security administration retain their distinctions. Password reset specifically identifies account recovery. Existing copy already follows the plain-language convention; no unrelated editorial changes were needed.

The registry builds the SQL selection predicate in `projections.py` before ordering, offset, limit, and the `has_next` lookahead. Removing the registry entry therefore excludes hidden events before pagination. No additional frontend filtering is necessary.

Authentication/session business logic, AuditEvent persistence/schema, My Activity presenters, endpoints, capabilities, and privacy-governance code are unchanged. A real password-login regression checks both persisted audit facts, the session target, and one canonical displayed sign-in in each self feed. Projection tests also verify hidden historical audit rows survive activity retrieval.

The existing response remains limited to event UUID, safe type, static title/description, and timestamp. Actor attribution, target ownership, and outcome constraints remain in the SQL predicate. Tests exercise anonymous/foreign-actor/foreign-target/wrong-outcome failures and existing invalid target/unknown action concealment.

## Changed files

- `be/compass/activity/presenters.py`: remove the redundant presentation only.
- `be/tests/test_activity.py`: update the projection expectation; add interleaved hidden-event pagination and failed-sign-in attribution checks.
- `be/tests/test_authentication.py`: assert real login preserves session and login audit evidence while presenting one sign-in.
- `fe/tests/security-activity.browser.mjs`: exercise safe Security Activity presentation, retained events, pagination, My Activity navigation, responsive layout, and read-only behavior in both engines.
- `outputs/BACKLOG-SEC-1-Implementation-Report.md`: this report.

## Validation

Passed checks:

- `pnpm api:generate`.
- `node --import ./tests/support/register-tsx.mjs --test tests/activity-retrieval.test.mjs`: **15 passed**.
- `COMPASS_UI_BASE_URL=http://127.0.0.1:3147 node tests/security-activity.browser.mjs`: **2/2 Chromium passed**.
- Same browser command with `COMPASS_UI_BROWSER=webkit`: **2/2 WebKit passed**.
- `pnpm lint`: exit 0, **0 errors**. Four inherited unused-variable warnings in `tests/portal-navigation-attention.browser.mjs`.
- `pnpm typecheck`: exit 0.
- `pnpm build`: exit 0 (Turbopack production compilation, TypeScript, and prerendering).
- Ruff lint and format checks for activity modules and the three inspected/affected test modules: passed.
- `node --check fe/tests/security-activity.browser.mjs` and `git diff --check`: passed.
- Visually reviewed the phone screenshot; safe event copy and paging controls fit without horizontal overflow. Both engines also checked 1440px.

Final backend focused run: `POSTGRES_DB=compass_agent_d_security POSTGRES_PORT=55471 /Users/reynantlntno/Projects/COMPASS/be/.venv/bin/python -m pytest tests/test_activity.py tests/test_activity_retrieval.py tests/test_authentication.py -q` from `be/`: **128 passed in 70.25s**. This includes all four added attribution cases. Ready for owner review with the inherited audit-test failures disclosed.

Broader audit check and inherited failures:

- Initial `pytest tests/test_activity.py tests/test_activity_retrieval.py tests/test_authentication.py tests/test_audit.py -q`: **139 passed, 2 failed** (before adding four further attribution cases).
- `test_success_audit_event_rolls_back_with_surrounding_transaction` and `test_policy_sync_rolls_back_if_audit_recording_fails` each expect `AuditEvent.objects.count() == 0`, but the autouse institutional-form synchronization leaves one event.
- Reproduced **both failures on an untouched archive of staging SHA above**, using a separate `compass_agent_d_security_baseline` test database. These failures are inherited, not changes to audit persistence. No unrelated test fixes included.

Logs and screenshots for this local run are under `/tmp/compass-agent-d-security/` (ephemeral, not institutional data or a committed CI artifact).

Unexecuted: the entire repository-wide backend/frontend browser matrices, live deployment checks, and live-account tests. Local synthetic coverage does not assert hosted CI success.

## Limitations and integration

- Browser fixtures validate presentation and navigation; backend database tests validate real audit persistence and allowlisting. No live institutional records were read or changed.
- Historical session creation stays available to authorized audit investigation, but is no longer a separate account Security Activity entry.
- Domain-Rich My Activity and GCO-assisted Good Moral initiation remain deferred.
- Open PRs #238 (Inventory) and #239 (Exit Interview) had no changed-file overlap when inspected. PG-1A was an audit worktree with no open PR; its privacy-governance scope is untouched.
- No migration, identity synchronization, merge, deployment, or data reset is required/performed by this slice. Normal backend release is needed for the new presentation to reach users.
