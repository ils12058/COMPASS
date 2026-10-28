// Synthetic only; mutations stay inside the local browser harness.
import { readFileSync } from "node:fs";
import { exitRecord } from "./form-ui-1b-fixtures.mjs";
import { user } from "./ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./guidance-messages-fixtures.mjs";
const contract = JSON.parse(readFileSync(new URL("../../../contracts/openapi.json", import.meta.url), "utf8"));
export const selfCodes = contract.components.schemas.SelfAssessmentItemValue.enum;
export const feedbackCodes = contract.components.schemas.CollegeFeedbackItemValue.enum.filter(code => !code.startsWith("PROGRAM_CHAIR_"));
export const student = { ...user("STUDENT"), capabilities: ["exit_interviews.view_self", "exit_interviews.manage_self"], exit_interview_workspace_available: true };
export const exitPath = "/portal/exit-interviews/exit-1b";
export function exitFixture({ missing = false, correction = false } = {}) {
  let detail = { ...exitRecord(feedbackCodes, selfCodes), course: "Synthetic Degree Program", contact_number: "0917 123 4567", program_completion: "ACCORDING_TO_SCHEDULE" };
  if (missing) {
    detail.self_assessment_ratings = detail.self_assessment_ratings.filter(row => row.item_code !== "SELF_ESTEEM");
    detail.college_feedback_ratings = detail.college_feedback_ratings.filter(row => row.item_code !== "GUIDANCE_COUNSELOR_EFFICIENCY");
  }
  if (correction) detail.reopen_events = [
    { id: "earlier", reason: "Earlier synthetic request.", targets: ["general.home_address"], reopened_by: { id: "reviewer", display_name: "Synthetic Reviewer" }, reopened_at: "2026-10-19T02:00:00Z" },
    { id: "latest", reason: "Please review these synthetic answers.", targets: ["general.contact_number", "completion.extra_terms_count", "self_assessment.SELF_ESTEEM", "section.suggestions"], reopened_by: { id: "reviewer", display_name: "Synthetic Reviewer" }, reopened_at: "2026-10-20T02:00:00Z" },
  ];
  const state = { writes: [], submissions: 0, failSave: false, submitMode: "ok", failRefresh: false, holdSave: null, holdSubmit: null };
  const canonical = () => ({ ...detail,
    self_assessment_ratings: detail.self_assessment_ratings.map(row => ({ ...row, item_label: row.item_code })),
    college_feedback_ratings: detail.college_feedback_ratings.map(row => ({ ...row, item_label: row.item_code, category: "Synthetic" })),
  });
  state.handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(student)); return true; }
    if (pathname === "/api/v1/exit-interviews/me/status") { await reply({ academic_year: detail.academic_year, current_record: detail, has_records: true, can_edit_current: detail.can_edit }); return true; }
    if (pathname === "/api/v1/exit-interviews/me") { await reply({ items: [] }); return true; }
    if (pathname === "/api/v1/exit-interviews/me/exit-1b") {
      if (method === "PUT") {
        const body = JSON.parse(request.postData()); state.writes.push(body);
        if (state.holdSave) await state.holdSave;
        if (state.failSave) { await reply({ error: { code: "synthetic_failure", message: "Synthetic save failure" } }, 500); return true; }
        detail = { ...detail, ...body };
      } else if (state.failRefresh) { await reply({ error: { code: "synthetic_failure", message: "Synthetic refresh failure" } }, 503); return true; }
      await reply(canonical()); return true;
    }
    if (pathname === "/api/v1/exit-interviews/me/exit-1b/submit") {
      state.submissions++;
      if (state.holdSubmit) await state.holdSubmit;
      if (state.submitMode !== "unknown-draft") detail = { ...detail, status: "SUBMITTED", can_edit: false, last_submitted_at: "2026-10-21T04:00:00Z" };
      if (state.submitMode !== "ok") { await reply({ error: { code: "synthetic_failure", message: "Synthetic uncertain result" } }, 503); return true; }
      await reply(canonical()); return true;
    }
    return false;
  };
  return state;
}
