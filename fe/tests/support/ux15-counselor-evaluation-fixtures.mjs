// Synthetic Routine Interview records only. The shared browser harness blocks every unhandled
// API/provider request, so no professional record or live account is used.
import { user } from "./ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./guidance-messages-fixtures.mjs";

export const routineEvaluationId = "c0000000-0000-4000-8000-000000000015";
export const routineEvaluationPath = `/portal/routine-interviews/${routineEvaluationId}`;

export const evaluationFields = {
  academic_adjustment_rating: 7,
  physical_adjustment_rating: null,
  social_adjustment_rating: 6,
  spiritual_adjustment_rating: 5,
  financial_adjustment_rating: 8,
  emotional_adjustment_rating: 7,
  other_adjustment: "Synthetic other adjustment.",
  special_concern: "Synthetic professional note.",
  recommendations: "Synthetic recommendation.",
};

export const syntheticEncounter = (suffix = "001", entryMode = "WALK_IN") => ({
  id: `d0000000-0000-4000-8000-${suffix.padStart(12, "0")}`,
  started_at: "2026-10-20T02:00:00Z",
  ended_at: "2026-10-20T02:45:00Z",
  entry_mode: entryMode,
  delivery_mode: "IN_PERSON",
  appointment: entryMode === "APPOINTMENT"
    ? { id: "a0000000-0000-4000-8000-000000000015", reference_code: "SYN-APT-015" }
    : null,
});

