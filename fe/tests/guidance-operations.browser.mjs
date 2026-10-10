// Actual Next UI in Chromium/WebKit. Aggregate HTTP and socket seams use synthetic facts only.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { operationsAccount, operationsData } from "./support/guidance-operations-fixtures.mjs";
import { sessionFor, threadIds, staffWorld, COUNSELOR, STUDENT } from "./support/guidance-messages-fixtures.mjs";

const { baseURL, check, shown, hidden, finish, noHorizontalOverflow, screenshot } = await createBrowserHarness("guidance-operations");
const labels = ["Messages awaiting reply", "Routine evaluations pending", "Good Moral needs preparation", "Good Moral ready for issuance", "Call Slips due"];
const emptyCopy = "No work is currently waiting for your action.";

function world(role = "COUNSELOR") {
  const state = { account: operationsAccount(role), data: operationsData(role), status: 200, reads: 0, sockets: [] };
  state.handler = async ({ pathname, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(state.account)); return true; }
    if (pathname === "/api/v1/guidance-operations") {
      state.reads++;
      if (state.status !== 200) await reply({ error: { code: "synthetic_failure", message: "Synthetic" } }, state.status);
      else await reply(state.data);
      return true;
    }
    return false;
  };
  state.options = (extra = {}) => ({ handler: state.handler, ...extra });
  return state;
}

function clearBacklog(state) {
  for (const metric of Object.values(state.data.backlog)) {
    if (metric === null) continue;
    metric.count = 0;
    if ("oldest_due_at" in metric) metric.oldest_due_at = null;
    else metric.oldest_waiting_since = null;
  }
}

const row = (page, label) => page.getByRole("main").locator("dl > div").filter({ has: page.getByText(label, { exact: true }) });

for (const width of [320, 375, 390, 430, 768, 1440]) {
  const state = world();
  await check(`compact semantic metrics, oldest times and links at ${width}`, "/portal/operations", state.options({ viewport: { width, height: 1000 } }), async (page) => {
    await shown(page.getByRole("heading", { name: "Guidance operations", exact: true }));
    await shown(page.getByRole("heading", { name: "Actionable backlog", exact: true }));
    await shown(page.getByRole("heading", { name: "Schedule", exact: true }));
    assert.deepEqual(await page.getByRole("main").locator('dl[aria-label="Actionable backlog metrics"] dt').evaluateAll((nodes) => nodes.map((node) => node.firstElementChild.textContent)), labels);
    assert.equal(await row(page, labels[0]).locator("dd").textContent(), "7");
    assert.match(await row(page, labels[0]).textContent(), /Oldest waiting:/);
    assert.match(await row(page, labels[4]).textContent(), /Oldest due:/);
    for (const label of [labels[0], labels[1], labels[4]]) assert.equal(await row(page, label).locator("a").count(), 0);
    assert.equal(await row(page, labels[2]).locator("a").getAttribute("href"), "/portal/good-moral?status=REQUESTED");
    assert.equal(await row(page, labels[3]).locator("a").getAttribute("href"), "/portal/good-moral?status=READY_FOR_ISSUANCE");
    assert.equal(await row(page, "Your upcoming appointments").locator("a").getAttribute("href"), "/portal/appointments/my?status=UPCOMING");
    assert.equal(await row(page, "Active Call Slips").locator("a").getAttribute("href"), "/portal/call-slips?state=ACTIVE");
    const link = page.getByRole("link", { name: "Open My work", exact: true });
    await link.focus();
    assert.ok(await link.evaluate((node) => node === document.activeElement));
    assert.ok((await link.boundingBox()).height >= 44);
    await noHorizontalOverflow(page);
    await screenshot(page, `guidance-operations-${width}`);
  });
}

for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  const state = world(role);
  await check(`navigation and direct route authority for ${role}`, "/portal/operations", state.options(), async (page) => {
    const nav = page.getByRole("navigation", { name: "Portal navigation" });
    if (["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role)) {
      await shown(page.getByRole("heading", { name: "Guidance operations", exact: true }));
      await shown(page.getByText(labels[0], { exact: true }));
      const links = await nav.locator("a").allTextContents();
      assert.deepEqual(links.slice(1, 3).map((value) => value.trim()), ["My work", "Guidance operations"]);
      if (role === "GUIDANCE_SERVICES_STAFF") {
        await hidden(page.getByText(labels[1], { exact: true }));
        await hidden(page.getByText(labels[3], { exact: true }));
        await hidden(page.getByText("Your upcoming appointments", { exact: true }));
        assert.equal(await row(page, "Upcoming managed appointments").locator("a").getAttribute("href"), "/portal/appointments/manage?status=UPCOMING");
      }
    } else {
      await shown(page.getByRole("heading", { name: "Guidance operations unavailable" }));
      assert.equal(await nav.getByRole("link", { name: "Guidance operations", exact: true }).count(), 0);
      assert.equal(state.reads, 0);
    }
  });
}

