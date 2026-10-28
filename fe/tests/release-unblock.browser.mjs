import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("release-unblock");
const service = { id: "release-service", code: "WORKSHOP", name: "Career Workshop", description: "", booking_pathways: ["GROUP_SESSION"], delivery_modes: ["IN_PERSON"], is_active: true, appointment_booking_enabled: false, activation_blockers: [], is_system_required: false, provider_coverage: "ALL_COUNSELORS" };
const event = { id: "release-session", service_id: service.id, service_name: service.name, title: "Career planning", description: "Plan your next steps.", starts_at: "2026-11-12T01:00:00Z", ends_at: "2026-11-12T02:00:00Z", status: "PUBLISHED", delivery_mode: "IN_PERSON", venue_or_meeting_url: "Room A", reg_opens_at: null, reg_closes_at: null, capacity: 20, active_registrations_count: 1, seats_remaining: 19, is_registered_by_me: false, can_register: true, facilitators: [], can_manage: true, can_view: true, can_access_participants: true, can_record_attendance: true, can_export_roster: true, can_complete: false, version: 1, schedule_revision: 1 };
const metrics = { total_sessions: 1, published_sessions: 1, completed_sessions: 0, total_registrations: 1, capacity_utilization_percent: 5, attendance_rate_percent: 0 };
const pageOf = items => ({ items, page: 1, page_size: 50, has_next: false, ordering: "NAME_ASC" });
function account(role) {
  return { ...user(role), capabilities: role === "STUDENT" ? ["appointments.view_self", "appointments.manage_self"] : ["appointments.manage", "services.catalog.view"] };
}
function staffFixture(role) {
  const state = { created: [], attendance: [] };
  const staff = account(role);
  const handler = async ({ pathname, method, reply, request }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(staff)); return true; }
    if (pathname === "/api/v1/services") {
      await reply(pageOf([service, { ...service, id: "flex-only", name: "Individual counseling", booking_pathways: ["FLEXIBLE_APPOINTMENT"] }, { ...service, id: "inactive", name: "Inactive workshop", is_active: false }])); return true;
    }
    if (pathname === `/api/v1/services/${service.id}`) { await reply(service); return true; }
    if (pathname === "/api/v1/group-sessions") { await reply([event]); return true; }
    if (pathname === "/api/v1/group-sessions/metrics") { await reply(metrics); return true; }
    if (pathname === "/api/v1/group-sessions/facilitator-candidates") { await reply([{ id: staff.id, display_name: "Example User", role }]); return true; }
    if (pathname === `/api/v1/group-sessions/create/${service.id}`) {
      state.created.push(JSON.parse(request.postData())); await reply({ ...event, status: "DRAFT" }, 201); return true;
    }
    if (pathname.endsWith("/registrations")) {
      await reply(["REGISTERED", "CANCELLED"].map((status, index) => ({ id: `registration-${index}`, session_id: event.id, student_name: index ? "Cancelled Student" : "Synthetic Student", student_email: "synthetic@example.test", status, attended: null, attendance_notes: null, registered_at: "2026-10-18T00:00:00Z" }))); return true;
    }
    if (pathname.endsWith("/attendance") && method === "POST") {
      state.attendance.push(JSON.parse(request.postData())); await reply({ session_id: event.id, updated_count: 1 }); return true;
    }
    return false;
  };
  return { handler, state };
}

await check("Student canonical entry opens tabs and accessible Help", "/portal/group-sessions", {
  role: "STUDENT", device: "phone", handler: async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(account("STUDENT"))); return true; }
    if (pathname === "/api/v1/group-sessions/discover") { await reply([event]); return true; }
    return false;
  },
}, async page => {
  const nav = page.getByRole("navigation", { name: "Group Sessions navigation" });
  await shown(nav.getByRole("link", { name: "Browse Sessions" }));
  assert.equal(await nav.getByRole("link", { name: "Browse Sessions" }).getAttribute("aria-current"), "page");
  await shown(nav.getByRole("link", { name: "My Registrations" }));
  const help = page.getByRole("button", { name: "Help: Group Sessions", exact: true });
  await help.focus(); await page.keyboard.press("Enter");
  await shown(page.getByRole("dialog"));
  await shown(page.getByRole("heading", { name: "Browse and register" }));
  await page.keyboard.press("Escape");
  assert.equal(await help.evaluate(el => el === document.activeElement), true);
  await noHorizontalOverflow(page); await screenshot(page, "student-tabs-phone");
});

