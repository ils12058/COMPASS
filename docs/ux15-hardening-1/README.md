# UX15 Submission Correctness and Inventory Reflow

This proposal hardens three existing workflows on `integration/ux15-modernization` without changing domain permissions, questionnaire content, persistence formats, or deployed environments.

- **A — CORRECTNESS-1:** Routine Student Intake now reconciles uncertain submissions with a fresh, authorized read of the same Routine Interview.
- **B — ACCESSIBILITY-2:** Individual Inventory chooses its section navigation and panel layout from the available workspace width, allowing enlarged text to reflow inside the Portal Shell.
- **C — CORRECTNESS-2:** Customer Feedback and CSM retain the exact submission intent through network and ambiguous HTTP failures, then reconcile against the canonical opportunity or offer only a same-key replay when safe.

Base branch: `integration/ux15-modernization`

Verified baseline: `0aa6de7ff8f26c8afd6531a8b2d7d87e52869ef4`

Feature branch: `feat/ux15-correctness-accessibility-hardening`

## Architecture and safeguards

The work keeps submission decisions inside their domain owners. Routine Intake uses `routineInterviewsGetMine`; Feedback uses `feedbackGetMyOpportunity` and its existing key/fingerprint replay contract. No shared submission engine, new endpoint, backend schema, permission, migration, generated client, or second submission lifecycle was introduced. Inventory changes are presentational and do not alter official values or workflow rules.

Routine submission remains a user-confirmed POST. An ambiguous result triggers a fresh no-cache GET, exact record identity validation, and a submitted/draft/unknown decision. A failed or mismatched read remains unknown. A DRAFT read never causes an automatic POST; the user returns to the existing confirmation flow only when the canonical saved content still matches. If a conflict and a read disagree, the flow stays blocked until a later status read resolves it.

Feedback preserves each form's original request body, fingerprint, and idempotency key while unresolved. The backend service transaction locks the Student-owned opportunity and writes the response and matching submitted timestamp together. Its idempotency layer can replay a completed response, report a key conflict/in-progress reservation, or return unavailable when the replay boundary cannot be used safely. The canonical opportunity exposes distinct Customer Feedback and CSM flags; a submitted flag proves the opportunity is consumed, not which exact request body was stored. Frontend synthetic tests do not establish live database concurrency or infrastructure behavior.

## Changed files

- Routine Intake: `fe/src/features/routine-interviews/routine-student-intake.tsx`, `fe/tests/support/ux15-routine-intake-fixtures.mjs`, `fe/tests/ux15-routine-intake.browser.mjs`.
- Inventory: `fe/src/features/inventory/editor/inventory-editor.tsx`, `fe/src/components/ui/form-experience.tsx`, `fe/tests/ux15-inventory.browser.mjs`.
- Feedback/CSM: `fe/src/features/feedback/customer-feedback-form.tsx`, `fe/src/features/feedback/csm-form.tsx`, `fe/src/features/feedback/feedback-shared.tsx`, `fe/tests/ux15-feedback-csm.browser.mjs`.
- Evidence and validation: files in this directory, including synthetic screenshots and captured geometry.

Package design and evidence: [Routine Intake](routine-intake-reconciliation.md), [Inventory](inventory-reflow.md), [Feedback and CSM](feedback-recovery.md), [validation](validation.md), [screenshots](screenshots.md), and [follow-ups](followups.md).
