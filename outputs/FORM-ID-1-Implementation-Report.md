# FORM-ID-1 implementation and release evidence

The approved UCN identities are implemented for F2–F7 and F9. Five superseded CNSC identities remain supported for historical records. Customer Feedback retains CNSC F14 Revision 0. The change includes saved F7/F9 revision binding, an additive F9 migration, exact saved-identity PDF guards, source-specific presentation changes, and version-aware F9 validation/display. No merge, deployment, staging reset, production migration, institutional-record deletion, or key provisioning was performed.

## Audited staging and source authority

Initial staging: `40492b1aacca7b608c1cf8bc0a4aef618d9d78f1`. Updated staging base after navigation PR #231 landed: `d6ce342dab9b5721b38d508984c7785152453078`. The branch was rebased onto the updated base and its OpenAPI client regenerated. Navigation implementation is outside this PR's diff.

The nine approved specimens were read from the owner's supplied DOCX files and rendered with the documents runtime for visual comparison. [Approved source matrix](FORM-ID-1-Approved-Source-Matrix.json) records exact filenames and SHA-256 hashes. F1 and F8 are source-only; no application workflows were added.

| Family | Active identity | Answer schema | Compatibility decision |
|---|---|---:|---|
| Call Slip | UCN-OP-GCO-01F2 Rev 2 | 1 | Printed Revision 2 overrides filename Rev 1. UCN renderer 2 retains source paper fields and wording; digital answer schema unchanged. |
| Referral Slip | UCN-OP-GCO-01F3 Rev 1 | 1 | Existing answers/actions fit; UCN renderer 2 restores source signature/date wording. |
| Good Moral current Student | UCN-OP-GCO-01F4 Rev 1 | 1 | UCN renderer 2 removes the extra course insertion absent from approved wording. Receipt and signature fields remain. |
| Individual Inventory | UCN-OP-GCO-01F5 Rev 1 | 1 | Existing answer schema fits; exact supported identity guard accepts UCN and CNSC history. UCN headings match approved source; CNSC transportation wording remains. |
| Good Moral graduate | UCN-OP-GCO-01F6 Rev 1 | 1 | Existing certificate wording, degree/major/date, receipt and signature fit. Renderer 1 reused. |
| Routine Interview | UCN-OP-GCO-01F7 Rev 1 | 1 | Questions 1–7, concern options, six 1–10 adjustment ratings and text fields fit. New scheduled/direct records bind F7. No PDF added. |
| Exit Interview | UCN-OP-GCO-01F9 Rev 1 | 2 | Approved source omits Program Chair: 15 self-ratings, 23 College ratings, six categories. Null-revision history retains 26 College ratings and seven categories. Renderer 2. |
| Customer Feedback | CNSC-OP-GTA-01F14 Rev 0 | 1 | No UCN replacement supplied; existing active identity and optional respondent identity stay operational. |

Official revision, internal answer schema and rendering version are distinct. F2 official Revision 2 uses answer schema 1. F9 schema 2 reflects a verified answer-contract change, not its official Revision 1.

## Registry, creation and historical ownership

`canonical.py` defines eight families, thirteen exact supported revision identities, and eight active definitions. Synchronization creates missing legacy and UCN rows, retires obsolete/unknown active rows, preserves IDs and references, and is idempotent. Schema conflicts under an existing official identity now fail for operator investigation rather than changing saved identity metadata.

New record resolution requires an exact supported **current** definition. An old CNSC revision incorrectly left active in the DB cannot govern a new record. Institutional Forms readiness uses that same rule; historical support remains visible separately.

Inventory, Referral and Call Slip creation already use the shared resolver. Good Moral binds its revision and chosen renderer at issuance. Reprints use the saved revision; Call Slip/Referral select the supported renderer from that saved identity, and Good Moral uses its saved renderer key/version. All affected official PDF consumers reject unknown identities. Inventory's confidential-data projection remains unchanged.

New scheduled/direct Routine Interviews now require F7. Existing null relationships remain null and readable. Existing records are returned before new-creation resolution and are never relabelled during synchronization.

Exit Interview migration `0005_saved_form_revision` adds only a nullable protected FK with no default or backfill. New service-created records bind approved F9. Existing drafts, submissions and corrections retain their saved identity, including null. Validation and PDF projection follow that saved contract; unknown identities and incompatible answers fail safely. The read-only API returns saved identity and applicable College-feedback codes; mutation schemas cannot change either. The frontend uses those codes for categories, answer counts and submitted ratings. UCN answers containing Program Chair content are rejected without silent loss. The 0–5 College scale and meaning of zero are unchanged.