for (const status of [403, 500, 503]) {
  let attempts = 0;
  await check(`discovery ${status} remains an error and Retry restores a valid empty state`, "/portal/group-sessions/discover", {
    role: "STUDENT", handler: async ({ pathname, reply }) => {
      if (pathname === "/api/v1/auth/session") { await reply(sessionFor(account("STUDENT"))); return true; }
      if (pathname === "/api/v1/group-sessions/discover") { attempts++; await reply(attempts === 1 ? { error: { code: "synthetic_failure", message: "Internal implementation details" } } : [], attempts === 1 ? status : 200); return true; }
      return false;
    },
  }, async page => {
    await shown(page.getByRole("alert"));
    await hidden(page.getByText("No upcoming group sessions are currently scheduled.", { exact: true }));
    await hidden(page.getByText("Internal implementation details"));
    if (status === 403) await shown(page.getByText("You don’t have access to this Group Sessions view.", { exact: true }));
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText("No upcoming group sessions are currently scheduled.", { exact: true }));
    assert.equal(attempts, 2);
  });
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
  const f = staffFixture(role);
  await check(`${role} opens scoped staff workspace and participant-specific attendance`, "/portal/group-sessions/attendance", { role, handler: f.handler, device: role === "COUNSELOR" ? "desktop" : "phone" }, async (page, { requests }) => {
    await shown(page.getByRole("link", { name: event.title, exact: true }));
    assert.equal(requests.some(r => r.pathname.endsWith("/registrations")), false);
    await hidden(page.getByRole("button", { name: "Schedule Group Session", exact: true }));
    await page.getByRole("button", { name: /Roster & Attendance/ }).click();
    const dialog = page.getByRole("dialog"); await shown(dialog);
    await shown(dialog.getByText("Synthetic Student", { exact: true }));
    await dialog.getByLabel("Attended: Synthetic Student", { exact: true }).check();
    assert.equal(await dialog.getByLabel("Attended: Cancelled Student", { exact: true }).isDisabled(), true);
    await dialog.getByRole("button", { name: "Save Attendance", exact: true }).click();
    await shown(dialog.getByText("Attendance saved successfully.", { exact: true }));
    assert.deepEqual(f.state.attendance[0].records.map(r => r.registration_id), ["registration-0"]);
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
    await noHorizontalOverflow(page); await screenshot(page, `staff-attendance-${role}`);
  });
}

{
  const f = staffFixture("COUNSELOR");
  await check("central creation selects only eligible Services and keeps the existing creation contract", "/portal/group-sessions/manage", { handler: f.handler }, async page => {
    await page.getByRole("button", { name: "Schedule Group Session", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("option", { name: service.name }).waitFor({ state: "attached" });
    assert.equal(await dialog.getByLabel("Service *", { exact: true }).locator("option").count(), 2);
    await dialog.getByLabel("Service *", { exact: true }).selectOption(service.id);
    await dialog.getByLabel("Title *", { exact: true }).fill("Synthetic new workshop");
    await dialog.getByLabel("Start Time *", { exact: true }).fill("2026-11-12T09:00");
    await dialog.getByLabel("End Time *", { exact: true }).fill("2026-11-12T10:00");
    await dialog.getByRole("button", { name: "Create Session (Draft)", exact: true }).click();
    await shown(page.getByText("Group Session created in Draft status.", { exact: true }));
    assert.equal(f.state.created.length, 1);
    assert.equal(f.state.created[0].starts_at, "2026-11-12T01:00:00.000Z");
    assert.equal(f.state.created[0].facilitators[0].internal_user_id, "counselor");
  });
}

await check("IT Admin does not obtain operational Group Sessions or participant reads", "/portal/group-sessions/attendance", {
  role: "IT_ADMIN", handler: async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(account("IT_ADMIN"))); return true; }
    return false;
  },
}, async (page, { requests }) => {
  await shown(page.getByRole("heading", { name: "Group Sessions unavailable", exact: true }));
  assert.equal(requests.some(r => r.pathname.startsWith("/api/v1/group-sessions")), false);
});

