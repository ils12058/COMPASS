# PG-1A PR 2 Implementation Report: Code-Owned Retention & Read-Only DPO Oversight

- Date: 2026-10-16
- Repository: `ils12058/COMPASS`
- Base: `origin/staging` `5b67b550a315d71c14e38b4f86104b251a47e89c` (PG-1A PR 1, #244)
- Branch: `feat/pg-1a-code-owned-retention-oversight`
- Worktree: `/Users/reynantlntno/Projects/COMPASS-PG-1A-PR2`
- Decision record: ADR-115 (new). ADR-114, ADR-072 and ADR-092 headers point to it.
- **Merge and CI.** The owner asked for the merge without waiting for CI and for the remaining local
  tests to be skipped. Some checks below are therefore marked "not run".
- **Not deployed.** No live system was touched.

## A. Baseline and scope

The following were reviewed:

- the audit deliverables in `../COMPASS-PG-1A-AUDIT/outputs/pg-1a/`;
- ADR-069, ADR-072, ADR-092 and ADR-114;
- the merged #244 code (tombstones, fail-closed services, preflight command);
- the retention router, the identity policy and sync, the activity presentations, the frontend
  workspace and Student copy, and `deploy-staging.yml`.

Where the owner's locked decisions differ from the audit's optional design (digest lock, deploy-sync
audit event, legacy history page), the locked decisions win. The register is the minimal six-field
contract, and there is no history page.

## B. Code-owned register

**Module.** `be/compass/privacy_governance/retention_policy_register.py`. It holds frozen
dataclasses with no Django imports (imports are limited to `dataclasses`, `datetime` and `enum`).
It has no model, table, setting, environment variable or API write.

**Fields.**

| Field | Type |
| --- | --- |
| `category_code` | `RetentionPolicyCategory` |
| `category_label` | `str` |
| `adoption_status` | `RetentionAdoptionStatus` (`NOT_ADOPTED` or `ADOPTED`) |
| `retention_period` | `str \| None`; verbatim schedule wording, never parsed |
| `policy_reference` | `str \| None` |
| `effective_date` | `date \| None` |

**Initial entries.** Each is `NOT_ADOPTED`, with every term `null`:

- `GRADUATE_TRACER`: Graduate Tracer responses
- `ECOUNSELING_RECORDING`: E-Counseling recordings
- `ECOUNSELING_TRANSCRIPT`: E-Counseling transcripts

Legacy contract versions 1 and 2 collapse into one entry per category. No legacy trigger, duration,
action or rule is copied into the register.

**Validation**, which fails at import:

- types are exact, with no raw strings for enums and no datetime for a date;
- labels are nonblank, unpadded and bounded;
- `NOT_ADOPTED` rejects any period, reference or date, including `""`, `"0 days"` and `"N/A"`;
- `ADOPTED` requires nonblank period wording, a reference and an explicit `date`;
- categories are unique, and the register must be a nonempty tuple of entries.

**Policy-source limitation.** Code can require an adoption's terms, but it cannot verify that an
approval is genuine. Review of a change citing the institutional source is the control.

**Non-enforcement.** An AST test confirms that the only consumer is the read-only route. The register
does not query records, create cases, schedule tasks, anonymize or delete.

## C. Capability changes

**Retained.** `privacy_governance.retention.view`, now named "View retention policy oversight": "View
the code-owned retention policy register. Grants no rule, hold, approval, or disposition authority."
The DPO designation keeps it.

**Retired.** `privacy_governance.retention.manage` and `.approve`:

- removed from `CAPABILITY_DEFINITIONS`, the DPO grants and `CAPABILITY_DEPENDENCIES`;
- added to `RETIRED_CAPABILITY_CODES`. The three earlier retired codes are kept.

**Sync.** A test seeds pre-ADR-115 state, then runs sync twice:

- The seeded state has the retired rows, the DPO and Institutional Officer grants, a user override,
  and the old view name.
- The first sync deletes 2 role grants, 2 designation grants, 2 overrides and 2 capability rows, and
  updates the view capability's name.
- Unrelated grants and overrides are unchanged.
- A second sync reports zero changes.
- Historical AuditEvents are byte-identical; each sync only appends its `identity.policy.synced` event.

**Negative authorization (all tested).**

- The DPO's effective capabilities are exactly the activity export, `privacy_governance.view`,
  `privacy_governance.manage` and `.retention.view`.
- `set_capability_override` rejects either retired code with `InvalidManagementInput`, including
  when an IT Admin attempts it.
- No IT Admin, Counselor, GSS, Student, plain Institutional Officer or Head gains any
  `privacy_governance.*` capability.
- A REVOKE override removes the DPO's view, and a GRANT override gives read-only view.
- Privacy Notices and Privacy & Security Activity stay available to the DPO.

## D. API changes

**New.** `GET /api/v1/privacy/retention/policies`, operation `privacyGovernanceListRetentionPolicies`:

- session-authenticated, with `privacy_governance.retention.view` required;
- responses are `{items: [...]}` with 200, 401 and 403;
- strict schemas `RetentionPolicyRegisterResponse` and `RetentionPolicyEntryResponse`, plus the enums
  `RetentionPolicyCategory` and `RetentionAdoptionStatus`;
- it reads no `privacy_governance_`, `ecounseling_` or `graduate_tracer_` table (asserted on
  captured SQL);
- it dispatches nothing;
- POST, PUT, PATCH and DELETE return 405.

**Removed: 14 operations**, all now returning 404:

- `privacyGovernanceRetentionCategories`, `privacyGovernanceRetentionSummary`;
- rules: `privacyGovernanceListRetentionRules`, `CreateRetentionRule`, `GetRetentionRule`,
  `UpdateRetentionRule`, `ActivateRetentionRule`, `RetireRetentionRule`;
- cases: `privacyGovernanceListDispositionCases`, `GetDispositionCase`, `PlaceDispositionHold`,
  `ReleaseDispositionHold`, `ApproveDispositionCase`, `RetryDispositionCase`.

Their request and response schemas are gone from the contract. This holds for the DPO with recent
MFA and for a view-override holder. No dispatch, no `on_commit` callback and no ledger change occurs.

**Route inventory.** There are 355 registered operations, all documented, and none is excluded from
the schema. `retention_api` has exactly one route. No production module calls the PR 1 fail-closed
services, which stay as the PR 3 fallback.

**Contract.** `contracts/openapi.json` was regenerated (+235 / −1996 lines). The `CapabilityCode`
enum loses the two retired codes. Generated clients (`pnpm api:generate`) are untracked, and they
typecheck clean.

## E. Frontend

**New page.** `/portal/privacy/retention` is "Retention Policies", built in
`retention-policies-page.tsx`:

- the requested intro text;
- one row per category with an Adopted or Not adopted badge;
- "No adopted retention policy has been recorded in COMPASS for this category.";
- recorded terms shown only when adopted, with no "0 days" or "N/A";
- one visible line: "COMPASS doesn't delete or anonymize records under these policies…";
- a Help dialog covering code ownership, the read-only role and external disposition;
- shared `PageHeader`, `Panel`, loading, error with Retry, refresh-failure and unavailable states;
- no buttons except Help, and no forms.

**Removed.**

- The rule editor, rule list, case page, summary and dashboard, the hold, approve and retry dialogs,
  and `retention-shared.tsx`.
- The access helpers `canManageRetention` and `canApproveDisposition`.
- The retention error copy (`retention_state_changed`, `invalid_retention_rule`,
  `invalid_disposition_hold`).
- The command-palette entries "Retention Rules" and "Create Retention Rule".
- The `/rules`, `/rules/new`, `/rules/[ruleId]` and `/cases/[caseId]` routes. A
  `retention/[...legacy]` page now redirects them to the overview. There is no Disposition History
  page.

**Navigation.** The tab, landing card and palette entry now read "Retention Policies"; the landing
description is "Retention policy status recorded in COMPASS."

**Student and staff copy.**

- The consent withdrawal dialog now reads: "Withdrawing doesn't delete files already created. They
  remain subject to the University's records and privacy requirements, and copies already downloaded
  can't be recalled."
- V2 session help now reads: "…stops affected capture but doesn't delete files already captured.
  They remain subject to the University's records and privacy requirements; COMPASS doesn't delete
  them automatically after a set period."
- Both are verified against `withdraw_my_consent`, which stops capture and storage but never
  deletes. Consent behavior itself is unchanged.

**Historical wording.** The descriptions of four historical activity events are now past tense, so
none reads as an available operation:

- rule activated;
- hold placed;
- hold released;
- disposition unresolved.

Their titles and codes are unchanged. "Deleted under an approved retention rule" on disposed
historical media and tracer rows is unchanged, because it accurately describes past outcomes.

## F. Historical evidence

- No migration (`makemigrations --check`: no changes).
- These are unchanged:
  - the `OperationalRetentionRule`, `DispositionCase` and `DispositionHold` tables;
  - AuditEvents;
  - anonymous Graduate Tracer contributions and disposed-participation markers;
  - disposed E-Counseling markers.
- The legacy ledger is no longer served by any route. Tests assert that its rows, holds and blockers
  are intact.
- `DispositionCase.source_id` stays internal and is never serialized.
- The E-Counseling webhook, ingestion and reconciliation fences, `delete_v2_provider` and the custody
  cleanup code are unchanged.
- The PR 1 tombstones and the 409 fallback services are unchanged; their tests pass.

## G. Tests

All runs used synthetic data, against disposable PostgreSQL 17.11 (:5452) and Redis 8.10.1 (:6392).

| Check | Result |
| --- | --- |
| `tests/test_retention_policy_register.py` (new) + `tests/test_operational_retention.py` (updated) | **82 passed** |
| Combined backend batch: register, decommission, accounts, authentication, privacy governance, contract, expansion, activity, pending acknowledgment, release audit, capability dependencies, account management and OpenAPI contract | **234 passed, 7 failed.** All 7 also fail on the staging-identical tree; see below. |
| `ruff check` / `ruff format --check` on changed backend files | clean |
| `manage.py check`, `makemigrations --check --dry-run`, `export_openapi --check` | ok, no changes, current |
| `backend_ci.py verify` | only inherited files missing a bundle: `test_domain_activity.py`, `test_good_moral_assisted.py`, `test_graduate_tracer_graduation_classification.py`. The new file is registered. |
| `pnpm typecheck`; ESLint on changed files | clean |
| `pnpm test` (frontend unit) | **763 / 764**. The 1 failure is inherited (see below). The new `retention-policies.test.mjs` passes 6 of 6. |
| `ui-information-hierarchy.browser.mjs`, Chromium | **18 / 18**, including the Retention Policies checks at desktop and 390 px, Help keyboard (Escape), GET-only privacy requests, and redirects from three legacy bookmarks |
| `user-copy.browser.mjs`, Chromium | **42 / 44**. `retention-unavailable` passes at 320 and 1440 px. The 2 Good Moral failures are not retention-related. |
| `user-copy.browser.mjs`, WebKit | stopped partway at the owner's request. `retention-unavailable` passed at 320 and 1440 px; the 2 Good Moral checks failed as in Chromium. |
| `git diff --check` | clean |

**Inherited failures, identical on the base tree** (the PR 1 worktree, same tree as `5b67b550`):

- `test_accounts::test_policy_sync_is_idempotent…`: pins 93 role grants; there are actually 95,
  because of `good_moral.initiate` from #243.
- `test_accounts::test_effective_capabilities_combine…`: `good_moral.initiate`.
- `test_privacy_release_audit::test_graduate_tracer_xlsx_release…`: the graduation filters from #242
  and #243.
- `test_openapi_contract`, four tests: missing operation IDs (355 vs 351, the same gap of 4 as
  before), tracer filters, and capability ordering (`good_moral.initiate`, `student_support.view`).
- Frontend `user-copy.test.mjs` "Raw API message reading…": `good-moral-assisted-request.ts` (#243)
  is not in the allowlist.

The capability count pins I touched in `test_accounts` were set to the real post-PR values: 78
capabilities and 20 designation grants. The stale pin of 93 role grants is left alone, so its
inherited failure stays visible.

**New regressions:** none observed in the suites that ran.

**Not run, because the owner said to skip:**

- the full 6-shard backend suite;
- the E-Counseling media, realtime and Graduate Tracer suites;
- `ecounseling-call.browser.mjs` (its withdrawal assertion is updated);
- `ui-information-hierarchy` in WebKit;
- the rest of `pnpm test:ui:regressions`;
- `pnpm build` and `pnpm lint` on the whole repo.

Those backend suites are not touched by this diff; the media and tracer code is unchanged.

## H. Deployment gate

- **The live-staging preflight is still unresolved.** No authorized operator has run ADR-114's G1–G10
  on live staging (build `0512e9ec`). Approved or queued cases need review by authorized
  institutional personnel; a DPO approval is not sufficient.
- **Release order**, from `deploy-staging.yml`. Steps 2–4 run as one-off containers while the old web,
  worker and Beat keep running:
  1. Read-only preflight.
  2. `migrate`. This PR adds none, but staging bundles other undeployed migrations, such as the
     Good Moral initiation provenance migration.
  3. `sync_identity_policy`. It must show the two retired retention codes deleted; compare with the
     G9 counts. Sync deletes these grants while the old web is still running, so in the overlap the
     old web fails closed.
  4. `up -d`.
  5. Backend health checks.
  6. Frontend `vercel --prod`.
  7. Post-deploy checks: the register returns three `NOT_ADOPTED` entries, 404 on retired routes, the
     tombstones are registered, there is no `retention-*` Beat entry, Notices and Activity work, and
     custody cleanup continues.
- **Version mixing.** An old frontend on the new backend gets 404 on the retired routes and cannot
  mutate. The new frontend on an old backend shows the safe error state.
- **Rollback.** Rolling back re-creates the retired grants through sync, but not the purged
  overrides. PR 1's refusal still blocks every mutation.
- **PG-1A PR 3, not started:**
  - remove the tombstones after a drained broker is verified;
  - remove the fallback services and `SUPPORTED_CONTRACTS`;
  - optionally add database write protection to the legacy tables;
  - move the restore-boundary documentation.
