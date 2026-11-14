import assert from "node:assert/strict";
import { test } from "node:test";

import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";
import {
  caseCallSlipHref,
  isStaleProposalError,
  isUncertainProposalResult,
  messageThreadHref,
  proposalErrorMessage,
  proposalStateLabel,
  proposeSessionHref,
  purposeLabel,
  refusedOption,
  studentProposalHref,
} from "../src/features/counseling/session-proposals/session-proposal-presentation.ts";
import { presentStudentAction } from "../src/features/student-actions/student-actions-presentation.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const id = "12345678-1234-4234-8234-123456789abc";
const caseId = "22345678-1234-4234-8234-123456789abc";

function apiError(status, code, details) {
  return new CompassApiError({ status, body: { error: { code, message: "backend text", ...(details ? { details } : {}) } }, headers: {}, method: "POST", url: "/api/v1/x" });
}

test("purpose and state labels never fall back to backend codes", () => {
  assert.equal(purposeLabel("FOLLOW_UP_SESSION"), "Follow-up session");
  assert.equal(purposeLabel("UNKNOWN"), "Counseling session");
  assert.equal(proposalStateLabel("PENDING"), "Waiting for the Student");
  assert.equal(proposalStateLabel("PENDING", "student"), "Waiting for your answer");
  assert.equal(proposalStateLabel("WITHDRAWN", "student"), "Withdrawn by your Counselor");
  assert.equal(proposalStateLabel("EXPIRED"), "Expired without an answer");
});

test("errors map by code and name the refused time, never backend wording", () => {
  const taken = apiError(409, "session_proposal_time_unavailable", { option: 2, reason: "conflict" });
  assert.equal(refusedOption(taken), 2);
  assert.equal(proposalErrorMessage(taken, "fallback"), "Time 2 is no longer available. Choose another time.");
  assert.equal(
    proposalErrorMessage(apiError(409, "session_proposal_student_action_required", { reason: "current_inventory_required" }), "fallback"),
    "Submit your Individual Inventory for this Academic Year, then accept a time.",
  );
  assert.match(proposalErrorMessage(apiError(409, "session_proposal_open"), "fallback"), /Withdraw it/);
  assert.equal(proposalErrorMessage(apiError(409, "something_new"), "fallback"), "fallback");
  assert.equal(isStaleProposalError(apiError(409, "session_proposal_changed")), true);
  assert.equal(isStaleProposalError(apiError(409, "session_proposal_closed")), true);
  assert.equal(isUncertainProposalResult(new TypeError("offline")), true);
  assert.equal(isUncertainProposalResult(apiError(503, "x")), true);
  assert.equal(isUncertainProposalResult(apiError(409, "x")), false);
});

test("shortcut links carry identifiers and a bounded return only", () => {
  const back = "/portal/follow-ups/abc?status=all";
  const propose = proposeSessionHref(caseId, back, id);
  assert.equal(propose, `/portal/counseling/cases/${caseId}/propose-session?follow_up_id=${id}&return_to=${encodeURIComponent(back)}`);
  const slip = new URL(caseCallSlipHref({ studentId: id, caseId, appointmentId: id, reportAt: "2026-11-23T10:00:00+08:00", followUpId: id, returnTo: back }), "https://x.invalid");
  assert.equal(slip.pathname, "/portal/call-slips/new");
  assert.deepEqual([...slip.searchParams.keys()], ["student_id", "case_id", "appointment_id", "report_at", "return_to"]);
  const plain = new URL(caseCallSlipHref({ studentId: id, followUpId: id, returnTo: "https://evil.example" }), "https://x.invalid");
  assert.equal(plain.searchParams.get("follow_up_id"), id);
  assert.equal(plain.searchParams.get("return_to"), "/portal");
  assert.equal(messageThreadHref(id, back), `/portal/messages/${id}?return_to=${encodeURIComponent(back)}`);
  assert.equal(studentProposalHref(id), `/portal/appointments/proposals/${id}`);
});

test("Student action and notifications lead to the respond page and the case", () => {
  const row = presentStudentAction({
    id: `session-proposal-response:${id}`,
    kind: "SESSION_PROPOSAL_RESPONSE",
    priority: "ACTION_REQUIRED",
    source_id: id,
    due_at: "2026-11-20T02:00:00Z",
    waiting_since: "2026-11-14T02:00:00Z",
    conversation_kind: null,
    pending_count: null,
  });
  assert.equal(row.href, `/portal/appointments/proposals/${id}`);
  assert.equal(row.actionLabel, "Choose a session time");
  assert.match(row.timing, /^Answer by: /);
  assert.doesNotMatch(`${row.title} ${row.detail}`, /case/i);
  const notice = (target_type) => ({ id, target_type, target_id: id, title: "t", message: "m" });
  assert.deepEqual(notificationDestination(notice("SESSION_PROPOSAL"), "user"), { href: `/portal/appointments/proposals/${id}`, label: "Choose a session time" });
  assert.deepEqual(notificationDestination(notice("COUNSELING_CASE"), "user"), { href: `/portal/counseling/cases/${id}`, label: "Open case" });
});

test("the mocked session-proposal browser suite runs in both engines in CI", () => {
  assertBrowserSuiteInCI("next-session-proposals.browser.mjs");
});

test("RA-1 session reassignment notifications open the review page", () => {
  const id = "e1000000-0000-4000-8000-000000000001";
  assert.deepEqual(
    notificationDestination({ target_type: "APPOINTMENT_REASSIGNMENT", target_id: id }, "user"),
    { href: `/portal/counseling/reassignments/${id}`, label: "Review session reassignment" },
  );
});