{
  const state = world(); clearBacklog(state);
  await check("authorized zeros retain schedule and actor-scoped empty wording", "/portal/operations", state.options(), async (page, { requests }) => {
    await shown(page.getByText(emptyCopy, { exact: true }));
    assert.equal(await page.getByRole("main").locator('dl[aria-label="Actionable backlog metrics"] dd').filter({ hasText: /^0$/ }).count(), 5);
    assert.equal(await row(page, "Active Call Slips").locator("dd").textContent(), "9");
    assert.equal(requests.filter((r) => r.pathname === "/api/v1/realtime/tickets").length, 0);
  });
}

{
  const state = world(); state.account.designations = ["HEAD_GUIDANCE_COUNSELOR"];
  state.data.backlog.guidance_messages = null; state.data.backlog.routine_evaluations = null;
  await check("Head renders only returned authority with no office-wide inference", "/portal/operations", state.options(), async (page) => {
    await shown(page.getByText("Active Call Slips", { exact: true }));
    await hidden(page.getByText(labels[0], { exact: true }));
    await hidden(page.getByText(labels[1], { exact: true }));
    assert.equal(await page.getByRole("main").getByText(/institution-wide|All Counselors|performance|SLA/).count(), 0);
  });
}

{
  const state = world();
  await check("refresh failure retains facts; authority loss conceals them", "/portal/operations", state.options(), async (page) => {
    await shown(page.getByText(labels[0], { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("Latest information could not be refreshed. Showing the last confirmed result."));
    assert.equal(await row(page, labels[0]).locator("dd").textContent(), "7");
    state.status = 403;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText("You don't have access to Guidance Operations."));
    await hidden(page.getByText(labels[0], { exact: true }));
  });
}

{
  const state = world(); state.status = 500;
  await check("first-load error offers Retry without fabricated zeroes", "/portal/operations", state.options(), async (page) => {
    await shown(page.getByText("Guidance operations could not be loaded. Try again."));
    assert.equal(await page.getByRole("main").locator("dd").count(), 0);
    state.status = 200;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText(labels[0], { exact: true }));
  });
}

{
  const state = world(); clearBacklog(state);
  await check("failed refresh of zeroes no longer asserts a current empty backlog", "/portal/operations", state.options(), async (page) => {
    await shown(page.getByText(emptyCopy, { exact: true }));
    state.status = 500;
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await shown(page.getByText("The last confirmed result showed no work waiting for your action."));
    await hidden(page.getByText(emptyCopy, { exact: true }));
  });
}

{
  const state = world();
  await check("new account discards previous confirmed protected metrics", "/portal/operations", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page) => {
    await shown(page.getByText(labels[1], { exact: true }));
    state.account = operationsAccount("GUIDANCE_SERVICES_STAFF", { id: "synthetic-operations-B" });
    state.data = operationsData("GUIDANCE_SERVICES_STAFF");
    state.data.backlog.guidance_messages = null;
    await page.clock.fastForward(31_000);
    await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
    await shown(page.getByText("Upcoming managed appointments", { exact: true }));
    await hidden(page.getByText(labels[0], { exact: true }));
    await hidden(page.getByText(labels[1], { exact: true }));
  });
}

