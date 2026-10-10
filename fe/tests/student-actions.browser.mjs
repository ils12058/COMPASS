// Student actions in both engines, with synthetic canonical HTTP and shared socket seams.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { messagesAccount, sessionFor, threadIds, studentWorld } from "./support/guidance-messages-fixtures.mjs";

import { appointmentId as sessionId, consents, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow, screenshot } = await createBrowserHarness("student-actions");
const instant = "2026-10-10T00:00:00Z";
const kinds = ["ECOUNSELING_JOIN", "CALL_SLIP_ACTIVE", "ROUTINE_INTAKE", "EXIT_INTERVIEW_START", "EXIT_INTERVIEW_CONTINUE", "EXIT_INTERVIEW_CORRECTION", "ECOUNSELING_CONSENT", "GUIDANCE_MESSAGE_UNREAD", "INVENTORY_START", "INVENTORY_CONTINUE", "GRADUATE_TRACER_CONTINUE"];
const titles = ["E-Counseling", "Call Slip", "Routine Interview", "Exit Interview", "Exit Interview", "Exit Interview correction", "E-Counseling consent", "Guidance Messages", "Individual Inventory", "Individual Inventory", "Graduate Tracer Survey"];
const rows = kinds.map((kind, i) => ({
  id: `${kind.toLowerCase()}:${i}`, kind, priority: i < 2 ? "TIME_SENSITIVE" : i < 8 ? "ACTION_REQUIRED" : "INCOMPLETE_SELF_SERVICE",
  source_id: i === 7 ? threadIds.office : `a0000000-0000-4000-8000-0000000000${String(i + 5).padStart(2, "0")}`,
  conversation_kind: i === 7 ? "OFFICE" : null, pending_count: i === 6 ? 2 : i === 7 ? 1 : null,
  due_at: i < 2 ? instant : null, waiting_since: i < 2 ? null : instant,
}));

function world(role = "STUDENT") {
  const state = { account: messagesAccount(role), items: structuredClone(rows), status: 200, reads: [], sockets: [] };
  state.handler = async ({ pathname, reply, url }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(state.account)); return true; }
    if (pathname === "/api/v1/student-actions") {
      state.reads.push(url.search);
      if (state.status !== 200) await reply({ error: { code: "synthetic_unavailable", message: "Synthetic" } }, state.status);
      else {
        const page = Number(url.searchParams.get("page") ?? 1);
        const pageSize = Number(url.searchParams.get("page_size") ?? 20);
        await reply({ items: page === 1 ? state.items.slice(0, pageSize) : [], page, page_size: pageSize, has_next: page === 1 && state.hasNext, generated_at: instant });
      }
      return true;
    }
    if (pathname === "/api/v1/overview") {
      await reply({ generated_at: instant, guidance: null, platform: null, student: {
        upcoming_appointments_count: 2, routine_intake_draft_count: 8, good_moral_requested_count: 6,
        good_moral_ready_count: 4, active_call_slip_count: 5,
      } }); return true;
    }
    return false;
  };
  state.options = (extra = {}) => ({ handler: state.handler, ...extra });
  return state;
}

for (const width of [320, 375, 390, 430, 768, 1440]) {
  const state = world();
  await check(`My actions order, routes and wrapping labels at ${width}`, "/portal/actions", state.options({ viewport: { width, height: 900 } }), async (page) => {
    await shown(page.getByRole("heading", { name: "My actions", exact: true }));
    await shown(page.getByText(titles[7], { exact: true }));
    const main = page.getByRole("main");
    assert.deepEqual(await main.locator("li > div > p:first-child").allTextContents(), titles);
    assert.equal(await main.getByRole("link", { name: "Read new Guidance message" }).getAttribute("href"), `/portal/messages/${threadIds.office}`);
    for (const path of ["/portal/call-slips/", "/portal/routine-interviews/", "/portal/exit-interviews/", "/portal/e-counseling/"]) {
      assert.ok(await main.locator(`a[href^="${path}"]`).count());
    }
    await noHorizontalOverflow(page);
    assert.equal(await main.getByRole("button", { name: /Resolve|Issue|Mark complete|Reply inline/ }).count(), 0);
    await main.getByRole("link", { name: "Read new Guidance message" }).focus();
    assert.equal(await main.getByRole("link", { name: "Read new Guidance message" }).evaluate((node) => node === document.activeElement), true);
    await screenshot(page, `my-actions-${width}`);
  });
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  const state = world(role);
  await check(`My actions navigation and direct route for ${role}`, "/portal/actions", state.options(), async (page) => {
    if (role === "STUDENT") {
      await shown(page.getByRole("heading", { name: "My actions", exact: true }));
      const nav = page.getByRole("navigation", { name: "Portal navigation" });
      assert.equal(await nav.getByRole("link", { name: "My actions", exact: true }).count(), 1);
      assert.equal((await nav.locator("a").allTextContents())[1].trim(), "My actions");
    } else {
      await shown(page.getByRole("heading", { name: "My actions unavailable" }));
      assert.equal(await page.getByRole("link", { name: "My actions", exact: true }).count(), 0);
      assert.equal(state.reads.length, 0);
    }
  });
}

