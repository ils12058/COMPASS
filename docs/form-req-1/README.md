# FORM-REQ-1 — Individual Inventory required fields follow the official F5 form

**Status:** Implemented on `integration/ux15-modernization`; not deployed.
**Date:** 2026-11-08.
**Official form:** CNSC-OP-GCO-01F5, Individual Inventory, Revision 0.

The Student Individual Inventory now requires exactly the answers the official F5 form asks for
when it is submitted, and no longer offers "Prefer not to specify". Drafts keep their earlier,
looser rules. Existing submitted Inventories and their PDFs keep their stored answers.

## 1. Rules that hold unchanged

1. A draft may stay incomplete. `replace_current_inventory` still saves any valid payload; the F5
   requirements run only in `_validate_submission`.
2. Old submitted Inventories are untouched. `NOT_SPECIFIED` stays in the model choices, the API
   enums, the stored data, and the PDF labels; only new answers may not choose it.
3. A reopened correction is judged only on the answers its targets name. `_correction_required_keys`
   filters the requirement list, and the frontend mirrors that filter, so a field the Student was
   not asked to review never blocks resubmission. A reason-only correction (no targets) keeps its
   old answers.
4. No data migration. Values are not rewritten or invalidated.
5. No invented answers. Text fields accept a short truthful answer such as "None"; choice lists
   gained truthful options rather than "Not applicable".
6. Permissions, encryption, and confidential-content handling are unchanged
   (`compass/inventory/confidential_content.py`).
7. No new `FormRevision` and no change to the official PDF layout
   (`compass/inventory/documents.py`).

## 2. Change A — "Prefer not to specify" removed from new answers

The stored value `NOT_SPECIFIED` remains readable and renderable. New answers may not choose it:
submit validation rejects it in `civil_status_category`, `current_religion_category`,
`occupation_category`, `parent_status_category`, `annual_income_status`, `four_ps_status`,
`indigenous_peoples_status`, `pwd_status`, `mother_life_status`, `father_life_status`,
`transportation_entries.*.frequency_category`, and the CURRENT PSGC `not_specified` flag.

Three truthful values were added:

| Field | Choices now offered |
| --- | --- |
| `FourPsStatus` | 4Ps beneficiary / Not a 4Ps beneficiary / **Not sure (`NOT_SURE`)** |
| `IndigenousPeoplesStatus` | Member / Not a member |
| `PWDStatus` | PWD / Non-PWD |
| `ParentLifeStatus` | Living / Deceased / **Unknown (`UNKNOWN`)** |
| `AnnualIncomeStatus` | Reported / None / **Unknown (`UNKNOWN`)** |

The other affected lists simply dropped `NOT_SPECIFIED`: civil status, current religion,
occupation category, parent-status category, and transportation frequency.

### Migrations (additive only, no data change)

- `be/compass/inventory/migrations/0002_alter_inventoryfamilymember_annual_income_status.py`
  adds `UNKNOWN` to `AnnualIncomeStatus`.
- `be/compass/student_support/migrations/0002_alter_studentsupportprofile_father_life_status_and_more.py`
  adds `UNKNOWN` to `ParentLifeStatus` and `NOT_SURE` to `FourPsStatus`.

Both files are registered in `be/compass/common/canonical_migrations.json` under
`additive_migrations`. `contracts/openapi.json` and the generated frontend client were regenerated
from the backend (`export_openapi`, `pnpm api:generate`), never hand-edited.

## 3. Change B — Required at submission

The rules below are implemented in `be/compass/inventory/services.py`
(`_submission_requirements`, `_member_requirements`) and mirrored in
`fe/src/features/inventory/inventory-payload.ts` (`getInventorySubmissionIssues`).

### Page 1 — Personal data

| F5 section | Required answers |
| --- | --- |
| Personal data | full name, nickname, student number, date of birth, place of birth, nationality, sex, birth order among siblings, civil status category, current address, permanent address, contact number, email address, languages spoken at home, languages most fluent in, religion from birth, current religion category; the other civil-status / religion detail when the category is Other |
| Location details | CURRENT region and city or municipality (an actual PSGC location, not `not_specified`) |

