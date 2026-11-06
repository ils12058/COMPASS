import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppointmentDetailPage } from "../src/features/appointments/appointment-detail-page.tsx";
import { CounselingWorkspace } from "../src/features/counseling/counseling-workspace.tsx";
import {
  finishCounselingNotice,
  finishCounselingState,
  unconfirmedFinishMessage,
} from "../src/features/counseling/finish-counseling-availability.ts";
import { counselingErrorMessage } from "../src/features/counseling/counseling-shared.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { getAppointmentsGetQueryKey } from "../src/lib/api/generated/appointments/appointments.ts";
import * as counselingApi from "../src/lib/api/generated/counseling/counseling.ts";
import { withNextRouter } from "./support/next-router.mjs";
import { appointmentId, counselor, overview, session } from "./support/cont1a-summary-fixtures.mjs";

const ok = (data) => ({ data, status: 200, headers: { date: new Date().toUTCString() } });
const action = (allowed) => ({ allowed, blocker: null, consequences: [] });
const counselingService = { id: "svc-counseling", code: "COUNSELING", name: "Counseling" };
const careerService = { id: "svc-career", code: "CAREER_GUIDANCE", name: "Career Guidance" };

function render(element, { user = counselor(), seed = () => {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(
    withNextRouter(h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: session(user) }, h(UnsavedChangesProvider, null, element)))),
  );
  client.clear();
  return html;
}

const DETAIL_ID = "finish-apt";
function detail(overrides = {}) {
  return {
    id: DETAIL_ID,
    reference_code: "APT-2026-000456",
    student_id: "student",
    student: { id: "student", institutional_id: "2026-0001", display_name: "Student Example" },
    service: counselingService,
    provider: { id: "counselor", display_name: "Counselor Example" },
    delivery_mode: "IN_PERSON",
    starts_at: "2026-11-06T01:00:00Z",
    ends_at: "2026-11-06T02:00:00Z",
    status: "SCHEDULED",
    cancellation_cutoff_minutes: 30,
    cancelled_at: null,
    completed_at: null,
    no_show_at: null,
    created_at: "2026-11-01T00:00:00Z",
    counseling_context_available: false,
    counseling_encounter_recorded: false,
    actions: { cancel: action(false), reschedule: action(false), reassign: action(false), complete: action(true), mark_no_show: action(false) },
    ...overrides,
  };
}
const detailPage = (record, user) =>
  render(h(AppointmentDetailPage, { appointmentId: DETAIL_ID }), {
    user,
    seed: (client) => client.setQueryData(getAppointmentsGetQueryKey(DETAIL_ID), ok(record)),
  });

const workspacePage = (record) =>
  render(h(CounselingWorkspace, { anchorType: "APPOINTMENT", anchorId: appointmentId }), {
    seed: (client) => {
      client.setQueryData(
        counselingApi.getCounselingContextGetOverviewQueryKey("APPOINTMENT", appointmentId),
        ok(overview({ matching_encounter: null })),
      );
      if (record) client.setQueryData(getAppointmentsGetQueryKey(appointmentId), ok(record));
    },
  });

const finishActor = counselor();
const studentActor = {
  id: "student", first_name: "Student", last_name: "Example", middle_name: "", email: "s@example.test",
  role: "STUDENT", student_lifecycle_status: "CURRENT", designations: [], institutional_id: "2026-0001",
  capabilities: ["appointments.view_self", "ecounseling.view_self"],
};

