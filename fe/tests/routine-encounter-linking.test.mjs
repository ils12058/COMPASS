import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { contextEncounterState } from "../src/features/counseling/counseling-shared.tsx";
import { encounterCreatePayload } from "../src/features/counseling/record-encounter-form.tsx";
import { RoutineCounselorEvaluationWorkspace } from "../src/features/routine-interviews/routine-counselor-evaluation.tsx";
import { StudentRoutineWorkspace } from "../src/features/routine-interviews/routine-student-workspace.tsx";
import {
  getRoutineInterviewsListEncounterCandidatesQueryKey,
  getRoutineInterviewsListMineQueryKey,
  getRoutineInterviewsListMyAppointmentCandidatesQueryKey,
} from "../src/lib/api/generated/routine-interviews/routine-interviews.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const ROUTINE = "routine-1";
const evaluation = {
  academic_adjustment_rating: null,
  physical_adjustment_rating: null,
  social_adjustment_rating: null,
  spiritual_adjustment_rating: null,
  financial_adjustment_rating: null,
  emotional_adjustment_rating: null,
  other_adjustment: "",
  special_concern: "",
  recommendations: "",
};
const encounter = { id: "encounter-1", started_at: "2026-10-07T01:00:00Z", ended_at: "2026-10-07T01:45:00Z" };
const candidate = { ...encounter, id: "encounter-2", entry_mode: "WALK_IN", delivery_mode: "IN_PERSON", appointment: null };

function render(element, seed = () => {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(withNextRouter(h(QueryClientProvider, { client }, element)));
  client.clear();
  return html;
}

function evaluationPanel({ entryMode = "WALK_IN", linkedEncounter = null, candidates = null, workspaceHref = null }) {
  return render(
    h(RoutineCounselorEvaluationWorkspace, {
      routineInterviewId: ROUTINE,
      entryMode,
      linkedEncounter,
      workspaceHref,
      initialEvaluation: evaluation,
      evaluationFinalized: false,
    }),
    (client) => {
      if (candidates) {
        client.setQueryData(
          getRoutineInterviewsListEncounterCandidatesQueryKey(ROUTINE, { page: 1, page_size: 20 }),
          ok({ items: candidates, page: 1, page_size: 20, has_next: false }),
        );
      }
    },
  );
}

const finalizeButton = (html) => html.match(/<button[^>]*>Finalize Counselor Evaluation<\/button>/)?.[0] ?? "";

test("appointment Routine Interviews are completed, not started, by the Student", () => {
  const access = { isStudent: true, isCounselor: false, isCurrentStudent: true, canViewSelf: true, canManageSelf: true, canViewAssigned: false, canManageAssigned: false, hasWorkspace: true };
  const appointment = {
    id: "appointment-1",
    reference_code: "APT-2026-000001",
    counselor: { id: "counselor", display_name: "Counselor Example" },
    delivery_mode: "IN_PERSON",
    starts_at: "2026-10-08T01:00:00Z",
    ends_at: "2026-10-08T02:00:00Z",
  };
  const html = render(h(StudentRoutineWorkspace, { access }), (client) => {
    client.setQueryData(getRoutineInterviewsListMineQueryKey(), ok({ items: [] }));
    client.setQueryData(getRoutineInterviewsListMyAppointmentCandidatesQueryKey(), ok({ items: [appointment] }));
  });
  assert.match(html, /Complete Routine Interview<span class="sr-only"> for APT-2026-000001<\/span>/);
  assert.doesNotMatch(html, /Start Routine Interview/);
});

test("a linked Encounter finalizes without any Encounter selection", () => {
  const html = evaluationPanel({ linkedEncounter: encounter });
  assert.doesNotMatch(html, /name="routine-finalize-encounter"/);
  assert.doesNotMatch(html, /recorded outside this Routine Interview/);
  assert.match(html, /<dt[^>]*>Counseling Encounter<\/dt>/);
  assert.doesNotMatch(finalizeButton(html), / disabled=""/);
});

test("an Appointment-backed Routine Interview never asks for a choice", () => {
  const html = evaluationPanel({ entryMode: "APPOINTMENT", candidates: [{ ...candidate, entry_mode: "APPOINTMENT" }] });
  assert.doesNotMatch(html, /name="routine-finalize-encounter"/);
  assert.match(html, /Finalizing links it to this Routine Interview/);
});

test("an unlinked direct Routine Interview points to its workspace and offers recovery only for recorded Encounters", () => {
  const empty = evaluationPanel({ candidates: [], workspaceHref: `/portal/counseling/workspace/routine-interview/${ROUTINE}` });
  assert.match(empty, /Counseling Encounter not yet recorded/);
  assert.match(empty, /href="\/portal\/counseling\/workspace\/routine-interview\/routine-1"/);
  assert.doesNotMatch(empty, /name="routine-finalize-encounter"/);
  assert.match(finalizeButton(empty), / disabled=""/);

  const recovery = evaluationPanel({ candidates: [candidate] });
  assert.match(recovery, /Encounters recorded outside this Routine Interview/);
  assert.match(recovery, /name="routine-finalize-encounter"/);
  assert.match(finalizeButton(recovery), / disabled=""/);
});

test("workspace state follows the persisted link, not similarity", () => {
  const recorded = { ...encounter, routine_interview_linked: true };
  const similar = { ...encounter, routine_interview_linked: false };
  assert.equal(contextEncounterState({ source_type: "ROUTINE_INTERVIEW", matching_encounter: recorded }), "RECORDED");
  assert.equal(contextEncounterState({ source_type: "ROUTINE_INTERVIEW", matching_encounter: similar }), "RECORDED_OUTSIDE_ROUTINE");
  assert.equal(contextEncounterState({ source_type: "APPOINTMENT", matching_encounter: similar }), "RECORDED");
  assert.equal(contextEncounterState({ source_type: "ROUTINE_INTERVIEW", matching_encounter: null }), "NOT_RECORDED");
});

test("recording from a Routine Interview workspace sends its Routine Interview", () => {
  const origin = { entryMode: "WALK_IN", studentId: "student", studentName: "Student", deliveryMode: "IN_PERSON" };
  assert.deepEqual(encounterCreatePayload({ ...origin, routineInterviewId: ROUTINE }, "start", "end"), {
    student_id: "student",
    entry_mode: "WALK_IN",
    delivery_mode: "IN_PERSON",
    routine_interview_id: ROUTINE,
    started_at: "start",
    ended_at: "end",
  });
  assert.equal("routine_interview_id" in encounterCreatePayload(origin, "start", "end"), false);
  assert.deepEqual(
    encounterCreatePayload({ entryMode: "APPOINTMENT", appointmentId: "appointment", studentName: "Student", deliveryMode: "ONLINE" }, "start", "end"),
    { appointment_id: "appointment", entry_mode: "APPOINTMENT", started_at: "start", ended_at: "end" },
  );
});