function emptyIntake() {
  return {
    coping_with_college_challenges: "Synthetic submitted Intake.",
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

export function counselorEvaluationRecord({
  entryMode = "WALK_IN",
  linkedEncounter = null,
  evaluationStatus = "DRAFT",
  evaluation = evaluationFields,
} = {}) {
  return {
    id: routineEvaluationId,
    workflow_state: "ACTIVE",
    student: { id: "e0000000-0000-4000-8000-000000000015", display_name: "Synthetic Student" },
    academic_year: { id: "f0000000-0000-4000-8000-000000000015", label: "2026–2027" },
    inventory_context: null,
    entry_mode: entryMode,
    delivery_mode: "IN_PERSON",
    intake_status: "SUBMITTED",
    intake_submitted_at: "2026-10-19T02:00:00Z",
    intake: emptyIntake(),
    evaluation_status: evaluationStatus,
    evaluation_finalized_at: evaluationStatus === "FINALIZED" ? "2026-10-21T02:00:00Z" : null,
    evaluation,
    form_revision: { id: "form-015", family_key: "routine_interview", official_code: "SYN-RI-015", official_revision: "1", internal_schema_version: 1 },
    appointment: entryMode === "APPOINTMENT"
      ? { id: "a0000000-0000-4000-8000-000000000015", reference_code: "SYN-APT-015", starts_at: "2026-10-20T01:00:00Z", ends_at: "2026-10-20T02:00:00Z" }
      : null,
    counseling_encounter: linkedEncounter,
    counseling_context_available: true,
    created_at: "2026-10-19T01:00:00Z",
  };
}

const counselor = {
  ...user("COUNSELOR"),
  capabilities: [
    ...user("COUNSELOR").capabilities,
    "routine_interviews.view_assigned",
    "routine_interviews.manage_assigned",
    "guidance_followups.view",
  ],
};

export function counselorEvaluationFixture({
  entryMode = "WALK_IN",
  linkedEncounter = null,
  candidates = [syntheticEncounter("001")],
  evaluationStatus = "DRAFT",
  candidateFailurePages = [],
} = {}) {
  const state = {
    detail: counselorEvaluationRecord({ entryMode, linkedEncounter, evaluationStatus }),
    candidates,
    writes: [],
    finalizations: [],
    candidateRequests: [],
    detailReads: 0,
    failCandidatePages: new Set(candidateFailurePages),
    failDetailReads: 0,
    saveFailure: null,
    finalizeMode: "ok",
    holdSave: null,
    holdFinalize: null,
    onWrite: null,
    listCandidates(url) {
      state.candidateRequests.push(url.search);
      const page = Number(url.searchParams.get("page") ?? 1);
      if (state.failCandidatePages.has(page)) {
        state.failCandidatePages.delete(page);
        return { status: 503, body: { error: { code: "synthetic_failure", message: "Synthetic candidate lookup failure." } } };
      }
      const pageSize = Number(url.searchParams.get("page_size") ?? 20);
      const start = (page - 1) * pageSize;
      return {
        status: 200,
        body: {
          items: state.candidates.slice(start, start + pageSize),
          page,
          page_size: pageSize,
          has_next: start + pageSize < state.candidates.length,
        },
      };
    },
  };

  state.handler = async ({ pathname, method, request, reply, route, url }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(sessionFor(counselor));
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${routineEvaluationId}/encounter-candidates` && method === "GET") {
      const result = state.listCandidates(url);
      await reply(result.body, result.status);
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${routineEvaluationId}` && method === "GET") {
      state.detailReads += 1;
      if (state.failDetailReads > 0) {
        state.failDetailReads -= 1;
        await reply({ error: { code: "synthetic_failure", message: "Synthetic current record check failure." } }, 503);
      } else {
        await reply(state.detail);
      }
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${routineEvaluationId}/evaluation` && method === "PUT") {
      const body = JSON.parse(request.postData());
      state.writes.push(body);
      state.onWrite?.(body);
      if (state.holdSave) await state.holdSave;
      if (state.saveFailure === "network") {
        await route.abort("failed");
        return true;
      }
      if (state.saveFailure) {
        await reply({ error: { code: "synthetic_failure", message: "Synthetic evaluation save failure." } }, state.saveFailure);
        return true;
      }
      state.detail = { ...state.detail, evaluation: body };
      await reply(state.detail);
      return true;
    }
    if (pathname === `/api/v1/routine-interviews/${routineEvaluationId}/evaluation/finalize` && method === "POST") {
      const body = JSON.parse(request.postData());
      state.finalizations.push(body);
      if (state.holdFinalize) await state.holdFinalize;
      if (state.finalizeMode === "uncertain-draft") {
        await reply({ error: { code: "synthetic_failure", message: "Synthetic uncertain finalization." } }, 503);
        return true;
      }
      if (state.finalizeMode === "uncertain-committed") {
        state.detail = {
          ...state.detail,
          evaluation_status: "FINALIZED",
          evaluation_finalized_at: "2026-10-21T02:00:00Z",
          counseling_encounter: state.detail.counseling_encounter ?? state.candidates.find((item) => item.id === body.encounter_id) ?? null,
        };
        await reply({ error: { code: "synthetic_failure", message: "Synthetic lost finalization response." } }, 503);
        return true;
      }
      if (state.finalizeMode === "mismatch") {
        await reply({ error: { code: "routine_interview_encounter_mismatch", message: "Synthetic stale candidate." } }, 409);
        return true;
      }
      const encounter = state.detail.counseling_encounter
        ?? state.candidates.find((item) => item.id === body.encounter_id)
        ?? (state.detail.entry_mode === "APPOINTMENT" ? state.candidates[0] : null);
      state.detail = {
        ...state.detail,
        evaluation_status: "FINALIZED",
        evaluation_finalized_at: "2026-10-21T02:00:00Z",
        counseling_encounter: encounter ? { id: encounter.id, started_at: encounter.started_at, ended_at: encounter.ended_at } : null,
      };
      await reply(state.detail);
      return true;
    }
    if (pathname === "/api/v1/routine-interviews" || pathname.startsWith("/api/v1/guidance-followups/")) {
      await reply({ items: [], page: 1, page_size: 20, has_next: false });
      return true;
    }
    return false;
  };
  return state;
}
