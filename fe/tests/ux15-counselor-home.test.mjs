import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { CounselorHome, getCounselorAgendaParams } from "../src/features/portal/home/counselor-home.tsx";
import {
  getCounselorHomeDestinations,
  getHeadGuidanceHomeDestinations,
  isHeadGuidanceCounselor,
} from "../src/features/portal/home/counselor-home-presentation.ts";
import { getAppointmentsListMyQueryKey } from "../src/lib/api/generated/appointments/appointments.ts";
import { AppointmentListOrdering, AppointmentStatus, DesignationCode } from "../src/lib/api/generated/model/index.ts";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { counselorAppointment, counselorDate, workItem } from "./support/ux15-counselor-home-fixtures.mjs";

const response = (data) => ({ data, status: 200, headers: {} });

function counselorUser({ head = false, capabilities = [] } = {}) {
  return homeWorld({
    role: "COUNSELOR",
    designations: head ? [DesignationCode.HEAD_GUIDANCE_COUNSELOR] : [],
    capabilities,
    items: [],
  }).account;
}

function renderHome(user, appointments, attention) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  const params = getCounselorAgendaParams(counselorDate);
  client.setQueryData(getAppointmentsListMyQueryKey(params), response({
    items: appointments,
    page: 1,
    page_size: params.page_size,
    has_next: false,
    ordering: AppointmentListOrdering.EARLIEST_START,
  }));
  const html = renderToStaticMarkup(h(
    QueryClientProvider,
    { client },
    h(CounselorHome, { user, attention, summary: null, now: new Date("2026-10-22T01:30:00Z") }),
  ));
  client.clear();
  return html;
}

const attention = (items = []) => ({
  items,
  isPending: false,
  isVisible: true,
  staleNotices: [],
  viewAllWork: true,
  workHasNext: false,
  isCaughtUp: items.length === 0,
});

test("the agenda requests today's bounded, chronological self Appointment page", () => {
  assert.deepEqual(getCounselorAgendaParams("2026-10-22"), {
    status: AppointmentStatus.SCHEDULED,
    from_date: "2026-10-22",
    to_date: "2026-10-22",
    ordering: AppointmentListOrdering.EARLIEST_START,
    page: 1,
    page_size: 5,
  });
});

test("Counselor continuity links are selected only from already visible workspaces", () => {
  const user = counselorUser({ capabilities: [
    "routine_interviews.view_assigned",
    "guidance_followups.view",
    "counseling.view_assigned",
    "guidance_messages.view",
    "reports.view",
  ] });
  assert.deepEqual(getCounselorHomeDestinations(user).map((item) => item.href), [
    "/portal/routine-interviews",
    "/portal/follow-ups",
    "/portal/counseling",
    "/portal/messages",
  ]);
  assert.deepEqual(getCounselorHomeDestinations(homeWorld({ role: "IT_ADMIN" }).account), []);
});

test("Head Guidance designation does not create oversight links or Appointment access", () => {
  const head = counselorUser({ head: true });
  assert.equal(isHeadGuidanceCounselor(head), true);
  assert.deepEqual(getHeadGuidanceHomeDestinations(head), []);
  assert.deepEqual(getCounselorHomeDestinations(head).map((item) => item.href), ["/portal/operations"]);
});

test("Head oversight links follow each existing workspace capability", () => {
  const capabilities = [
    "appointments.view_self",
    "appointments.manage",
    "reports.view",
    "organization.manage",
    "availability.manage",
    "services.manage",
    "services.catalog.view",
  ];
  const head = counselorUser({ head: true, capabilities });
  assert.deepEqual(getHeadGuidanceHomeDestinations(head).map((item) => item.href), [
    "/portal/reports",
    "/portal/organization",
    "/portal/availability",
    "/portal/services",
    "/portal/appointments/manage",
  ]);
  assert.deepEqual(getHeadGuidanceHomeDestinations(counselorUser({ capabilities })), []);
});

test("the Counselor Home keeps a chronological agenda beside backend-ordered My Work", () => {
  const user = counselorUser({ capabilities: ["appointments.view_self"] });
  const agendaItems = [counselorAppointment(1, { hour: 10 }), counselorAppointment(2, { hour: 11 })];
  const workItems = [
    { id: "one", title: "Review Routine Interview", subject: "Synthetic Work Student 1", detail: "Awaiting your review", href: "/portal/routine-interviews/one", actionLabel: "Review Routine Interview", priorityLabel: "Time sensitive" },
    { id: "two", title: "Review Guidance follow-up", subject: "Synthetic Work Student 2", detail: "Due date unavailable", href: "/portal/follow-ups/two", actionLabel: "Open follow-up" },
  ];
  const html = renderHome(user, agendaItems, attention(workItems));
  const schedule = html.indexOf("counselor-agenda-heading");
  const work = html.indexOf("counselor-work-heading");
  assert.ok(work >= 0 && schedule > work, "My Work appears before the agenda in reading order");
  assert.ok(html.indexOf("Synthetic Student 1") < html.indexOf("Synthetic Student 2"));
  assert.match(html, /href="\/portal\/appointments\/c0000000-0000-4000-8000-000000000501"/);
  assert.match(html, /href="\/portal\/follow-ups\/two"/);
  assert.match(html, /Time sensitive/);
  assert.equal((html.match(/<h1\b/g) ?? []).length, 0, "CounselorHome composes beneath the shared page h1");
  assert.doesNotMatch(html, /private counseling narrative|assessment finding|case handoff/i);
});

test("without self Appointment authority the agenda is omitted instead of reporting an empty day", () => {
  const html = renderHome(counselorUser(), [counselorAppointment(1)], attention([{
    id: "task", title: "Review Routine Interview", detail: "Awaiting your review", href: "/portal/routine-interviews/task", actionLabel: "Review Routine Interview",
  }]));
  assert.doesNotMatch(html, /counselor-agenda-heading|No scheduled appointments today/);
  assert.match(html, /counselor-work-heading/);
});

test("empty canonical work is not mistaken for completed professional responsibilities", () => {
  const html = renderHome(counselorUser({ capabilities: ["appointments.view_self"] }), [], attention());
  assert.match(html, /No scheduled appointments today\./);
  assert.match(html, /No items currently need attention in My work\./);
  assert.match(html, /Continue in your workspace|Guidance operations/);
});

test("My Work follows the received source order and keeps the first-page boundary honest", () => {
  const items = Array.from({ length: 5 }, (_, index) => workItem("ROUTINE_EVALUATION", index + 1))
    .map((item, index) => ({
      id: item.id,
      title: `Canonical task ${index + 1}`,
      subject: item.student.display_name,
      detail: "Awaiting your review",
      href: `/portal/routine-interviews/${index + 1}`,
      actionLabel: "Review Routine Interview",
    }));
  const html = renderHome(counselorUser({ capabilities: ["appointments.view_self"] }), [], {
    ...attention(items),
    workHasNext: true,
  });
  assert.ok(html.indexOf("Canonical task 1") < html.indexOf("Canonical task 2"));
  assert.match(html, /Showing the first 5 items\. More work is available in the full queue\./);
  assert.match(html, /href="\/portal\/work"/);
});
