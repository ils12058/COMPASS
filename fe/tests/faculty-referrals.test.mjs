import assert from "node:assert/strict";
import { test } from "node:test";
import { facultyReferralAccess, facultySubmissionAvailable } from "../src/features/faculty-referrals/access.ts";
import { facultyReferralError, confirmationRetryDeadline, uncertainSubmission } from "../src/features/faculty-referrals/presentation.ts";
import { validateReferralFields } from "../src/features/faculty-referrals/use-submission.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";

const faculty = { role: "FACULTY", capabilities: ["referrals.submit_self", "referrals.view_submitted_self"] };
const approved = { can_confirm_student: true, can_submit_referral: true, can_view_submissions: true, valid_until: null };
const error = (status, code, headers = {}) => new CompassApiError({ status, body: { error: { code, message: "Internal details must not appear" } }, headers, method: "POST", url: "/api/v1/faculty/referrals" });

test("Faculty navigation requires independent current availability as well as narrow capabilities", () => {
  assert.deepEqual(portalWorkspaceGroups(faculty), []);
  assert.equal(portalWorkspaceGroups(faculty, approved)[0].links.length, 2);
  const readOnly = { ...approved, can_confirm_student: false, can_submit_referral: false };
  assert.deepEqual(portalWorkspaceGroups(faculty, readOnly)[0].links.map(x => x.label), ["My Referrals"]);
  assert.equal(facultySubmissionAvailable(readOnly), false);
  for (const role of ["STUDENT", "COUNSELOR", "IT_ADMIN", "GUIDANCE_SERVICES_STAFF", "INSTITUTIONAL_OFFICER"]) {
    assert.deepEqual(facultyReferralAccess({ ...faculty, role }), { read: false, submit: false });
  }
  assert.deepEqual(facultyReferralAccess({ ...faculty, capabilities: ["referrals.submit_self"] }), { read: false, submit: false });
});

test("Referral validation preserves overlong content and identifies exact field boundaries", () => {
  assert.deepEqual(validateReferralFields("S-1", "Course", "Concern"), { identifier: "", course: "", reason: "" });
  for (const values of [["", "", ""], [" ", " ", " "], ["x".repeat(65), "x".repeat(256), "x".repeat(10001)]]) {
    const result = validateReferralFields(...values);
    assert.ok(result.identifier && result.course && result.reason);
  }
});

test("Policy denial, conflict and uncertain outcomes use safe actionable copy", () => {
  for (const code of ["faculty_referral_lookup_policy_unconfirmed", "faculty_referral_submission_policy_unconfirmed", "faculty_referral_policy_unconfirmed"]) {
    const message = facultyReferralError(error(403, code), "submit");
    assert.match(message, /not available/);
    assert.doesNotMatch(message, /Internal details|provider|policy_unconfirmed/);
  }
  assert.equal(uncertainSubmission(new TypeError("network")), true);
  assert.equal(uncertainSubmission(error(500, "unexpected")), true);
  assert.equal(uncertainSubmission(error(409, "referral_creation_conflict")), false);
  assert.match(facultyReferralError(error(409, "referral_creation_conflict"), "submit"), /Check My Referrals/);
  assert.match(facultyReferralError(error(503, "unavailable"), "confirm"), /temporarily unavailable/);
  assert.match(facultyReferralError(error(401, "session_expired"), "submit"), /No request will be repeated automatically/);
});

test("Student confirmation honors both Retry-After formats without guessing a retry interval", () => {
  assert.equal(confirmationRetryDeadline(error(429, "rate_limited", { "retry-after": "5" }), 0), "1970-01-01T00:00:05.000Z");
  assert.equal(confirmationRetryDeadline(error(429, "rate_limited", { "retry-after": "Thu, 01 Jan 1970 00:00:10 GMT" }), 0), "1970-01-01T00:00:10.000Z");
  assert.equal(confirmationRetryDeadline(error(429, "rate_limited"), 0), null);
});