test("the Finish state follows status, the Encounter fact, Complete eligibility and capabilities", () => {
  const offered = { canFinish: true };
  assert.equal(finishCounselingState(detail(), offered), "OFFERED");
  assert.equal(finishCounselingState(detail({ actions: { ...detail().actions, complete: action(false) } }), offered), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail({ counseling_encounter_recorded: true }), offered), "RECORDED");
  assert.equal(finishCounselingState(detail({ status: "COMPLETED", counseling_encounter_recorded: false, actions: { ...detail().actions, complete: action(false) } }), offered), "OFFERED");
  assert.equal(finishCounselingState(detail({ status: "COMPLETED", counseling_encounter_recorded: true, actions: { ...detail().actions, complete: action(false) } }), offered), "RECORDED");
  assert.equal(finishCounselingState(detail({ status: "CANCELLED" }), offered), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail({ status: "NO_SHOW" }), offered), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail({ counseling_encounter_recorded: null }), offered), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail({ service: careerService }), offered), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail(), { canFinish: false }), "UNAVAILABLE");
  assert.equal(finishCounselingState(detail({ service: careerService, counseling_encounter_recorded: true }), offered), "UNAVAILABLE");
});

test("each Finish outcome says what actually happened", () => {
  assert.equal(
    finishCounselingNotice({ already_finished: true, encounter_result: "EXISTING" }, { wasCompleted: false }),
    "Counseling was already finished. The latest details are now shown.",
  );
  assert.equal(
    finishCounselingNotice({ already_finished: false, encounter_result: "EXISTING" }, { wasCompleted: false }),
    "Counseling finished. The Encounter already recorded for this Appointment was kept.",
  );
  assert.equal(
    finishCounselingNotice({ already_finished: false, encounter_result: "CREATED" }, { wasCompleted: true }),
    "Counseling Encounter recorded for this completed Appointment.",
  );
  assert.equal(
    finishCounselingNotice({ already_finished: false, encounter_result: "CREATED" }, { wasCompleted: false }),
    "Counseling finished and the Encounter recorded.",
  );
  assert.equal(unconfirmedFinishMessage, "We couldn’t confirm whether counseling was finished.");
});

test("Finish conflicts explain themselves instead of repeating the server message", () => {
  const error = (code) => new CompassApiError({
    status: 409,
    body: { error: { code, message: "server detail" } },
    headers: {},
    method: "POST",
    url: `/api/v1/counseling/appointments/${DETAIL_ID}/finish`,
  });
  assert.equal(counselingErrorMessage(error("counseling_appointment_closed"), "fallback"), "This Appointment was cancelled or marked no-show, so it cannot be finished.");
  assert.equal(counselingErrorMessage(error("counseling_finish_conflict"), "fallback"), "This Counseling session is already recorded with different details. Review it in My counseling encounters.");
  assert.equal(counselingErrorMessage(error("appointment_lifecycle_conflict"), "fallback"), "This Appointment changed before it could be finished. Review the latest details.");
  assert.equal(counselingErrorMessage(error("ecounseling_access_open"), "fallback"), "Wait until the online counseling access or rejoin period has ended before finishing this Appointment.");
  assert.equal(counselingErrorMessage(error("unknown_code"), "fallback"), "fallback");
});

test("Appointment Detail replaces Complete with Finish and states the documentation fact", () => {
  const open = detailPage(detail(), finishActor);
  assert.match(open, />Finish counseling</);
  assert.doesNotMatch(open, /Complete appointment/);
  assert.match(open, />Counseling encounter<\/dt><dd[^>]*>Not recorded</);

  const documented = detailPage(detail({ counseling_encounter_recorded: true }), finishActor);
  assert.match(documented, />Counseling encounter<\/dt><dd[^>]*>Recorded</);
  assert.match(documented, /Complete appointment/);
  assert.doesNotMatch(documented, />Finish counseling</);
});

test("a completed Appointment without its Encounter is offered Finish and says so", () => {
  const html = detailPage(
    detail({ status: "COMPLETED", counseling_encounter_recorded: false, actions: { ...detail().actions, complete: action(false) } }),
    finishActor,
  );
  assert.match(html, />Finish counseling</);
  assert.match(html, /This Appointment is marked completed, but no Counseling Encounter is recorded for it\. If the session took place, finish counseling to record it\./);
});