await check("Counselor directory keeps concise copy and keyboard-accessible schedule Help", "/portal/availability/providers", {
  role: "IT_ADMIN", device: "tablet", handler: async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor({ ...user("IT_ADMIN"), capabilities: ["availability.view", "availability.manage"] })); return true; }
    if (pathname === "/api/v1/availability/providers") { await reply(pageOf([])); return true; }
    return false;
  },
}, async page => {
  await shown(page.getByText("Find a counselor to manage their availability.", { exact: true }));
  const help = page.getByRole("button", { name: "Help: Office and Counselor availability", exact: true });
  await help.focus(); await page.keyboard.press("Enter");
  await shown(page.getByRole("heading", { name: "Managing a Counselor’s schedule", exact: true }));
  await page.keyboard.press("Escape");
  assert.equal(await help.evaluate(el => el === document.activeElement), true);
  await noHorizontalOverflow(page); await screenshot(page, "availability-help-tablet");
});

await check("supervision or authority denial does not offer staff creation", "/portal/group-sessions/manage", {
  role: "GUIDANCE_SERVICES_STAFF", handler: async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(account("GUIDANCE_SERVICES_STAFF"))); return true; }
    if (pathname.startsWith("/api/v1/group-sessions")) { await reply({ error: { code: "permission_denied", message: "Internal policy detail" } }, 403); return true; }
    return false;
  },
}, async page => {
  await shown(page.getByRole("alert").first());
  assert.equal(await page.getByRole("button", { name: "Schedule Group Session", exact: true }).isDisabled(), true);
  await hidden(page.getByText("No group sessions match this view.", { exact: true }));
  await hidden(page.getByText("Internal policy detail", { exact: true }));
});

await check("fixed-slot API failure is visible and Retry restores the list", "/portal/appointments/book?pathway=FIXED_DATE_SLOT", {
  role: "STUDENT", handler: (() => {
    let attempts = 0;
    return async ({ pathname, reply }) => {
      if (pathname === "/api/v1/auth/session") { await reply(sessionFor({ ...account("STUDENT"), capabilities: [...account("STUDENT").capabilities, "services.catalog.view"] })); return true; }
      if (pathname === "/api/v1/services") { await reply(pageOf([{ ...service, booking_pathways: ["FIXED_DATE_SLOT"] }])); return true; }
      if (pathname === `/api/v1/services/${service.id}`) { await reply({ ...service, booking_pathways: ["FIXED_DATE_SLOT"] }); return true; }
      if (pathname === `/api/v1/services/${service.id}/slots/bookable`) { attempts++; await reply(attempts === 1 ? { error: { code: "unavailable", message: "Internal detail" } } : [], attempts === 1 ? 500 : 200); return true; }
      return false;
    };
  })(),
}, async page => {
  await page.getByLabel("Service", { exact: true }).selectOption(service.id);
  await shown(page.getByText("Appointment slots could not be loaded. Try again.", { exact: true }));
  await hidden(page.getByText("No fixed consultation slots are currently available for this Service.", { exact: true }));
  await page.getByRole("button", { name: "Retry slots", exact: true }).click();
  await shown(page.getByText("No fixed consultation slots are currently available for this Service.", { exact: true }));
});

{
  let booked = false;
  await check("Student can complete existing fixed-date slot booking outside the Services management gate", "/portal/appointments/book?pathway=FIXED_DATE_SLOT", {
    role: "STUDENT", device: "phone", handler: async ({ pathname, method, reply }) => {
      if (pathname === "/api/v1/auth/session") { await reply(sessionFor({ ...account("STUDENT"), capabilities: [...account("STUDENT").capabilities, "services.catalog.view"] })); return true; }
      if (pathname === "/api/v1/services") { await reply(pageOf([{ ...service, booking_pathways: ["FIXED_DATE_SLOT"] }])); return true; }
      if (pathname === `/api/v1/services/${service.id}`) { await reply({ ...service, booking_pathways: ["FIXED_DATE_SLOT"] }); return true; }
      if (pathname === `/api/v1/services/${service.id}/slots/bookable`) { await reply(booked ? [] : [{ id: "release-slot", provider_name: "Example Counselor", starts_at: event.starts_at, ends_at: event.ends_at, delivery_mode: "IN_PERSON" }]); return true; }
      if (pathname === `/api/v1/services/${service.id}/slots/release-slot/book` && method === "POST") { booked = true; await reply({ appointment_id: "release-appointment", reference_code: "SYNTHETIC-ONLY" }, 201); return true; }
      return false;
    },
  }, async page => {
    await page.getByLabel("Service", { exact: true }).selectOption(service.id);
    await page.getByRole("button", { name: "Book this slot", exact: true }).click();
    await page.getByRole("button", { name: "Confirm booking", exact: true }).click();
    await shown(page.getByRole("link", { name: "View your confirmed Appointment", exact: true }));
    assert.equal(booked, true);
    await noHorizontalOverflow(page);
  });
}

await finish();
