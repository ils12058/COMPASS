import assert from "node:assert/strict";
import { test } from "node:test";
import { getAssessmentRecordsAccess } from "../src/features/assessment-records/assessment-records-access.ts";
import { safeAssessmentDetail, assessmentErrorMessage } from "../src/features/assessment-records/assessment-records-shared.tsx";
import { assessmentDraftError } from "../src/features/assessment-records/assessment-record-editor.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const capabilities = ["assessment_records.view", "assessment_records.manage"];
const account = (role = "COUNSELOR", grants = capabilities, head = true) => ({ role, capabilities: grants, designations: head ? ["HEAD_GUIDANCE_COUNSELOR"] : [], id: "test" });
const failure = (status, code) => new CompassApiError({ status, body: { error: { code, message: "PRIVATE-SERVER-SENTINEL" } }, headers: {}, method: "GET", url: "/api/v1/assessment-records/test" });

test("Records navigation and catalog commands respect both role and effective capability", () => {
  for (const role of ["STUDENT", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const user = account(role);
    assert.deepEqual(getAssessmentRecordsAccess(user), { canView: false, canManage: false, canManageTypes: false });
    assert.equal(portalWorkspaceGroups(user).flatMap((group) => group.links).some((link) => link.href === "/portal/assessment-records"), false);
    assert.equal(portalCommandDestinations(user).some((item) => item.href.startsWith("/portal/assessment-records")), false);
  }
  const viewer = account("COUNSELOR", ["assessment_records.view"], false);
  assert.deepEqual(getAssessmentRecordsAccess(viewer), { canView: true, canManage: false, canManageTypes: false });
  assert.equal(portalCommandDestinations(viewer).filter((item) => item.href.startsWith("/portal/assessment-records")).length, 1);
  assert.equal(getAssessmentRecordsAccess(account("COUNSELOR", capabilities, false)).canManageTypes, false);
  assert.equal(getAssessmentRecordsAccess(account()).canManageTypes, true);
  assert.equal(getAssessmentRecordsAccess(account("COUNSELOR", ["assessment_records.manage"])).canManage, false);
});

test("Detail conceals a cached confidential result after authorization, scope or envelope rejection", () => {
  const data = { score: "CONFIDENTIAL-CACHE-SENTINEL" };
  for (const error of [failure(401, "unauthenticated"), failure(403, "permission_denied"), failure(404, "assessment_record_not_found"), failure(500, "assessment_record_content_unavailable")]) {
    assert.equal(safeAssessmentDetail({ data, isError: true, error }), undefined);
    assert.ok(!assessmentErrorMessage(error).includes("PRIVATE-SERVER-SENTINEL"));
  }
  assert.equal(safeAssessmentDetail({ data, isError: true, error: failure(503, "unavailable") }), data);
  assert.equal(safeAssessmentDetail({ data, isError: false, error: null }), data);
  assert.match(assessmentErrorMessage(failure(403, "csrf_failed")), /security check expired/);
});

test("Create form validates eligibility, date and one nonblank source-text result", () => {
  const draft = { assessment_type_id: "type", administered_on: "2020-01-01", score: "88/100", result: "", interpretation: "", remarks: "" };
  assert.equal(assessmentDraftError(draft, "student"), null);
  assert.match(assessmentDraftError(draft), /Student/);
  assert.match(assessmentDraftError({ ...draft, assessment_type_id: "" }, "student"), /Type/);
  assert.match(assessmentDraftError({ ...draft, administered_on: "" }, "student"), /date/);
  assert.match(assessmentDraftError({ ...draft, administered_on: "2099-01-01" }, "student"), /future/);
  assert.match(assessmentDraftError({ ...draft, score: " \n" }, "student"), /at least one/);
  for (const score of ["High", "7.5", "Percentile: source report", "  source text  "]) assert.equal(assessmentDraftError({ ...draft, score }, "student"), null);
});
