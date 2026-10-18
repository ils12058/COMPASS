// CAL-1 uses synthetic appointment records and a local browser only. No student, counseling,
// account, or live backend data is requested by this suite.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment as baseAppointment } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("appointments-calendar");

const syntheticStudent = (name, suffix) => ({
  id: `student-${suffix}`,
  institutional_id: `SYN-${suffix}`,
  display_name: name,
});

function event({
  id,
  reference,
  student,
  service,
  startsAt,
  endsAt,
  status = "SCHEDULED",
}) {
  return {
    ...baseAppointment,
    id,
    reference_code: reference,
    student_id: student.id,
    student,
    service: { ...baseAppointment.service, name: service },
    provider: { id: "counselor-sample", display_name: "Counselor Sample" },
    starts_at: startsAt,
    ends_at: endsAt,
    status,
  };
}

const appointments = [
  event({
    id: baseAppointment.id,
    reference: "APT-CAL-101",
    student: syntheticStudent("Jordan Sample", "101"),
    service: "Academic Advising",
    startsAt: "2026-10-20T09:00:00+08:00",
    endsAt: "2026-10-20T10:00:00+08:00",
  }),
  event({
    id: "appointment-cal-102",
    reference: "APT-CAL-102",
    student: syntheticStudent("Taylor Sample", "102"),
    service: "Wellbeing Consultation",
    startsAt: "2026-10-21T13:30:00+08:00",
    endsAt: "2026-10-21T14:15:00+08:00",
    status: "COMPLETED",
  }),
  event({
    id: "appointment-cal-103",
    reference: "APT-CAL-103",
    student: syntheticStudent("Avery Sample", "103"),
    service: "Study Planning",
    startsAt: "2026-10-21T15:30:00+08:00",
    endsAt: "2026-10-21T16:00:00+08:00",
    status: "CANCELLED",
  }),
  event({
    id: "appointment-cal-104",
    reference: "APT-CAL-104",
    student: syntheticStudent("Morgan Sample", "104"),
    service: "Student Support",
    startsAt: "2026-10-22T11:00:00+08:00",
    endsAt: "2026-10-22T11:45:00+08:00",
    status: "NO_SHOW",
  }),
];

const baselineResponse = {
  items: [appointments[0]],
  page: 1,
  page_size: 20,
  has_next: false,
  ordering: "EARLIEST_START",
};

