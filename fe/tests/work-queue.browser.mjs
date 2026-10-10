// Read-only Guidance work in both browser engines, with synthetic canonical HTTP and socket seams.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { messagesAccount, sessionFor, threadIds } from "./support/guidance-messages-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow } = await createBrowserHarness("work-queue");
const instant = "2026-10-10T00:00:00Z";
const kinds = ["CALL_SLIP_DUE", "GUIDANCE_MESSAGE_REPLY", "ROUTINE_EVALUATION", "GOOD_MORAL_PREPARATION", "GOOD_MORAL_ISSUANCE"];
const titles = ["Review Call Slip", "Reply to Guidance Message", "Review Routine Interview", "Prepare Good Moral request", "Issue Good Moral certificate"];
const rows = kinds.map((kind, i) => ({
  id: `${kind.toLowerCase()}:${i}`, kind, priority: i === 0 ? "TIME_SENSITIVE" : "ACTION_REQUIRED",
  source_id: i === 1 ? threadIds.office : `a0000000-0000-4000-8000-00000000000${i + 5}`,
  student: { id: "synthetic-student", display_name: `Student ${i} ` + "VeryLongUnbrokenSyntheticName".repeat(6) },
  conversation_kind: i === 1 ? "OFFICE" : null, due_at: i === 0 ? instant : null,
  waiting_since: i === 0 ? null : instant,
}));

function world(role = "COUNSELOR") {
  const state = { account: messagesAccount(role), items: structuredClone(rows), status: 200, reads: [], sockets: [] };
  state.handler = async ({ pathname, reply, url }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(state.account)); return true; }
    if (pathname === "/api/v1/work") {
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
      await reply({ generated_at: instant, student: null, platform: null, guidance: {
        upcoming_self_appointments_count: 2, upcoming_managed_appointments_count: 3,
        routine_evaluation_pending_count: 8, good_moral_requested_count: 6, good_moral_ready_count: 4, active_call_slip_count: 5,
      } }); return true;
    }
    return false;
  };
  state.options = (extra = {}) => ({ handler: state.handler, ...extra });
  return state;
}

