// CENC-3: what the Counselor's E-Counseling session says about its Counseling Encounter, and which
// single action it offers. The decision and its copy live in encounter-section-state.ts, so this
// suite covers them without the Daily call runtime.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { encounterSectionView } from "../src/features/ecounseling/encounter-section-state.ts";
import { ECounselingWorkspace } from "../src/features/ecounseling/ecounseling-workspace.tsx";
import { ActiveECounselingCallContext } from "../src/features/ecounseling/runtime/active-call-context.ts";
import { initialCallSnapshot } from "../src/features/ecounseling/call/call-model.ts";
import { finishCounselingState, unconfirmedFinishMessage } from "../src/features/counseling/finish-counseling-availability.ts";
import { counselingErrorMessage, unconfirmedEncounterMessage } from "../src/features/counseling/counseling-shared.tsx";
import { sessionEncounterPreset } from "../src/features/ecounseling/ecounseling-shared.ts";
import { encounterCreatePayload } from "../src/features/counseling/record-encounter-form.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { getAppointmentsGetQueryKey } from "../src/lib/api/generated/appointments/appointments.ts";
import { getECounselingGetAssignedWorkspaceQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { withNextRouter } from "./support/next-router.mjs";
import { appointmentId, user, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const ENCOUNTER_ID = "e0000000-0000-4000-8000-000000000001";
const AUTHORING = ["finish", "record"];

// One section input set, with every axis open; the defaults are the mid-session case where the
// Counselor could finish and the access window has ended.
function section(overrides = {}) {
  return {
    canManageAssigned: true,
    appointmentReadConfirmed: true,
    finishState: "OFFERED",
    joinState: "CLOSED",
    encounterId: undefined,
    recorded: false,
    uncertainSave: null,
    ...overrides,
  };
}

const actions = (view) => view.actions.filter((action) => AUTHORING.includes(action));

test("RECORDED: the session's own Counseling Encounter exists", () => {
  const view = encounterSectionView(section({ recorded: true, encounterId: ENCOUNTER_ID }));
  assert.equal(view.state, "RECORDED");
  assert.equal(view.status, "Recorded");
  assert.equal(view.message, "Encounter recorded.");
  assert.deepEqual(view.actions, ["view-encounter"]);

  // A confirmed Appointment read saying the same thing is enough, even if this projection is stale.
  const fromAppointment = encounterSectionView(section({ finishState: "RECORDED", appointmentReadConfirmed: true }));
  assert.equal(fromAppointment.state, "RECORDED");
  // With nothing to open, the review list is offered instead of an invented Encounter id.
  assert.deepEqual(fromAppointment.actions, ["view-encounters"]);
});

test("MISMATCH: a linked Encounter that is not this Appointment's record", () => {
  const view = encounterSectionView(section({ encounterId: ENCOUNTER_ID, recorded: false }));
  assert.equal(view.state, "MISMATCH");
  assert.equal(view.status, "Not this Appointment’s record");
  assert.equal(
    view.message,
    "A Counseling Encounter is linked to this Appointment but is not its Counseling-Appointment record. Review it in My counseling encounters.",
  );
  assert.deepEqual(actions(view), [], "A mismatch is reviewed, never recorded over");
});

test("FINISH: one action records the Encounter and completes the Appointment", () => {
  const view = encounterSectionView(section());
  assert.equal(view.state, "FINISH");
  assert.equal(view.status, "Not yet recorded");
  assert.equal(
    view.message,
    "Finish counseling after the conversation. This records the Encounter and completes the Appointment.",
  );
  assert.deepEqual(view.actions, ["finish"]);
});

test("WINDOW_OPEN: the access period is explained, and nothing is offered", () => {
  const view = encounterSectionView(section({ joinState: "OPEN" }));
  assert.equal(view.state, "WINDOW_OPEN");
  assert.equal(view.status, "Not yet recorded");
  assert.equal(view.message, "The online access period is still open. Finish counseling becomes available here once it ends.");
  assert.deepEqual(view.actions, []);
});

test("FALLBACK_RECORD: only an unconfirmed Appointment read falls back to recording", () => {
  const view = encounterSectionView(section({ appointmentReadConfirmed: false, finishState: "UNAVAILABLE" }));
  assert.equal(view.state, "FALLBACK_RECORD");
  assert.equal(view.status, "Not yet recorded");
  assert.equal(view.message, "Record the encounter after the counseling conversation.");
  assert.deepEqual(view.actions, ["record"]);
});

test("UNCERTAIN: an unconfirmed outcome is checked, never replayed", () => {
  const finish = encounterSectionView(section({ uncertainSave: "FINISH" }));
  assert.equal(finish.state, "UNCERTAIN");
  assert.equal(finish.status, "Not confirmed");
  assert.equal(finish.message, unconfirmedFinishMessage);
  assert.deepEqual(finish.actions, ["check-again", "view-encounters"]);

  const record = encounterSectionView(section({ appointmentReadConfirmed: false, uncertainSave: "RECORD" }));
  assert.equal(record.state, "UNCERTAIN");
  assert.equal(record.message, unconfirmedEncounterMessage);
  assert.deepEqual(actions(record), [], "The fallback save is not offered again while its result is unknown");
});

test("No manage authority: the session reports and never authors", () => {
  const view = encounterSectionView(section({ canManageAssigned: false, finishState: "UNAVAILABLE", appointmentReadConfirmed: false }));
  assert.equal(view.state, "READ_ONLY");
  assert.equal(view.status, "Not yet recorded");
  assert.equal(view.message, "Record the encounter after the counseling conversation.");
  assert.deepEqual(view.actions, []);

  // The record itself is still reported to a Counselor who cannot manage it.
  assert.equal(encounterSectionView(section({ canManageAssigned: false, recorded: true, encounterId: ENCOUNTER_ID })).state, "RECORDED");
});

test("NOT_AVAILABLE: a confirmed read that cannot be finished routes to the Appointment", () => {
  const view = encounterSectionView(section({ finishState: "UNAVAILABLE", joinState: "CLOSED" }));
  assert.equal(view.state, "NOT_AVAILABLE");
  assert.equal(view.status, "Not yet recorded");
  assert.deepEqual(actions(view), [], "Nothing is offered that the server would refuse");
  assert.deepEqual(view.actions, ["view-appointment"]);
});

test("nothing authoring is offered while the online access window is open", () => {
  for (const canManageAssigned of [true, false]) {
    for (const appointmentReadConfirmed of [true, false]) {
      for (const finishState of ["OFFERED", "RECORDED", "UNAVAILABLE"]) {
        for (const uncertainSave of [null, "FINISH", "RECORD"]) {
          const view = encounterSectionView(section({
            canManageAssigned,
            appointmentReadConfirmed,
            finishState,
            uncertainSave,
            joinState: "OPEN",
          }));
          assert.deepEqual(actions(view), [], `${canManageAssigned}/${appointmentReadConfirmed}/${finishState}/${uncertainSave}`);
        }
      }
    }
  }
  // Recording during the window is the bypass this slice closes; the linked record is still shown.
  assert.deepEqual(actions(encounterSectionView(section({ joinState: "OPEN", recorded: true, encounterId: ENCOUNTER_ID }))), []);
});

test("Record is offered only when the Appointment read is not confirmed", () => {
  for (const canManageAssigned of [true, false]) {
    for (const appointmentReadConfirmed of [true, false]) {
      for (const finishState of ["OFFERED", "RECORDED", "UNAVAILABLE"]) {
        for (const joinState of ["TOO_EARLY", "OPEN", "CLOSED", "PROVIDER_DISABLED"]) {
          const view = encounterSectionView(section({
            canManageAssigned,
            appointmentReadConfirmed,
            finishState,
            joinState,
            uncertainSave: null,
          }));
          if (view.actions.includes("record")) {
            assert.equal(appointmentReadConfirmed, false, `${canManageAssigned}/${finishState}/${joinState}`);
          }
          if (view.actions.includes("finish")) {
            assert.equal(appointmentReadConfirmed, true);
            assert.equal(finishState, "OFFERED");
            assert.notEqual(joinState, "OPEN");
          }
        }
      }
    }
  }
});

test("Finish needs Counseling management and Appointment management", () => {
  // The same wiring EncounterSection uses: the state comes from the confirmed Appointment read, and
  // canFinish is the conjunction of both capabilities.
  const appointment = {
    status: "SCHEDULED",
    service: { id: "svc", code: "COUNSELING", name: "Counseling" },
    counseling_encounter_recorded: false,
    actions: { complete: { allowed: true, blocker: null, consequences: [] } },
  };
  const viewFor = ({ canManageAssigned, canManageAppointments }) => {
    const canFinish = canManageAssigned && canManageAppointments;
    // EncounterSection only asks for the Appointment when both capabilities could finish it, so an
    // unread Appointment is, by definition, an unconfirmed read.
    const record = canFinish ? appointment : undefined;
    return encounterSectionView(section({
      canManageAssigned,
      appointmentReadConfirmed: Boolean(record),
      finishState: record ? finishCounselingState(record, { canFinish }) : "UNAVAILABLE",
    }));
  };
  assert.deepEqual(viewFor({ canManageAssigned: true, canManageAppointments: true }).actions, ["finish"]);
  // Counseling management alone cannot complete, so the session records the way it always could.
  assert.deepEqual(viewFor({ canManageAssigned: true, canManageAppointments: false }).actions, ["record"]);
  // Appointment management alone does not document anything in this workspace.
  assert.deepEqual(viewFor({ canManageAssigned: false, canManageAppointments: true }).actions, []);
});

test("the access-period refusal keeps its shared copy", () => {
  const error = new CompassApiError({
    status: 409,
    body: { error: { code: "ecounseling_access_open", message: "server detail" } },
    headers: {},
    method: "POST",
    url: `/api/v1/counseling/appointments/${appointmentId}/finish`,
  });
  assert.equal(
    counselingErrorMessage(error, "The Appointment could not be finished."),
    "Wait until the online counseling access or rejoin period has ended before finishing this Appointment.",
  );
  // The same answer the section gives before the request is ever made.
  assert.equal(
    encounterSectionView(section({ joinState: "OPEN" })).message,
    "The online access period is still open. Finish counseling becomes available here once it ends.",
  );
  const conflict = new CompassApiError({
    status: 409,
    body: { error: { code: "counseling_finish_conflict", message: "server detail" } },
    headers: {},
    method: "POST",
    url: `/api/v1/counseling/appointments/${appointmentId}/finish`,
  });
  assert.equal(
    counselingErrorMessage(conflict, "The Appointment could not be finished."),
    "This Counseling session is already recorded with different details. Review it in My counseling encounters.",
  );
});

test("the session's own recording path can only ever create an Appointment-origin Encounter", () => {
  const started = "2026-10-08T02:05:30Z";
  const ended = "2026-10-08T02:55:15Z";
  const fromSession = encounterCreatePayload(sessionEncounterPreset(workspace()), started, ended);
  assert.equal(fromSession.entry_mode, "APPOINTMENT");
  assert.equal(fromSession.appointment_id, appointmentId);
  assert.equal(fromSession.student_id, undefined);

  // The direct lookup paths name a Student and never an Appointment, so the pair cannot be sent.
  for (const entryMode of ["WALK_IN", "CALLED_IN", "REFERRED"]) {
    const direct = encounterCreatePayload({ entryMode, studentId: "student", studentName: "Student Example", deliveryMode: "IN_PERSON" }, started, ended);
    assert.equal(direct.entry_mode, entryMode);
    assert.equal(direct.appointment_id, undefined);
    assert.equal(direct.student_id, "student");
  }
});

// One static render of the real session workspace. The call runtime is a portal-level context, so an
// idle one is supplied; nothing here joins a call, reads media or reaches a provider.
const ok = (data) => ({ data, status: 200, headers: { date: new Date().toUTCString() } });
const sessionCounselor = () => ({
  ...user("COUNSELOR"),
  capabilities: [
    ...user("COUNSELOR").capabilities,
    "ecounseling.view_assigned",
    "counseling.view_assigned",
    "counseling.manage_assigned",
    "appointments.manage",
  ],
});
function appointmentRecord(overrides = {}) {
  return {
    id: appointmentId,
    reference_code: "APT-EC-3",
    student: { id: "student", institutional_id: "2026-0001", display_name: "Student Example" },
    service: { id: "svc", code: "COUNSELING", name: "Counseling" },
    provider: { id: "counselor", display_name: "Counselor Example" },
    delivery_mode: "ONLINE",
    starts_at: "2026-10-08T02:00:00Z",
    ends_at: "2026-10-08T03:00:00Z",
    status: "SCHEDULED",
    cancellation_cutoff_minutes: 30,
    counseling_context_available: false,
    counseling_encounter_recorded: false,
    actions: { complete: { allowed: true, blocker: null, consequences: [] } },
    ...overrides,
  };
}
const noop = async () => {};
const idleRuntime = {
  role: "COUNSELOR",
  state: "inactive",
  live: false,
  appointmentId: null,
  previewAppointmentId: null,
  participantName: null,
  call: {
    ...initialCallSnapshot,
    startPreview: noop,
    closePreview: noop,
    setMicrophone: () => {},
    setCamera: () => {},
    refreshDevices: noop,
    selectCamera: noop,
    selectMicrophone: noop,
    selectSpeaker: noop,
  },
  otherTabActive: false,
  availabilityFor: () => "available",
  startPreview: noop,
  closePreview: noop,
  join: noop,
  timing: { phase: "before", notice: null, endsAt: null },
  requestLeave: () => {},
  end: noop,
  audio: { blocked: false, resume: () => {} },
  canonical: { media: undefined, current: true },
  captureWarnings: [],
  capture: {
    canStop: { recording: false, transcription: false },
    stopping: { recording: false, transcription: false },
    failed: { recording: false, transcription: false },
    error: null,
    stop: noop,
  },
  presentStage: () => () => {},
};

function renderSession({ joinState = "CLOSED", encounter = null, withAppointment = true } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  const value = workspace();
  value.provider_readiness.join_state = joinState;
  value.counseling_encounter = encounter;
  client.setQueryData(getECounselingGetAssignedWorkspaceQueryKey(appointmentId), ok(value));
  if (withAppointment) client.setQueryData(getAppointmentsGetQueryKey(appointmentId), ok(appointmentRecord()));
  const session = { user: sessionCounselor(), session: { id: "s", expires_at: "2099-01-01T00:00:00Z", is_current: true } };
  const html = renderToStaticMarkup(withNextRouter(
    h(QueryClientProvider, { client },
      h(ActiveECounselingCallContext.Provider, { value: idleRuntime },
        h(PortalSessionProvider, { value: session },
          h(UnsavedChangesProvider, null, h(ECounselingWorkspace, { appointmentId }))))),
  ));
  client.clear();
  return html;
}

test("the rendered session offers Finish, and only the fallback when the read is not confirmed", () => {
  const finished = renderSession();
  assert.match(finished, /Counseling Encounter/);
  assert.match(finished, />Finish counseling</);
  assert.doesNotMatch(finished, />Record encounter</);
  assert.match(finished, /This records the Encounter and completes the Appointment\./);

  const open = renderSession({ joinState: "OPEN" });
  assert.match(open, /The online access period is still open\./);
  assert.doesNotMatch(open, />Finish counseling<|>Record encounter</);

  // An Appointment read that has not confirmed anything keeps the ordinary recording path.
  const unread = renderSession({ withAppointment: false });
  assert.match(unread, />Record encounter</);
  assert.doesNotMatch(unread, />Finish counseling</);
  assert.match(unread, /Record the encounter after the counseling conversation\./);

  assert.match(renderSession({ encounter: { id: ENCOUNTER_ID, recorded: true } }), /Encounter recorded\.<\/p>[\s\S]*href="\/portal\/counseling\/encounters\/e0000000/);
  const mismatch = renderSession({ encounter: { id: ENCOUNTER_ID, recorded: false } });
  assert.match(mismatch, /is not its Counseling-Appointment record/);
  assert.doesNotMatch(mismatch, />Finish counseling<|>Record encounter</);
});
