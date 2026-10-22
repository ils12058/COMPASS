// Synthetic Student Home scenarios, visual pairs and geometry. No live accounts or providers.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeAction, homeWorld } from "./support/ux15-home-fixtures.mjs";

const { artifacts, check, shown, hidden, finish, screenshot, noHorizontalOverflow } = await createBrowserHarness("ux15-student-home");
const baseline = process.env.COMPASS_HOME_PHASE === "before";
const geometry = [];
const attention = (page) => page.locator('section[aria-labelledby="overview-attention-heading"]');

const visualScenarios = [
  ["desktop-pending", {}, 1440, false],
  ["desktop-empty", { items: [] }, 1440, false],
  ["mobile-pending", {}, 390, false],
  ["narrow-enlarged", {}, 320, true],
  ["join-now", { items: [homeAction("ECOUNSELING_JOIN", "TIME_SENSITIVE", 8, { due_at: "2026-10-22T02:00:00Z" })] }, 1440, false],
  ["failed-actions", { failure: true }, 1440, false],
  ["graduated", { lifecycle: "GRADUATED", items: [homeAction("GRADUATE_TRACER_CONTINUE", "INCOMPLETE_SELF_SERVICE", 9)] }, 1440, false],
  ["professional", { role: "COUNSELOR", designations: ["HEAD_GUIDANCE_COUNSELOR"] }, 1440, false],
];
for (const [name, setup, width, enlarged] of visualScenarios) {
  const state = homeWorld(setup);
  if (setup.failure) state.actionsStatus = 500;
  await check(`visual-${name}`, "/portal", state.options({ viewport: { width, height: 1000 } }), async (page) => {
    await shown(page.locator("#overview-announcements-heading"));
    await shown(page.getByText("Guidance Office schedule for October", { exact: true }));
    if (setup.role === "COUNSELOR") {
      await shown(page.locator("#counselor-work-heading"));
      await shown(page.locator('section[aria-labelledby="counselor-work-heading"] li').first());
    } else {
      await shown(attention(page));
      if (setup.failure) await shown(page.getByText("My actions could not be loaded", { exact: true }));
      else if (setup.items?.length === 0) await shown(attention(page).getByText(/caught up|No current actions/));
      else await shown(attention(page).locator("li").first());
    }
    if (enlarged) await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
    await page.evaluate(() => document.fonts.ready);
    const measurement = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth,
      header: document.querySelector("header").scrollWidth, rootText: getComputedStyle(document.documentElement).fontSize }));
    geometry.push({ name, phase: baseline ? "before" : "after", ...measurement });
    if (!baseline) await noHorizontalOverflow(page);
    await screenshot(page, `${baseline ? "before" : "after"}-${name}`);
  });
}

