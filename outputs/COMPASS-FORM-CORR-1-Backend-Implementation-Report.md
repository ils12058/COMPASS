# COMPASS FORM-CORR-1 PR 1 — Backend Correction Targets: Implementation Report

**Slice:** PR 1 of 3. Backend foundation only: no Student or reviewer interface.
**Design:** audit Option **A2**. Existing reopen events gain a separately encrypted, revision-aware list of correction targets.
**Evidence:** [validation evidence](COMPASS-FORM-CORR-1-Backend-Validation-Evidence.json). The audit artifacts live in the audit worktree (`/Users/reynantlntno/Projects/COMPASS-FORM-CORR-1-AUDIT/outputs/`).

---

## 1. Baseline

| Item | Value |
|---|---|
| Staging baseline | `fea0f3c483d5fade22457efba6b73aed8d1893ce` (FORM-UI-1B #235 squash commit) |
| Staging moved since the audit? | **No.** `origin/staging` was re-fetched before branching and was still `fea0f3c4`, so there was nothing to reconcile |

## 2. Worktree and branch

| Item | Value |
|---|---|
| Worktree | `/Users/reynantlntno/Projects/COMPASS-FORM-CORR-1-BE` (new) |
| Branch | `feat/form-corr-1-backend-targets` (new, from the baseline) |
| Untouched | The audit worktree, the FORM-INPUT-1A worktree (`.claude/worktrees/form-input-1a`), and the main checkout |
| Test resources | Disposable `corr1-be-pg` (PostgreSQL 17.11) on `127.0.0.1:55434` and `corr1-be-redis` (Redis 8.10.1) on `127.0.0.1:56381`, with audit-only database names. Removed afterwards |

## 3. Files changed

| File | Change |
|---|---|
| `be/compass/inventory/correction_targets.py` | **New.** Inventory catalog (148 codes), coverage map, exclusions, normalization, read projection |
| `be/compass/exit_interviews/correction_targets.py` | **New.** Exit Interview catalog (68 codes), revision-aware `allowed_correction_targets`, normalization, read projection |
| `be/compass/inventory/models.py`, `be/compass/exit_interviews/models.py` | `targets_ciphertext` on each reopen-event model |
| `be/compass/inventory/migrations/0008_inventoryreopenevent_targets_ciphertext.py` | **New.** Additive column |
| `be/compass/exit_interviews/migrations/0006_exitinterviewreopenevent_targets_ciphertext.py` | **New.** Additive column |
| `be/compass/inventory/confidential_content.py`, `be/compass/exit_interviews/confidential_content.py` | Separate targets envelope: write, read, rewrap. Unavailable errors name the targets envelope |
| `be/compass/inventory/services.py`, `be/compass/exit_interviews/services.py` | Reopen accepts `targets`; validation inside the existing transaction; EI saved-revision guard (T-8) |
| `be/compass/inventory/api.py`, `be/compass/exit_interviews/api.py` | Optional request `targets`; `latest_correction.targets` (Inventory); `reopen_events[].targets` (EI); EI reason `minLength 1 / maxLength 1000` |
| `be/compass/{inventory,exit_interviews}/management/commands/rotate_*_confidential_content.py` | New correction-targets pass |
| `contracts/openapi.json` | Regenerated: two new enums, four schemas extended |
| `be/tests/test_inventory_correction_targets.py`, `be/tests/test_exit_interview_correction_targets.py` | **New.** 29 + 24 tests |
| `be/tests/test_inventory_counselor_review.py` | `latest_correction` key set now includes `targets` (asserted `[]` for a reason-only request) |
| `be/tests/test_inventory_confidential_content_encryption.py`, `be/tests/test_exit_interview_confidential_content_encryption.py` | Rotation output counts one more envelope line: 7→8 and 3→4. Five legacy migration tests now step to the new additive migration before reading through current models and assert the column is `''`, following the FORM-ID-1 precedent for EI `0005`. The Inventory reverse-corruption test stays exactly at the `0007` boundary and selects only the column it corrupts |
| `be/tests/test_openapi_contract.py` | Inventory correction-summary expectation includes `targets`. New assertions cover the optional request `targets`, the EI reason limits, and the history-event `targets` |
| `.github/scripts/backend_ci.py` | Registers the two new test files in their existing `inventory` and `exit-interviews` CI bundles |
| `outputs/COMPASS-FORM-CORR-1-Backend-*.{md,json}` | This report and the validation evidence |

**Not changed:**

- Frontend source.
- Form layout, PDF templates and notification wording.
- Permissions and identity policy.
- FormRevisions.
- Encrypted answer schemas.
- Good Moral files.

The generated frontend client (`fe/src/lib/api/generated`, git-ignored) was regenerated locally to check compatibility and is not committed, as in previous PRs.

## 4. Final catalog design

**Ownership:**

- Each domain owns a `StrEnum` in `correction_targets.py`. Enum order is the canonical order.
- OpenAPI publishes the enums as `InventoryCorrectionTarget` and `ExitInterviewCorrectionTarget`.
- Each module's docstring records the compatibility rules: append-only; never renamed, reused or removed; no answer values, positions, row ids or element ids.

**Coverage contract:** `TARGET_COVERAGE` maps every non-section code to the payload answers it stands for. Tests assert three things:

1. Every editable answer in the update schema is covered by **exactly one** code, or appears in an explicit exclusion.
2. No answer is covered twice.
3. Section codes cover no keys.

**Inventory (148 codes, all Form Revisions share answer schema 1):**

- **8 section codes:** `section.personal` … `section.plans`. These are the editor sections; there is no code for `review`.
- **Question codes:** for example `personal.date_of_birth`. A category and its "Other" detail share one code, as in `personal.civil_status`, `health.pwd_status` and `plans.prior_counseling`.
- **Natural-key codes:**
  - `family.{father|mother|spouse}.<question>`, 15 questions per member.
  - `education.history.<level>`.
  - `organizations.transportation.<mode>`.
  - `personal.{current|permanent}_location`.
- **List codes:** `background.siblings`, `organizations.inside_school`, `organizations.outside_school`. There are **no per-row codes** (P-8).
- **`EXCLUDED_ANSWERS`** (P-9): `student_number`, which is account-owned and copied from the account on every save, and `course_currently_enrolled`, which is derived from the Program and covered by `education.program`.

**Exit Interview (68 codes, spanning every supported saved contract):**

- **5 section codes.**
- **General information:** 8 codes.
- **Section I:** program completion, extra terms, delay reasons (+ Other), learning experiences (+ Other), `career.work`, `career.study`.
- **Self-Assessment:** 15 codes using the fixed item codes, for example `self_assessment.SELF_ESTEEM`.
- **College Feedback:** 26 codes (`college_feedback.<ITEM_CODE>`), plus 7 comment codes (`college_feedback.comments.<category>`).
- **Suggestions:** `suggestions.suggestions_recommendations`.
- **`allowed_correction_targets(item)`** narrows the catalog to one record by reusing `college_feedback_codes(item)`:
  - UCN F9 → **64** allowed. The three Program Chair ratings and the Program Chair comment are excluded.
  - Legacy null revision → all **68**.
  - A comment code is allowed only when its category has at least one allowed rating.

**Generated TypeScript:** orval drops the dots in the generated object keys (`personalfull_name`). The type is the union of the values, so PR 2 and PR 3 should key their maps by **value**, for example `Record<InventoryCorrectionTarget, …>` with `'personal.full_name'`. TypeScript typecheck passed, so no key collisions exist.

## 5. Fields and target-count boundaries

| Rule | Where | Behavior |
|---|---|---|
| At most 30 submitted selections (T-3) | Request schema `maxItems: 30` and the service | Counted **before** de-duplication. 31 → 422 |
| De-duplicate | Service | Repeats collapse |
| Canonical order | Service | Stored and returned in catalog order |
| Empty or omitted | Schema default `[]` | Accepted; no target ciphertext written |
| Unknown or non-catalog code | Schema enum (API) and service | 422 |
| Code not on the record's saved revision (EI) | Service, inside the lock | 422 `invalid_exit_interview_request` |
| Read-side sanity bound | Envelope reader | Up to 256 well-formed codes accepted, so codes or limits from a newer build never read as corruption |

Error messages never repeat submitted values. The validation-error handler returns only `loc` and `msg` (`compass/common/errors.py`), so an enum error lists the allowed values but never echoes the submitted one.

## 6. Database migrations

| Migration | Operation | Depends on |
|---|---|---|
| `inventory/0008_inventoryreopenevent_targets_ciphertext` | `AddField targets_ciphertext TextField(blank=True, default="", editable=False)` | `inventory/0007_remove_plaintext_confidential_content` |
| `exit_interviews/0006_exitinterviewreopenevent_targets_ciphertext` | Same | `exit_interviews/0005_saved_form_revision` |

**Generated SQL** (`sqlmigrate`), the same for each table:

```sql
ALTER TABLE "<table>" ADD COLUMN "targets_ciphertext" text DEFAULT '' NOT NULL;
ALTER TABLE "<table>" ALTER COLUMN "targets_ciphertext" DROP DEFAULT;
```

The column is **NOT NULL** with no lasting database default; Django supplies `""`. Neither migration creates a table, touches the reason column, backfills data, migrates permissions, changes a FormRevision or replaces a key.

**Verified PostgreSQL 17.11 behavior** (evidence JSON, `migration_checks`):

- **No table rewrite.** `pg_relation_filenode` was unchanged across the forward migration, both on a disposable database and in the upgrade-path tests that contain existing reopen events. `pg_attribute.atthasmissing = true` shows PostgreSQL's constant-default fast path: existing rows read `''` without being rewritten.
- **A lock is required.** `ADD COLUMN` needs a brief `ACCESS EXCLUSIVE` lock. With a concurrent session holding only `AccessShareLock` (an ordinary reader), the DDL failed with `canceling statement due to lock timeout` under `lock_timeout = '500ms'`. In production it waits behind any open transaction on the table and blocks new access to that table while it waits.
  - **Recommendation:** run the migrations at low activity. They are near-instant once the lock is granted.
- **Upgrade path.** A reopen event created before the column existed survives the migration. Its reason ciphertext is byte-identical, its targets column reads `''`, and the API returns `targets: []`. Both domains have a transactional test for this.
- **Fresh database.** A full `migrate` from empty applies both migrations. `makemigrations --check` reports no changes.

## 7. Encryption design

**Envelope:**

- The payload is `{"targets": [code, …]}`, encrypted with the existing `encrypt_bound_json` / `decrypt_bound_json` and the **domain's existing keyring**.
- The envelope has `schema_version=1`. No new key or algorithm is introduced.

**Binding**, which is authenticated inside the token:

| Domain | Binding |
|---|---|
| Inventory | `{"inventory_id", "reopen_event_id", "content": "correction_targets"}` |
| Exit Interview | `{"exit_interview_id", "reopen_event_id", "content": "correction_targets"}` |

`decrypt_bound_json` requires the envelope's key set to match exactly. That rules out four transplants (all tested):

| Transplant | Result |
|---|---|
| Different correction event, or different record | `binding_mismatch` |
| Reason ↔ targets columns | `malformed` in both directions. The `content` key and the payload shape each reject it independently |
| Inventory ↔ Exit Interview | `undecryptable` (separate keyrings), or `malformed` even if the same key were configured, because the binding names differ |

**The reason envelope is unchanged:** same key set, payload and bytes. The audit showed that today's readers reject any extended reason envelope; this design never produces one.

**Empty versus unreadable:**

- `""` means "no targets" and is never decrypted. A test replaces the decrypt function with one that fails and confirms it is never called.
- Any non-empty value is decrypted and validated:
  - It must be a list of 1–256 unique codes, each matching `[A-Za-z0-9_.-]{1,128}`.
  - A failure raises the domain's existing `…ConfidentialContentUnavailable`. Inventory reports family `InventoryReopenEventTargets`; Exit Interview sets `content="correction_targets"`.
  - The API returns the existing generic 500 (`inventory_confidential_content_unavailable` / `exit_interview_confidential_content_unavailable`). A failure never silently becomes an empty list, and the response contains no ciphertext.

## 8. Request validation

| | Inventory `POST /api/v1/inventory/records/{id}/reopen` | Exit Interview `POST /api/v1/exit-interviews/{id}/reopen` |
|---|---|---|
| `reason` | Unchanged: required, 1–1000 | **Now** `minLength 1`, `maxLength 1000` in the contract, matching Inventory (T-7). The service still strips whitespace and requires text, so `"   "` → 422 as before |
| `targets` | Optional, default `[]`, ≤ 30, catalog enum | Optional, default `[]`, ≤ 30, catalog enum |
| Order of checks | Capability (API + service) → scope (404) → current year / submitted / current Student → **targets** → write | Capability (API + service) → submitted / current Student → **saved-revision support (T-8)** → **targets on that revision** → write |
| Partial writes on invalid input | None: no event, audit or notification (tested) | None (tested) |
| Locking | Unchanged `select_for_update` on the record | Unchanged lock order: owner, then record |

**EI reason contract edge:** the API now rejects a raw reason over 1000 characters even if trimming would bring it under. Inventory already behaves this way. The current Head dialog trims before sending, so it never produces such a value.

## 9. API response contracts

**Inventory:**

- `InventoryCorrectionSummary` (the existing `latest_correction`) gains a required `targets: InventoryCorrectionTarget[]`.
  - Pending with targets → codes.
  - Pending without targets → `[]`.
  - No pending correction → `latest_correction: null`, unchanged.
- No top-level Inventory property was added (T-10). A test round-trips `GET /me/current` → strip envelope fields → `PUT /me/current` and gets **200**.
- Lists, history and Counselor views carry no correction content, as before.

**Exit Interview:**

- `ReopenEventResponse` gains a required `targets: ExitInterviewCorrectionTarget[]`. Every earlier event returns `[]`.
- Timestamps, `reopened_by` and the audiences (owner Student, Head) are unchanged.
- Ordinary Counselors and Guidance Services Staff get 403. Another Student gets 404.

**Unknown stored codes (T-5):**

- Codes that the running build doesn't recognize are dropped from the response. Known codes are kept in stored order.
- The ciphertext is never rewritten: a test compares the raw row before and after the read.
- A single structural warning is logged:
  - `inventory_correction_targets_omitted` or `exit_interview_correction_targets_omitted`.
  - Fields: `target_type` and `target_id` (the reopen-event UUID), all already on the logging allowlist.
  - No codes, reasons or counts.

## 10. Saved-revision compatibility (T-8)

`reopen_for_correction` now calls `allowed_correction_targets(item)`, which uses `college_feedback_codes(item)`, **before** creating the event, whether or not targets were sent.

- A record whose saved Form Revision is not supported returns `409 exit_interview_conflict`, stays `SUBMITTED`, and gets no event. Previously it could be reopened into a draft the Student could not save.
- UCN F9 and legacy null-revision records reopen exactly as before.
- Historical records are never relabelled. Program Chair ratings and comments stay intact; a test confirms 26 ratings before and after.
- Rating `0` is untouched and still has no label. A zero-rated row can be targeted, and the draft resubmits unchanged.

## 11. Authorization invariants

| Actor | Inventory reopen (with targets) | Exit Interview reopen (with targets) |
|---|---|---|
| Counselor within college scope | 200 | 403 |
| Counselor outside scope | 404 (service: `InventoryNotFound`) | 403 |
| Counselor with `inventory.reopen` revoked | 403 (service: `InventoryNotPermitted`) | — |
| Head Guidance Counselor | 200 (unscoped) | 200 |
| Guidance Services Staff | 403 | 403 |
| Student | 403 | 403 |
| IT Admin | 403 | 403 (existing test) |

- No capability, role or designation changed.
- Targets are read only in `_correction` (Inventory) and `_reopen_events` (EI), the same paths and audiences as the reason.

## 12. Legacy-event behavior

- Every reopen event that exists before deployment has `targets_ciphertext = ''` after migration. These read as `targets: []` with no decryption.
- Reason-only requests from existing clients keep working and store `''`.
- Multiple cycles:
  - **Inventory:** only the latest pending event is shown, so earlier targets never carry over. A test reopens with targets, resubmits, then reopens reason-only and gets `[]`.
  - **Exit Interview:** each history entry shows its own targets.

## 13. Rotation coverage

Both commands now report one extra line for the targets envelope:

```
InventoryReopenEventTargets: scanned N; empty E; current C; rotated R; failures F
Reopen Event correction targets: scanned N; empty E; current C; rotated R; failures F
```

| Case | Result (tested) |
|---|---|
| Valid previous-key ciphertext | Rewrapped with `MultiFernet.rotate`. Plaintext bytes and the original Fernet timestamp are preserved. Binding verified before rewrapping |
| Empty column | Counted as `empty`; never decrypted or written |
| Already on the primary key | Counted as `current` (idempotent rerun) |
| Corrupt token / wrong binding | Counted as failures and listed on stderr with ids and the failure reason only, never the token. Left byte-identical. The command exits non-zero |
| Partial failure | The other rows still rotate. The existing batch commit and resume behavior is unchanged |
| Reason rotation | Unchanged; the existing tests still pass |

No key was rotated or retired in any shared environment.

## 14. Deployment and rollback

**Deployment order** (not executed):

1. Apply both migrations (`migrate`), preferably at low activity because each needs a brief `ACCESS EXCLUSIVE` lock. No `sync_identity_policy` is needed: no capability changed.
2. Deploy this backend.
3. Verify on staging with synthetic accounts:
   - A reason-only reopen in both domains still works and returns `targets: []`.
   - A target-aware reopen through the API returns canonical codes to the Student.
   - F9 rejects Program Chair codes.
4. Deploy the PR 2 and PR 3 frontends separately after approval. Today's frontend ignores the new fields and sends no targets.

**Rollback (conservative):**

- **Prefer an application-only rollback that keeps both columns.** The previous code ignores `targets_ciphertext` and reads reasons exactly as before, because the reason envelope never changed. Structured targets are hidden while rolled back but kept.
- **Do not reverse the migrations** after any target-bearing event exists. Dropping the column permanently discards those targets. The narrative reasons survive.
- **Do not retire encryption keys while rolled back.** The previous rotation commands do not scan `targets_ciphertext`, so targets would stay on the old key. Re-deploy this code before retiring keys.
- **Re-deploying after a rollback is safe.** Any events created meanwhile have `''` (no targets).
- Lossless rollback of the schema itself is not promised.

## 15. Tests and results

Every run used disposable services. Exact commands are in the evidence JSON.

| Check | Result |
|---|---|
| New Inventory target tests (`test_inventory_correction_targets.py`) | **29 passed** |
| New Exit Interview target tests (`test_exit_interview_correction_targets.py`) | **24 passed** |
| Existing correction suites (`test_inventory_counselor_review.py`, `test_exit_interviews.py`, both encryption suites, `test_exit_interview_opportunities.py`) | Pass, after the documented expectation updates |
| **Full backend suite (3 parallel shards, 164 files, 4,519 tests)** | Shard 0: 7 failed, 2,362 passed (66:50). Shard 1: 8 failed, 1,144 passed, 17 errors (21:43). Shard 2: 26 failed, 950 passed, 5 errors (22:31) |
| Failures introduced by this PR | **6, all fixed and rerun green.** Five legacy migration tests read current models at a migration state without the new column; they now apply the additive migration first (11 node ids, 270.9 s, all pass). One contract expectation (`test_inventory_frontend_readiness_openapi_contract`) now includes `targets`; `test_openapi_contract.py` reruns as 35 passed with only the 3 inherited failures |
| Inherited failures (identical on the untouched baseline `fea0f3c4`, rerun in a temporary detached worktree) | **57:**
- 51: demo seed `SCENARIO_ALUMNI` (`graduated_college is required before submission`).
- 3: `test_openapi_contract` graduate-tracer / operation-count checks.
- 1: `test_privacy_release_audit` graduate-tracer xlsx check.
- 2: `test_audit` rollback-count tests. These fail the same way when `test_audit.py` runs alone on both baseline and branch. |
| GitHub Actions on #237 | Every failing job is inherited from staging:
- `prepare` fails on the inherited CI-bundle gap for `test_graduate_tracer_graduation_classification.py`. That gate also skips CI's backend test steps, so the local runs above are this PR's test evidence.
- `static and contract` fails on the same 8 unformatted graduate-tracer/report files.
- `frontend-browser-regressions` fails on the #231 `My work31` / `My work22` badge checks.

`frontend-tests` and `targeted-frontend` pass. |
| `makemigrations --check --dry-run` | No changes detected |
| `manage.py check` | No issues |
| `export_openapi --check` | Contract is current |
| Ruff on changed and new files | Clean. Repository-wide `ruff format --check` / `ruff check` still flag **8 files and 38 lint findings outside this change** (graduate tracer, reports, guidance-messages tests); these are inherited from staging |
| Fresh-database `migrate` | Both migrations applied |
| Lock / rewrite verification | See §6 |
| Frontend `pnpm api:generate`, `pnpm typecheck`, `pnpm lint` | Pass (lint: 4 pre-existing warnings, no errors) |
| Frontend unit tests (`node --test tests/*.test.mjs`) | **718 passed, 0 failed** |
| Mutation spot-check | Disabling the T-8 guard makes the unsupported-revision and F9 Program Chair tests fail. Removing the `content` binding key alone does not: payload-shape validation independently rejects reason↔targets swaps (defense in depth), and the envelope test asserts the key directly |
| `git diff --check` | Clean |

**Privacy regression coverage, both domains:**

- Target codes and the reason are absent from:
  - Notification title and message, the rendered email, and the push body.
  - Audit metadata (no key containing `target`).
  - Student Actions JSON.
  - Captured log records (formatted with the production `JsonFormatter`).
  - The PDF after resubmission (text extracted with `pypdf`).
  - Unauthorized and other-reader responses.
  - Raw reopen-event rows.

## 16. Remaining slices

1. **PR 2 — Inventory frontend:**
   - Reviewer chooser in the existing reopen dialog; Student "Answers to review" list inside the existing notice.
   - Navigation through `selectIssue`; the 9 missing Inventory control ids; opening the Family details section; fallback anchors.
   - Key maps by enum value.
2. **PR 3 — Exit Interview frontend:**
   - Revision-aware chooser from `college_feedback_item_codes`, a reason counter, Student navigation that focuses the checked radio, history labels, and the program-completion fieldset id.

## 17. Remaining institutional decisions

None block this PR. The owner's directions P-1…P-12 and T-1…T-10 were applied as engineering directions, not as formal GCO/QMS policy approval. Three items remain open for later:

- Student and reviewer wording for PR 2 and PR 3 (audit P-6 / P-7), to confirm when the interfaces are reviewed.
- Inventory correction-history visibility (P-5): deferred.
- Academic Year rollover for reopened Inventories (P-12): deferred.
