// Synthetic Intake records only. The browser harness blocks every unhandled API/provider request.
import { user } from "./ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./guidance-messages-fixtures.mjs";

export const routineIntakeId = "b0000000-0000-4000-8000-000000000015";
export const routineIntakePath = `/portal/routine-interviews/${routineIntakeId}`;

export function blankRoutineIntake() {
  return {
    coping_with_college_challenges: "",
    coping_remarks: "",
    college_experience: "",
    reason_for_choosing_institution: "",
    difficulties_encountered: "",
    stress_anxiety_causes: "",
    stress_anxiety_management: "",
    family_description: "",
    concerns: [],
    other_concern_specification: "",
    concerns_explanation: "",
    college_adjustment_and_peer_group: "",
    academic_goals: "",
    career_goals: "",
  };
}

function routineRecord({
  intake = blankRoutineIntake(),
  intakeStatus = "DRAFT",
  workflowState = "ACTIVE",
} = {}) {
  return {
    id: routineIntakeId,
    workflow_state: workflowState,
    student: { id: "student", display_name: "Synthetic Student" },
    academic_year: { id: "academic-year", label: "2026–2027" },
    inventory_context: null,
    entry_mode: "WALK_IN",
    delivery_mode: "IN_PERSON",
    intake_status: intakeStatus,
    intake_submitted_at:
      intakeStatus === "SUBMITTED" ? "2026-10-20T02:00:00Z" : null,
    intake,
    evaluation_status: "DRAFT",
    evaluation_finalized_at: null,
    evaluation: null,
    form_revision: {
      id: "form-ux15-synthetic",
      family_key: "routine_interview",
      official_code: "SYN-RI-015",
      official_revision: "1",
      internal_schema_version: 1,
    },
    counselor: { id: "counselor", display_name: "Synthetic Counselor" },
    appointment: null,
    counseling_encounter: null,
    counseling_context_available: false,
    created_at: "2026-10-20T01:00:00Z",
  };
}

function studentAccount({ current = true, canView = true, canManage = true } = {}) {
  const base = user("STUDENT");
  return {
    ...base,
    id: "student",
    first_name: "Synthetic",
    last_name: "Student",
    student_lifecycle_status: current ? "CURRENT" : "GRADUATED",
    capabilities: [
      ...(canView ? ["routine_interviews.view_self"] : []),
      ...(canManage ? ["routine_interviews.manage_self"] : []),
    ],
  };
}

function counselorAccount() {
  return {
    ...user("COUNSELOR"),
    id: "counselor",
    capabilities: ["routine_interviews.view_assigned", "routine_interviews.manage_assigned"],
  };
}

export function routineIntakeFixture({
  account = studentAccount(),
  submitted = false,
  intake = submitted
    ? { ...blankRoutineIntake(), coping_with_college_challenges: "Synthetic response for review." }
    : blankRoutineIntake(),
  workflowState = "ACTIVE",
  counselorDraft = false,
  statusReadFailures = [],
  conflictSubmit = false,
  commitThenLoseSubmitResponse = false,
} = {}) {
  const state = {
    account,
    detail: routineRecord({
      intake: counselorDraft ? null : intake,
      intakeStatus: submitted ? "SUBMITTED" : "DRAFT",
      workflowState,
    }),
    reads: 0,
    writes: [],
    submissions: 0,
    statusChecks: 0,
    failSave: false,
    failSubmit: false,
    statusReadFailures: [...statusReadFailures],
    conflictSubmit,
    commitThenLoseSubmitResponse,
    holdSave: null,
    holdSubmit: null,
  };

  state.handler = async ({ pathname, method, request, reply, route }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(sessionFor(account));
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/me/${routineIntakeId}` && method === "GET") {
      state.reads += 1;
      if (state.submissions > 0) state.statusChecks += 1;
      if (state.statusReadFailures.length && state.submissions > 0) {
        const failure = state.statusReadFailures.shift();
        await reply({ error: { code: failure.code ?? "synthetic_failure" } }, failure.status ?? 503);
        return true;
      }
      if (state.submissions > 0 && state.holdStatusRead) await state.holdStatusRead;
      await reply(state.detail);
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${routineIntakeId}` && method === "GET") {
      state.reads += 1;
      await reply(state.detail);
      return true;
    }
    if (
      pathname === `/api/v1/routine-interviews/me/${routineIntakeId}/intake` &&
      method === "PUT"
    ) {
      const payload = JSON.parse(request.postData());
      state.writes.push(payload);
      state.onWrite?.();
      if (state.holdSave) await state.holdSave;
      if (state.failSave) {
        await reply({ error: { code: "synthetic_failure" } }, 503);
        return true;
      }
      state.detail = { ...state.detail, intake: payload };
      await reply(state.detail);
      return true;
    }
    if (
      pathname === `/api/v1/routine-interviews/me/${routineIntakeId}/submit` &&
      method === "POST"
    ) {
      state.submissions += 1;
      if (state.holdSubmit) await state.holdSubmit;
      if (state.conflictSubmit) {
        state.detail = {
          ...state.detail,
          intake_status: "SUBMITTED",
          intake_submitted_at: "2026-10-21T02:00:00Z",
        };
        await reply({ error: { code: "routine_interview_intake_already_submitted" } }, 409);
        return true;
      }
      if (state.commitThenLoseSubmitResponse) {
        state.detail = {
          ...state.detail,
          intake_status: "SUBMITTED",
          intake_submitted_at: "2026-10-21T02:00:00Z",
        };
        await route.abort("connectionreset");
        return true;
      }
      if (state.failSubmit) {
        await reply({ error: { code: "synthetic_failure" } }, 503);
        return true;
      }
      state.detail = {
        ...state.detail,
        intake_status: "SUBMITTED",
        intake_submitted_at: "2026-10-21T02:00:00Z",
      };
      await reply(state.detail);
      return true;
    }
    if (method !== "GET") {
      await reply({ error: { code: "synthetic_failure" } }, 500);
      return true;
    }
    return false;
  };

  if (account.role === "COUNSELOR") {
    state.detail = routineRecord({ intake: null, intakeStatus: "DRAFT", workflowState });
  }

  return state;
}

export const syntheticStudent = studentAccount;
export const syntheticCounselor = counselorAccount;
