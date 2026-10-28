# Browser regression triage

## Feedback and CSM

`fe/tests/user-copy.browser.mjs` has four matching failures per engine: Customer Feedback and CSM, each at 320px and 1440px. On the current production build the full suite is 40/44 in Chromium and 40/44 in WebKit. Each failure times out in `oneAlert(page, 'The submission result could not be confirmed.')`, which searches for `role=alert`.

The rendered unconfirmed state is a polite `role=status`/`aria-live=polite` Notice. In these server-error fixtures its heading is “Submission result not confirmed” and its copy says “Your response is still unsubmitted. You can safely retry this same submission.” The Feedback and CSM components implement this state in `customer-feedback-form.tsx` and `csm-form.tsx`; the test expects older alert semantics and wording. The test/source and Feedback/CSM files are unchanged from the clean pre-SVC-UX-1 baseline. The same four cases failed against that baseline in both engines. This is pre-existing test expectation debt, not evidence of a SVC-UX regression. No unrelated copy or assertions were changed.

## Routine Interview focus

An initial full Chromium run also failed `routine-form-blocker-1440` on focus restoration. The isolated 1440px case passed on both current and clean baseline builds. A full rerun passed it in both Chromium and WebKit; no reproducible product failure was established. The final `user-copy` count remains 40/44 per engine because of the four Feedback/CSM cases.

Failure screenshots are in the task's temporary browser-artifact folders, not committed to the repository. This suite must not be reported green.
