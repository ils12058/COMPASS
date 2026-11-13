import assert from "node:assert/strict";
import { test } from "node:test";
import { CaseClosureReason, CaseClosureOutcome, CaseReopenReason, CaseClosureBlockerKind } from "../src/lib/api/generated/model/index.ts";
import { closureReasonLabels, closureReasonOptions, closureOutcomeLabels, reopenReasonLabels, closureBlockerLabels, closureSummary, closureNoteError, closureError, closureRequiresReview } from "../src/features/counseling/cases/closure-presentation.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { caseHistoryRows } from "../src/features/counseling/cases/case-history-panel.tsx";
import { continuityError, continuityStale } from "../src/features/counseling/continuity/continuity-presentation.ts";

test("closure reason, outcome, reopening and blocker labels cover the canonical vocabularies", () => {
  for (const [enumeration, labels] of [[CaseClosureReason, closureReasonLabels], [CaseClosureOutcome, closureOutcomeLabels], [CaseReopenReason, reopenReasonLabels], [CaseClosureBlockerKind, closureBlockerLabels]]) assert.deepEqual(Object.keys(labels).sort(), Object.values(enumeration).sort());
  assert.deepEqual(Object.keys(closureReasonOptions).sort(), Object.keys(closureReasonLabels).sort());
  for (const label of Object.values(closureReasonOptions)) assert.ok(label.length < 25, "Native select labels fit phone width; full labels are separate help text");
});

for (const reason of ["PLANNED_SUPPORT_CONCLUDED", "STUDENT_DISCONTINUED", "CONTACT_NOT_REESTABLISHED", "EXTERNAL_HANDOVER_CONFIRMED", "ELIGIBILITY_ENDED"]) {
  for (const outcome of ["GOALS_MET", "GOALS_PARTLY_MET", "GOALS_NOT_MET", "NOT_ASSESSED"]) {
    test(`${reason} with ${outcome} preserves the reason without overstating the outcome`, () => {
      const label = closureSummary(reason, outcome);
      assert.doesNotMatch(label, /resolved|successful/i);
      if (reason === "PLANNED_SUPPORT_CONCLUDED" && outcome === "GOALS_MET") assert.equal(label, "Support concluded — goals met");
      else {
        assert.equal(label, `${closureReasonLabels[reason]} · ${closureOutcomeLabels[outcome]}`);
        assert.notEqual(label, "Support concluded — goals met");
      }
    });
  }
}

test("contact-not-restored requires documented attempts without imposing an attempt count", () => {
  assert.match(closureNoteError("CONTACT_NOT_REESTABLISHED", "   a brief note   "), /at least 20 characters/);
  assert.equal(closureNoteError("CONTACT_NOT_REESTABLISHED", "Contact attempts are documented in the retained case record."), null);
  assert.equal(closureNoteError("STUDENT_DISCONTINUED", ""), null);
  assert.equal(closureNoteError("PLANNED_SUPPORT_CONCLUDED", "x".repeat(4000)), null);
  assert.match(closureNoteError("PLANNED_SUPPORT_CONCLUDED", "x".repeat(4001)), /at most 4,000/);
});

function error(code) { return new CompassApiError({ status: 409, body: { error: { code, message: "Confidential diagnostic must never render" } }, headers: {}, method: "POST", url: "/api/v1/counseling/cases/synthetic/close" }); }

test("blocked closure presents each work kind and tells the owner to resolve its owning workflow", () => {
  assert.deepEqual(Object.values(closureBlockerLabels), ["Pending transfer", "Pending or current coverage", "Delegated action awaiting return", "Upcoming linked Appointment", "Pending action without an after-closure plan"]);
  assert.match(closureError(error("counseling_case_close_blocked")), /resolve each through its own workflow/);
  assert.doesNotMatch(closureError(error("counseling_case_close_blocked")), /Confidential diagnostic/);
});

test("stale and newly blocked requests require deliberate review while ordinary failures keep input", () => {
  for (const code of ["counseling_case_changed", "counseling_case_closed", "case_not_active", "counseling_case_not_closed", "counseling_case_close_blocked"]) assert.equal(closureRequiresReview(error(code)), true);
  for (const code of ["counseling_case_closure_invalid", "permission_denied", "future_code"]) assert.equal(closureRequiresReview(error(code)), false);
  assert.equal(closureRequiresReview(new TypeError("Failed to fetch")), false);
  assert.equal(closureError(error("future_code"), "Safe fallback"), "Safe fallback");
});

test("closure and continuity history joins true instants across institutional and UTC offsets", () => {
  const person = { id: "person", display_name: "Synthetic Counselor" };
  const rows = caseHistoryRows({
    history: [{ id: "opening", occurred_at: "2026-11-13T08:00:00+08:00", kind: "OPENED", detail_code: null, encounter_started_at: null, actor: person, primary_counselor: person }],
    continuity: { history: [{ id: "acceptance", occurred_at: "2026-11-13T06:00:00Z", kind: "accepted", reference_code: "TRF-SYNTH", actor: person, authorization_route: null }], coverage_history: [] },
    closures: [{ id: "cycle", closed_at: "2026-11-13T11:00:00+08:00", closed_by: person, reason: "STUDENT_DISCONTINUED", outcome: "NOT_ASSESSED", reopened_at: "2026-11-13T15:00:00+08:00", reopened_by: person, reopen_reason: "FURTHER_SUPPORT_NEEDED" }],
  });
  assert.deepEqual(rows.map(row => row.id), ["opening", "closure-cycle", "acceptance", "reopen-cycle"]);
});

test("a reopening transfer accepted after the owner reopened the case is a stale refusal with a plain message", () => {
  const refused = error("case_continuity_case_not_closed");
  assert.equal(continuityStale(refused), true, "The review page refreshes instead of leaving the confirmation open");
  assert.equal(continuityError(refused), "This case is no longer Closed, so this reopening transfer can't be accepted.");
});
