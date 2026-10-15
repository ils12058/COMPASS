# FORM-UI-1B — Inventory review copy and Exit Interview field guidance

## Final scope and baseline

Target: `ils12058/COMPASS`, `staging`. Fetched baseline: `b49407e6b478ab256dc87404f8893798d4eb1e8b` (rechecked before PR creation). Initial working tree was clean on the previous FORM-UI-1A branch at `0f83543bcae9e7c06673920281e99887bde4cebc`. The implementation branch starts directly from current staging and is named `fix/form-ui-1b-form-guidance`.

Confirmed merged dependencies through GitHub and staging history:

- FORM-ID-1 #232: `180759f0b79b8a3d2b418ad0fd38101196f18942`.
- FORM-INPUT-1C #233: `b7f365b5828ab5db8fc541d90321558a5183f7f2`.
- FORM-UI-1A #234: `b49407e6b478ab256dc87404f8893798d4eb1e8b`.

Reviewed the FORM-FIDELITY-0 package, including the discrepancy register (FF-02/FF-16), implementation roadmap, contract/privacy matrix, GCO decisions, field/workflow traces, document comparison, and synthetic verification evidence. Current owning source, rather than audit conclusions alone, determined this implementation.

**The final scope follows the owner's subsequent instructions:** remove the Inventory PDF-capacity guidance entirely, and remove technical/robotic review wording. No replacement PDF-capacity note or banner is included. FF-02 remains deferred. The Inventory change is limited to the Review section's copy and removal of its unnecessary success notice. The other delivered change is the bounded FF-16 Exit Interview input guidance.

## Confirmed initial behavior

Inventory's editor accepts additional rows. `be/compass/inventory/documents.py` rejects more than 12 sibling rows or more than 3 organization rows in either scope for its two supported F5 identities. The error is the generic `inventory_document_unavailable`, also used for other document failures; it cannot safely identify row overflow. Those contracts, download messages, row controls, and PDF behavior are unchanged in the final implementation.

The Review section displayed “Submission readiness” and a success notice saying “No required-field issues were found…” when there were no issues. This copy was unnecessary for the student's task. Exit Interview inputs lacked applicable existing server length bounds, and the conditional Other textareas shared IDs with their corresponding checkboxes.

## Exact changed files

1. `fe/src/features/inventory/editor/review-section.tsx` — plain review copy; no positive validation-status banner.
2. `fe/src/features/exit-interviews/exit-interview-field-limits.ts` — verified existing text limits.
3. `fe/src/features/exit-interviews/exit-interview-form-sections.tsx` — native length bounds, accessible descriptions, complete saved values, unique conditional textarea IDs.
4. `fe/tests/form-input-standardization.test.mjs` — update the existing contact test to expect the server's 64-character bound while preserving the example, multiple-number value, and absence of a phone-format pattern.
5. `fe/tests/form-ui-1b.test.mjs` — focused actual-component and server-bound consistency tests.
6. `fe/tests/form-ui-1b.browser.mjs` — Chromium/WebKit draft, submission, history-contract, preservation, and review-focus checks.
7. `fe/tests/support/form-ui-1b-fixtures.mjs` — synthetic Exit Interview records.
8. `fe/package.json` — focused two-engine browser command, run first in the existing UI regression commands.
9. `outputs/COMPASS-FORM-UI-1B-Implementation-Report.md` — this report.
10. `outputs/COMPASS-FORM-UI-1B-Validation-Evidence.json` — compact final validation evidence.

## Inventory behavior

The Review heading is now “Before you submit.” When answers are missing, “Complete these answers” introduces the existing actionable question links. When none are missing, there is no success notice. The section retains a plain explanation that submitted answers cannot be edited and that a counselor can help with corrections. The unavailable-program message now simply says the choices could not be loaded and the saved choice is kept.

`getInventorySubmissionIssues`, issue counts, issue-selection handlers, field focus, saving, submission, correction/resubmission, and all input requirements are untouched. The PDF download component, Student current/history pages, Counselor detail/history, read-only projections, and row editors have no final diff. No capacity helper or persisted readiness field remains. Existing full digital values and row arrays remain unchanged.

## Exit Interview limit alignment

| Input | Existing server maximum |
|---|---:|
| Student name | 200 |
| Civil status | 80 |
| Course and major | 180 each |
| Email | 320 |
| Contact number | 64 |
| Home address | 2,000 |
| Other delay reason and other learning experience | 1,000 each |
| Each feedback-category comment, including historical Program Chair | 4,000 |
| Suggestions/recommendations | 4,000 |

Verified against `be/compass/exit_interviews/services.py`, `models.py`, and `confidential_content.py:CONTENT_LIMITS`; tests compare the declared frontend values against the owning server bounds. No arbitrary limit was added to numeric age or extra-term fields.

Existing `FormField` and `FormTextArea` accept `maxLength`. A polite, field-associated description appears at the limit. Existing hints and errors remain connected through `aria-describedby`. A saved value longer than the current bound remains complete in form state and the rendered control, with an explanation of the write conflict; no slicing, trimming, or normalization was added.