### Page 1 — Family and student support

| F5 section | Required answers |
| --- | --- |
| Family data | For each living parent (father, mother): name, date of birth, place of birth, current address, permanent address, contact number, email address, educational attainment, occupation category (plus the occupation detail when Other), annual income status (plus the amount when Reported), business address, business telephone, languages spoken, religion raised with, current religion. Text answers may say "None" where that is truthful. Spouse details are required only when civil status is Married. A parent whose life status is Deceased or Unknown is exempt from every requirement above, including name. |
| Parent status | parent-status category, and at least one additional parent circumstance (`parent_statuses`) |
| Guardian and emergency contact | guardian name, relationship, address, contact number; emergency contact name and number |
| Student support information | 4Ps status, Indigenous Peoples status, mother's life status, father's life status |

### Page 2 — Siblings, background, living, health

| F5 section | Required answers |
| --- | --- |
| Siblings | At least one row, one row marked "This is me" (`is_self`); every row needs name, sex, age |
| Personal background and unique features | friends in school, friends outside school, special interest, special skills and talents, hobbies and recreation, ambition or goal, characteristics |
| Living conditions | living arrangement, number of people in the present living place, number of people sharing the room; when the arrangement is Boarding house: exclusivity, landlord/landlady name, boarding-house address |
| Health conditions | accidents experienced, operations experienced, height, weight, physical disadvantage, PWD status, illness this year, previous illness. Accident/operation effects are required only when that experience is not "None" (compared case-insensitively). Immunizations stay optional; the other immunization detail is required when Other is ticked. |

### Page 2 — Educational background and current study

| F5 section | Required answers |
| --- | --- |
| Educational background | Elementary, Junior High, and Senior High rows with school and address plus inclusive years. Preparatory, technical/vocational, and collegiate stay optional. |
| Current study | current Program (an active Program), Year Level, satisfaction with the present schedule; the reason when not satisfied. Major stays optional. |

### Page 3 — Course choice, interests, perceptions, plans

| F5 section | Required answers |
| --- | --- |
| Course choice and educational perception | first-choice answer, at least one course-choice reason, the other reason when Other is chosen, lowest and highest subjects with grades, the three inclination answers |
| Interests and daily routine | other skills and hobbies, desired extracurricular activities, reading preferences, handedness, all six daily-hours fields. The interests checkbox list stays optional. |
| Plans after graduation | ideal monthly allowance, intended work field (plus the other field when Other) |
| Prior counseling experience | the yes/no answer; counselor name, when, and where only when the answer is yes |
| Current concerns and fears | current concerns and current fears |
| Organizations and transportation | Organization memberships stay optional. Every selected transportation mode needs its frequency category; the fare stays optional. |

## 4. Change C — Frontend agreement

- `inventory-presentation.ts` no longer lists `NOT_SPECIFIED` in any new-answer choice list, and
  still renders it as "Prefer not to specify" for historical records (`enumLabel`).
- `inventory-payload.ts` mirrors every backend submission rule and returns the complete issue list,
  sorted by section, so the Review section shows every missing answer at once. Messages are plain
  language and never contain enum values or field codes.
- Editor controls carry the existing `required` marker (`aria-required` plus the visible asterisk)
  and an inline error for each rule.
- The PSGC current location is always entered directly; a saved `not_specified` answer shows a
  warning that it must be replaced, while the permanent location keeps its optional
  "Prefer not to specify" path.
- During a pending correction, `inventoryCorrectionIssueAllowed`
  (`inventory-correction-targets.ts`) keeps only the issues the named targets cover, plus save-time
  checks for answers the Student edits. A legacy reason-only correction is not blocked by the new
  rules.
- The current-location correction target now points at `inventory-current-region`, the control the
  Student can actually use.

