# Focused validation

All browser and backend fixtures use synthetic records. No live account or institutional record was used.

## Results

| Check | Result |
| --- | --- |
| `pnpm api:generate` | Passed; generated output is ignored and no generated client is part of the diff. |
| `pnpm lint` | Passed. |
| `pnpm typecheck` | Passed. |
| `pnpm build` | Passed; production build generated all 95 static pages and compiled the dynamic Routine Interview detail route. |
| Focused frontend workflow tests | 28 passed across Routine Encounter linking, Encounter consistency, and Online delivery behavior. |
| Counselor Evaluation browser tests — Chromium | 18/18 passed. |
| Counselor Evaluation browser tests — WebKit | 18/18 passed. |
| Focused backend Routine Interview tests | 78 passed across `test_routine_interviews.py`, `test_routine_encounter_linking.py`, and `test_routine_interview_encryption.py`; five existing Ninja tuple-response deprecation warnings. |
| `git diff --check` | Passed. |

## Behavioral coverage

The browser suite checks all six native rating groups, all ten values and Not rated, keyboard arrow behavior, target size, exact narrative payload preservation, no implicit saving, confirmed saving, pending-save control protection, failed-save draft retention, and the shared unsaved-navigation guard.

Finalization coverage includes empty/optional evaluation behavior, cancel and confirmed submission, read-only history, an already-linked Encounter, Appointment-backed server resolution, missing candidates, candidate retry and pagination, no automatic selection, stale Encounter reconciliation, canonical Evaluation refresh after a draft status check, an uncertain request whose status read initially fails, and an uncertain request that the server committed. Uncertain requests are never replayed without a fresh deliberate confirmation. Browser checks also cover 1440px desktop, 1024px tablet, 390px phone, 320px narrow phone, keyboard input, and 200% enlarged root text.

The frontend command was run from `fe/`:

`node --import ./tests/support/register-tsx.mjs --test tests/routine-encounter-linking.test.mjs tests/counseling-encounter-consistency.test.mjs tests/counseling-online-delivery.test.mjs`

Browser commands, also from `fe/`:

`COMPASS_UI_ARTIFACTS=/tmp/compass-ux15-evaluation-after node tests/ux15-counselor-evaluation.browser.mjs`

`COMPASS_UI_BROWSER=webkit COMPASS_UI_ARTIFACTS=/tmp/compass-ux15-evaluation-after node tests/ux15-counselor-evaluation.browser.mjs`

Backend command, from `be/`:

`uv run pytest -q tests/test_routine_interviews.py tests/test_routine_encounter_linking.py tests/test_routine_interview_encryption.py`

At narrow-phone 200% text, the assertion checks the modified form's own reflow. The surrounding portal shell has a pre-existing narrow viewport overflow, also documented by earlier UX15 pilots. No new assertion treats that unrelated shell behavior as part of this component. Automated browser checks do not establish manual assistive-technology or institutional acceptance.
