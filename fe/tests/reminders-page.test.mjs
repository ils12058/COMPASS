import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { RemindersPage } from "../src/features/reminders/reminders-page.tsx";
import {
  activityReminderParams,
  deliveryStateLabel,
  inAppStateLabel,
  lastReminderLabel,
  manualReminderLabel,
  nextAutomaticLabel,
  reminderIssuerLabel,
  reminderKindLabel,
  upcomingReminderParams,
} from "../src/features/reminders/reminders-shared.ts";
import {
  getAppointmentsListReminderActivityQueryKey,
  getAppointmentsListUpcomingRemindersQueryKey,
} from "../src/lib/api/generated/appointments/appointments.ts";

const manager = {
  id: "counselor-1",
  role: "COUNSELOR",
  first_name: "Casey",
  last_name: "Counselor",
  email: "casey@example.test",
  designations: [],
  student_lifecycle_status: null,
  capabilities: ["appointments.view_self", "appointments.manage"],
};

const student = {
  ...manager,
  id: "student-1",
  role: "STUDENT",
  student_lifecycle_status: "CURRENT",
  capabilities: ["appointments.view_self"],
};

const upcomingRow = {
  appointment_id: "appointment-1",
  reference_code: "APT-0001",
  student_name: "Student One",
  counselor: { id: "counselor-1", display_name: "Casey Counselor" },
  service_name: "Counseling",
  starts_at: "2026-11-09T01:00:00Z",
  next_automatic: "AUTO_24H",
  last_reminder_kind: null,
  last_reminder_at: null,
  manual_available: true,
  manual_reason: "ELIGIBLE",
};

const blockedRow = {
  ...upcomingRow,
  appointment_id: "appointment-2",
  reference_code: "APT-0002",
  student_name: "Student Two",
  next_automatic: null,
  manual_available: false,
  manual_reason: "COOLDOWN",
};

const activityRow = {
  id: "occurrence-1",
  kind: "MANUAL",
  issued_at: "2026-11-08T02:00:00Z",
  scheduled_start: "2026-11-09T01:00:00Z",
  is_current: true,
  issued_by: { id: "counselor-1", display_name: "Casey Counselor" },
  in_app: "CREATED",
  email: "SENT",
  push: "NOT_REQUESTED",
  appointment_id: "appointment-1",
  reference_code: "APT-0001",
  student_name: "Student One",
};

const supersededRow = {
  ...activityRow,
  id: "occurrence-2",
  kind: "AUTO_3H",
  is_current: false,
};

const ok = (data) => ({ data, status: 200, headers: {} });

function render(search = "", { upcoming = [upcomingRow, blockedRow], activity = [activityRow, supersededRow], user = manager } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
  });
  client.setQueryData(
    getAppointmentsListUpcomingRemindersQueryKey(upcomingReminderParams({ from: "", to: "", counselor: "" }, 1)),
    ok({ items: upcoming, page: 1, page_size: 20, has_next: false, ordering: "EARLIEST_START" }),
  );
  client.setQueryData(
    getAppointmentsListReminderActivityQueryKey(activityReminderParams({ from: "", to: "" }, 1)),
    ok({ items: activity, page: 1, page_size: 20, has_next: false }),
  );
  const html = renderToStaticMarkup(
    withNextRouter(
      h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(RemindersPage))),
      { pathname: "/portal/reminders", search },
    ),
  );
  client.clear();
  return html;
}

const destinations = (user) => portalWorkspaceGroups(user).flatMap((group) => group.links).map((link) => link.href);

test("row states are described in plain words, never as stored codes", () => {
  assert.equal(reminderKindLabel("AUTO_24H"), "24-hour reminder");
  assert.equal(reminderKindLabel("AUTO_3H"), "3-hour reminder");
  assert.equal(reminderKindLabel("MANUAL"), "Manual reminder");
  assert.equal(reminderKindLabel(null), "Reminder");

  assert.equal(nextAutomaticLabel("AUTO_24H"), "24 hours before start");
  assert.equal(nextAutomaticLabel("AUTO_3H"), "3 hours before start");
  assert.equal(nextAutomaticLabel(null), "None scheduled");

  assert.equal(manualReminderLabel(upcomingRow), "Ready to send");
  assert.match(manualReminderLabel(blockedRow), /sent recently/);
  assert.match(manualReminderLabel({ manual_available: false, manual_reason: "TOO_SOON" }), /less than 15 minutes/);
  assert.match(manualReminderLabel({ manual_available: false, manual_reason: "NOT_SCHEDULED" }), /Only scheduled appointments/);

  assert.equal(deliveryStateLabel("NOT_REQUESTED"), "Not requested");
  assert.equal(deliveryStateLabel("PENDING"), "Pending");
  assert.equal(deliveryStateLabel("SENT"), "Sent");
  assert.equal(deliveryStateLabel("FAILED"), "Not sent");
  assert.equal(deliveryStateLabel("CANCELLED"), "Cancelled");
  assert.equal(inAppStateLabel("CREATED"), "Created");
  assert.equal(inAppStateLabel("NOT_CREATED"), "Not created");

  assert.equal(reminderIssuerLabel(null), "Sent automatically");
  assert.equal(reminderIssuerLabel({ display_name: "Casey Counselor" }), "Sent by Casey Counselor");

  assert.equal(lastReminderLabel({ last_reminder_kind: null, last_reminder_at: null }), "No reminders yet");
  assert.match(lastReminderLabel({ last_reminder_kind: "AUTO_24H", last_reminder_at: "2026-11-08T01:00:00Z" }), /^24-hour reminder · /);
});

