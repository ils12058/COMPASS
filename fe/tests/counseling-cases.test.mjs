import assert from "node:assert/strict";
import { test } from "node:test";

import {
  CASES_PATH,
  SESSION_RECORDS_PATH,
  caseHref,
  openCaseHref,
  caseStatusLabel,
  caseOriginLabel,
  caseOrderingOptions,
  caseSessionRemovalReasons,
  sessionCountLabel,
  caseEventSummary,
  caseSessionOffers,
  caseErrorCode,
  caseErrorMessage,
  isUncertainCaseResult,
  isStaleCaseError,
} from "../src/features/counseling/cases/case-presentation.ts";
import { encounterCreatePayload } from "../src/features/counseling/record-encounter-form.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";

const caseId = "10000000-0000-4000-8000-000000000001";
const started = "2026-01-06T01:00:00Z";
const ended = "2026-01-06T02:00:00Z";
test("source and linked-Appointment offers show an explicitly projected session once", () => {
  const first = { encounter_id: "one", started_at: started, ended_at: ended, appointment: null };
  const second = { ...first, encounter_id: "two" };
  assert.deepEqual(caseSessionOffers({ unlinked_origin_session: first, unlinked_appointment_sessions: [first, second] }), [first, second]);
  assert.deepEqual(caseSessionOffers({ unlinked_origin_session: null, unlinked_appointment_sessions: [] }), []);
  assert.deepEqual(caseSessionOffers({ unlinked_origin_session: null, unlinked_appointment_sessions: [second] }), [second]);
});
function apiError(code, status = 409, message = "Untrusted backend wording") {
  return new CompassApiError({ status, body: { error: { code, message } }, headers: {}, method: "POST", url: "/api/v1/counseling/cases" });
}

test("case destinations keep My cases, Session records and the case overview distinct", () => {
  assert.equal(CASES_PATH, "/portal/counseling");
  assert.equal(SESSION_RECORDS_PATH, "/portal/counseling/encounters");
  assert.equal(caseHref(caseId), `/portal/counseling/cases/${caseId}`);
});

test("an intake can start with or without a selected Student, and encodes the ID", () => {
  assert.equal(openCaseHref(), "/portal/counseling/cases/new");
  assert.equal(openCaseHref({ origin: "INTAKE" }), "/portal/counseling/cases/new");
  assert.equal(openCaseHref({ origin: "INTAKE", studentId: "" }), "/portal/counseling/cases/new");
  assert.equal(openCaseHref({ origin: "INTAKE", studentId: "student/1 &2" }), "/portal/counseling/cases/new?student=student%2F1%20%262");
});
for (const origin of ["APPOINTMENT", "ENCOUNTER", "ROUTINE_INTERVIEW"]) {
  for (const studentId of [undefined, "student/1"]) {
    test(`${origin} links carry the source, with ${studentId ? "a" : "no"} Student supplied`, () => {
      assert.equal(openCaseHref({ origin, sourceId: "source/1 &2", ...(studentId ? { studentId } : {}) }), `/portal/counseling/cases/new?origin=${origin}&source=source%2F1%20%262`);
    });
  }
}

for (const [status, label] of [["ACTIVE", "Active"], ["CLOSED", "Closed"], ["FUTURE_STATUS", "Not available"]]) {
  test(`case status ${status} has safe display copy`, () => assert.equal(caseStatusLabel(status), label));
}
for (const [origin, label] of [["INTAKE", "Counseling intake"], ["APPOINTMENT", "Appointment"], ["ENCOUNTER", "Recorded session"], ["ROUTINE_INTERVIEW", "Routine Interview"], ["FUTURE_ORIGIN", "Not available"]]) {
  test(`case origin ${origin} has safe display copy`, () => assert.equal(caseOriginLabel(origin), label));
}
test("sort and removal choices use the complete closed vocabularies", () => {
  assert.deepEqual(caseOrderingOptions.map(({ value }) => value), ["LATEST_ACTIVITY", "LATEST_OPENED", "OLDEST_OPENED", "STUDENT_ASC", "STUDENT_DESC"]);
  assert.deepEqual(caseSessionRemovalReasons, [
    { value: "BELONGS_TO_ANOTHER_CASE", label: "It belongs to another case" },
    { value: "NOT_PART_OF_THIS_CASE", label: "It isn't part of this case" },
    { value: "LINKED_BY_MISTAKE", label: "It was added by mistake" },
  ]);
});
for (const [count, label] of [[0, "0 completed sessions"], [1, "1 completed session"], [2, "2 completed sessions"], [10, "10 completed sessions"]]) {
  test(`${count} linked sessions use the right count label`, () => assert.equal(sessionCountLabel(count), label));
}

