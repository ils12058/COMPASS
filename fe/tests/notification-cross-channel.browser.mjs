// Real UI, synthetic intercepted HTTP. Backend cross-channel tests separately enforce access.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointment, slip, user } from "./support/ui-hierarchy-fixtures.mjs";
import { certificate } from "./support/good-moral-print-fixtures.mjs";

const { check, shown, hidden, navigate, settleFetches, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("notification-cross-channel");
const id = "12345678-1234-4234-8234-123456789abc";
const noticeId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const center = "/portal/notifications";
const families = [
  ["APPOINTMENT", "Appointment Scheduled", "Open Appointment", "appointments", appointment.reference_code],
  ["GROUP_SESSION", "Group Session Updated", "Open Group Session", "group-sessions", "Synthetic Group Session"],
  ["GOOD_MORAL", "Good Moral Certificate Issued", "Open Good Moral request", "good-moral", "Synthetic Applicant"],
  ["CALL_SLIP", "New Call Slip", "Open Call Slip", "call-slips", slip.student_name_snapshot],
];
const failed = { error: { code: "synthetic_failure", message: "Synthetic failure" } };

function world({ family = families[0], role = "STUDENT", read = false, deny = false, markFailure = false, empty = false, listFailure = false, long = false } = {}) {
  const state = { read, markFailure, listFailure, authenticated: true, account: "a", marks: 0, recordReads: 0, switchOnMark: false };
  const accounts = Object.fromEntries(["a", "b"].map(name => [name, {
    ...user(role), id: `synthetic-${name}`, capabilities: [...user(role).capabilities, "good_moral.view_self", "services.catalog.view"],
  }]));
  const notification = () => ({ id: noticeId, event_code: { APPOINTMENT: "appointment.scheduled", GROUP_SESSION: "group_session.rescheduled", GOOD_MORAL: "good_moral.issued", CALL_SLIP: "call_slip.issued" }[family[0]] ?? "security.account_access.changed", policy: "MANDATORY_OPERATIONAL",
    title: state.account === "b" ? "Account B notice" : family[1], message: long ? "Long synthetic notification wording. ".repeat(30) : "Review the current record in COMPASS.",
    target_type: family[0], target_id: id, created_at: "2026-10-22T00:00:00Z", read_at: state.read ? "2026-10-23T00:00:00Z" : null, is_read: state.read, is_current: true });
  const handler = async ({ pathname, method, reply }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(state.authenticated ? { user: accounts[state.account], session: { id: `session-${state.account}`, expires_at: "2099-10-07T00:00:00Z", is_current: true } } : failed, state.authenticated ? 200 : 401);
      return true;
    }
    if (pathname === "/api/v1/auth/logout") { state.authenticated = false; await reply({}); return true; }
    if (pathname === "/api/v1/auth/login") { state.authenticated = true; state.account = "a"; await reply({ authenticated: true, mfa_required: false, mfa_methods: [] }); return true; }
    if (pathname === "/api/v1/notifications") {
      if (state.listGate) await state.listGate;
      await reply(state.listFailure ? failed : { items: empty ? [] : [notification()], page: 1, page_size: 20, has_next: false }, state.listFailure ? 500 : 200);
      return true;
    }
    if (pathname === "/api/v1/notifications/unread-count") { await reply({ unread_count: empty || state.read ? 0 : 1 }); return true; }
    if (method === "PATCH" && pathname.startsWith("/api/v1/notifications/")) {
      state.marks++;
      if (state.switchOnMark) { state.account = "b"; await reply(failed, 401); }
      else if (state.markFailure) await reply(failed, 500);
      else { state.read = true; await reply(pathname.endsWith("read-all") ? { updated_count: 1 } : notification()); }
      return true;
    }
    if ([`/api/v1/appointments/${id}`, `/api/v1/group-sessions/${id}`, `/api/v1/good-moral/me/${id}`, `/api/v1/call-slips/me/${id}`].includes(pathname)) {
      state.recordReads++;
      const records = {
        APPOINTMENT: { ...appointment, id },
        CALL_SLIP: { ...slip, id, updated_at: slip.created_at },
        GOOD_MORAL: { ...certificate("ISSUED"), id },
        GROUP_SESSION: { id, title: "Synthetic Group Session", description: "", status: "PUBLISHED", service_id: "synthetic-service", service_name: "Synthetic service", delivery_mode: "IN_PERSON", venue_or_meeting_url: "Synthetic venue", starts_at: "2099-10-23T01:00:00Z", ends_at: "2099-10-23T02:00:00Z", capacity: 20, facilitators: [], active_registrations_count: 1, version: 1, schedule_revision: 1, can_view: true, can_manage: false, can_access_participants: false, can_record_attendance: false, can_export_roster: false },
      };
      await reply(deny ? { error: { code: "appointment_not_found", message: "Unavailable." } } : records[family[0]], deny ? 404 : 200);
      return true;
    }
    if (pathname.startsWith(`/api/v1/appointments/${id}/`)) { await reply({ items: [] }); return true; }
    return false;
  };
  return { state, options: { role, handler } };
}

