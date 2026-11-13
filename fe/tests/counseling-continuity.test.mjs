import assert from "node:assert/strict";
import { test } from "node:test";
import { arrangementLabel, authorizationLabel, continuityError, continuityStale, continuityReasonLabels, enumChoice, transferHref, transferPrepareHref } from "../src/features/counseling/continuity/continuity-presentation.ts";
import { CaseContinuityReason } from "../src/lib/api/generated/model/index.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";

const summary = { state: "PREPARED", waiting_for: null, receiving_counselor: { display_name: "Receiving Counselor" } };
test("pending, effective and ended arrangements name the actual next actor", () => {
  assert.equal(arrangementLabel(summary), "Prepared — ready for review");
  assert.equal(arrangementLabel({ ...summary, waiting_for: "Head approval" }), "Waiting for Head approval");
  assert.equal(arrangementLabel({ ...summary, state: "AUTHORIZED" }), "Waiting for Receiving Counselor to accept");
  assert.equal(arrangementLabel({ ...summary, state: "ACCEPTED" }), "Accepted");
  for (const state of ["DECLINED", "CANCELLED", "EXPIRED"]) assert.match(arrangementLabel({ ...summary, state }), /another arrangement is needed/);
});
test("the single-Head route explicitly identifies the absence of independent authorization", () => {
  assert.match(authorizationLabel("OWNER_TO_HEAD"), /Personally requested.*no independent Head authorization/);
  assert.match(authorizationLabel("DIRECT_OUTGOING_HEAD"), /own outgoing case/);
  assert.match(authorizationLabel("INDEPENDENT_HEAD"), /before.*accepts/);
});
test("neutral reason choices exhaust the canonical vocabulary without a misconduct label", () => {
  assert.deepEqual(Object.keys(continuityReasonLabels), Object.values(CaseContinuityReason));
  assert.equal(continuityReasonLabels.IMPARTIALITY_CONCERN, "Potential conflict of interest or impartiality concern");
  assert.equal(enumChoice(Object.values(CaseContinuityReason), "constructor"), undefined);
});
test("continuity destinations encode identifiers and queue items use the case reference", () => {
  assert.equal(transferHref("id/1"), "/portal/counseling/transfers/id%2F1");
  assert.equal(transferPrepareHref("id/1"), "/portal/counseling/cases/id%2F1/transfer");
  for (const kind of ["CASE_TRANSFER_AUTHORIZATION", "CASE_TRANSFER_ACCEPTANCE"]) {
    const row = presentWork({ kind, source_id: "transfer", case_reference_code: "CASE-2026-000001", waiting_since: null, due_at: null });
    assert.equal(row.href, "/portal/counseling/transfers/transfer");
    assert.equal(row.title, `${kind === "CASE_TRANSFER_AUTHORIZATION" ? "Authorize case transfer" : "Review incoming case"} · CASE-2026-000001`);
  }
});
function error(code) { return new CompassApiError({ status: 409, body: { error: { code, message: "Private diagnostic" } }, headers: {}, method: "POST", url: "/api/v1/counseling/continuity" }); }
test("stale and denied errors use closed safe copy instead of backend diagnostics", () => {
  assert.equal(continuityError(error("case_continuity_no_independent_approver")), "No independent approver is available.");
  for (const code of ["case_continuity_changed", "case_continuity_owner_changed", "case_continuity_review_expired", "case_continuity_terminal_arrangement", "case_continuity_authorization_changed", "case_continuity_case_not_active"]) assert.equal(continuityStale(error(code)), true);
  for (const value of [error("constructor"), error("future_error"), new Error("Private diagnostic"), null]) {
    assert.equal(continuityError(value, "Safe fallback"), "Safe fallback");
    assert.equal(continuityStale(value), false);
  }
});
