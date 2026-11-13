import assert from "node:assert/strict";
import { test } from "node:test";
import { coverageHref, coverageIntervalError, coveragePrepareHref, coverageStateLabel, coverageTaskInputs, continuityError, returnPlanLabels } from "../src/features/counseling/continuity/continuity-presentation.ts";
import { CaseCoverageReturnPlan } from "../src/lib/api/generated/model/index.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";

const DAY = 86_400_000;
const now = Date.parse("2026-11-13T00:00:00Z");
const iso = offset => new Date(now + offset).toISOString();

test("the coverage interval keeps the 30-day duration and 14-day advance limits", () => {
  assert.equal(coverageIntervalError(null, iso(DAY), now), "Enter when coverage starts and ends.");
  assert.equal(coverageIntervalError(iso(DAY), iso(DAY), now), "Coverage must end after it starts.");
  assert.equal(coverageIntervalError(iso(0), iso(30 * DAY), now), null);
  assert.match(coverageIntervalError(iso(0), iso(30 * DAY + 60_000), now), /at most 30 days/);
  assert.equal(coverageIntervalError(iso(14 * DAY), iso(15 * DAY), now), null);
  assert.match(coverageIntervalError(iso(14 * DAY + 60_000), iso(15 * DAY), now), /at most 14 days ahead/);
  assert.match(coverageIntervalError(iso(-2 * DAY), iso(-DAY), now), /end in the future/);
});

test("only selected, delegable actions are delegated, each with its version and return plan", () => {
  const context = { tasks: [
    { task_id: "a", version: 3, can_delegate: true },
    { task_id: "b", version: 1, can_delegate: false },
    { task_id: "c", version: 2, can_delegate: true },
  ] };
  const choices = {
    a: { selected: true, plan: "REVIEW_WITH_PRIMARY" },
    b: { selected: true, plan: "RETURN_TO_PRIMARY" },
    c: { selected: false, plan: "RETURN_TO_PRIMARY" },
  };
  assert.deepEqual(coverageTaskInputs(context, choices), [{ task_id: "a", expected_version: 3, return_plan: "REVIEW_WITH_PRIMARY" }]);
  assert.deepEqual(coverageTaskInputs(context, {}), []);
  assert.deepEqual(Object.keys(returnPlanLabels), Object.values(CaseCoverageReturnPlan));
});

test("coverage states name the covering Counselor and never imply a change of primary responsibility", () => {
  const format = value => value.slice(0, 10);
  const item = { state: "PREPARED", waiting_for: null, receiving_counselor: { display_name: "Covering Counselor" }, starts_at: "2026-11-14T00:00:00Z", expires_at: "2026-11-20T00:00:00Z" };
  assert.equal(coverageStateLabel(item, format), "Prepared — ready for review");
  assert.equal(coverageStateLabel({ ...item, waiting_for: "Head approval" }, format), "Waiting for Head approval");
  assert.equal(coverageStateLabel({ ...item, state: "AUTHORIZED" }, format), "Waiting for Covering Counselor to accept");
  assert.equal(coverageStateLabel({ ...item, state: "SCHEDULED" }, format), "Covering Counselor covers from 2026-11-14 until 2026-11-20");
  assert.equal(coverageStateLabel({ ...item, state: "ACTIVE" }, format), "Covering counselor: Covering Counselor until 2026-11-20");
  assert.match(coverageStateLabel({ ...item, state: "REVOKED" }, format), /primary Counselor keeps the work/);
  for (const state of ["DECLINED", "CANCELLED", "EXPIRED"]) assert.match(coverageStateLabel({ ...item, state }, format), /another arrangement is needed/);
  for (const state of ["PREPARED", "AUTHORIZED", "SCHEDULED", "ACTIVE", "ENDED", "DECLINED", "CANCELLED", "REVOKED", "EXPIRED"]) {
    assert.doesNotMatch(coverageStateLabel({ ...item, state }, format), /transferred|primary counselor is/i);
  }
});

test("coverage work items and notifications open the coverage review, with only the case reference", () => {
  const base = { id: "case-coverage:x", source_id: "cov-1", student: { id: "s", display_name: "Synthetic Student" }, conversation_kind: null, due_at: "2026-11-20T00:00:00Z", waiting_since: null, case_reference_code: "CASE-2026-000001", priority: "ACTION_REQUIRED" };
  for (const [kind, title] of [["CASE_COVERAGE_AUTHORIZATION", /^Authorize temporary coverage · CASE-2026-000001$/], ["CASE_COVERAGE_ACCEPTANCE", /^Review coverage request/], ["CASE_COVERAGE_WORK", /^Covering case/], ["CASE_COVERAGE_RECOVERY", /^Recover delegated actions/]]) {
    const work = presentWork({ ...base, kind });
    assert.match(work.title, title);
    assert.equal(work.href, coverageHref("cov-1"));
  }
  assert.deepEqual(notificationDestination({ target_type: "CASE_COVERAGE", target_id: "cov-1" }, "me"), { href: "/portal/counseling/coverages/cov-1", label: "Review case coverage" });
  assert.equal(coveragePrepareHref("case/1"), "/portal/counseling/cases/case%2F1/coverage");
});

test("coverage-specific refusals have plain messages", () => {
  const error = code => new CompassApiError({ status: 409, body: { error: { code, message: "Private diagnostic" } }, headers: {}, method: "POST", url: "/api/v1/counseling/coverages/x/submit" });
  assert.equal(continuityError(error("case_continuity_return_plan_required")), "Choose a return plan for every delegated action.");
  assert.match(continuityError(error("case_continuity_coverage_conflict")), /Conflicting coverage/);
  assert.equal(continuityError(error("case_continuity_unknown_code"), "fallback"), "fallback");
});