for (const family of families) {
  const f = world({ family });
  await check(`Student opens ${family[0]} then reloads read history`, center, f.options, async page => {
    await shown(page.getByRole("heading", { name: family[1], exact: true }));
    const action = page.getByRole("button", { name: family[2], exact: true });
    await action.focus();
    assert.equal(await action.evaluate(node => node === document.activeElement), true);
    await page.keyboard.press("Enter");
    await shown(page.getByText(family[4], { exact: true }).first());
    assert.equal(new URL(page.url()).pathname, `/portal/${family[3]}/${id}`);
    assert.equal(f.state.marks, 1);
    assert.ok(f.state.recordReads > 0);
    await navigate(page, center);
    await hidden(page.getByText("Unread", { exact: true }));
    await shown(page.getByRole("button", { name: family[2], exact: true }));
    await page.getByRole("button", { name: family[2], exact: true }).click();
    await shown(page.getByText(family[4], { exact: true }).first());
    assert.equal(f.state.marks, 1, "Already-read notices navigate without another mutation");
  });
}

for (const family of families) {
  const f = world({ family });
  f.state.authenticated = false;
  const destination = `/portal/${family[3]}/${id}`;
  await check(`signed-out email link returns to ${family[0]} after login`, destination, f.options, async page => {
    await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("next"), destination);
    assert.equal(f.state.recordReads, 0);
    await page.getByLabel("Email", { exact: true }).fill("synthetic@example.test");
    await page.getByLabel("Password", { exact: true }).fill("synthetic-test-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await shown(page.getByText(family[4], { exact: true }).first());
    assert.equal(new URL(page.url()).pathname, destination);
  });
}

{
  const f = world({ markFailure: true });
  await check("failed mark-read keeps unread/cache/destination; explicit retry succeeds", center, f.options, async page => {
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(page.getByRole("alert").filter({ hasText: "could not be marked as read" }));
    await shown(page.getByText("Unread", { exact: true }));
    await shown(page.getByRole("link", { name: "Notifications, 1 unread", exact: true }));
    assert.equal(new URL(page.url()).pathname, center);
    assert.equal(f.state.recordReads, 0);
    f.state.markFailure = false;
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(page.getByText(appointment.reference_code, { exact: true }));
  });
}

{
  const f = world({ markFailure: true });
  await check("mark-all failure leaves count and rows; successful retry reconciles both", center, f.options, async page => {
    await page.getByRole("button", { name: "Mark all read", exact: true }).click();
    await shown(page.getByRole("alert").filter({ hasText: "could not be marked as read" }));
    await shown(page.getByText("Unread", { exact: true }));
    f.state.markFailure = false;
    await page.getByRole("button", { name: "Mark all read", exact: true }).click();
    await hidden(page.getByText("Unread", { exact: true }));
    await hidden(page.getByRole("link", { name: "Notifications, 1 unread", exact: true }));
  });
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
  const denied = role !== "COUNSELOR";
  const f = world({ role, deny: denied });
  await check(`${role} Notification opens only backend-permitted Appointment`, center, f.options, async page => {
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(denied ? page.getByRole("heading", { name: "Appointment not available", exact: true }) : page.getByText(appointment.reference_code, { exact: true }));
    if (denied) await hidden(page.getByText(appointment.reference_code, { exact: true }));
  });
}