for (const [detail_code, phrase] of [["INTAKE", "a Counseling intake"], ["APPOINTMENT", "an Appointment"], ["ENCOUNTER", "a recorded session"], ["ROUTINE_INTERVIEW", "a Routine Interview"], ["FUTURE_ORIGIN", "an authorized record"]]) {
  test(`opening history names ${detail_code} from the event's own facts`, () => {
    assert.equal(caseEventSummary({ kind: "OPENED", detail_code, encounter_started_at: null }), `Case opened from ${phrase}`);
  });
}
test("an opening without a source code and an unknown event have safe summaries", () => {
  assert.equal(caseEventSummary({ kind: "OPENED", detail_code: null, encounter_started_at: null }), "Case opened");
  assert.equal(caseEventSummary({ kind: "OPENED", detail_code: "", encounter_started_at: null }), "Case opened");
  assert.equal(caseEventSummary({ kind: "FUTURE_EVENT", detail_code: null, encounter_started_at: null }), "Case updated");
});
for (const [time, subject] of [[null, "A session"], [started, "Session of Jan 6, 2026, 9:00 AM"]]) {
  test(`link history ${time ? "dates the session in Philippine Time" : "handles an absent session date"}`, () => {
    assert.equal(caseEventSummary({ kind: "SESSION_LINKED", detail_code: null, encounter_started_at: time }), `${subject} added to the case`);
  });
  for (const [detail_code, suffix] of [["BELONGS_TO_ANOTHER_CASE", ": it belongs to another case"], ["NOT_PART_OF_THIS_CASE", ": it isn't part of this case"], ["LINKED_BY_MISTAKE", ": it was added by mistake"], [null, ""], ["FUTURE_REASON", ""]]) {
    test(`removal history ${detail_code ?? "without a reason"}, ${time ? "dated" : "undated"}`, () => {
      assert.equal(caseEventSummary({ kind: "SESSION_UNLINKED", detail_code, encounter_started_at: time }), `${subject} removed from the case${suffix}`);
    });
  }
}

const errors = {
  permission_denied: "You can't use Counseling cases.",
  counseling_case_not_found: "You don't have access to this case.",
  counseling_case_source_not_found: "You don't have access to the record this case would start from.",
  counseling_case_session_not_found: "This session isn't available to add or remove. Refresh the case and try again.",
  counseling_case_invalid_request: "Some case details need attention. Review them and try again.",
  counseling_case_source_invalid: "A case can't be opened from this record now.",
  counseling_case_review_required: "Your active cases for this Student changed. Review them before opening a case.",
  counseling_case_closed: "This case is closed, so its sessions can't be changed.",
  counseling_case_changed: "This case changed before your action completed. The latest details are now shown.",
  counseling_case_session_already_linked: "This session already belongs to a case.",
  counseling_case_session_student_mismatch: "This session is for a different Student than the case.",
  counseling_case_reference_exhausted: "A case can't be opened right now. Contact your IT Administrator.",
  counseling_service_not_configured: "Cases can't be opened until the Counseling Service is set up.",
  counseling_not_permitted: "You can't perform this counseling action.",
};
for (const [code, copy] of Object.entries(errors)) {
  test(`case error ${code} is mapped by its code, independent of backend wording`, () => {
    assert.equal(caseErrorCode(apiError(code)), code);
    assert.equal(caseErrorMessage(apiError(code), "Fallback"), copy);
    assert.equal(caseErrorMessage(apiError(code, 422, ""), "Fallback"), copy);
  });
}
test("unknown, malformed and non-API case errors use the supplied fallback", () => {
  for (const error of [apiError("future_case_error"), apiError("constructor"), apiError("counseling-case-not-found"), new Error("counseling_case_not_found"), null, undefined, { error: { code: "counseling_case_not_found" } }, new CompassApiError({ status: 422, body: null, headers: {}, method: "POST", url: "/api/v1/counseling/cases" })]) {
    assert.equal(caseErrorMessage(error, "Safe fallback"), "Safe fallback");
  }
});
for (const status of [400, 403, 404, 409, 422, 499, 500, 503]) {
  test(`HTTP ${status} ${status >= 500 ? "does not confirm" : "confirms refusal of"} a case mutation`, () => assert.equal(isUncertainCaseResult(apiError("synthetic_error", status)), status >= 500));
}
test("a connection error or absent API response is an uncertain result", () => {
  for (const error of [new TypeError("Failed to fetch"), new Error("Connection closed"), null, undefined]) assert.equal(isUncertainCaseResult(error), true);
});
for (const [code, stale] of [["counseling_case_changed", true], ["counseling_case_closed", true], ["counseling_case_review_required", false], ["counseling_case_session_already_linked", false], ["future_case_error", false]]) {
  test(`${code} ${stale ? "requires" : "does not select"} case-detail stale recovery`, () => assert.equal(isStaleCaseError(apiError(code)), stale));
}
test("a network failure cannot be treated as a stale-case response", () => assert.equal(isStaleCaseError(new TypeError("Failed to fetch")), false));

for (const case_id of [undefined, caseId]) {
  test(`a direct session ${case_id ? "carries the case ID" : "remains valid without a case"}`, () => {
    assert.deepEqual(encounterCreatePayload({ entryMode: "WALK_IN", studentId: "student-1", studentName: "Synthetic Student", deliveryMode: "IN_PERSON" }, started, ended, case_id), { student_id: "student-1", entry_mode: "WALK_IN", delivery_mode: "IN_PERSON", started_at: started, ended_at: ended, ...(case_id ? { case_id } : {}) });
  });
  test(`an Appointment session ${case_id ? "carries the case ID" : "remains valid without a case"} and leaves identity to the Appointment`, () => {
    assert.deepEqual(encounterCreatePayload({ entryMode: "APPOINTMENT", appointmentId: "appointment-1", studentId: "unused-student", studentName: "Synthetic Student", deliveryMode: "ONLINE", scheduledStartsAt: "2026-01-06T00:00:00Z" }, started, ended, case_id), { appointment_id: "appointment-1", entry_mode: "APPOINTMENT", started_at: started, ended_at: ended, ...(case_id ? { case_id } : {}) });
  });
}
test("Routine Interview provenance survives recording into a case", () => {
  assert.deepEqual(encounterCreatePayload({ entryMode: "CALLED_IN", studentId: "student-1", studentName: "Synthetic Student", routineInterviewId: "routine-1", deliveryMode: "IN_PERSON" }, started, ended, caseId), { student_id: "student-1", entry_mode: "CALLED_IN", delivery_mode: "IN_PERSON", routine_interview_id: "routine-1", case_id: caseId, started_at: started, ended_at: ended });
});
