// Shared synthetic Inventory fixture; never touches a live account.
import { user } from "./ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./guidance-messages-fixtures.mjs";
const student = { ...user("STUDENT"), capabilities: ["inventory.view_self", "inventory.manage_self"] };
const revision = { id: "revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" };
export function inventoryFixture({ incomplete = false, submitted = false } = {}) {
  let current = {
    id: "synthetic-inventory", academic_year: { id: "year", label: "2026–2027" }, status: submitted ? "SUBMITTED" : "DRAFT", program: null, form_revision: revision,
    correction_pending: false, latest_correction: null, submitted_at: submitted ? "2026-10-21T03:00:00Z" : null, first_submitted_at: submitted ? "2026-10-21T03:00:00Z" : null, last_submitted_at: submitted ? "2026-10-21T03:00:00Z" : null,
    full_name: "Synthetic Student", nickname: "Syn", student_number: "SYNTHETIC-01", sex: incomplete ? null : "FEMALE", date_of_birth: "2005-01-15",
    place_of_birth: "Synthetic City", nationality: "Filipino", birth_order_among_siblings: "First",
    civil_status_category: "SINGLE", current_address: "Synthetic Street", permanent_address: "Synthetic Street",
    current_religion_category: "NONE", contact_number: "0917 000 0000", email_address: "synthetic@example.test",
    languages_spoken_at_home: "Filipino", languages_most_fluent: "Filipino, English", religion_from_birth: "None",
    geographic_locations: [{ kind: "CURRENT", region_psgc_code: "050000000", city_municipality_psgc_code: "051603000" }], parent_statuses: ["MARRIED_ANNULLED_LEGALLY_SEPARATED"],
    support_profile: { four_ps_status: "NOT_BENEFICIARY", indigenous_peoples_status: "NOT_MEMBER", mother_life_status: "LIVING", father_life_status: "LIVING" },
    family_members: [
      { kind: "FATHER", name: "Synthetic Father", date_of_birth: "1975-01-01", place_of_birth: "Synthetic City", current_address: "Synthetic Street", permanent_address: "Synthetic Street", contact_number: "0917 000 0001", email_address: "None", educational_attainment: "College", occupation_category: "FARMER", annual_income_status: "UNKNOWN", business_address: "None", business_telephone: "None", languages_spoken: "Filipino", religion_raised_with: "None", current_religion: "None" },
      { kind: "MOTHER", name: "Synthetic Mother", date_of_birth: "1976-01-01", place_of_birth: "Synthetic City", current_address: "Synthetic Street", permanent_address: "Synthetic Street", contact_number: "0917 000 0002", email_address: "None", educational_attainment: "College", occupation_category: "NONE", annual_income_status: "NONE", business_address: "None", business_telephone: "None", languages_spoken: "Filipino", religion_raised_with: "None", current_religion: "None" },
    ],
    guardian_name: "Synthetic Guardian", guardian_relationship: "Aunt", guardian_address: "Synthetic Street", guardian_contact_number: "0917 000 0003",
    emergency_contact_name: "Synthetic Contact", emergency_contact_number: "0917 000 0004",
    siblings: [{ sort_order: 0, name: "Synthetic Student", sex: "FEMALE", age: 21, is_self: true }],
    friends_in_school: "None", friends_outside_school: "None", special_interest: "None", special_skills_talents: "None", hobbies_recreation: "None", ambition_goal: "None", characteristics: "None",
    living_arrangement: "OWN_HOUSE", present_place_people_count: 4, room_sharing_people_count: 2,
    accidents_experienced: "None", operations_experienced: "None", height: "160 cm", weight: "55 kg", physical_disadvantage: "None", pwd_status: "NON_PWD", illness_this_year: "None", previous_illness: "None", immunizations: [],
    education_entries: [
      { level: "ELEMENTARY", school_attended_address: "Synthetic Elementary, Synthetic City", inclusive_years: "2012–2018" },
      { level: "JUNIOR_HIGH", school_attended_address: "Synthetic Junior High, Synthetic City", inclusive_years: "2018–2022" },
      { level: "SENIOR_HIGH", school_attended_address: "Synthetic Senior High, Synthetic City", inclusive_years: "2022–2024" },
    ],
    year_level: 2, schedule_satisfied: true, course_first_choice: true, course_choice_reasons: ["INTEREST_APTITUDE"], lowest_subjects_grades: "Math — 85", highest_subjects_grades: "English — 95",
    inclination_performing_arts: "None", inclination_sports: "None", inclination_leadership: "None", interests: ["PAINTING"], other_skills_hobbies: "None", desired_extracurricular_activities: "None", reading_preferences: "None", handedness: "RIGHT",
    daily_hours_class: "6", daily_hours_library: "1", daily_hours_studying: "2", daily_hours_rest: "8", daily_hours_recreation: "2", daily_hours_other: "1", ideal_monthly_allowance: "FROM_500_TO_1000", intended_work_field: "PROFESSIONAL",
    prior_counseling_experience: false, current_concerns: "None", current_fears: "None", organization_memberships: [], transportation_entries: [],
  };
  const state = { writes: [], submissions: 0, failSave: false, holdSave: null, holdSubmit: null };
  state.handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(student)); return true; }
    if (pathname === "/api/v1/inventory/me/status") { await reply(current); return true; }
    if (pathname === "/api/v1/inventory/me/history") { await reply({ items: [], page: 1, page_size: 20, has_next: false }); return true; }
    if (pathname === "/api/v1/inventory/me/current") {
      if (method === "PUT") {
        state.writes.push(JSON.parse(request.postData()));
        if (state.holdSave) await state.holdSave;
        if (state.failSave) { await reply({ error: { code: "synthetic_failure", message: "Synthetic save failure" } }, 500); return true; }
        current = { ...current, ...state.writes.at(-1) };
      }
      await reply(current); return true;
    }
    if (pathname === "/api/v1/inventory/me/current/submit") {
      state.submissions++;
      if (state.holdSubmit) await state.holdSubmit;
      current = { ...current, status: "SUBMITTED", submitted_at: "2026-10-21T03:00:00Z" };
      await reply(current); return true;
    }
    return false;
  };
  return state;
}