{
  const f = world({ role: "COUNSELOR", deny: true, read: true });
  await check("former Counselor read history leads to safe record denial", center, f.options, async page => {
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Appointment not available", exact: true }));
    await hidden(page.getByText(appointment.reference_code, { exact: true }));
    await hidden(page.getByText(appointment.student.display_name, { exact: true }));
    assert.equal(f.state.marks, 0);
  });
}

{
  const f = world();
  f.state.switchOnMark = true;
  await check("same-tab session reconciliation evicts account A Notification state", center, f.options, async page => {
    await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Account B notice", exact: true }));
    await hidden(page.getByRole("heading", { name: families[0][1], exact: true }));
    assert.equal(f.state.recordReads, 0);
  });
}

{
  const f = world();
  await check("session expiry on mark-read reconciles to login without old rows", center, f.options, async page => {
    await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
    f.state.authenticated = false;
    f.state.switchOnMark = true;
    await page.getByRole("button", { name: "Open Appointment", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("next"), center);
    await hidden(page.getByRole("heading", { name: families[0][1], exact: true }));
  });
}

for (const mode of ["empty", "error", "long desktop", "long phone dark preference reduced motion"]) {
  const f = world({ empty: mode === "empty", listFailure: mode === "error", long: mode.startsWith("long") });
  await check(`Notification Center ${mode}`, center, { ...f.options, ...(mode.includes("phone") ? { device: "phone" } : {}) }, async page => {
    if (mode.includes("dark")) await page.emulateMedia({ colorScheme: "dark", reducedMotion: "reduce" });
    await shown(page.getByRole("heading", { name: "Notifications", exact: true }));
    if (mode === "empty") await shown(page.getByText("No notifications are available yet.", { exact: true }));
    else if (mode === "error") {
      await shown(page.getByRole("alert").filter({ hasText: "could not be loaded" }));
      f.state.listFailure = false;
      await page.getByRole("button", { name: "Retry", exact: true }).click();
      await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
    } else {
      await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
      assert.equal(await page.locator("ol article").count(), 1);
      await settleFetches(page);
      await screenshot(page, mode);
    }
    await noHorizontalOverflow(page);
  });
}

{
  const f = world({ family: [null, "Unsupported target", "", "", ""] });
  await check("unsupported target offers mark-read without invented navigation", center, f.options, async page => {
    await page.getByRole("button", { name: "Mark as read", exact: true }).click();
    await hidden(page.getByText("Unread", { exact: true }));
    assert.equal(new URL(page.url()).pathname, center);
    assert.equal(f.state.recordReads, 0);
  });
}

{
  const f = world();
  await check("sign out then reopen emailed Appointment requires a fresh login", center, f.options, async page => {
    await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
    await page.getByRole("button", { name: /Open user menu/ }).click();
    await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
    await page.waitForURL(url => url.pathname === "/");
    assert.equal(f.state.authenticated, false);
    const destination = `/portal/appointments/${id}`;
    await navigate(page, destination);
    await shown(page.getByRole("heading", { name: "Sign in", exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("next"), destination);
    assert.equal(f.state.recordReads, 0);
    await page.getByLabel("Email", { exact: true }).fill("synthetic@example.test");
    await page.getByLabel("Password", { exact: true }).fill("synthetic-test-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await shown(page.getByText(appointment.reference_code, { exact: true }));
  });
}

{
  const f = world();
  let release;
  f.state.listGate = new Promise(resolve => { release = resolve; });
  await check("loading Notification list announces a busy status before data", center, f.options, async page => {
    try {
      await shown(page.getByRole("status").filter({ hasText: "Loading notifications…" }));
      assert.equal(await page.locator('[aria-busy="true"]').count() > 0, true);
      await hidden(page.getByRole("heading", { name: families[0][1], exact: true }));
    } finally { release(); }
    await shown(page.getByRole("heading", { name: families[0][1], exact: true }));
  });
}

await finish();