if (!baseline) {
  for (const width of [320, 360, 390, 768, 1024, 1440]) {
    for (const enlarged of [false, true]) {
      const state = homeWorld();
      state.account.first_name = "AlexandriaMariaCatherineJohnsonWilliams";
      state.announcements[0].title = "SyntheticAnnouncementWithAnUnbrokenTitleToVerifyEmergencyWrapping";
      await check(`layout-${width}-${enlarged ? "200" : "100"}-percent-text`, "/portal", state.options({ viewport: { width, height: 1000 } }), async (page) => {
        await shown(attention(page).getByRole("heading", { name: "Individual Inventory", exact: true }));
        await shown(page.getByText(state.announcements[0].title, { exact: true }));
        if (enlarged) await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
        await page.evaluate(() => document.fonts.ready);
        await noHorizontalOverflow(page);
        const measures = await page.evaluate(() => {
          const rect = (node) => { const r = node.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
          const main = document.querySelector("main");
          const panels = [...main.querySelectorAll("section[aria-labelledby]")];
          const links = [...main.querySelectorAll("a")].filter((node) => node.getClientRects().length);
          const boxes = links.map((node) => ({ name: node.textContent.trim(), ...rect(node), tabIndex: node.tabIndex }));
          const collisions = boxes.flatMap((a, i) => boxes.slice(i + 1).filter((b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1).map((b) => [a.name, b.name]));
          const rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
          const targets = [...main.querySelectorAll('section[aria-labelledby="overview-attention-heading"] a, section[aria-labelledby="student-home-services-heading"] a')].map((node) => rect(node));
          return { viewport: innerWidth, document: document.documentElement.scrollWidth, rootText: getComputedStyle(document.documentElement).fontSize, targets, minimumTarget: 2.75 * rootSize,
            panels: panels.map((node) => ({ id: node.getAttribute("aria-labelledby"), scroll: node.scrollWidth, client: node.clientWidth, ...rect(node) })), boxes, collisions };
        });
        assert.equal(measures.collisions.length, 0, "Home links do not overlap");
        assert.ok(measures.panels.every((panel) => panel.scroll <= panel.client + 1), "Each Home region reflows internally");
        assert.ok(measures.boxes.every((link) => link.left >= -1 && link.right <= width + 1 && link.tabIndex >= 0), "Every Home link remains within the viewport and focusable");
        assert.ok(measures.targets.every((target) => target.height >= measures.minimumTarget - 1), "Student actions and discovery retain the established 44px/rem-scaled minimum targets");
        assert.deepEqual(await page.locator("main h2").allTextContents(), ["Needs your attention", "Guidance services", "At a glance", "Announcements"]);
        geometry.push({ name: `layout-${width}`, enlarged, ...measures });
        if (width === 320 && enlarged) {
          await screenshot(page, "after-announcements-320-200-detail", page.locator('section[aria-labelledby="overview-announcements-heading"]'));
        }
        if (width === 1440) {
          await page.getByRole("button", { name: "Collapse navigation" }).click();
          await noHorizontalOverflow(page);
        }
      });
    }
  }

  {
    const state = homeWorld({ items: [homeAction("INVENTORY_START", "INCOMPLETE_SELF_SERVICE")] });
    await check("new-current-student-has-only-canonical-inventory-action", "/portal", state.options(), async (page, { requests }) => {
      await shown(attention(page).getByRole("link", { name: "Start Inventory", exact: true }));
      assert.equal(await attention(page).locator("li").count(), 1);
      assert.equal(await attention(page).getByText("Time sensitive", { exact: true }).count(), 0);
      assert.equal(await page.locator("main").getByRole("link", { name: "Book appointment", exact: true }).getAttribute("href"), "/portal/appointments/book");
      assert.equal(requests.filter((r) => r.method !== "GET").length, 0, "Rendering never mutates");
    });
  }
  {
    const state = homeWorld();
    await check("canonical-first-five-preview-and-view-all-open-the-owning-workspace", "/portal", state.options(), async (page, { requests }) => {
      await shown(attention(page).getByRole("heading", { name: "Individual Inventory", exact: true }));
      assert.deepEqual(await attention(page).locator("li h3").allTextContents(), ["Call Slip", "Routine Interview", "Guidance Messages", "Exit Interview", "Individual Inventory"]);
      assert.equal(await attention(page).getByRole("link", { name: "Review consent", exact: true }).count(), 0);
      assert.ok(requests.some((r) => r.pathname === "/api/v1/student-actions" && new URLSearchParams(r.search).get("page_size") === "5"));
      assert.equal(requests.filter((r) => ["/api/v1/inventory/me/status", "/api/v1/routine-interviews/me", "/api/v1/exit-interviews/me/current", "/api/v1/graduate-tracer/me"].includes(r.pathname)).length, 0);
      await attention(page).getByRole("link", { name: "View all actions" }).click();
      await shown(page.getByRole("heading", { name: "My actions", exact: true }));
      await shown(page.getByRole("link", { name: "Review consent", exact: true }));
      assert.equal(requests.filter((r) => r.method !== "GET").length, 0, "Opening the action workspace never completes work");
    });
  }
  for (const lifecycle of ["GRADUATED", "FORMER"]) {
    const state = homeWorld({ lifecycle, items: lifecycle === "GRADUATED" ? [homeAction("GRADUATE_TRACER_CONTINUE", "INCOMPLETE_SELF_SERVICE")] : [] });
    await check(`lifecycle-${lifecycle}-keeps-own-reading-and-action-eligibility`, "/portal", state.options(), async (page) => {
      const services = page.locator('section[aria-labelledby="student-home-services-heading"]');
      await shown(services);
      assert.equal(await page.locator("main").getByRole("link", { name: "Book appointment", exact: true }).count(), 0);
      assert.equal(await attention(page).getByRole("link", { name: /Start Inventory|Continue Inventory/ }).count(), 0);
      assert.equal(await page.locator('section[aria-labelledby="overview-summary-heading"]').getByText("Routine Interview drafts", { exact: true }).count(), 0, "Non-Current draft counts are unavailable, not zero");
      if (lifecycle === "GRADUATED") {
        await shown(attention(page).getByRole("link", { name: "Continue survey", exact: true }));
        assert.equal(await services.locator('a[href="/portal/graduate-tracer"]').count(), 1);
        assert.equal(await services.locator('a[href="/portal/inventory"]').count(), 0);
      } else {
        await shown(attention(page).getByText(/No current actions/));
        assert.equal(await services.locator('a[href="/portal/inventory"]').count(), 1, "Former accounts may read existing Inventory records");
        assert.equal(await services.locator('a[href="/portal/graduate-tracer"]').count(), 0);
      }
    });
  }
  {
    const state = homeWorld({ capabilities: [], items: [] });
    state.summary.student = { upcoming_appointments_count: null, routine_intake_draft_count: null, good_moral_requested_count: null, active_call_slip_count: null };
    await check("no-unauthorized-shortcuts-or-fabricated-zero-counts", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByText(/No current actions/));
      assert.equal(await page.locator("#student-home-services-heading, #overview-summary-heading").count(), 0);
      assert.equal(await page.locator("main").getByRole("link", { name: "Book appointment", exact: true }).count(), 0);
      assert.equal(await page.locator('main a[href="/portal/services"]').count(), 0);
      await shown(page.locator("#overview-announcements-heading"));
    });
  }
  {
    const state = homeWorld();
    let release;
    state.actionsHold = new Promise((resolve) => { release = resolve; });
    await check("loading-actions-keeps-confirmed-context-and-announcements-usable", "/portal", state.options(), async (page) => {
      try {
        await shown(attention(page).locator('[aria-busy="true"]'));
        await shown(page.getByText("Guidance Office schedule for October", { exact: true }));
        await shown(page.locator("#overview-summary-heading"));
        assert.equal(await attention(page).getByText(/caught up/).count(), 0);
        await screenshot(page, "after-loading-actions");
      } finally { release(); state.actionsHold = null; }
      await shown(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
    });
  }
  {
    const state = homeWorld(); state.actionsStatus = 500;
    await check("initial-action-failure-retries-without-claiming-completion", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByText("My actions could not be loaded", { exact: true }));
      assert.equal(await attention(page).getByText(/caught up/).count(), 0);
      await shown(page.locator("#student-home-services-heading"));
      state.actionsStatus = 200; state.items = [];
      await attention(page).getByRole("button", { name: "Retry", exact: true }).click();
      await shown(attention(page).getByText(/No current actions/));
    });
  }
  {
    const state = homeWorld(); state.summaryStatus = 500;
    await check("summary-failure-does-not-hide-actions-or-invent-counts", "/portal", state.options(), async (page) => {
      const summary = page.locator('section[aria-labelledby="overview-summary-heading"]');
      await shown(summary.getByRole("alert"));
      assert.equal(await summary.locator("dd").count(), 0);
      await shown(attention(page).getByRole("link", { name: "Review Call Slip", exact: true }));
      await shown(page.getByText("Guidance Office schedule for October", { exact: true }));
      state.summaryStatus = 200;
      await summary.getByRole("button", { name: "Retry", exact: true }).click();
      await shown(summary.locator("dd").first());
      assert.deepEqual(await summary.locator("dd").allTextContents(), ["2", "1", "1", "1"]);
      assert.deepEqual(await summary.locator("a").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href"))), ["/portal/appointments/my?status=UPCOMING", "/portal/routine-interviews", "/portal/good-moral", "/portal/call-slips?state=ACTIVE"]);
    });
  }
  {
    const state = homeWorld();
    await check("stale-actions-retain-confirmed-order-offer-retry-and-hide-after-denial", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
      state.actionsStatus = 500;
      await page.evaluate(() => window.dispatchEvent(new Event("focus")));
      await shown(attention(page).getByText("My actions could not be refreshed. Showing the last confirmed result.", { exact: true }));
      assert.deepEqual(await attention(page).locator("li h3").allTextContents(), ["Call Slip", "Routine Interview", "Guidance Messages", "Exit Interview", "Individual Inventory"]);
      await screenshot(page, "after-stale-actions");
      state.actionsStatus = 403;
      await attention(page).getByRole("button", { name: "Retry", exact: true }).click();
      await shown(attention(page).getByText("My actions could not be loaded", { exact: true }));
      await hidden(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
      assert.equal(await attention(page).getByText(/caught up/).count(), 0);
    });
  }
  {
    const state = homeWorld({ items: [] });
    await check("failed-empty-refresh-cannot-claim-the-student-is-currently-caught-up", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByText(/No current actions/));
      state.actionsStatus = 500;
      await page.evaluate(() => window.dispatchEvent(new Event("focus")));
      await shown(attention(page).getByText("Your last confirmed result had no actions.", { exact: true }));
      assert.equal(await attention(page).getByText(/caught up/).count(), 0);
      state.actionsStatus = 200; state.items = [homeAction("INVENTORY_START", "INCOMPLETE_SELF_SERVICE")];
      await attention(page).getByRole("button", { name: "Retry", exact: true }).click();
      await shown(attention(page).getByRole("link", { name: "Start Inventory", exact: true }));
    });
  }
  {
    const state = homeWorld();
    await check("announcements-retain-server-order-pins-links-and-preview-parameters", "/portal", state.options(), async (page, { requests }) => {
      const announcements = page.locator('section[aria-labelledby="overview-announcements-heading"]');
      await shown(announcements.getByText(state.announcements[2].title, { exact: true }));
      assert.deepEqual(await announcements.locator("li a").evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href"))), state.announcements.map((a) => `/announcements/${a.id}`));
      assert.equal(await announcements.getByText("Pinned", { exact: true }).count(), 1);
      assert.equal(await announcements.getByRole("link", { name: "All announcements", exact: true }).getAttribute("href"), "/announcements");
      const read = requests.find((r) => r.pathname === "/api/v1/announcements");
      assert.equal(new URLSearchParams(read.search).get("page_size"), "3");
      assert.equal(new URLSearchParams(read.search).get("page"), "1");
      assert.equal(new URLSearchParams(read.search).has("audience"), false, "Audience visibility remains backend-owned");
    });
  }
  {
    const state = homeWorld(); state.announcementsStatus = 500;
    await check("announcement-failure-retry-and-empty-do-not-disrupt-student-actions", "/portal", state.options(), async (page) => {
      const announcements = page.locator('section[aria-labelledby="overview-announcements-heading"]');
      await shown(announcements.getByText("Announcements could not be loaded.", { exact: true }));
      await shown(attention(page).getByRole("link", { name: "Review Call Slip", exact: true }));
      assert.equal(await announcements.getByText("No current announcements.", { exact: true }).count(), 0);
      state.announcementsStatus = 200; state.announcements = [];
      await announcements.getByRole("button", { name: "Retry", exact: true }).click();
      await shown(announcements.getByText("No current announcements.", { exact: true }));
    });
  }
  {
    const state = homeWorld();
    await check("account-switch-discards-private-action-presentation-and-rechecks-discovery", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
      state.account = { ...state.account, id: "synthetic-account-B", first_name: "Blair", capabilities: [] };
      state.items = []; state.summary.student = null;
      await page.clock.fastForward(31_000);
      await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
      await shown(page.getByRole("heading", { level: 1, name: "Good morning, Blair", exact: true }));
      await shown(attention(page).getByText(/No current actions/));
      await hidden(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
      assert.equal(await page.locator("#student-home-services-heading").count(), 0);
    });
  }
  {
    const state = homeWorld();
    await check("ended-session-removes-private-home-and-returns-to-sign-in", "/portal", state.options(), async (page) => {
      await shown(attention(page).getByRole("heading", { name: "Call Slip", exact: true }));
      state.actionsStatus = 401; state.sessionStatus = 401;
      await page.evaluate(() => window.dispatchEvent(new Event("focus")));
      await page.waitForURL(/\/login\?/);
      assert.equal(await attention(page).count(), 0);
      assert.equal(await page.locator("#student-home-services-heading").count(), 0);
    });
  }
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const state = homeWorld({ role, designations: role === "COUNSELOR" ? ["HEAD_GUIDANCE_COUNSELOR"] : role === "INSTITUTIONAL_OFFICER" ? ["DPO"] : [] });
    await check(`professional-home-${role}-preserves-queues-metrics-and-role-boundaries`, "/portal", state.options(), async (page, { requests }) => {
      await shown(page.getByText(state.announcements[0].title, { exact: true }));
      assert.equal(await page.locator("#student-home-services-heading").count(), 0);
      assert.equal(requests.filter((r) => r.pathname === "/api/v1/student-actions").length, 0);
      if (["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role)) {
        await shown(page.getByRole("link", { name: "View all work", exact: true }));
        if (role === "COUNSELOR") {
          await shown(page.locator("#counselor-work-heading"));
          await shown(page.locator('section[aria-labelledby="counselor-work-heading"]').getByText("Review Routine Interview", { exact: true }));
          assert.equal(await page.locator("#overview-attention-heading").count(), 0);
        } else if (role === "GUIDANCE_SERVICES_STAFF") {
          await shown(page.getByRole("heading", { name: "Guidance Services Home", exact: true }));
          await shown(page.locator("#gss-work-heading"));
          await shown(page.locator("#gss-operations-heading"));
          assert.equal(await page.getByText("Review Routine Interview", { exact: true }).count(), 0, "Counselor evaluation work stays out of GSS Home");
          assert.equal(await page.locator("#overview-attention-heading, #overview-summary-heading, #counselor-work-heading").count(), 0);
        } else {
          assert.equal(await page.locator("#counselor-work-heading").count(), 0);
        }
      } else if (role === "IT_ADMIN") {
        await shown(page.getByText("Email delivery", { exact: true }));
        await shown(page.getByText("2 failed", { exact: true }));
      } else {
        assert.equal(await page.locator("#overview-attention-heading, #overview-summary-heading").count(), 0);
      }
    });
  }
  {
    const state = homeWorld({ items: [homeAction("INVENTORY_START", "INCOMPLETE_SELF_SERVICE")] });
    await check("home-keyboard-order-focus-rings-and-native-navigation", "/portal", state.options({ viewport: { width: 390, height: 844 } }), async (page) => {
      await shown(attention(page).getByRole("link", { name: "Start Inventory", exact: true }));
      const main = page.locator("main");
      const links = main.locator("a");
      const count = await links.count();
      await main.focus();
      await page.keyboard.press("Tab");
      for (let i = 0; i < count; i++) {
        const link = links.nth(i);
        // WebKit's macOS default skips links with Tab. Check authored order and keyboard-focus
        // treatment directly there; Chromium exercises the full native Tab sequence.
        if (process.env.COMPASS_UI_BROWSER === "webkit") await link.focus();
        const focused = await link.evaluate((node) => ({ active: node === document.activeElement, tabIndex: node.tabIndex,
          ring: getComputedStyle(node).boxShadow !== "none" || getComputedStyle(node, "::after").boxShadow !== "none" }));
        assert.equal(focused.active, true, `Link ${i + 1} follows content order`);
        assert.ok(focused.tabIndex >= 0 && focused.ring, "Link has native focusability and a visible ring");
        if (i < count - 1 && process.env.COMPASS_UI_BROWSER !== "webkit") await page.keyboard.press("Tab");
      }
      await attention(page).getByRole("link", { name: "View all actions" }).focus();
      await page.keyboard.press("Enter");
      await shown(page.getByRole("heading", { name: "My actions", exact: true }));
    });
  }
}

await writeFile(join(artifacts, "geometry.json"), JSON.stringify(geometry, null, 2) + "\n");
await finish();