{
  const state = world(); state.items = []; state.hasNext = false;
  await check("confirmed empty HTTP queue works with realtime disabled", "/portal/actions", state.options(), async (page, { requests }) => {
    await shown(page.getByText("You're all caught up.", { exact: true }));
    assert.equal(requests.filter((r) => r.pathname === "/api/v1/realtime/tickets").length, 0);
  });
}

{
  const state = world(); state.hasNext = true;
  await check("canonical pagination preserves backend pages", "/portal/actions", state.options(), async (page) => {
    await shown(page.getByText(titles[7], { exact: true }));
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await shown(page.getByText("No items on this page. Return to the previous page to check your actions."));
    assert.ok(state.reads.some((search) => search.includes("page=2")));
    await page.getByRole("button", { name: "Previous", exact: true }).click();
    await shown(page.getByText(titles[7], { exact: true }));
  });
}

{
  const state = world();
  await check("refresh failure keeps confirmed work; 403 hides it", "/portal/actions", state.options(), async (page) => {
    await shown(page.getByText(titles[7], { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("Latest information could not be refreshed. Showing the last confirmed result."));
    await shown(page.getByText(titles[7], { exact: true }));
    state.status = 403;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText("You don't have access to My actions."));
    await hidden(page.getByText(titles[7], { exact: true }));
    assert.equal(await page.getByText("You're all caught up.", { exact: true }).count(), 0);
  });
}

{
  const state = world();
  await check("Student Overview uses the shared preview and keeps counts", "/portal", state.options(), async (page, { requests }) => {
    await shown(page.getByRole("link", { name: "View all actions" }));
    await shown(page.getByRole("link", { name: "Join E-Counseling", exact: true }));
    assert.equal(await page.getByRole("link", { name: "View all actions" }).getAttribute("href"), "/portal/actions");
    assert.ok(state.reads.some((search) => search.includes("page_size=5")));
    assert.equal(requests.filter((r) => ["/api/v1/inventory/me/status", "/api/v1/routine-interviews/me", "/api/v1/exit-interviews/me/current", "/api/v1/graduate-tracer/me"].includes(r.pathname)).length, 0);
    await shown(page.getByText("At a glance", { exact: true }));
  });
}

{
  const state = world(); state.items = [];
  const socketURL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
  const overrides = { "POST /api/v1/realtime/tickets": ({ reply }) => reply({ ticket: "synthetic-actions-ticket", expires_in_seconds: 30, user_id: state.account.id }) };
  const beforeNavigate = async ({ context }) => context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
    state.sockets.push(route);
    route.onMessage((message) => { if (JSON.parse(String(message)).type === "authenticate") route.send(JSON.stringify({ v: 1, type: "ready" })); });
  });
  await check("shared Message and Notification hints add and remove unread actions with one socket", "/portal/actions", state.options({ overrides, beforeNavigate, initScripts: [`window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(socketURL)} };`] }), async (page) => {
    await shown(page.getByText("You're all caught up.", { exact: true }));
    for (let i = 0; i < 100 && state.sockets.length === 0; i++) await page.waitForTimeout(50);
    assert.equal(state.sockets.length, 1);
    state.items = [rows[7]];
    state.sockets[0].send(JSON.stringify({ v: 1, type: "messages.thread_changed", thread_id: threadIds.office }));
    await shown(page.getByText(titles[7], { exact: true }));
    state.items = [];
    state.sockets[0].send(JSON.stringify({ v: 1, type: "notifications.changed" }));
    await shown(page.getByText("You're all caught up.", { exact: true }));
    assert.equal(state.sockets.length, 1);
  });
}

{
  const state = world();
  await check("account boundary discards prior confirmed work", "/portal/actions", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page) => {
    await shown(page.getByText(titles[7], { exact: true }));
    state.account = messagesAccount("STUDENT", { id: "synthetic-account-B" }); state.items = [];
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("You're all caught up.", { exact: true }));
    await hidden(page.getByText(titles[7], { exact: true }));
  });
}