Conditional delay/learning Other textareas now have distinct `-detail` IDs, allowing their labels and limit descriptions to identify the textarea rather than the checkbox. Their conditions, requiredness, state handlers, and payload keys are unchanged.

## Historical handling, privacy, and authorization

UCN F9 retains six feedback categories/23 ratings. Historical null-revision forms retain seven categories/26 ratings and Program Chair content. The existing saved item-code contract still governs rendering and payloads. Rating scales, numeric 0, career hierarchy, submission/reopening rules, and Good Moral prerequisites are untouched.

Browser tests save and submit both contracts on desktop and phone. A separate overlong legacy-comment scenario verifies that an unrelated correction sends the complete saved comment, and a server rejection preserves both that comment and the new correction. Such a value may still conflict with current write validation; the UI does not silently repair it or bypass the server.

No new data fetch, capability, access grant, telemetry, external service, audit field, or confidential projection was introduced. All browser fixtures are synthetic and every API request is intercepted by the existing local harness. The backend remains authoritative.

## Verification

| Directory | Command | Outcome |
|---|---|---|
| `fe` | `pnpm api:generate` | Passed; no generated client committed. |
| `fe` | `pnpm test` | **718 passed, 0 failed** after the scope/copy changes. |
| `fe` | `node --import ./tests/support/register-tsx.mjs --test tests/form-ui-1b.test.mjs tests/form-input-standardization.test.mjs tests/exit-interview-workflow.test.mjs` | **40 passed, 0 failed** after the final wording polish. |
| `fe` | `COMPASS_UI_ARTIFACTS=<local-artifacts>/final-copy pnpm test:ui:form-guidance` | **6/6 Chromium; 6/6 WebKit**, including desktop and phone. |
| `fe` | `pnpm lint` | Exit 0, **0 errors / 4 inherited unused-variable warnings** in unchanged `tests/portal-navigation-attention.browser.mjs` (`copyFile`, `baseURL`, `hidden`, `noHorizontalOverflow`). |
| `fe` | `pnpm typecheck` | Passed, including final wording. |
| `fe` | `pnpm build` | Passed, including final wording; production compilation and route generation succeeded. |
| `be` | `uv run pytest tests/test_inventory_documents.py tests/test_exit_interview_documents.py tests/test_inventory_confidential_content_encryption.py::test_all_unauthorized_or_draft_raw_reads_fail_before_decrypt tests/test_exit_interview_confidential_content_encryption.py::test_unauthorized_detail_pdf_and_draft_edits_fail_before_decryption tests/test_exit_interview_confidential_content_encryption.py::test_exact_text_schema_preserves_limits_and_postgresql_input_boundary --reuse-db -q --junitxml=<local-artifacts>/backend.xml` | **81 passed in 46.58s**. Existing document/authorization/limit checks; no backend code changed. |
| repository | `git diff --check` | Passed. |

The final focused unit suite verifies all declared text limits against server constants/models, current and legacy answer contracts, preservation of overlong values, conditional fields, accessible limit descriptions, and review rendering with/without missing answers. The browser suite verifies both F9 contracts on desktop and phone, valid draft save/submission, retained numeric 0, legacy Program Chair preservation after an unrelated edit and rejected save, and unchanged question-link focus from Inventory Review.

The only post-full-suite edits were wording refinements; focused unit/browser, TypeScript, and production build checks were rerun after those edits. Earlier broad Inventory-capacity experiments are excluded from the final deliverable and final test totals. There is no remaining focused test failure.

The final complete diff was reviewed for scope, saved-value preservation, permission/fetch boundaries, conditional labels, issue counts/focus, and unchanged submission handlers. Browser screenshots were inspected at desktop and phone widths. No independent human/adviser approval is claimed.

Known Guidance Operations browser failures and the prior backend CI shard-registration problem are separate from this change. This workstream does not modify those files or claim that the full repository browser suite or remote CI is green. Final focused failures, if any, are listed above; preliminary test-fixture/selector corrections are not classified as application regressions.

## Compatibility and deferred decisions

No database migrations; no backend API changes; no encryption changes; no FormRevision modifications; no official PDF template changes; no renderer text-fitting changes; no new submission blockers; no removal of accepted siblings or organizations; no historical-data rewriting; no new institutional policies. Generated API clients are neither edited nor committed.

FF-02 remains the existing PDF row-capacity limitation; its UI advice was excluded at the owner's request. FF-01's text-fitting/ellipsis strategy remains intentional, with verbatim document completeness and any continuation/overflow rendition policy deferred to GCO/QMS. No QMS approval or complete narrative reproduction in the PDF is claimed. Fare/income bands, profiling methodology, career hierarchy, rating-0 interpretation, new paper fields, and other institutional decisions remain outside scope.

No merge, deployment, migration, staging reset, or live institutional-record mutation was performed.