Demo prerequisites include F7/F9, and the Exit Interview seed adapter selects the saved contract. Legacy encrypted fields and model item choices remain available; historical records are not globally rewritten.

## PDF comparison and DOC-TPL-1 handoff

The review compared institutional masthead, title, source code/revision, questions/options, receipt fields, signature blocks, footer/page numbering, and Student/Counselor fields. Actual Chromium PDFs were rendered and inspected with Poppler. Representative UCN output page counts: F2 1, F3 1, F4 1, F5 3, F6 1, F9 3; saved official metadata is present on every page. Legacy CNSC and null-F9 PDFs remain covered by regression tests.

UCN F2 restores Reference No., both destination choices, the exact legacy-office instruction, Interview Start/End, Student signature, purpose choices, receipt/attendance remarks/date/time and status. Uncaptured paper fields are blank for manual completion, with no fabricated answers or new capture workflow. F3 and F4 have separate UCN templates so historical presentations remain available. F5's approved “UNIQUE FEATURES” and “PERCEPTIONS” headings are conditional on its saved UCN identity.

Visual inspection also identified an inherited layering defect: opaque Chromium page backgrounds could cover repeated artwork. The artwork now paints above that background in reserved margins; a three-page opaque-background regression verifies the layer order.

Remaining DOC-TPL-1 differences are explicit: F2 source contains two duplicate copies with Page 1 of 1 on both; COMPASS emits one response copy. F2's source masthead spells COUNCELLING while shared approved institutional artwork spells COUNSELLING. Exact Word typography/imposition remains separate. The supplied Word files render with pagination drift in LibreOffice (F7 2 pages; F9 3 despite Page 1 of 1 footer text); PDFs report actual page counts and flow long answers rather than truncating them. Approved legacy terms in F5 and F9 remain unchanged. No Fare/Income ranges, reporting methodology, F1/F8 workflow or broad template redesign is included.

## Fresh bootstrap and inherited release blockers

All validation used isolated local PostgreSQL databases, not the live staging database. A database created from empty state passed all migrations, identity policy sync, canonical Service sync, Institutional Forms sync, organization sync and Django system checks. Fresh registry reconstruction and repeat synchronization are also tested without preexisting CNSC rows.

Full `seed_demo_staging` stops at `SCENARIO_ALUMNI` with `InvalidGraduateTracerInput: graduated_college is required before submission.` A separate pristine snapshot of staging was migrated and seeded in a second isolated database and produced the same failure. The owning Graduate Tracer source files have identical hashes on the initial and updated bases. This is an inherited release blocker; complete fresh demo seeding is **not** claimed successful. The isolated F9 seed-contract test verifies this change's adapter independently.