## 5. What stays optional, and why

| Optional | Reason |
| --- | --- |
| Preparatory, technical/vocational, and collegiate rows | F5 asks for the levels that apply; not every Student attended them |
| Major | Not every Program has one |
| Organization memberships | F5 lists them but does not require an entry |
| Transportation entries, and each fare | A Student may not use any mode, and the form asks for a fare only as a detail of a selected mode; the frequency of a selected mode is required |
| Interests checkbox list | The narrative interest answers carry the requirement |
| Immunizations | F5 does not require a tick; the Other detail is required when Other is ticked |
| Parent details when life status is Deceased or Unknown | They cannot be truthfully answered; the name is kept if already known |
| Spouse details unless civil status is Married | The form asks for them only for a married Student |
| Accident/operation effects when the answer is "None" | There is no effect to describe |
| Schedule reason when satisfied | The form asks for a reason only when not satisfied |
| Prior-counseling details when the answer is No | The form asks for them only after Yes |

## 6. Verification

Backend, from `be/`:

```
uv run pytest tests/test_inventory*.py tests/test_program_inventory_academic_context.py \
  tests/test_routine_inventory_decoupling.py tests/test_openapi_contract.py \
  tests/test_canonical_baseline.py -q -p no:cacheprovider
```

Result: **506 passed** (2026-11-08). The new `be/tests/test_inventory_form_req_1.py` adds 28
tests covering: each removed `NOT_SPECIFIED` rejected at submit but accepted in a draft; `NOT_SURE`
and `UNKNOWN` accepted; spouse/boarding/deceased-or-unknown-parent/prior-counseling/schedule/
"None"-accident conditions in both directions; an old submitted Inventory with `NOT_SPECIFIED`
still reading and rendering its PDF; and a reopened correction not blocked by non-target answers.
`be/tests/test_inventory_form_req_1.py` is registered in the `inventory` bundle in
`.github/scripts/backend_ci.py`.

```
uv run python manage.py makemigrations --check --dry-run --settings=tests.settings
uv run python manage.py export_openapi --check --settings=tests.settings
```

Result: both clean (no pending migrations, OpenAPI current).

Frontend, from `fe/`:

```
pnpm -s typecheck
pnpm -s exec eslint src/features/inventory tests
node --import ./tests/support/register-tsx.mjs --test \
  tests/form-corr-1-inventory.test.mjs tests/routine-inventory-decoupling.test.mjs \
  tests/form-req-1-inventory.test.mjs tests/form-input-standardization.test.mjs
```

Result: **57 tests passed, 0 failed**. The new `fe/tests/form-req-1-inventory.test.mjs` adds 15
tests covering the complete-form baseline, every removed choice, the truthful replacements,
historical labels, each conditional rule, required markers in the rendered sections, and the
correction issue filter.

Not run, by design: the full backend suite and browser regression specs. The frontend CI browser
bundle is unchanged.

## 7. Fix-up (2026-11-08)

FORM-REQ-1's rules are unchanged. This fix-up makes the staging seed, the other backend suites, and
lint obey them again.

### Staging seed

- Every seeded Inventory now carries a complete synthetic F5 answer set. Identity-derived answers
  (contact number, guardian, emergency contact) and parent details are deterministic and consistent
  with each seeded Student; no real people's data is used.
- Seeded Inventories record a real CURRENT location (Bicol Region / Camarines Norte / Daet /
  Barangay I). Seeding resolves PSGC answers offline through `be/compass/staging_seed/psgc.py`,
  which patches the client only for the seed run. Production PSGC validation is untouched, and no
  submit rule was lowered or bypassed.

### Cross-domain tests

- `tests/inventory_test_helpers.py` produces a complete F5 answer baseline with a valid CURRENT
  location.