test("default query parameters send nothing beyond the first page and its window", () => {
  assert.deepEqual(upcomingReminderParams({ from: "", to: "", counselor: "" }, 1), { page: 1, page_size: 20 });
  assert.deepEqual(upcomingReminderParams({ from: "", to: "", counselor: "", available: true }, 2), {
    manual_available: true,
    page: 2,
    page_size: 20,
  });
  assert.deepEqual(upcomingReminderParams({ from: "2026-11-08", to: "2026-11-10", counselor: "10000000-0000-4000-8000-000000000001" }, 1, "LATEST_START"), {
    from_date: "2026-11-08",
    to_date: "2026-11-10",
    provider_id: "10000000-0000-4000-8000-000000000001",
    ordering: "LATEST_START",
    page: 1,
    page_size: 20,
  });
  assert.deepEqual(activityReminderParams({ from: "", to: "", kind: "MANUAL", delivery: "SENT" }, 1), {
    kind: "MANUAL",
    delivery: "SENT",
    page: 1,
    page_size: 20,
  });
});

test("the Upcoming view reports row state in plain words and never opens a send confirmation", () => {
  const html = render("");
  assert.match(html, /Upcoming reminders/);
  assert.match(html, /Student One/);
  assert.match(html, /Student Two/);
  assert.match(html, /Casey Counselor/);
  assert.match(html, /Ready to send/);
  assert.match(html, /A manual reminder was sent recently/);
  assert.match(html, /24 hours before start/);
  assert.match(html, /None scheduled/);
  assert.match(html, /No reminders yet/);
  assert.match(html, /href="\/portal\/appointments\/appointment-1"/);
  assert.doesNotMatch(html, /AUTO_24H|AUTO_3H|COOLDOWN|ELIGIBLE|NOT_REQUESTED/);
  // Opening the page renders no confirmation and no send control: sending starts only after a
  // staff member selects Appointments and opens the existing preview-and-confirm dialog.
  assert.doesNotMatch(html, /Review the students before sending/);
  assert.doesNotMatch(html, /Send 1 reminder/);
});

test("the Sent view names the reminder, its sender and each channel without transport diagnostics", () => {
  const html = render("tab=sent");
  assert.match(html, /Sent reminders/);
  assert.match(html, /Manual reminder/);
  assert.match(html, /3-hour reminder/);
  assert.match(html, /Sent by Casey Counselor/);
  assert.match(html, /Superseded by reschedule/);
  assert.match(html, /Created/);
  assert.match(html, /Not requested/);
  assert.match(html, /Student One/);
  assert.match(html, /href="\/portal\/appointments\/appointment-1"/);
  // Filter options carry the closed values, but no row ever shows a stored code as its state.
  assert.doesNotMatch(html, />AUTO_3H<|>MANUAL<|>CREATED<|>NOT_REQUESTED</);
  assert.doesNotMatch(html, /failure_code|claim_token|casey@example\.test|smtp|\/api\/v1\//);
});

test("Reminders appears in navigation only for staff who manage Appointments", () => {
  const managerLinks = portalWorkspaceGroups(manager).flatMap((group) => group.links);
  const reminders = managerLinks.find((link) => link.href === "/portal/reminders");
  assert.equal(reminders?.label, "Reminders");
  assert.equal(
    managerLinks[managerLinks.findIndex((link) => link.href === "/portal/reminders") - 1]?.href,
    "/portal/appointments",
  );
  assert.ok(!destinations(student).includes("/portal/reminders"));
  assert.ok(!destinations({ ...manager, capabilities: ["appointments.view_self"] }).includes("/portal/reminders"));
});

test("a non-manager sees only the unavailable message, with no reminder data", () => {
  const html = render("", { user: student, upcoming: [], activity: [] });
  assert.match(html, /Reminders unavailable/);
  assert.doesNotMatch(html, /Upcoming reminders|Sent reminders/);
});

test("sending stays behind the one existing preview-and-confirm component", () => {
  const page = readFileSync(new URL("../src/features/reminders/reminders-page.tsx", import.meta.url), "utf8");
  const sender = readFileSync(new URL("../src/features/appointments/appointment-reminders.tsx", import.meta.url), "utf8");

  assert.match(page, /<ReminderSender/);
  assert.doesNotMatch(page, /appointmentsSendReminders|useAppointmentsSendReminders|appointmentsPreviewReminders/);

  assert.match(sender, /appointmentsPreviewReminders/);
  assert.match(sender, /useAppointmentsSendReminders/);
  assert.match(sender, /onConfirm=\{\(\) => void sendConfirmedReminders\(\)\}/);
  assert.match(sender, /props\.open \?/);
});