{
  const state = world();
  const socketURL = `${baseURL.replace(/^http/, "ws")}/api/realtime/v1/socket`;
  const overrides = { "POST /api/v1/realtime/tickets": ({ reply }) => reply({ ticket: "synthetic-operations-ticket", expires_in_seconds: 30, user_id: state.account.id }) };
  const beforeNavigate = async ({ context }) => context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
    state.sockets.push(route);
    route.onMessage((message) => { if (JSON.parse(String(message)).type === "authenticate") route.send(JSON.stringify({ v: 1, type: "ready" })); });
  });
  await check("existing Message hint and ready generation reconcile via one shared socket", "/portal/operations", state.options({ overrides, beforeNavigate, initScripts: [`window.__COMPASS_REALTIME_TEST_CONFIG__ = { url: ${JSON.stringify(socketURL)} };`] }), async (page) => {
    await shown(page.getByText(labels[0], { exact: true }));
    for (let i = 0; i < 100 && state.sockets.length === 0; i++) await page.waitForTimeout(50);
    assert.equal(state.sockets.length, 1);
    state.data.backlog.guidance_messages.count = 8;
    state.sockets[0].send(JSON.stringify({ v: 1, type: "messages.thread_changed", thread_id: threadIds.office }));
    await shown(row(page, labels[0]).locator("dd").filter({ hasText: /^8$/ }));
    state.data.backlog.guidance_messages.count = 9;
    await state.sockets[0].close({ code: 4000, reason: "lifetime_expired" });
    for (let i = 0; i < 120 && state.sockets.length < 2; i++) await page.waitForTimeout(50);
    assert.equal(state.sockets.length, 2, "One replacement socket after the old connection closes");
    await shown(row(page, labels[0]).locator("dd").filter({ hasText: /^9$/ }));
    assert.equal(state.sockets.length, 2);
  });
}

{
  const state = world();
  await check("visible online safety polling heals time changes and pauses hidden offline", "/portal/operations", state.options({ beforeNavigate: async ({ page }) => page.clock.install() }), async (page, { context }) => {
    await shown(page.getByText(labels[4], { exact: true }));
    const before = state.reads;
    await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" }); document.dispatchEvent(new Event("visibilitychange")); });
    await page.clock.fastForward(65_000);
    assert.equal(state.reads, before);
    await page.evaluate(() => { Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" }); document.dispatchEvent(new Event("visibilitychange")); });
    await page.waitForTimeout(300);
    await context.setOffline(true);
    const offline = state.reads;
    await page.clock.fastForward(65_000);
    assert.equal(state.reads, offline);
    state.data.backlog.call_slips_due.count = 4;
    await context.setOffline(false);
    await page.evaluate(() => window.dispatchEvent(new Event("online")));
    await shown(row(page, labels[4]).locator("dd").filter({ hasText: /^4$/ }));
    state.data.backlog.call_slips_due.count = 0; state.data.backlog.call_slips_due.oldest_due_at = null;
    await page.clock.fastForward(65_000);
    await shown(row(page, labels[4]).locator("dd").filter({ hasText: /^0$/ }));
  });
}

{
  const state = world(); const backend = staffWorld();
  backend.state.threads.get(threadIds.office).assigned_to = COUNSELOR;
  const handler = async (request) => {
    if (request.pathname === "/api/v1/guidance-operations") {
      const thread = backend.state.threads.get(threadIds.office);
      const last = backend.state.messages.get(threadIds.office).at(-1);
      const count = thread.status === "OPEN" && thread.assigned_to?.id === COUNSELOR.id && last?.sender.id === STUDENT.id ? 1 : 0;
      state.data.backlog.guidance_messages = { count, oldest_waiting_since: count ? last.created_at : null };
    }
    return await state.handler(request) || await backend.handler(request);
  };
  await check("same-tab reading preserves reply backlog; confirmed send reconciles it without a socket", "/portal/operations", state.options({ handler }), async (page) => {
    await shown(row(page, labels[0]).locator("dd").filter({ hasText: /^1$/ }));
    await page.evaluate((id) => window.next.router.push(`/portal/messages/${id}`), threadIds.office);
    await shown(page.getByText("Good afternoon po.", { exact: true }));
    for (let i = 0; i < 100 && backend.reads().length === 0; i++) await page.waitForTimeout(50);
    assert.ok(backend.reads().length > 0);
    await page.getByRole("navigation", { name: "Portal navigation" }).getByRole("link", { name: "Guidance operations", exact: true }).click();
    await shown(row(page, labels[0]).locator("dd").filter({ hasText: /^1$/ }));
    await page.evaluate((id) => window.next.router.push(`/portal/messages/${id}`), threadIds.office);
    await shown(page.getByText("Good afternoon po.", { exact: true }));
    await page.getByRole("textbox", { name: /^Message/ }).fill("Synthetic confirmed reply");
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await shown(page.getByText("Synthetic confirmed reply", { exact: true }));
    const before = state.reads;
    await page.getByRole("navigation", { name: "Portal navigation" }).getByRole("link", { name: "Guidance operations", exact: true }).click();
    await shown(row(page, labels[0]).locator("dd").filter({ hasText: /^0$/ }));
    assert.ok(state.reads > before, "Canonical HTTP summary was invalidated by confirmed send");
  });
}

await finish();
