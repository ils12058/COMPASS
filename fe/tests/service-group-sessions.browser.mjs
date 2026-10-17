import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, finish } = await createBrowserHarness(
  "service-group-sessions",
);

const serviceId = "service-group-sessions-browser";
const sessionId = "group-session-history-browser";
const event = {
  id: sessionId,
  service_id: serviceId,
  service_name: "Career Planning Workshop",
  title: "Resume and Interview Workshop",
  description: "Practical guidance for preparing for interviews.",
  delivery_mode: "IN_PERSON",
  venue_or_meeting_url: "Conference Room B",
  starts_at: "2026-11-10T14:00:00Z",
  ends_at: "2026-11-10T15:00:00Z",
  reg_opens_at: "2026-11-01T00:00:00Z",
  reg_closes_at: "2026-11-10T12:00:00Z",
  capacity: 25,
  seats_remaining: 10,
  is_full: false,
  is_registered_by_me: false,
  can_register: false,
  registration_block_reason:
    "This session overlaps another Appointment or registered Group Session.",
  facilitators: [],
};

const service = {
  id: serviceId,
  code: "CAREER_WORKSHOP",
  name: "Career Planning Workshop",
  description: "Workshops and group sessions for students.",
  appointment_booking_enabled: false,
  booking_pathways: ["GROUP_SESSION"],
  default_appointment_duration_minutes: 60,
  cancellation_cutoff_minutes: 60,
  requires_current_inventory: false,
  delivery_modes: ["IN_PERSON"],
  provider_coverage: "ALL_COUNSELORS",
  is_active: true,
  is_system_required: false,
  activation_blockers: [],
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-07T00:00:00Z",
};

const studentAccount = {
  ...user("STUDENT"),
  id: "student-group-sessions-browser",
  capabilities: ["appointments.view_self", "services.catalog.view"],
};

function handlerFor({ history = false } = {}) {
  return async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(sessionFor(studentAccount));
      return true;
    }
    if (pathname === `/api/v1/services/${serviceId}`) {
      await reply(service);
      return true;
    }
    if (pathname === "/api/v1/group-sessions/discover") {
      await reply([event]);
      return true;
    }
    if (pathname === "/api/v1/group-sessions/me/registrations" && history) {
      await reply([
        {
          id: "registration-history-browser",
          session_id: sessionId,
          session_title: event.title,
          service_id: serviceId,
          starts_at: event.starts_at,
          ends_at: event.ends_at,
          student_id: studentAccount.id,
          student_name: "Student User",
          student_email: "student@example.test",
          status: "CANCELLED",
          registered_at: "2026-10-01T00:00:00Z",
          cancelled_at: "2026-10-02T00:00:00Z",
          cancellation_reason: "The event was cancelled by the organizer.",
          attended: null,
          attendance_notes: null,
        },
      ]);
      return true;
    }
    if (pathname === `/api/v1/group-sessions/${sessionId}` && history) {
      await reply({
        ...event,
        status: "CANCELLED",
        organizer_id: "organizer-browser",
        organizer_name: "Workshop Organizer",
        cancellation_reason: "The event was cancelled by the organizer.",
        cancelled_at: "2026-10-02T00:00:00Z",
        version: 2,
        schedule_revision: 1,
        active_registrations_count: 0,
        can_view: true,
        can_manage: false,
        can_access_participants: false,
        can_record_attendance: false,
        can_export_roster: false,
        created_at: "2026-10-01T00:00:00Z",
        updated_at: "2026-10-02T00:00:00Z",
        facilitators: [
          {
            id: "external-facilitator-browser",
            kind: "EXTERNAL",
            internal_user_id: null,
            external_display_name: "Guest Speaker",
            display_name: "Guest Speaker",
            is_current: true,
            is_lead: true,
            counselor_id: null,
            counselor_name: null,
          },
          {
            id: "former-facilitator-browser",
            kind: "INTERNAL",
            internal_user_id: "former-counselor-browser",
            external_display_name: "",
            display_name: "Former Counselor",
            is_current: false,
            is_lead: false,
            counselor_id: "former-counselor-browser",
            counselor_name: "Former Counselor",
          },
        ],
      });
      return true;
    }
    return false;
  };
}

await check(
  "Student registration availability follows the server response",
  "/portal/group-sessions/discover",
  { role: "STUDENT", handler: handlerFor(), device: "phone" },
  async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Upcoming Group Sessions & Workshops" }));
    await shown(page.getByRole("link", { name: event.title }));
    await shown(page.getByText("Registration unavailable", { exact: true }));
    await shown(page.getByText(event.registration_block_reason, { exact: true }));
    await hidden(page.getByRole("button", { name: "Register", exact: true }));
    assert.equal(requests.some((request) => request.method !== "GET"), false);
    assert.equal(
      await page.getByRole("link", { name: "My group sessions", exact: true }).getAttribute("href"),
      "/portal/group-sessions/my",
    );
    await noHorizontalOverflow(page);
  },
);

await check(
  "Student can review a cancelled registration and its event history",
  "/portal/group-sessions/my",
  { role: "STUDENT", handler: handlerFor({ history: true }), device: "phone" },
  async (page) => {
    await shown(page.getByRole("link", { name: event.title }));
    await shown(page.getByText("Cancelled", { exact: true }));
    await page.getByRole("link", { name: event.title }).click();
    await shown(page.getByRole("heading", { name: event.title, exact: true }));
    await shown(page.getByText("Cancelled", { exact: true }));
    await shown(page.getByText("The event was cancelled by the organizer.", { exact: true }));
    await shown(page.getByText("Guest Speaker · Lead facilitator · Guest speaker", { exact: true }));
    await shown(page.getByText("Former Counselor · Former facilitator", { exact: true }));
    await noHorizontalOverflow(page);
  },
);

await finish();
