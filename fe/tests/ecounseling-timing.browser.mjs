// E-Counseling scheduled-end warnings and overtime awareness browser regression tests (EC-1 Option A).
// Verifies visual notices on CallStage, expanded GlobalCallDock, collapsed dock, mobile dock,
// screen reader polite announcements, and non-blocking safety invariants across all 4 phases.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { consents, user, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, screenshot, finish } = await createBrowserHarness("ecounseling-timing");

const appointmentId = "11111111-1111-4111-8111-111111111111";
const ePath = `/portal/e-counseling/${appointmentId}`;
const ROUTINE = "routine-timing-test";
const STUDENT = "Maria Santos";
const COUNSELOR = "Maria Reyes";

const evaluation = {
  academic_adjustment_rating: null, physical_adjustment_rating: null, social_adjustment_rating: null,
  spiritual_adjustment_rating: null, financial_adjustment_rating: null, emotional_adjustment_rating: null,
  other_adjustment: "", special_concern: "", recommendations: "",
};
const routineBase = {
  id: ROUTINE, academic_year: null, appointment: { id: appointmentId, reference_code: "APT-TEST-1024", starts_at: "2026-10-08T02:00:00Z", ends_at: "2026-10-08T03:00:00Z" },
  counseling_encounter: null, created_at: "2026-10-07T00:00:00Z", delivery_mode: "ONLINE", entry_mode: "APPOINTMENT",
  form_revision: null, inventory_context: null, workflow_state: "ACTIVE", intake_submitted_at: null,
};

function timingSession({ student = false, endsAtOffsetMs = 0, recording = "NOT_STARTED", transcription = "NOT_STARTED", consent = "APPROVED" } = {}) {
  const state = { recording, transcription, consent, joins: 0 };
  const prefix = `/api/v1/e-counseling/${student ? "me/" : ""}appointments`;
  const base = user(student ? "STUDENT" : "COUNSELOR");
  const sessionUser = {
    ...base,
    capabilities: [...base.capabilities, ...(student ? ["routine_interviews.view_self", "routine_interviews.manage_self"] : ["routine_interviews.view_assigned", "routine_interviews.manage_assigned"])],
  };

  const endsAt = new Date(Date.now() + endsAtOffsetMs).toISOString();

  const data = (id) => {
    const value = workspace();
    value.appointment = {
      ...value.appointment,
      id,
      ends_at: endsAt,
    };
    value.media.media_policy_version = 2;
    value.media.recording.capture_status = state.recording;
    value.media.transcription.capture_status = state.transcription;
    value.media.recording.consent_status = state.consent;
    value.media.transcription.consent_status = state.consent;
    value.routine_interview = student ? { id: ROUTINE, intake_status: "DRAFT" } : { id: ROUTINE, intake_status: "SUBMITTED", evaluation_status: "DRAFT" };
    return value;
  };

  const overrides = {
    [`${prefix}/${appointmentId}`]: ({ reply }) => reply(data(appointmentId)),
    [`${prefix}/${appointmentId}/consents`]: ({ reply }) => reply({ items: [{ ...consents(state.consent)[0], id: "v2-media", scope: "SESSION_MEDIA_CAPTURE" }] }),
    [`POST /api/v1/e-counseling/appointments/${appointmentId}/join`]: ({ reply }) => {
      state.joins += 1;
      return reply({
        appointment_id: appointmentId,
        workspace_id: "w",
        provider: "DAILY",
        room_url: "https://synthetic.daily.co/room",
        meeting_token: `synthetic-meeting-token-${state.joins}`,
        token_expires_at: new Date(Date.now() + 900_000).toISOString(),
      });
    },
    "/api/v1/auth/session": ({ reply }) => reply({ user: sessionUser, session: { id: "test-session", expires_at: "2099-10-07T00:00:00Z", is_current: true } }),
    "/api/v1/platform/status": ({ reply }) => reply({ status: "operational", starts_at: null, ends_at: null, message: null }),
    [`/api/v1/routine-interviews/${ROUTINE}`]: { ...routineBase, counseling_context_available: false, evaluation, evaluation_finalized_at: null, evaluation_status: "DRAFT", intake: {}, intake_status: "SUBMITTED", student: { id: "student", display_name: STUDENT } },
    [`/api/v1/routine-interviews/me/${ROUTINE}`]: { ...routineBase, counselor: { id: "counselor", display_name: COUNSELOR }, intake: {}, intake_status: "DRAFT" },
  };

  return { state, overrides, endsAt };
}

const fake = (page, method, ...args) => page.evaluate(([name, values]) => window.__COMPASS_FAKE_DAILY__[name](...values), [method, args]);
const fakeCount = (page, method) => page.evaluate((name) => window.__COMPASS_FAKE_DAILY__.count(name), method);
const stage = (page) => page.getByRole("region", { name: "Video call" });
const dock = (page) => page.getByRole("region", { name: "Active E-Counseling call" });

async function joinCall(page, waitingFor = STUDENT) {
  await page.getByRole("button", { name: "Join session", exact: true }).click();
  await shown(stage(page).getByText(`Waiting for ${waitingFor}…`, { exact: true }).first());
}

