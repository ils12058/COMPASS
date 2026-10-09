// UX-001–008: existing COMPASS routes, synthetic APIs, local Next server, both browser engines.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { worlds, auth, account, empty, longEmail } from "./support/ux-hardening-fixtures.mjs";
import { service, serviceId, user } from "./support/ui-hierarchy-fixtures.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, finish, shown, noHorizontalOverflow, artifacts } = await createBrowserHarness(`ux-hardening-${engine}`);
const measurements = [];
const viewport = (width) => ({ width, height: 900 });
async function measure(page, name) {
  await noHorizontalOverflow(page);
  measurements.push({ name, ...await page.evaluate(() => {
    const table = [...document.querySelectorAll("table")].find((element) => element.offsetWidth > 0);
    return { client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
      tableWidth: table?.scrollWidth, tableClient: table?.parentElement.clientWidth,
      stickyWidth: table?.querySelector("tbody th")?.getBoundingClientRect().width };
  }) });
}
for (const width of [320, 375, 390, 393, 430, 768, 1440]) {
  for (const [name, path] of [["inventory", "/portal/inventory"], ["exit-responses", "/portal/exit-interviews"], ["resources", "/portal/resources"], ["accounts-unaffected", "/portal/accounts"]]) {
    await check(`containment-${name}-${width}`, path, { viewport: viewport(width), overrides: worlds }, async (page) => {
      const table = page.locator("table:visible"); await shown(table);
      await measure(page, `${name}-${width}`);
      const scroller = table.locator("..");
      if (width <= 430) assert.equal(await scroller.evaluate((e) => e.scrollWidth > e.clientWidth), true, "Table retains local scrolling");
      const first = table.locator("tbody th").first(); const start = await first.boundingBox();
      await scroller.evaluate((e) => { e.scrollLeft = e.scrollWidth; });
      assert.ok(Math.abs(start.x - (await first.boundingBox()).x) <= 1, "Identity remains sticky");
      await measure(page, `${name}-${width}-end`);
      if (name !== "accounts-unaffected") assert.equal(await table.locator("thead button .sr-only").evaluateAll((es) => es.every((e) => e.offsetParent === e.parentElement)), true, "Sort descriptions are locally contained");
      const filters = page.getByRole("button", { name: /^Filters/ });
      await filters.click();
      await shown(page.getByRole("dialog", { name: "Filters", exact: true }));
      await page.keyboard.press("Escape");
      if (width === 393) {
        if (name === "inventory") await page.screenshot({ path: join(artifacts, "inventory-393-end.png"), fullPage: true });
        const button = table.locator("thead button").last();
        await button.click();
        await shown(table.locator('th[aria-sort="descending"]'));
        await measure(page, `${name}-${width}-sorted`);
      }
    });
  }
}
for (const width of [393, 1440]) {
  for (const [name, path, overrides] of [
    ["header-email", "/portal/exit-interviews", {}],
    ["announcement-title", "/portal/announcements/long", {}],
    ["service-name-code", `/portal/services/${serviceId}`, { [`/api/v1/services/${serviceId}`]: { ...service, name: "S".repeat(120), code: "C".repeat(64) } }],
    ["service-list", "/portal/services", { "/api/v1/services": { ...empty, items: [{ ...service, name: "S".repeat(120), code: "C".repeat(64) }] } }],
    ["referral-url", "/portal/referrals/long", {}],
  ]) {
    await check(`accepted-${name}-${width}`, path, { viewport: viewport(width), overrides: { ...worlds, ...overrides } }, async (page) => {
      await shown(page.getByRole("heading", { level: 1 }).first());
      if (name === "header-email") {
        // Replace only the text of the real rendered PageHeader description.
        await page.locator("h1").locator("..").locator("..").locator("p").first().evaluate((element, text) => { element.textContent = text; }, longEmail);
        await shown(page.getByText(longEmail, { exact: true }));
      } else {
        await shown(page.getByText(name === "announcement-title" ? "A".repeat(120) : name === "referral-url" ? worlds["/api/v1/referrals/long"].reason : "S".repeat(120), { exact: true }).first());
      }
      await measure(page, `${name}-${width}`);
      if (name === "referral-url" && width === 393) await page.screenshot({ path: join(artifacts, "referral-long-url-393.png"), fullPage: true });
    });
  }
}
for (const [name, identity] of [["normal", { ...account, email: "maria@example.test" }], ["long-email", account], ["long-id", { ...account, full_name: "N".repeat(120), institutional_id: "I".repeat(50) }]]) {
  await check(`sticky-account-${name}`, "/portal/accounts", { viewport: viewport(393), overrides: { ...worlds, "/api/v1/accounts": { ...empty, items: [identity], ordering: "NAME_ASC" } } }, async (page) => {
    const table = page.locator("table:visible"); await shown(table); const scroller = table.locator(".."); const sticky = table.locator("tbody th");
    assert.equal(await sticky.innerText(), `${identity.full_name}\n${identity.institutional_id} · ${identity.email}`);
    assert.ok((await sticky.boundingBox()).width < (await scroller.boundingBox()).width - 80, "Sticky identity leaves space for later columns");
    if (name === "long-email") await page.screenshot({ path: join(artifacts, "accounts-long-identity-393.png"), fullPage: true });
    // Later Accounts cells contain text. A synthetic control tests keyboard and pointer
    // reachability in the final cell without changing the product's keyboard model (UX-012).
    await table.locator("tbody td").last().evaluate((cell) => { const input = document.createElement("input"); input.setAttribute("aria-label", "Verification target"); input.style.width = "6rem"; cell.append(input); });
    await scroller.evaluate((e) => { e.scrollLeft = e.scrollWidth; });
    const target = page.getByRole("textbox", { name: "Verification target" });
    assert.equal(await target.evaluate((e) => { const r = e.getBoundingClientRect(); return e.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)); }), true);
    await table.locator("tbody th a").focus(); await page.keyboard.press("Tab");
    assert.equal(await target.evaluate((e) => e === document.activeElement), true, "Keyboard reaches the later-column target");
    await measure(page, `sticky-${name}`);
  });
}
await check("accounts-explicit-search", "/portal/accounts?search=Old&role=STUDENT&page=3&ordering=NAME_DESC", { overrides: worlds }, async (page, { requests }) => {
  const input = page.getByLabel("Search accounts", { exact: true }); await shown(page.locator("table:visible"));
  const original = await input.elementHandle(); const initialURL = page.url(); const reads = () => requests.filter((r) => r.pathname === "/api/v1/accounts"); const initialReads = reads().length;
  await input.fill(""); await input.pressSequentially("  Maria  ", { delay: 15 }); await page.waitForTimeout(600);
  assert.equal(page.url(), initialURL); assert.equal(reads().length, initialReads, "Drafting never fetches");
  assert.equal(await original.evaluate((e) => e.isConnected && e === document.activeElement), true);
  assert.equal(await input.evaluate((e) => e.selectionStart), 9);
  await input.press("Enter"); await page.waitForURL((u) => u.searchParams.get("search") === "Maria");
  await shown(page.locator("table:visible"));
  assert.ok(reads().some((r) => new URLSearchParams(r.search).get("search") === "Maria"), "Server query receives the applied term");
  assert.equal(new URL(page.url()).searchParams.has("page"), false); assert.equal(new URL(page.url()).searchParams.get("role"), "STUDENT"); assert.equal(new URL(page.url()).searchParams.get("ordering"), "NAME_DESC");
  assert.equal(await original.evaluate((e) => e.isConnected && e === document.activeElement), true);
  await input.fill("Ana"); await page.getByRole("button", { name: "Search", exact: true }).click(); await page.waitForURL((u) => u.searchParams.get("search") === "Ana");
  await page.goBack(); await page.waitForURL((u) => u.searchParams.get("search") === "Maria"); assert.equal(await input.inputValue(), "Maria");
  await page.goForward(); await page.waitForURL((u) => u.searchParams.get("search") === "Ana"); assert.equal(await input.inputValue(), "Ana");
  await page.reload(); assert.equal(await input.inputValue(), "Ana");
  await page.getByRole("button", { name: /^Filters/ }).click(); await page.getByRole("button", { name: "Clear filters", exact: true }).click();
  await page.waitForURL((u) => !u.searchParams.has("search") && !u.searchParams.has("role")); assert.equal(await input.inputValue(), ""); assert.equal(new URL(page.url()).searchParams.get("ordering"), "NAME_DESC");
  await page.keyboard.press("Escape"); await input.fill("Draft remains local"); await page.getByRole("button", { name: "Next", exact: true }).click(); await page.waitForURL((u) => u.searchParams.get("page") === "2");
  assert.equal(new URL(page.url()).searchParams.has("search"), false); assert.equal(await input.inputValue(), "Draft remains local");
});
async function holdSearch(page, path, term) {
  let release; let issued; const pending = new Promise((r) => { release = r; }); const started = new Promise((r) => { issued = r; });
  await page.route(`**${path}?*`, async (route) => {
    if (new URL(route.request().url()).searchParams.get("search") === term) {
      // Finish server work before holding the acknowledgement. Releasing then commits the old
      // navigation before a new 350ms debounce can mask the race by issuing its next request.
      const response = await route.fetch();
      issued();
      await pending;
      await route.fulfill({ response });
    } else await route.continue();
  });
  return { release, started };
}
await check("accounts-older-submit-keeps-new-draft", "/portal/accounts", { overrides: worlds }, async (page) => {
  const input = page.getByLabel("Search accounts", { exact: true }); const hold = await holdSearch(page, "/portal/accounts", "Mar");
  try { await input.fill("Mar"); await input.press("Enter"); await hold.started; await input.fill("Maria"); hold.release(); await page.waitForURL((u) => u.searchParams.get("search") === "Mar"); assert.equal(await input.inputValue(), "Maria"); await page.waitForTimeout(600); assert.equal(new URL(page.url()).searchParams.get("search"), "Mar"); } finally { hold.release(); }
});
for (const [name, path, label] of [["services", "/portal/services", "Search Services"], ["affiliations", "/portal/organization/student-affiliations", "Search student affiliations"]]) {
  for (const inFlight of [false, true]) {
    await check(`clear-${name}-${inFlight ? "in-flight" : "timer"}`, `${path}?search=Old`, { overrides: worlds }, async (page) => {
      const input = page.getByLabel(label, { exact: true }); const hold = inFlight ? await holdSearch(page, path, "New") : null;
      try { await input.fill("New"); if (hold) await hold.started; await page.getByRole("button", { name: /^Filters/ }).click(); await page.getByRole("button", { name: "Clear filters", exact: true }).click(); hold?.release(); await page.waitForURL((u) => !u.searchParams.has("search")); await page.waitForTimeout(650); assert.equal(new URL(page.url()).searchParams.has("search"), false); assert.equal(await input.inputValue(), ""); } finally { hold?.release(); }
    });
  }
}
for (const [name, path, label] of [["availability", "/portal/availability/providers", "Search Counselors"], ["services", "/portal/services", "Search Services"], ["affiliations", "/portal/organization/student-affiliations", "Search student affiliations"]]) {
  await check(`newest-intent-${name}`, path, { overrides: worlds }, async (page) => {
    const input = page.getByLabel(label, { exact: true }); const original = await input.elementHandle(); const hold = await holdSearch(page, path, "Mar");
    try {
      await input.fill("Mar"); await hold.started; await input.fill("Maria"); hold.release(); await page.waitForURL((u) => u.searchParams.get("search") === "Mar"); assert.equal(await input.inputValue(), "Maria"); await page.waitForURL((u) => u.searchParams.get("search") === "Maria"); assert.equal(await original.evaluate((e) => e.isConnected && e === document.activeElement), true);
      await input.fill(""); await page.waitForURL((u) => !u.searchParams.has("search")); assert.equal(await input.inputValue(), "");
      await page.evaluate((path) => window.history.pushState(null, "", `${path}?search=Historical`), path); await page.waitForURL((u) => u.searchParams.get("search") === "Historical");
      await input.fill("Uncommitted"); await page.goBack(); assert.equal(await input.inputValue(), ""); await page.goForward(); assert.equal(await input.inputValue(), "Historical");
    } finally { hold.release(); }
  });
}
for (const width of [320, 393, 1440]) {
  await check(`exit-siblings-${width}`, "/portal/exit-interviews", { viewport: viewport(width), overrides: worlds }, async (page) => {
    const nav = page.getByRole("navigation", { name: "Exit Interview navigation", exact: true }); assert.equal(await nav.getByRole("link", { name: "Responses", exact: true }).getAttribute("aria-current"), "page"); assert.equal(await nav.getByRole("link", { name: "Student access", exact: true }).getAttribute("aria-current"), null); assert.equal(await nav.getByRole("tab").count(), 0);
    await nav.getByRole("link", { name: "Student access", exact: true }).click(); await shown(page.getByText("No Exit Interview access records have been opened.", { exact: true })); assert.equal(await nav.getByRole("link", { name: "Student access", exact: true }).getAttribute("aria-current"), "page"); await shown(page.getByRole("button", { name: "Open Exit Interview access", exact: true }));
    await page.getByRole("searchbox").fill("Missing"); await page.getByRole("button", { name: "Search", exact: true }).click(); await shown(page.getByText("No Exit Interview access records match the current search or filters.", { exact: true })); await measure(page, `exit-siblings-${width}`); assert.equal(await page.getByText(/opportunit|review queue/i).count(), 0);
  });
}
for (const [name, capabilities, visible] of [["responses-only", ["exit_interviews.view"], false], ["access-only", ["exit_interviews.manage_opportunities"], true], ["neither", [], false]]) {
  await check(`exit-capability-${name}`, "/portal/exit-interviews", { overrides: { ...worlds, "/api/v1/auth/session": { ...auth["/api/v1/auth/session"], user: { ...user(), capabilities } } } }, async (page) => {
    await shown(page.getByRole("heading", { level: 1 }).first()); assert.equal(await page.getByRole("navigation", { name: "Exit Interview navigation", exact: true }).count(), 0); assert.equal(await page.getByRole("button", { name: "Open Exit Interview access", exact: true }).count(), visible ? 1 : 0);
  });
}
await writeFile(join(artifacts, "measurements.json"), `${JSON.stringify({ engine, measurements }, null, 2)}\n`);
await finish();
