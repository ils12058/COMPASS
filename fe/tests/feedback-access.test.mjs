import assert from "node:assert/strict";
import { test } from "node:test";

import { getFeedbackAccess } from "../src/features/feedback/feedback-access.ts";

// The portal navigation shows Feedback when `canOpenFeedback` is true.
function account(role, capabilities) {
  return { role, capabilities };
}

test("Students who can submit Feedback can open it without review capabilities", () => {
  const customerFeedback = getFeedbackAccess(
    account("STUDENT", ["feedback.submit_customer_feedback"]),
  );
  const csm = getFeedbackAccess(account("STUDENT", ["feedback.submit_csm"]));

  for (const access of [customerFeedback, csm]) {
    assert.equal(access.hasStudentSubmissionAccess, true);
    assert.equal(access.hasOperationalWorkspace, false);
    assert.equal(access.canOpenFeedback, true);
  }
});

test("Staff open Feedback through a response-review capability", () => {
  const access = getFeedbackAccess(account("COUNSELOR", ["feedback.view_csm"]));

  assert.equal(access.hasStudentSubmissionAccess, false);
  assert.equal(access.hasOperationalWorkspace, true);
  assert.equal(access.canOpenFeedback, true);
});

test("Submission capabilities open Feedback only for Student accounts", () => {
  const access = getFeedbackAccess(
    account("COUNSELOR", ["feedback.submit_customer_feedback", "feedback.submit_csm"]),
  );

  assert.equal(access.hasStudentSubmissionAccess, false);
  assert.equal(access.canOpenFeedback, false);
});

test("Accounts without Feedback capabilities cannot open Feedback", () => {
  assert.equal(getFeedbackAccess(account("STUDENT", [])).canOpenFeedback, false);
  assert.equal(getFeedbackAccess(account("IT_ADMIN", ["accounts.manage"])).canOpenFeedback, false);
});
