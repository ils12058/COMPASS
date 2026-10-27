import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, finish } = await createBrowserHarness("svc-ux-1");
const sid = "11111111-1111-4111-8111-111111111111";
const eid = "22222222-2222-4222-8222-222222222222";
const slot = "33333333-3333-4333-8333-333333333333";
const service = { id: sid, code: "GUIDANCE", name: "Guidance Service", description: "Guidance for students", booking_pathways: ["FIXED_DATE_SLOT", "GROUP_SESSION"], appointment_booking_enabled: false, default_appointment_duration_minutes: null, cancellation_cutoff_minutes: null, requires_current_inventory: false, delivery_modes: ["IN_PERSON"], provider_coverage: "ALL_COUNSELORS", is_active: true, is_system_required: false, activation_blockers: [], created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" };
const event = { id: eid, service_id: sid, service_name: service.name, title: "Student workshop", description: "", delivery_mode: "IN_PERSON", venue_or_meeting_url: "Room 1", starts_at: "2099-11-10T14:00:00Z", ends_at: "2099-11-10T15:00:00Z", reg_opens_at: null, reg_closes_at: null, capacity: 10, seats_remaining: 4, is_full: false, is_registered_by_me: false, can_register: true, registration_block_reason: null, facilitators: [] };
const account = { ...user("STUDENT"), capabilities: ["appointments.view_self", "appointments.manage_self", "services.catalog.view"] };
const pageOf = (items, page, has_next) => ({ items, page, page_size: 50, has_next, ordering: "NAME_ASC" });
function handler({ fixedResult = "ok", groupResult = "ok", registered = false, lifecycle = "CURRENT", changed = false, noManage = false, noSlots = false, inventory = false, noSessions = false, paths = service.booking_pathways, sessionBlock = null, registrationReadFails = false, bookingOnly = false, refreshFailure = false } = {}) {
  let committed = false;
  return async ({ pathname, method, url, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor({ ...account, capabilities: noManage ? ["appointments.view_self", "services.catalog.view"] : bookingOnly ? ["appointments.manage_self"] : account.capabilities, student_lifecycle_status: lifecycle })); return true; }
    if (pathname === "/api/v1/appointments/booking/services") { await reply(pageOf([], 1, false)); return true; }
    if (pathname === "/api/v1/services") { const p = Number(url.searchParams.get("page") ?? 1); await reply(p === 1 ? pageOf([{ ...service, booking_pathways: ["GROUP_SESSION"] }], 1, true) : pageOf([service], 2, false)); return true; }
    if (pathname === `/api/v1/services/${sid}`) { await reply(changed ? { ...service, is_active: false } : { ...service, booking_pathways: paths, requires_current_inventory: inventory }); return true; }
    if (pathname === `/api/v1/services/${sid}/slots/bookable`) { if (committed && refreshFailure) { await reply({ error: { code: "internal_error", message: "unavailable" } }, 500); return true; } await reply(noSlots ? [] : [{ id: slot, provider_name: "Counselor", starts_at: event.starts_at, ends_at: event.ends_at, delivery_mode: "IN_PERSON" }]); return true; }
    if (pathname === `/api/v1/services/${sid}/slots/${slot}/book` && method === "POST") { committed = fixedResult === "ok"; await reply(fixedResult === "ok" ? { appointment_id: "44444444-4444-4444-8444-444444444444", reference_code: "TEST-123" } : fixedResult === "malformed" ? {} : { error: { code: fixedResult === "conflict" ? "slot_already_booked" : "internal_error", message: "Unknown" } }, fixedResult === "ok" || fixedResult === "malformed" ? 201 : fixedResult === "conflict" ? 409 : 500); return true; }
    if (pathname === "/api/v1/group-sessions/discover") { if (committed && refreshFailure) { await reply({ error: { code: "internal_error", message: "unavailable" } }, 500); return true; } await reply(noSessions ? [] : [{ ...event, can_register: !sessionBlock, registration_block_reason: sessionBlock, is_full: sessionBlock === "This session is full." }]); return true; }
    if (pathname === `/api/v1/group-sessions/${eid}` && method === "GET") { await reply({ ...event, status: "PUBLISHED", cancellation_reason: "", facilitators: [] }); return true; }
    if (pathname === `/api/v1/group-sessions/${eid}/register` && method === "POST") { committed = groupResult === "ok"; await reply(groupResult === "ok" ? { id: "registration", session_id: eid, status: "REGISTERED" } : groupResult === "malformed" ? {} : { error: { code: groupResult === "full" ? "group_session_conflict" : "internal_error", message: groupResult === "full" ? "This session is full." : "Unknown" } }, groupResult === "ok" || groupResult === "malformed" ? 201 : groupResult === "full" ? 409 : 500); return true; }
    if (pathname === "/api/v1/group-sessions/me/registrations") { await reply(registrationReadFails ? { error: { code: "internal_error", message: "unavailable" } } : registered ? [{ id: "r", session_id: eid, status: "REGISTERED" }] : [], registrationReadFails ? 500 : 200); return true; }
    return false;
  };
}