- Test modules that submit Inventories apply the shared `inventory_psgc` fixture
  (`pytest.mark.usefixtures("inventory_psgc")`): `test_counseling_context.py`,
  `test_routine_interviews.py`, `test_student_actions.py`, `test_institutional_identity.py`,
  `test_student_session_summaries.py`, `test_catalog_final_integration.py`, `test_program_policy.py`,
  and the Inventory suites.
- `tests/test_student_support.py` had an outdated expectation that `NOT_SPECIFIED` support-profile
  answers submit successfully; it now asserts the F5 rule that they must be answered.

### Lint and formatting

- E501 lines wrapped in `compass/inventory/services.py`; E402 markers moved after imports in
  `test_program_policy.py`, `test_inventory_confidential_content_encryption.py`, and
  `test_inventory_correction_targets.py`; all changed files formatted.
- `uv run ruff check .` from `be/` reports only the six pre-existing errors in untouched files
  (`compass/referrals/provisional_activation.py`, `tests/test_fup3a_faculty_referral_journey.py`,
  `tests/test_guidance_followups.py` ×2, `tests/test_guidance_messages_faculty.py`,
  `tests/test_guidance_messages_migration.py`).

### Reports

- `combine_parent_annual_income()` still folds an `UNKNOWN` parent income into the same no-amount
  bucket as `NOT_SPECIFIED`. The bucket is now labelled "Not specified or unknown" in the report
  rows and legend, so the report no longer misstates "Unknown" answers. Old `NOT_SPECIFIED` data
  stays counted; the report contract and OpenAPI did not change.

### PSGC unavailable at submit

- A PSGC outage during submission returns 503 `psgc_reference_unavailable` with one plain message:
  "We can't check your location right now. Your draft is saved; try submitting again later." The
  frontend maps the code to the same text. The draft stays saved.
- `tests/test_inventory_frontend_readiness.py::test_psgc_outage_submission_shows_one_plain_message_and_keeps_the_draft`
  covers the message and the preserved draft.

### Verification

Backend targeted run, from `be/` (each file also confirmed individually):

| Test file | Result |
| --- | --- |
| `tests/test_inventory.py` | 17 passed |
| `tests/test_inventory_confidential_content_encryption.py` | 260 passed |
| `tests/test_inventory_correction_targets.py` | 28 passed |
| `tests/test_inventory_counseling_regression.py` | 2 passed |
| `tests/test_inventory_counselor_review.py` | 4 passed |
| `tests/test_inventory_documents.py` | 5 passed |
| `tests/test_inventory_form_req_1.py` | 28 passed |
| `tests/test_inventory_frontend_readiness.py` | 7 passed |
| `tests/test_inventory_profiling_normalization.py` | 90 passed |
| `tests/test_program_inventory_academic_context.py` | 8 passed |
| `tests/test_routine_inventory_decoupling.py` | 9 passed |
| `tests/test_openapi_contract.py` | 44 passed |
| `tests/test_canonical_baseline.py` | 5 passed |
| `tests/test_staging_seed.py` | 51 passed |
| `tests/test_counseling_context.py` | 31 passed |
| `tests/test_routine_interviews.py` | 24 passed |
| `tests/test_student_actions.py` | 55 passed |
| `tests/test_institutional_identity.py` | 5 passed |
| `tests/test_student_session_summaries.py` | 7 passed |
| `tests/test_student_support.py` | 15 passed |
| `tests/test_catalog_final_integration.py` | 17 passed |
| `tests/test_catalog_concurrency.py` | 26 passed |
| `tests/test_program_policy.py` | 37 passed |
| `tests/test_handoff.py` | 101 passed |
| `tests/test_exit_interviews.py` | 27 passed |
| **Total** | **903 passed, 0 failed** |

`tests/test_student_profiling_reports.py`: 19 passed after the label update; the PDF income-legend
test also passed. `makemigrations --check` and `export_openapi --check` are clean.

Frontend, from `fe/`: `pnpm -s typecheck` and `pnpm -s exec eslint src/features/inventory` clean;
the four Inventory unit-test files report **57 passed, 0 failed**.