for (const width of [320, 375, 390, 430, 768, 1440]) {
  const state = world();
  await check(`My work order, routes and long names at ${width}`, "/portal/work", state.options({ viewport: { width, height: 900 } }), async (page) => {
    await shown(page.getByRole("heading", { name: "My work", exact: true }));
    await shown(page.getByText(titles[1], { exact: true }));
    const main = page.getByRole("main");
    assert.deepEqual(await main.locator("li p.font-semibold").allTextContents(), titles);
    assert.equal(await main.getByRole("link", { name: "Open conversation" }).getAttribute("href"), `/portal/messages/${threadIds.office}`);
    for (const path of ["/portal/call-slips/", "/portal/routine-interviews/", "/portal/good-moral/"]) {
      assert.ok(await main.locator(`a[href^="${path}"]`).count());
    }
    await noHorizontalOverflow(page);
    assert.equal(await main.getByRole("button", { name: /Resolve|Issue|Mark complete|Reply inline/ }).count(), 0);
    await main.getByRole("link", { name: "Open conversation" }).focus();
    assert.equal(await main.getByRole("link", { name: "Open conversation" }).evaluate((node) => node === document.activeElement), true);
  });
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  const state = world(role);
  await check(`My work navigation and direct route for ${role}`, "/portal/work", state.options(), async (page) => {
    if (["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role)) {
      await shown(page.getByRole("heading", { name: "My work", exact: true }));
      const nav = page.getByRole("navigation", { name: "Portal navigation" });
      assert.equal(await nav.getByRole("link", { name: "My work", exact: true }).count(), 1);
      assert.equal((await nav.locator("a").allTextContents())[1].trim(), "My work");
    } else {
      await shown(page.getByRole("heading", { name: "My work unavailable" }));
      assert.equal(await page.getByRole("link", { name: "My work", exact: true }).count(), 0);
      assert.equal(state.reads.length, 0);
    }
  });
}

{
  const state = world(); state.items = []; state.hasNext = false;
  await check("confirmed empty HTTP queue works with realtime disabled", "/portal/work", state.options(), async (page, { requests }) => {
    await shown(page.getByText("You’re caught up.", { exact: true }));
    assert.equal(requests.filter((r) => r.pathname === "/api/v1/realtime/tickets").length, 0);
  });
}

{
  const state = world(); state.hasNext = true;
  await check("canonical pagination preserves backend pages", "/portal/work", state.options(), async (page) => {
    await shown(page.getByText(titles[1], { exact: true }));
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await shown(page.getByText("No items on this page. Return to the previous page to check your work."));
    assert.ok(state.reads.some((search) => search.includes("page=2")));
    await page.getByRole("button", { name: "Previous", exact: true }).click();
    await shown(page.getByText(titles[1], { exact: true }));
  });
}

{
  const state = world();
  await check("refresh failure keeps confirmed work; 403 hides it", "/portal/work", state.options(), async (page) => {
    await shown(page.getByText(titles[1], { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("Latest information could not be refreshed. Showing the last confirmed result."));
    await shown(page.getByText(titles[1], { exact: true }));
    state.status = 403;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText("You don't have access to My work."));
    await hidden(page.getByText(titles[1], { exact: true }));
    assert.equal(await page.getByText("You’re caught up.", { exact: true }).count(), 0);
  });
}

{
  const state = world();
  await check("Guidance Overview uses the shared preview and keeps counts", "/portal", state.options(), async (page, { requests }) => {
    await shown(page.getByRole("link", { name: "View all work" }));
    await shown(page.getByText(titles[1], { exact: true }));
    assert.equal(await page.getByRole("link", { name: "View all work" }).getAttribute("href"), "/portal/work");
    assert.ok(state.reads.some((search) => search.includes("page_size=5")));
    assert.equal(requests.filter((r) => r.pathname === "/api/v1/good-moral" || r.pathname.includes("routine-interviews/assigned")).length, 0);
    await shown(page.getByText("At a glance", { exact: true }));
  });
}

{
  const state = world(); state.items = [];
  const socketURL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
  const overrides = { "POST /api/v1/realtime/tickets": ({ reply }) => reply({ ticket: "synthetic-work-ticket", expires_in_seconds: 30, user_id: state.account.id }) };
  const beforeNavigate = async ({ context }) => context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
    state.sockets.push(route);
    route.onMessage((message) => { if (JSON.parse(String(message)).type === "authenticate") route.send(JSON.stringify({ v: 1, type: "ready" })); });
  });
  await check("shared Message hints add and remove reply work with one socket", "/portal/work", state.options({ overrides, beforeNavigate, initScripts: [`window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(socketURL)} };`] }), async (page) => {
    await shown(page.getByText("You’re caught up.", { exact: true }));
    for (let i = 0; i < 100 && state.sockets.length === 0; i++) await page.waitForTimeout(50);
    assert.equal(state.sockets.length, 1);
    state.items = [rows[1]];
    state.sockets[0].send(JSON.stringify({ v: 1, type: "messages.thread_changed", thread_id: threadIds.office }));
    await shown(page.getByText(titles[1], { exact: true }));
    state.items = [];
    state.sockets[0].send(JSON.stringify({ v: 1, type: "messages.thread_changed", thread_id: threadIds.office }));
    await shown(page.getByText("You’re caught up.", { exact: true }));
    assert.equal(state.sockets.length, 1);
  });
}

{
  const state = world();
  await check("account boundary discards prior confirmed work", "/portal/work", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page) => {
    await shown(page.getByText(titles[1], { exact: true }));
    state.account = messagesAccount("GUIDANCE_SERVICES_STAFF", { id: "synthetic-account-B" }); state.items = [];
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("You’re caught up.", { exact: true }));
    await hidden(page.getByText(titles[1], { exact: true }));
  });
}

{
  const state = world(); state.items = [];
  await check("a failed empty refresh never claims caught up", "/portal/work", state.options(), async (page) => {
    await shown(page.getByText("You’re caught up.", { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("Your last confirmed result had no work items."));
    assert.equal(await page.getByText("You’re caught up.", { exact: true }).count(), 0);
  });
}

{
  const state = world(); state.items = [];
  await check("visible online safety poll heals non-Message work without realtime", "/portal/work", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page, { context }) => {
    await shown(page.getByText("You’re caught up.", { exact: true }));
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
    state.items = [rows[2]];
    await page.clock.fastForward(65_000);
    await shown(page.getByText(titles[2], { exact: true }));
    await hidden(page.getByText(titles[0], { exact: true }));
  });
}

await finish();