for (const device of ["narrowPhone", "tablet", "desktop"]) await check(`booking choices ${device}`, "/portal/appointments/book", { role: "STUDENT", device, handler: handler() }, async page => {
  await shown(page.getByRole("link", { name: "Find an appointment" }));
  await shown(page.getByRole("link", { name: "View scheduled slots" }));
  await shown(page.getByRole("link", { name: "Browse group sessions" }));
  await noHorizontalOverflow(page);
});
await check("page-local fixed search and Service context", "/portal/appointments/book?pathway=FIXED_DATE_SLOT", { role: "STUDENT", device: "phone", handler: handler() }, async page => {
  await shown(page.getByText(/No Services with scheduled slots on this page/));
  await page.getByRole("button", { name: "More Services" }).click();
  await page.getByLabel("Service", { exact: true }).selectOption(sid);
  await shown(page.getByRole("link", { name: /Browse group sessions for Guidance Service/ }));
  const href = await page.getByRole("link", { name: /Browse group sessions for Guidance Service/ }).getAttribute("href");
  const context = new URL(href, "http://localhost");
  assert.equal(context.searchParams.get("service_id"), sid);
  assert.equal(context.searchParams.get("slot_page"), "2");
  await noHorizontalOverflow(page);
});
await check("fixed slot uncertain response is not replayed", "/portal/appointments/book?pathway=FIXED_DATE_SLOT", { role: "STUDENT", handler: handler({ fixedResult: "unknown" }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "More Services" }).click();
  await page.getByLabel("Service", { exact: true }).selectOption(sid);
  await page.getByRole("button", { name: "Book this slot" }).click();
  await page.getByRole("button", { name: "Confirm booking" }).click();
  await shown(page.getByRole("alertdialog").getByText(/We could not confirm whether this appointment was booked/));
  assert.equal(await page.getByRole("button", { name: "Confirm booking" }).isDisabled(), true);
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/book")).length, 1);
});
await check("group lost response checks exact registration without replay", `/portal/group-sessions/discover?service_id=${sid}`, { role: "STUDENT", handler: handler({ groupResult: "unknown", registered: true }) }, async (page, { requests }) => {
  await shown(page.getByText(/Showing group sessions for/));
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText('You are registered for "Student workshop".'));
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/register")).length, 1);
  assert.ok(requests.some(r => r.method === "GET" && r.pathname === "/api/v1/group-sessions/me/registrations"));
});
await check("group lost response with no registration stays unconfirmed", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ groupResult: "unknown" }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText(/The result for Student workshop is unconfirmed/));
  await page.getByRole("button", { name: "Check registration" }).click();
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/register")).length, 1);
});
await check("invalid Service context does not reach the API", "/portal/group-sessions/discover?service_id=invalid", { role: "STUDENT", handler: handler() }, async (page, { requests }) => {
  await shown(page.getByText(/This Service cannot be selected/));
  assert.equal(requests.some(r => r.pathname === "/api/v1/services/invalid"), false);
});
await check("non-current Student cannot register", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ lifecycle: "GRADUATED" }) }, async page => {
  await shown(page.getByText(/Registration is available to current students/));
  await hidden(page.getByRole("button", { name: "Register", exact: true }));
});
await check("fixed Service context is rechecked before showing opportunities", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ changed: true }) }, async page => {
  await shown(page.getByText(/This Service no longer offers scheduled slots/));
  await hidden(page.getByRole("button", { name: "Book this slot" }));
});
await check("fixed confirmation links to the saved appointment", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler() }, async page => {
  await page.getByRole("button", { name: "Book this slot" }).click();
  await page.getByRole("button", { name: "Confirm booking" }).click();
  await shown(page.getByRole("link", { name: "View your confirmed Appointment" }));
  assert.match(await page.getByRole("link", { name: "View your confirmed Appointment" }).getAttribute("href"), /44444444-4444-4444-8444-444444444444/);
});
await check("view permission does not grant registration", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ noManage: true }) }, async page => {
  await shown(page.getByText(/Registration is available to current students/));
  await hidden(page.getByRole("button", { name: "Register", exact: true }));
});
await check("booking choices remain usable at 200 percent", "/portal/appointments/book", { role: "STUDENT", device: "phone", handler: handler() }, async page => {
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  await shown(page.getByRole("link", { name: "Browse group sessions" }));
  await noHorizontalOverflow(page);
});
await check("booking choices are keyboard reachable", "/portal/appointments/book", { role: "STUDENT", handler: handler() }, async page => {
  const choice = page.getByRole("link", { name: "View scheduled slots" });
  await choice.focus();
  assert.equal(await choice.evaluate(element => element === document.activeElement), true);
  await page.keyboard.press("Enter");
  await shown(page.getByRole("heading", { name: "Scheduled appointment slots" }));
});
await check("fixed slot conflict reports no longer available", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ fixedResult: "conflict" }) }, async page => {
  await page.getByRole("button", { name: "Book this slot" }).click();
  await page.getByRole("button", { name: "Confirm booking" }).click();
  await shown(page.getByRole("alertdialog").getByText(/This slot is no longer available/));
});
await check("group success links to session and history", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler() }, async page => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByRole("link", { name: "View session" }));
  await shown(page.getByText(/Successfully registered/));
});
await check("group capacity conflict is shown without replay", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ groupResult: "full" }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText("This session is full.", { exact: true }));
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/register")).length, 1);
});
await check("invalid fixed context offers Service selection", "/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=invalid", { role: "STUDENT", handler: handler() }, async (page, { requests }) => {
  await shown(page.getByText(/The Service link is invalid/));
  assert.equal(requests.some(r => r.pathname === "/api/v1/services/invalid"), false);
});
await check("empty slots do not become promised availability", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ noSlots: true }) }, async page => {
  await shown(page.getByText("No fixed consultation slots are currently available for this Service."));
  await hidden(page.getByRole("button", { name: "Book this slot" }));
});
await check("configured Inventory is explained for fixed booking", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ inventory: true }) }, async page => {
  await shown(page.getByText(/A submitted Individual Inventory for the current Academic Year is required/));
});
await check("fixed-only without Inventory does not invent a requirement", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler() }, async page => {
  await shown(page.getByRole("button", { name: "Book this slot" }));
  await hidden(page.getByText(/A submitted Individual Inventory for the current Academic Year is required/));
});
await check("empty group discovery does not invent a prerequisite or an offering", `/portal/group-sessions/discover?service_id=${sid}`, { role: "STUDENT", handler: handler({ noSessions: true }) }, async page => {
  await shown(page.getByText(/No upcoming group sessions are currently scheduled for this Service/));
  await hidden(page.getByText(/Individual Inventory/));
});
await check("fixed and group navigation preserves Service and page context", `/portal/group-sessions/discover?service_id=${sid}&slot_search=Guidance&slot_page=2`, { role: "STUDENT", handler: handler() }, async page => {
  const href = await page.getByRole("link", { name: "View scheduled appointment slots" }).getAttribute("href");
  const url = new URL(href, "http://localhost");
  assert.equal(url.searchParams.get("service_id"), sid);
  assert.equal(url.searchParams.get("search"), "Guidance");
  assert.equal(url.searchParams.get("page"), "2");
});
await check("group detail returns to the Service-filtered browse", `/portal/group-sessions/${eid}?from=discover&service_id=${sid}`, { role: "STUDENT", handler: handler() }, async page => {
  await shown(page.getByRole("heading", { name: "Student workshop" }));
  assert.equal(await page.getByRole("link", { name: "Back to Browse Sessions" }).getAttribute("href"), `/portal/group-sessions/discover?service_id=${sid}`);
});
await check("unfiltered event identifies its Service", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler() }, async page => {
  await shown(page.getByText(/Service: Guidance Service/));
  assert.equal(await page.getByRole("link", { name: "See Service options" }).getAttribute("href"), `/portal/group-sessions/discover?service_id=${sid}`);
});
await check("Service with three pathways explains configuration without promising opportunities", `/portal/group-sessions/discover?service_id=${sid}`, { role: "STUDENT", handler: handler({ paths: ["FLEXIBLE_APPOINTMENT", "FIXED_DATE_SLOT", "GROUP_SESSION"], noSessions: true }) }, async page => {
  await shown(page.getByText(/This Service supports group sessions, scheduled appointment slots, and individual appointment booking/));
  await shown(page.getByText(/No upcoming group sessions are currently scheduled/));
});
await check("flexible-only Service is not a fixed-slot offering", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ paths: ["FLEXIBLE_APPOINTMENT"] }) }, async page => {
  await shown(page.getByText(/This Service no longer offers scheduled slots/));
  await hidden(page.getByRole("button", { name: "Book this slot" }));
});
await check("fixed-only Service has no invented group link", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ paths: ["FIXED_DATE_SLOT"] }) }, async page => {
  await shown(page.getByRole("button", { name: "Book this slot" }));
  await hidden(page.getByRole("link", { name: /Browse group sessions for/ }));
});
await check("group-only Service does not show appointment actions", `/portal/group-sessions/discover?service_id=${sid}`, { role: "STUDENT", handler: handler({ paths: ["GROUP_SESSION"] }) }, async page => {
  await shown(page.getByRole("link", { name: "Student workshop" }));
  await hidden(page.getByRole("link", { name: "View scheduled appointment slots" }));
});
await check("Service without pathways cannot be used for a fixed booking", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ paths: [] }) }, async page => {
  await shown(page.getByText(/This Service no longer offers scheduled slots/));
});
for (const reason of ["This session is full.", "Registration has closed."]) await check(`group restriction: ${reason}`, "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ sessionBlock: reason }) }, async page => {
  await shown(page.getByText(reason, { exact: true }));
  await hidden(page.getByRole("button", { name: "Register", exact: true }));
});
await check("failed reconciliation keeps result unconfirmed", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ groupResult: "unknown", registrationReadFails: true }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText(/The registration result could not be checked/));
  await page.getByRole("button", { name: "Check registration" }).click();
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/register")).length, 1);
});
await check("direct Group Session deep link keeps history return", `/portal/group-sessions/${eid}`, { role: "STUDENT", handler: handler() }, async page => {
  await shown(page.getByRole("heading", { name: "Student workshop" }));
  assert.equal(await page.getByRole("link", { name: "Back to My Registrations" }).getAttribute("href"), "/portal/group-sessions/my");
});
await check("booking permission alone does not expose fixed slot or group viewing", "/portal/appointments/book", { role: "STUDENT", handler: handler({ bookingOnly: true }) }, async page => {
  await shown(page.getByRole("link", { name: "Find an appointment" }));
  await shown(page.getByText("Scheduled slot browsing is unavailable to this account."));
  await shown(page.getByText("Group session browsing is unavailable to this account."));
  await hidden(page.getByRole("link", { name: "View scheduled slots" }));
  await hidden(page.getByRole("link", { name: "Browse group sessions" }));
});
await check("confirmed fixed booking remains success when refresh fails", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ refreshFailure: true }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Book this slot" }).click();
  await page.getByRole("button", { name: "Confirm booking" }).click();
  await shown(page.getByRole("link", { name: "View your confirmed Appointment" }));
  await shown(page.getByText(/Your appointment was booked, but the latest booking information could not be refreshed/));
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/book")).length, 1);
});
await check("confirmed group registration remains success when refresh fails", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ refreshFailure: true }) }, async (page, { requests }) => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText(/Successfully registered/));
  await shown(page.getByText(/Your registration was confirmed, but the latest information could not be refreshed/));
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  assert.equal(requests.filter(r => r.method === "POST" && r.pathname.endsWith("/register")).length, 1);
});
await check("inactive Service cannot filter group discovery", `/portal/group-sessions/discover?service_id=${sid}`, { role: "STUDENT", handler: handler({ changed: true }) }, async page => {
  await shown(page.getByText(/This Service no longer offers group sessions/));
  await hidden(page.getByRole("button", { name: "Register", exact: true }));
});
await check("malformed fixed success cannot fabricate an appointment", `/portal/appointments/book?pathway=FIXED_DATE_SLOT&service_id=${sid}`, { role: "STUDENT", handler: handler({ fixedResult: "malformed" }) }, async page => {
  await page.getByRole("button", { name: "Book this slot" }).click();
  await page.getByRole("button", { name: "Confirm booking" }).click();
  await shown(page.getByRole("alertdialog").getByText(/We could not confirm whether this appointment was booked/));
  await hidden(page.getByRole("link", { name: "View your confirmed Appointment" }));
});
await check("malformed group success remains unconfirmed without matching history", "/portal/group-sessions/discover", { role: "STUDENT", handler: handler({ groupResult: "malformed" }) }, async page => {
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Register", exact: true }).click();
  await shown(page.getByText(/The result for Student workshop is unconfirmed/));
  await hidden(page.getByText(/Successfully registered/));
});
await finish();
