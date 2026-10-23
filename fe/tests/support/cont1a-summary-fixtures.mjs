// Synthetic CONT-1A records. The old section value/body deliberately simulate stale responses.
import { appointmentId, user } from "./ui-hierarchy-fixtures.mjs";

export { appointmentId };
export const encounterId = "cont1a-encounter";
export const summaryId = "cont1a-summary";
export const privateBody = "CONT-1A-OTHER-COUNSELOR-PRIVATE-SUMMARY";
export const student = { id: "cont1a-student", display_name: "Synthetic CONT-1A Student", institutional_id: "CONT-1A-001" };
export const counselor = (summaries = true) => ({
  ...user(),
  capabilities: [...user().capabilities, "routine_interviews.view_assigned", ...(summaries ? ["shared_summaries.view_assigned", "shared_summaries.manage_assigned"] : [])],
});
export const session = (actor = counselor()) => ({
  user: actor, session: { id: "cont1a-session", expires_at: "2099-01-01T00:00:00Z", is_current: true },
});
export const overview = (changes = {}) => ({
  source_type: "APPOINTMENT", source_id: appointmentId, entry_mode: "APPOINTMENT", delivery_mode: "IN_PERSON",
  valid_from: "2026-01-01T00:00:00Z", valid_until: "2099-01-01T00:00:00Z",
  student: { ...student, campus: null, college: null, program: null, year_level: 4 },
  matching_encounter: null, routine_interview: null,
  available_sections: ["INVENTORY", "SUPPORT_INDICATORS", "HISTORY", "SHARED_SUMMARIES"],
  ...changes,
});
export const encounter = (changes = {}) => ({
  id: encounterId, student, counselor: { id: "counselor", display_name: "Synthetic Current Counselor" },
  service: { id: "cont1a-service", code: "COUNSELING", name: "Counseling" },
  appointment: { id: appointmentId, reference_code: "CONT-1A-APT" },
  entry_mode: "APPOINTMENT", delivery_mode: "IN_PERSON",
  started_at: "2026-01-06T01:00:00Z", ended_at: "2026-01-06T01:45:00Z",
  created_at: "2026-01-06T02:00:00Z", updated_at: "2026-01-06T02:00:00Z", ...changes,
});
export const recorded = { id: encounterId, started_at: encounter().started_at, ended_at: encounter().ended_at, routine_interview_linked: true };
export const summary = (changes = {}) => ({
  id: summaryId, encounter_id: encounterId, content: "Synthetic author draft", published_at: null,
  created_at: "2026-01-06T02:00:00Z", updated_at: "2026-01-06T02:00:00Z", ...changes,
});
export const priorSummary = { id: "cont1a-other-summary", content: privateBody, published_at: "2026-01-06T02:00:00Z", counseling_ended_at: encounter().ended_at, counselor: { id: "other-counselor", display_name: "Synthetic Previous Counselor" } };
