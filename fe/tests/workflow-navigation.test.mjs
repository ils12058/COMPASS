import assert from "node:assert/strict";
import { test } from "node:test";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "../src/features/portal/workflow-navigation.ts";

test("a case-task-case journey carries the originating list's complete filters", () => {
  const origin = "/portal/follow-ups?status=all&ordering=LATEST_DUE&page=3&student_id=student#tasks";
  const caseHref = withWorkflowReturn("/portal/counseling/cases/case-1", origin);
  const taskHref = withWorkflowReturn("/portal/follow-ups/task-1", caseHref);
  const returnedCase = new URL(taskHref, "https://compass.invalid").searchParams.get("return_to");
  assert.equal(returnedCase, caseHref);
  const returnedList = new URL(returnedCase, "https://compass.invalid").searchParams.get("return_to");
  assert.equal(returnedList, origin);
  assert.equal(portalReturnHref(returnedList, "/portal"), origin);
});

test("untrusted return paths stay inside the portal", () => {
  for (const value of [null, "", "https://example.com/portal", "//example.com/portal", "javascript:alert(1)", "/login", "/portal-mock/path", "/portal\\../login", "/portal/\u0000x"]) {
    assert.equal(portalReturnHref(value, "/portal/work"), "/portal/work");
  }
  assert.equal(portalReturnHref("/portal/work?page=4", "/portal"), "/portal/work?page=4");
});

test("back links name the originating workspace or record", () => {
  for (const [href, label] of [["/portal/work?page=3", "Back to My work"], ["/portal/follow-ups?status=all", "Back to Follow-Ups"], ["/portal/counseling/cases/case-1", "Back to case"], ["/portal/appointments?view=calendar", "Back to Appointments"], ["/portal/counseling/encounters", "Back to session records"], ["/portal/counseling/encounters/session-1", "Back to session record"], ["/portal/counseling?search=Ana", "Back to Counseling"]]) {
    assert.equal(workflowBackLabel(href), label);
  }
});
