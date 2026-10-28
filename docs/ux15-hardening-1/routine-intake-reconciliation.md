# Routine Intake uncertain-submission reconciliation

## Failure and audited contract

The Student editor submitted through `routineInterviewsSubmitMyIntake`. Before this change, network/5xx ambiguity could leave a message advising a refresh without performing canonical reconciliation. Cache invalidation alone could not determine whether the Student Intake committed.

The existing authorized `routineInterviewsGetMine(routineInterviewId)` response carries the Routine Interview id, intake status, submission timestamp, and saved Intake content. The backend submit service validates current Student eligibility and the parent Appointment, locks the target Routine Interview row in a transaction, checks the submitted timestamp, validates the seven-group Intake, and sets the timestamp. The service does not add a new submission identity. The GET is authorized for the Student's own record. No backend change was necessary.

## Implemented states

- Confirmed success preserves the existing submitted/read-only transition and Student Actions/detail/list cache refresh.
- A network, timeout, server error, or `routine_interview_intake_already_submitted` result causes a direct `cache: "no-store"` GET for the intended id. The response id is checked before status is accepted.
- Canonical `SUBMITTED` updates the query cache and displays the existing read-only experience without another POST.
- Canonical `DRAFT` remains distinct from success. When server-saved answers match the prior saved answers, the Student can return to the established confirmation flow. If they differ, the current page answers remain intact and are dirty relative to the fresh saved version; the Student must explicitly save before submitting.
- Failed, unauthorized, missing, inaccessible, mismatched, or otherwise unresolved reads preserve answers and uncertainty. Editing/submission is blocked while unresolved, and an authorized status check can be repeated.
- A conflict followed by a contradictory DRAFT read remains blocked; a later successful status check is needed to resolve it.

The Submit and Check Status operations share an in-flight guard. Status checking does not submit, Save Progress remains explicit, and no autosave or automatic retry was added.

## Consistency limitation

The local frontend tests exercise synthetic fresh GET responses. The backend uses a transaction and per-record row lock, but this work did not prove production read-after-write behavior across a deployed database topology or all network races. Therefore a DRAFT response only re-enables the deliberate confirmation flow when its content is consistent with the previously saved version; it never starts a POST itself. The backend lock and submitted timestamp remain authoritative if another request wins before a later submit.

## Validation

`fe/tests/ux15-routine-intake.browser.mjs`: 22/22 Chromium and 22/22 WebKit checks passed. Coverage includes lost response after commit, stale cached DRAFT, conflict then canonical submitted, canonical draft and deliberate confirmation, GET 403/404/503, answer preservation, no automatic POST, and overlapping Submit/Check Status attempts. See [validation](validation.md) for exact commands and whole-repository checks.