// 1. Student workspace CallStage with 10-minute warning
{
  const session = timingSession({ student: true, endsAtOffsetMs: 8 * 60 * 1000 }); // 8m remaining -> APPROACHING_END
  await check("timing-student-stage-10min-warning", ePath, { role: "STUDENT", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, COUNSELOR);
    await fake(page, "remoteJoin", { userId: "counselor", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    // Top overlay status pill
    const notice = stage(page).getByRole("status").filter({ hasText: "Appointment ending soon" });
    await shown(notice);
    assert.match(await notice.innerText(), /scheduled to end in 10 minutes/);
    await screenshot(page, "timing-10min-warning-student");

    // Non-blocking invariant: Daily not disconnected, stage remains active
    assert.equal(await fakeCount(page, "destroy"), 0);
  });
}

// 2. Counselor workspace CallStage with 5-minute reminder
{
  const session = timingSession({ student: false, endsAtOffsetMs: 3 * 60 * 1000 }); // 3m remaining -> FINAL_REMINDER
  await check("timing-counselor-stage-5min-reminder", ePath, { role: "COUNSELOR", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, STUDENT);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    const notice = stage(page).getByRole("status").filter({ hasText: "5 minutes remaining" });
    await shown(notice);
    assert.match(await notice.innerText(), /scheduled appointment ends in 5 minutes/);
    await screenshot(page, "timing-5min-reminder-counselor");

    // Governed controls remain accessible
    await shown(page.getByRole("button", { name: "Start recording", exact: true }));
    await shown(page.getByRole("button", { name: "Start transcription", exact: true }));
  });
}

// 3. CallStage at scheduled end notice
{
  const session = timingSession({ student: false, endsAtOffsetMs: 0 }); // exactly at scheduled end -> SCHEDULED_END_REACHED
  await check("timing-stage-scheduled-end-notice", ePath, { role: "COUNSELOR", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, STUDENT);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    const notice = stage(page).getByRole("status").filter({ hasText: "Scheduled time reached" });
    await shown(notice);
    assert.match(await notice.innerText(), /scheduled appointment time has ended/);
    await screenshot(page, "timing-scheduled-end-stage");

    // Active call not interrupted
    assert.equal(await fakeCount(page, "destroy"), 0);
    assert.equal(await fakeCount(page, "leave"), 0);
  });
}

// 4. CallStage with overtime indicator
{
  const session = timingSession({ student: false, endsAtOffsetMs: -5 * 60 * 1000 }); // 5m past end -> OVERTIME
  await check("timing-stage-overtime-awareness", ePath, { role: "COUNSELOR", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, STUDENT);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    const notice = stage(page).getByRole("status").filter({ hasText: "Past scheduled end" });
    await shown(notice);
    assert.match(await notice.innerText(), /scheduled appointment time has passed/);
    await screenshot(page, "timing-overtime-stage");
  });
}

// 5. GlobalCallDock collapsed and expanded presentations
{
  const session = timingSession({ student: false, endsAtOffsetMs: 8 * 60 * 1000 }); // 10 min left
  await check("timing-dock-presentations", ePath, { role: "COUNSELOR", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, STUDENT);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    // Navigate to routine interview page so dock steps in
    await page.getByRole("button", { name: /^Session details/ }).click();
    await page.getByRole("link", { name: "Open Routine Interview", exact: true }).click();
    await page.waitForURL(new RegExp(`/portal/routine-interviews/${ROUTINE}$`));
    await shown(dock(page));

    // Expanded dock shows timing notice box
    const fullNotice = dock(page).getByRole("status").filter({ hasText: "Appointment ending soon" });
    await shown(fullNotice);
    assert.match(await fullNotice.innerText(), /Your appointment is scheduled to end in 10 minutes/);
    await screenshot(page, "timing-expanded-dock");

    // Collapse dock: folds into single row with compact label
    await dock(page).getByRole("button", { name: "Minimize call", exact: true }).click();
    const compactLabel = dock(page).locator("[data-timing-compact='10 min left']");
    await shown(compactLabel);
    const box = await dock(page).boundingBox();
    assert.ok(box.height < 80, `Collapsed dock height ${box.height}px exceeds 80px`);
    await screenshot(page, "timing-collapsed-dock");
  });
}

// 6. Mobile dock presentation
{
  const session = timingSession({ student: true, endsAtOffsetMs: 3 * 60 * 1000 }); // 5 min left
  await check("timing-mobile-dock", ePath, { role: "STUDENT", mobile: true, fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, COUNSELOR);
    await fake(page, "remoteJoin", { userId: "counselor", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    // Navigate to routine interview
    await page.getByRole("button", { name: /^Session details/ }).click();
    await page.getByRole("link", { name: "Open Routine Interview", exact: true }).click();
    await page.waitForURL(new RegExp(`/portal/routine-interviews/${ROUTINE}$`));
    await shown(dock(page));

    // Fold mobile preview
    await dock(page).getByRole("button", { name: "Minimize call", exact: true }).click();
    await shown(dock(page).locator("[data-timing-compact='5 min left']"));
    await screenshot(page, "timing-mobile-dock");
  });
}

// 7. Screen reader polite live-region announcement
{
  const session = timingSession({ student: false, endsAtOffsetMs: 8 * 60 * 1000 });
  await check("timing-live-region-announcement", ePath, { role: "COUNSELOR", fakeDaily: true, overrides: session.overrides }, async (page) => {
    await joinCall(page, STUDENT);
    await fake(page, "remoteJoin", { userId: "student", name: "Maria" });
    await shown(stage(page).getByText("Connected", { exact: true }));

    // The single portal-wide polite announcement container for timing
    const liveRegion = page.locator('p[aria-live="polite"].sr-only').filter({ hasText: /Appointment ending soon/ });
    await shown(liveRegion);
    assert.match(await liveRegion.innerText(), /Appointment ending soon.*scheduled to end in 10 minutes/);
  });
}

await finish();
