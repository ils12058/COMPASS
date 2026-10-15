// Synthetic Exit Interview records for component and browser regression tests.
export const academicYear = { id: "year-1b", label: "2026-2027" };
export function exitRecord(feedbackCodes, selfCodes, legacy = false) {
  const codes = feedbackCodes.filter(code => legacy || !code.startsWith("PROGRAM_CHAIR_"));
  return {
    id: "exit-1b", academic_year: academicYear, can_edit: true, status: "DRAFT", inventory_id: "inventory-1b",
    student: { id: "student", display_name: "Synthetic Student", institutional_id: "TEST-1B" }, student_name: "Synthetic Student",
    form_revision: legacy ? null : { id: "ucn-f9", official_code: "UCN-OP-GCO-01F9", official_revision: "1", internal_schema_version: 2 },
    college_feedback_item_codes: codes,
    self_assessment_ratings: selfCodes.map(item_code => ({ item_code, item_label: item_code, rating: 5 })),
    college_feedback_ratings: codes.map(item_code => ({ item_code, category: "Synthetic", item_label: item_code, rating: 0 })),
    program_chair_comments: legacy ? "SYNTHETIC LEGACY CHAIR CONTENT" : "",
    reopen_events: [], created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z", first_submitted_at: null, last_submitted_at: null,
  };
}