test("the documentation fact and Finish stay hidden where the fact is not exposed", () => {
  const asStudent = detailPage(detail({ counseling_encounter_recorded: null }), studentActor);
  assert.doesNotMatch(asStudent, /Counseling encounter|Finish counseling/);

  const ordinary = detailPage(detail({ service: careerService }), finishActor);
  assert.doesNotMatch(ordinary, /Finish counseling|Counseling encounter/);
  assert.match(ordinary, /Complete appointment/);
});

test("the Counseling Workspace offers Finish instead of Record in an Appointment context", () => {
  const offered = workspacePage(detail());
  assert.match(offered, />Finish counseling</);
  assert.doesNotMatch(offered, /Record encounter/);
  assert.match(offered, /Records the Encounter and completes this Appointment\./);

  const completed = workspacePage(detail({ status: "COMPLETED", counseling_encounter_recorded: false, actions: { ...detail().actions, complete: action(false) } }));
  assert.match(completed, />Finish counseling</);
  assert.match(completed, /Records the Encounter for this completed Appointment\./);
});

test("a recorded Encounter ends the Appointment context's authoring actions", () => {
  const html = workspacePage(detail({ counseling_encounter_recorded: true }));
  assert.match(html, /A Counseling Encounter is recorded for this Appointment\. Review it in My counseling encounters\./);
  assert.doesNotMatch(html, /Finish counseling|Record encounter/);
  assert.match(html, /href="\/portal\/counseling#encounters"/);
});

test("an Appointment read that is not confirmed keeps the ordinary Record action", () => {
  const html = workspacePage(null);
  assert.match(html, /Record encounter/);
  assert.doesNotMatch(html, /Finish counseling/);
});

test("a linked but non-matching Encounter is never offered Finish", () => {
  const offered = { canFinish: true };
  assert.equal(
    finishCounselingState(detail({ counseling_encounter_recorded: false, counseling_encounter_linked: true }), offered),
    "UNAVAILABLE",
  );
  assert.equal(
    finishCounselingState(detail({ counseling_encounter_recorded: true, counseling_encounter_linked: true }), offered),
    "RECORDED",
  );
  // An unexposed or matching link must not suppress anything on its own.
  assert.equal(finishCounselingState(detail({ counseling_encounter_linked: false }), offered), "OFFERED");
});

test("a completed Appointment with no link keeps the missing-record warning and Finish", () => {
  const html = detailPage(
    detail({
      status: "COMPLETED",
      counseling_encounter_recorded: false,
      counseling_encounter_linked: false,
      actions: { ...detail().actions, complete: action(false) },
    }),
    finishActor,
  );
  assert.match(html, />Finish counseling</);
  assert.match(html, /This Appointment is marked completed, but no Counseling Encounter is recorded for it\./);
  assert.match(html, />Counseling encounter<\/dt><dd[^>]*>Not recorded</);
});

test("a completed Appointment with a non-matching link asks for review instead of offering Finish", () => {
  const html = detailPage(
    detail({
      status: "COMPLETED",
      counseling_encounter_recorded: false,
      counseling_encounter_linked: true,
      actions: { ...detail().actions, complete: action(false) },
    }),
    finishActor,
  );
  assert.match(
    html,
    /A Counseling Encounter is linked to this Appointment but doesn’t match its Counseling details\. This needs administrative review and can’t be corrected here\./,
  );
  assert.doesNotMatch(html, /no Counseling Encounter is recorded for it/);
  assert.doesNotMatch(html, /Finish counseling/);
  assert.match(html, />Counseling encounter<\/dt><dd[^>]*>Linked, needs review</);
});

test("a still-scheduled Appointment with its Encounter recorded points at Complete", () => {
  const html = detailPage(
    detail({ counseling_encounter_recorded: true, counseling_encounter_linked: true, actions: { ...detail().actions, complete: action(true) } }),
    finishActor,
  );
  assert.match(
    html,
    /This Counseling Encounter is already recorded\. Complete the Appointment to reconcile it; this won’t create another Encounter\./,
  );
  assert.match(html, /Complete appointment/);
  assert.doesNotMatch(html, />Finish counseling</);
});