function institutionDate(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const values = new Map(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${values.get("year")}-${values.get("month")}-${values.get("day")}`;
}

function appointmentPageFor(url, records) {
  const from = url.searchParams.get("from_date");
  const to = url.searchParams.get("to_date");
  const status = url.searchParams.get("status");
  const search = (url.searchParams.get("search") ?? "").toLowerCase();
  const filtered = records.filter((item) => {
    const day = institutionDate(item.starts_at);
    if (from && day < from) return false;
    if (to && day > to) return false;
    if (status && item.status !== status) return false;
    if (search && !`${item.reference_code} ${item.student.display_name} ${item.student.institutional_id}`.toLowerCase().includes(search)) return false;
    return true;
  });
  const page = Number(url.searchParams.get("page") ?? "1");
  const pageSize = Number(url.searchParams.get("page_size") ?? "20");
  const start = (page - 1) * pageSize;
  return {
    items: filtered.slice(start, start + pageSize),
    page,
    page_size: pageSize,
    has_next: start + pageSize < filtered.length,
    ordering: url.searchParams.get("ordering") ?? "EARLIEST_START",
  };
}

function appointmentHandler({ records = appointments, requests = [], baseline = false } = {}) {
  return async ({ pathname, url, reply }) => {
    if (pathname !== "/api/v1/appointments/me" && pathname !== "/api/v1/appointments") return false;
    requests.push({ pathname, search: url.search });
    await reply(baseline ? baselineResponse : appointmentPageFor(url, records));
    return true;
  };
}

async function installCalendarClock({ page }) {
  await page.clock.install({ time: new Date("2026-10-20T08:00:00Z") });
}

if (process.env.COMPASS_CAL1_BASELINE === "1") {
  for (const [role, path, label, expected] of [
    ["STUDENT", "/portal/appointments/my", "before-my-list", "Academic Advising"],
    ["COUNSELOR", "/portal/appointments/manage", "before-manage-list", "Jordan Sample"],
  ]) {
    await check(`${label}-synthetic-baseline`, path, {
      role,
      handler: appointmentHandler({ baseline: true }),
    }, async (page) => {
      await shown(page.getByRole("heading", { name: role === "STUDENT" ? "My appointments" : "Manage appointments", exact: true }));
      await shown(page.getByText(expected, { exact: true }).first());
      await screenshot(page, label);
      assert.equal(await page.getByRole("button", { name: "Calendar", exact: true }).count(), 0);
    });
  }
} else {
  await check("my-list-calendar-toggle-role-safe-events-and-detail-link", "/portal/appointments/my?status=ALL", {
    role: "STUDENT",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler(),
  }, async (page) => {
    const calendarToggle = page.getByRole("button", { name: "Calendar", exact: true });
    await shown(page.getByRole("heading", { name: "My appointments", exact: true }));
    await shown(page.getByText("Academic Advising", { exact: true }).first());
    await screenshot(page, "after-my-list");

    await calendarToggle.click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel);
    const academicEvent = calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ });
    await shown(academicEvent);
    assert.equal(await calendarPanel.getByText("Counselor Sample", { exact: true }).count(), 0);
    assert.equal(await calendarPanel.getByText("Jordan Sample", { exact: true }).count(), 0);
    assert.equal(await calendarPanel.getByText("SYN-101", { exact: true }).count(), 0);
    await screenshot(page, "after-my-calendar-month");
    await screenshot(page, "after-desktop-month");

    await page.getByRole("button", { name: "Week", exact: true }).click();
    await shown(page.getByRole("list", { name: "Appointment week", exact: true }));
    await shown(calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ }));
    await screenshot(page, "after-desktop-week");

    await page.getByRole("button", { name: "List", exact: true }).click();
    await shown(page.getByRole("searchbox", { name: "Search by Appointment reference" }));
    await calendarToggle.click();

    const detailsHref = await calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ }).getAttribute("href");
    assert.equal(detailsHref, `/portal/appointments/${baseAppointment.id}`);
    await calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ }).click();
    await page.waitForURL(`**/portal/appointments/${baseAppointment.id}`);
    await shown(page.getByRole("heading", { name: "APT-TEST-1024", exact: true }));
  });

  await check("calendar-period-navigation-and-today", "/portal/appointments/my?status=ALL", {
    role: "STUDENT",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler(),
  }, async (page, { requests }) => {
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    await shown(page.getByRole("heading", { name: "October 2026", exact: true }));
    await page.getByRole("button", { name: "Next month", exact: true }).click();
    await shown(page.getByRole("heading", { name: "November 2026", exact: true }));
    assert.ok(requests.some(({ search }) => search.includes("from_date=2026-11-01") && search.includes("to_date=2026-11-30")));
    await page.getByRole("button", { name: "Today", exact: true }).click();
    await shown(page.getByRole("heading", { name: "October 2026", exact: true }));
    assert.ok(requests.some(({ search }) => search.includes("from_date=2026-10-01") && search.includes("to_date=2026-10-31")));
  });

  await check("managed-list-calendar-toggle-and-staff-labels", "/portal/appointments/manage?status=ALL", {
    role: "GUIDANCE_SERVICES_STAFF",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler(),
  }, async (page) => {
    await shown(page.getByRole("heading", { name: "Manage appointments", exact: true }));
    await shown(page.getByText("Jordan Sample", { exact: true }).first());
    await screenshot(page, "after-manage-list");
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel.getByRole("link", { name: /Jordan Sample.*Academic Advising.*Scheduled/ }));
    assert.equal(await calendarPanel.getByText("SYN-101", { exact: true }).count(), 0);
    await screenshot(page, "after-manage-calendar-month");
  });

  await check("calendar-month-navigation-in-browser-local-time", "/portal/appointments/my?status=ALL", {
    role: "STUDENT",
    timezoneId: "America/Los_Angeles",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler(),
  }, async (page) => {
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel.getByRole("link", { name: /Monday, October 19, 2026, 6:00 PM.*Academic Advising/ }));
  });

  await check("calendar-fetches-all-authorized-pages", "/portal/appointments/my?status=ALL", {
    role: "STUDENT",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler({
      records: [
        ...Array.from({ length: 50 }, (_, index) => event({
          id: `appointment-cal-page-${index + 1}`,
          reference: `APT-CAL-PAGE-${String(index + 1).padStart(3, "0")}`,
          student: syntheticStudent(`Page ${index + 1} Sample`, String(index + 200)),
          service: "Academic Advising",
          startsAt: `2026-10-01T09:${String(index % 60).padStart(2, "0")}:00+08:00`,
          endsAt: `2026-10-01T10:${String(index % 60).padStart(2, "0")}:00+08:00`,
        })),
        event({
          id: "appointment-cal-page-51",
          reference: "APT-CAL-PAGE-051",
          student: syntheticStudent("Pagination Sample", "251"),
          service: "Study Planning",
          startsAt: "2026-10-20T17:00:00+08:00",
          endsAt: "2026-10-20T17:30:00+08:00",
        }),
      ],
    }),
  }, async (page, { requests }) => {
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel.getByRole("link", { name: /Study Planning.*Scheduled/ }));
    assert.ok(requests.some(({ search }) => search.includes("page_size=50") && search.includes("page=2")));
    const denseDay = calendarPanel.getByRole("button", {
      name: "Show 47 more appointments for Thursday, October 1, 2026",
      exact: true,
    });
    await shown(denseDay);
    await denseDay.click();
    await shown(calendarPanel.getByRole("list", { name: "Appointment week", exact: true }));
    await shown(calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ }).first());
  });

  await check("mobile-calendar-agenda-remains-usable", "/portal/appointments/my?status=ALL", {
    role: "STUDENT",
    device: "narrowPhone",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler(),
  }, async (page) => {
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel.getByRole("list", { name: /October 2026 appointment agenda/ }));
    await shown(calendarPanel.getByRole("link", { name: /Academic Advising.*Scheduled/ }));
    await noHorizontalOverflow(page);
    await screenshot(page, "after-mobile-calendar-agenda");
  });

  await check("calendar-empty-state-explains-the-period", "/portal/appointments/my", {
    role: "STUDENT",
    timezoneId: "Asia/Manila",
    beforeNavigate: installCalendarClock,
    handler: appointmentHandler({ records: [] }),
  }, async (page) => {
    await page.getByRole("button", { name: "Calendar", exact: true }).click();
    const calendarPanel = page.getByRole("region", { name: "Calendar", exact: true });
    await shown(calendarPanel.getByText("No appointments in this period.", { exact: true }));
    await shown(calendarPanel.getByRole("region", { name: "October 2026 appointment calendar", exact: true }));
    await screenshot(page, "after-calendar-empty");
  });
}

await finish();
