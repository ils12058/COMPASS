# Validation record

## Environment

- Isolated worktree branch `audit/svc-ux-3-final-validation-v2`, based on fetched `integration/ux15-modernization` SHA `55de058dc505b56ef26828662bbc2573c77b3eff`.
- Disposable PostgreSQL cluster: task-owned under `/tmp`, loopback port 55446; backend test database only.
- Production Next build served locally on loopback. The final real fixed-slot browser test used Next port 3112 and Django `live_server` port 8212. No deployed endpoint or institutional data was used.
- Node/browser suites used synthetic API fixtures except the explicit opt-in authenticated fixed-slot test.

## Backend results

- `tests/test_service_catalog.py tests/test_fixed_date_slots.py tests/test_group_sessions.py tests/test_appointments.py`: **91 passed, 1 skipped** (72.94s). The skipped opt-in browser test was run separately and passed.
- `tests/test_service_cross_pathway_scheduling.py tests/test_service_scheduling_consequences.py tests/test_service_provider_qualification.py tests/test_appointment_slot_reservations.py tests/test_appointment_management_scope.py tests/test_notification_email_links.py tests/test_authentication.py`: **173 passed** (91.46s).
- Opt-in `test_real_browser_fixed_slot_booking_next_django_postgres_workflow`: **1 passed** through the real browser→Next→Django→PostgreSQL path; verified persisted Appointment and slot provenance.
- `uv run --project be python .github/scripts/test_backend_ci.py`: **38 passed**.
- `ruff check compass/service_catalog/api.py tests/test_service_catalog.py tests/test_fixed_date_slots.py`: passed.
- Django `check`: passed; `makemigrations --check --dry-run`: no changes.
- `manage.py export_openapi --check --settings=tests.settings`: canonical OpenAPI current.

## Frontend results

- SVC-UX-1 browser suite: **40/40 per engine**; Group Session browser suite: **3/3 per engine**; draft/session safety: **24/24 per engine**; release-unblock: **12/12 per engine**. Chromium and WebKit. These browser suites use synthetic API behavior.
- `user-copy.browser.mjs`: **40/44 per engine** in the final full runs. The same four Feedback/CSM cases failed in Chromium and WebKit. The initial Chromium run also had one non-reproducible desktop Routine Interview focus assertion; the isolated case passed on current and baseline, and the full rerun passed it.
- Feedback/CSM targeted cases: **0/4** in Chromium and **0/4** in WebKit on both clean baseline and current build. See [triage](browser-regression-triage.md).
- Relevant Node regression selection: **52/52 passed**. `browser-registration.test.mjs`: **4/4 passed** (its deliberate failed/interrupted mock-run cases are assertions of runner behavior, not failed test results).
- `pnpm lint`, `pnpm typecheck`, `pnpm build`, `pnpm api:generate`, and `git diff --check`: passed. Production build generated 97 routes. OpenAPI/Orval generated clients did not change.

## Hosted CI, UAT, and operations

No final PR checks were available at report time; hosted CI is PENDING/NOT YET OBSERVED. Institutional UAT, human screen-reader/native-zoom testing, SMTP/provider delivery, staging deployment, and operational activation were not executed. No merge or deployment was performed.
