# Seven-Form Final Audit

## Integrated inventory

The seven form experiences comprise six Student-facing experiences and the Counselor Evaluation.
Their common presentation parts do not replace domain-owned workflow logic.

| Form | Navigation and persistence | Validation and submission/recovery | Final audit disposition |
| --- | --- | --- | --- |
| Student Individual Inventory | Eight answer sections plus Review; desktop section buttons and mobile native selector. Explicit draft save and Save & continue. | Draft and final checks differ; error targets return to their original field/section. Submission uses explicit confirmation and the existing canonical current/history state. Correction targets remain advisory and outside the payload. | **Consistent and appropriate.** 13 Chromium and 13 WebKit browser checks passed; enlarged layout includes the prior 1024px/200% case. |
| Student Exit Interview | Five official groups plus Review; continuous form with named section links. Explicit draft save. | Native conditional questions and rating groups, missing-rating/extra-terms guidance, explicit final confirmation, and canonical refresh after uncertain submission. Historical revision/item wording remains preserved. | **Intentionally different.** 15/15 passed in both engines. No universal stepper was added. |
| Graduate Tracer Study | Five official groups plus Review; continuous form and section links. Explicit replace-draft save. | Employment, training, and repeat-row branches retain their own rules; draft validation differs from final validation. Final submission uses confirmation and canonical status reconciliation. Participation and eligibility remain voluntary/domain-owned. | **Intentionally different.** 26/26 passed in both engines. |
| Routine Student Intake | Seven question groups plus Review; continuous form and explicit Save progress. No autosave. | Conditional “Other” and concern rules remain source-owned. After uncertain submission, a fresh canonical record read distinguishes submitted, still-draft, and unresolved states; it never automatically repeats POST. Answers remain intact until deliberate action. | **Consistent and appropriate.** 22/22 passed in both engines, including committed/lost-response, canonical DRAFT, blocked status check, and no duplicate submission cases. |
| Counselor Evaluation | Short professional evaluation; no artificial section navigator. Manual save precedes a separate authorized finalization workflow. | Six source ratings preserve nullable values; narratives remain separate; only eligible completed Encounters can be finalized. Confirmed finalization is read-only. No blanket completeness or self-service behavior is introduced. | **Intentionally different.** 18/18 passed in both engines, including uncertain finalization and read-only state. |
| Customer Feedback | Nine official groups with continuous section links. One-time response; no persisted draft or Save Progress. | Native requiredness/service/Counselor conditionals remain. Confirmation precedes one-time submission. Uncertain outcomes retain exact body/fingerprint/idempotency key for deliberate retry where the existing contract permits, and canonical opportunity state does not claim which body was accepted. Respondent identity remains optional. | **Intentionally different.** 27/27 passed in both engines. |
| Client Satisfaction Measurement (CSM) | Four groups; one-time response without draft persistence or section navigator. | Native numeric/email rules and all six SQD values remain; numeric zero and Not Applicable remain valid. It uses its own submission state and idempotent recovery, separate from Customer Feedback. | **Intentionally different.** Included in the 27/27 Feedback/CSM checks in both engines. |

## Invariants checked across the integrated forms

- Shared `FormSaveStatus`, section links/navigation, and error summary present the form owner's
  state. They do not own persistence, validation, eligibility, payloads, or routing.
- A save is shown as confirmed only after the owning mutation returns success. Failures preserve
  current input and dirty state; pending actions prevent duplicate submissions.
- Draft saves remain distinct from final submission. Confirmation, review, read-only, and
  professional finalization states retain their original domain-specific meaning.
- Native fields, labels, conditional branches, matrix semantics, and form revisions remain in
  place. Official wording, answer choices/order, requiredness, payload shape, scoring, and
  eligibility are unchanged by this consolidation.
- Inventory, Exit Interview, Graduate Tracer, and Routine Intake keep persisted draft workflows.
  Customer Feedback and CSM remain one-time forms without an invented draft promise.
- Counselor Evaluation remains a confidential professional workflow. The Student receives no
  Counselor narrative or finalization action.
- Cross-form behavior retains the existing dirty-form guard for navigation, browser Back, and
  beforeunload where the form owns meaningful unsaved input.

## Focused recovery evidence

The rerun browser coverage verified:

- Routine Intake's committed response followed by a lost response; fresh canonical submitted and
  DRAFT reads; unresolved/denied/missing status checks; preserved answers; no automatic duplicate
  POST; and explicit confirmation after a canonical DRAFT.
- Customer Feedback and CSM exact-intent retry (same body, fingerprint, and idempotency key),
  HTTP/network uncertainty, canonical opportunity flags, no false success, duplicate-action
  protection, optional respondent identity, zero/N/A, and separate instrument states.
- Counselor Evaluation nullable source ratings, authorized Encounter finalization, uncertain
  result reconciliation, and confirmed read-only state.
- Exit Interview and Graduate Tracer canonical recovery and their distinct continuous-form
  navigation; Inventory correction/readonly behavior and conditional target navigation.

The browser suites use synthetic API fixtures. They do not establish deployed database
concurrency, production Redis idempotency behavior, institutional questionnaire approval, or
backend enforcement. The backend source and existing negative tests are noted in
[privacy and correctness](privacy-and-correctness.md); no backend test suite was run because this
PR changes no backend contract or implementation.