{
  const state = world(); state.items = [];
  await check("a failed empty refresh never claims caught up", "/portal/actions", state.options(), async (page) => {
    await shown(page.getByText("You're all caught up.", { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("Your last confirmed result had no actions."));
    assert.equal(await page.getByText("You're all caught up.", { exact: true }).count(), 0);
  });
}

{
  const state = world(); state.items = [];
  await check("visible online safety poll opens and closes time-sensitive join actions without realtime", "/portal/actions", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page, { context }) => {
    await shown(page.getByText("You're all caught up.", { exact: true }));
    const before = state.reads.length;
    await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" }); document.dispatchEvent(new Event("visibilitychange")); });
    await page.clock.fastForward(65_000);
    assert.equal(state.reads.length, before, "Hidden tabs do not safety-poll");
    await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" }); document.dispatchEvent(new Event("visibilitychange")); });
    await page.waitForTimeout(300);
    await context.setOffline(true);
    const offline = state.reads.length;
    await page.clock.fastForward(65_000);
    assert.equal(state.reads.length, offline, "Offline tabs do not safety-poll");
    state.items = [rows[0]];
    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await shown(page.getByText(titles[0], { exact: true }));
    state.items = [];
    await page.clock.fastForward(65_000);
    await shown(page.getByText("You\'re all caught up.", { exact: true }));
    await hidden(page.getByText(titles[0], { exact: true }));
  });
}

{
  const state = world(); state.status = 500;
  await check("first load failure has Retry and never claims caught up", "/portal/actions", state.options(), async (page) => {
    await shown(page.getByText("Your actions could not be loaded. Try again."));
    assert.equal(await page.getByText("You're all caught up.", { exact: true }).count(), 0);
    state.status = 200; state.items = [];
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText("You're all caught up.", { exact: true }));
  });
}

{
  const state = world(); const backend = studentWorld();
  const handler = async (request) => {
    if (request.pathname === "/api/v1/student-actions") {
      state.items = backend.state.reads.get(threadIds.office) < 3 ? [rows[7]] : [];
    }
    return await state.handler(request) || await backend.handler(request);
  };
  await check("same-tab Message visibility read invalidates actions without polling or socket", "/portal/actions", state.options({ handler }), async (page) => {
    await shown(page.getByRole("link", { name: "Read new Guidance message", exact: true }));
    assert.equal(backend.reads().length, 0, "The action list never marks read");
    const before = state.reads.length;
    await page.getByRole("link", { name: "Read new Guidance message", exact: true }).click();
    await shown(page.getByText("Bring your ID.", { exact: true }));
    for (let i = 0; i < 100 && backend.reads().length === 0; i++) await page.waitForTimeout(50);
    assert.ok(backend.reads().length > 0);
    await page.getByRole("navigation", { name: "Portal navigation" }).getByRole("link", { name: "My actions", exact: true }).click();
    await shown(page.getByText("You're all caught up.", { exact: true }));
    assert.ok(state.reads.length > before);
  });
}
{
  const state = world(); const scopes = consents("PENDING");
  const handler = async (request) => {
    if (request.pathname === "/api/v1/student-actions") {
      const pending = scopes.filter((row) => row.decision === "PENDING").length;
      state.items = pending ? [{ ...rows[6], source_id: sessionId, pending_count: pending }] : [];
    }
    if (request.pathname.includes(`/e-counseling/me/appointments/${sessionId}/consents`)) {
      if (request.method === "GET") await request.reply({ items: scopes });
      else {
        const row = scopes.find((row) => request.pathname.includes(row.id));
        assert.ok(row); row.decision = "DENIED"; row.decided_at = instant;
        await request.reply(row);
      }
      return true;
    }
    if (request.pathname === `/api/v1/e-counseling/me/appointments/${sessionId}`) {
      const data = workspace(); data.media.recording.consent_status = scopes[0].decision;
      data.media.transcription.consent_status = scopes[1].decision;
      await request.reply(data); return true;
    }
    return state.handler(request);
  };
  await check("same-tab consent decisions refresh grouped actions without safety polling", "/portal/actions", state.options({ handler, fakeDaily: true }), async (page) => {
    await shown(page.getByText("2 consent decisions require your review.", { exact: true }));
    for (let remaining = 1; remaining >= 0; remaining--) {
      await page.getByRole("link", { name: "Review consent", exact: true }).click();
      await page.getByRole("button", { name: /^Decline / }).first().click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Decline", exact: true }).click();
      await shown(page.getByText("Your choice has been saved. Counseling remains available.", { exact: true }));
      await page.getByRole("navigation", { name: "Portal navigation" }).getByRole("link", { name: "My actions", exact: true }).click();
      await shown(page.getByText(remaining ? "A consent decision requires your review." : "You're all caught up.", { exact: true }));
    }
  });
}

await finish();