Base CI is red: [updated staging run 38678889565](https://github.com/ils12058/COMPASS/actions/runs/38678889565), [initial staging run 38676895704](https://github.com/ils12058/COMPASS/actions/runs/38676895704). A pristine updated-base check reproduces the unregistered `test_graduate_tracer_graduation_classification.py` CI bundle failure, formatting/lint failures in inherited files, and three inherited OpenAPI assertions about Graduate Tracer operation/filter/report additions. These remain with the GTS/CI workstream. Passing changed-file checks does not establish green repository CI.

Deployment requires the owner's reset/deployment approval, review of the documented source presentation differences, compatible backend/frontend deployment, the F9 migration, explicit canonical synchronization, and resolution of inherited CI/seeding blockers. Follow the separate [staging reset/release checklist](FORM-ID-1-Staging-Reset-Checklist.md).

## Files changed

- `be/compass/call_slips/services.py`
- `be/compass/demo_seed/history.py`
- `be/compass/demo_seed/seed.py`
- `be/compass/documents/rendering.py`
- `be/compass/documents/template_specs.py`
- `be/compass/documents/templates/documents/call_slips/ucn_call_slip.html`
- `be/compass/documents/templates/documents/good_moral/ucn_current_student.html`
- `be/compass/documents/templates/documents/inventory/page_three.html`
- `be/compass/documents/templates/documents/inventory/page_two.html`
- `be/compass/documents/templates/documents/referrals/ucn_referral_slip.html`
- `be/compass/exit_interviews/api.py`
- `be/compass/exit_interviews/documents.py`
- `be/compass/exit_interviews/form_contract.py`
- `be/compass/exit_interviews/migrations/0005_saved_form_revision.py`
- `be/compass/exit_interviews/models.py`
- `be/compass/exit_interviews/services.py`
- `be/compass/good_moral/services.py`
- `be/compass/institutional_forms/api.py`
- `be/compass/institutional_forms/bootstrap.py`
- `be/compass/institutional_forms/canonical.py`
- `be/compass/institutional_forms/services.py`
- `be/compass/inventory/documents.py`
- `be/compass/referrals/services.py`
- `be/compass/routine_interviews/services.py`
- `be/docs/decisions/ADR-113-approved-ucn-controlled-form-identities.md`
- `be/tests/conftest.py`
- `be/tests/inventory_test_helpers.py`
- `be/tests/test_call_slips.py`
- `be/tests/test_demo_seed.py`
- `be/tests/test_documents.py`
- `be/tests/test_exit_interview_confidential_content_encryption.py`
- `be/tests/test_exit_interview_documents.py`
- `be/tests/test_exit_interview_opportunities.py`
- `be/tests/test_exit_interviews.py`
- `be/tests/test_good_moral.py`
- `be/tests/test_institutional_forms.py`
- `be/tests/test_inventory.py`
- `be/tests/test_inventory_documents.py`
- `be/tests/test_openapi_contract.py`
- `be/tests/test_record_retrieval.py`
- `be/tests/test_referrals.py`
- `be/tests/test_routine_interviews.py`
- `contracts/openapi.json`
- `fe/src/features/exit-interviews/exit-interview-form-sections.tsx`
- `fe/src/features/exit-interviews/exit-interview-form.tsx`
- `fe/src/features/exit-interviews/exit-interview-presentation.ts`
- `fe/src/features/exit-interviews/exit-interview-response.tsx`
- `fe/tests/draft-and-session-safety.browser.mjs`
- `fe/tests/exit-interview-workflow.test.mjs`
- `outputs/FORM-ID-1-Approved-Source-Matrix.json`
- `outputs/FORM-ID-1-Implementation-Report.md`
- `outputs/FORM-ID-1-Staging-Reset-Checklist.md`
- `outputs/FORM-ID-1-Test-Evidence.json`

## Executed validation

- Cutover suite: **186 passed**. Includes canonical exact identities and active counts; F2 printed Revision 2/schema 1; synchronization idempotence and fresh reconstruction; retired/unknown identity rejection; UCN and legacy Inventory, Referral, Call Slip and both Good Moral render paths; scheduled/direct Routine creation and null-history preservation; F9 creation, correction, submission, zero ratings, legacy null history and saved-revision PDFs; the forward migration preserving submitted ciphertext/ratings without backfill; the focused F9 seed adapter; read-only F9 contract fields.
- Broader domain/privacy suite: **546 passed, 3 failed** in its initial collection. The three fixture corrections described below were subsequently rerun together: **3 passed**. No unresolved failure remains among those 549 selected cases. Coverage includes Inventory, Routine decoupling/encryption, Exit opportunities/encryption, Good Moral preparation, Referral/Call Slip lifecycle, Customer Feedback/encryption, record retrieval and document foundations.
- Those corrections preserve the intended checks: current-model reads after legacy encryption migrations now apply the additive FK migration and verify its new value is null; the Feedback name-search fixture deliberately supplies a respondent name while optional identity remains optional. Production Feedback code is unchanged.
- Frontend Node suite on the updated base: **670 passed**. Changed frontend ESLint and TypeScript checks passed.
- Browser verification: **8 passed** (UCN/legacy × desktop/phone × Chromium/WebKit). Verifies the six/seven categories, 23/26 item rows, unchanged zero explanation and enabled submission with zero ratings.
- Fresh empty database: all migrations, all canonical synchronization commands and Django system checks passed. `makemigrations --check --dry-run` and exported OpenAPI synchronization passed. All changed Python files pass Ruff lint/format and the diff whitespace check.
- Full demo seeding and repository-wide static/CI checks remain blocked by inherited failures reproduced on pristine staging, as detailed above. Three inherited OpenAPI contract assertions also fail on both pristine staging and this branch. No green full-suite or green CI claim is made.
- Final document/rendering rerun after the artwork correction: **58 passed**, including remote-resource blocking, safe HTML handling, opaque-background artwork order, Inventory fit guards, long answers, saved identity metadata and the official UCN PDF consumers. Synthetic capture instrumentation was removed for the source-inspection assertion before this clean rerun.

Machine-readable results, per-case final outcomes and PDF hashes/page counts are in [test evidence](FORM-ID-1-Test-Evidence.json). A separate local PDF evidence bundle contains only synthetic test responses; no institutional records or credentials are included.
