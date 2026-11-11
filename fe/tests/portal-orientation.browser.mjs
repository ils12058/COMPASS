// The guide is exercised only with synthetic API fixtures; no live account or record is touched.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { navigationWorld, profiles } from "./support/f2-navigation-fixtures.mjs";
import { service, serviceId } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, finish, navigate, artifacts, settleFetches } = await createBrowserHarness("portal-orientation");
const guide = page => page.getByRole("dialog", { name: "Getting around COMPASS", exact: true });
const launch = async page => {
  await page.getByRole("button", { name: "Guide to getting around COMPASS", exact: true }).click();
  await shown(guide(page));
  await page.waitForFunction(() => document.activeElement?.matches("[data-orientation-next]"));
};
async function bounds(page) {
  await shown(page.locator('[data-guide-placed="true"]'));
  const metrics = await page.evaluate(() => {
    const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, height: r.height }; };
    return { panel: rect("[data-orientation-panel]"), target: rect("[data-orientation-highlight]"), width: innerWidth, height: innerHeight, documentWidth: document.documentElement.scrollWidth };
  });
  for (const [name, r] of [["panel", metrics.panel], ["highlight", metrics.target]]) {
    assert.ok(r.left >= -1 && r.top >= -1 && r.right <= metrics.width + 1 && r.bottom <= metrics.height + 1, `${name} fits: ${JSON.stringify(metrics)}`);
  }
  assert.ok(metrics.panel.top >= metrics.target.bottom || metrics.panel.bottom <= metrics.target.top, `Panel clears target: ${JSON.stringify(metrics)}`);
  assert.ok(metrics.documentWidth <= metrics.width + 1, "No page overflow");
}
async function complete(page) {
  for (let index = 1; index < 5; index++) {
    await guide(page).getByRole("button", { name: "Next", exact: true }).click();
    await shown(guide(page).getByText(`Step ${index + 1} of 5`, { exact: true }));
    await bounds(page);
  }
  await guide(page).getByRole("button", { name: "Finish guide", exact: true }).click();
  await hidden(guide(page));
}

await check("home-next-back-skip-completion-replay-and-no-extra-requests", "/portal", homeWorld().options(), async (page, fixture) => {
  await shown(page.getByRole("button", { name: "Guide to getting around COMPASS" }));
  assert.equal(await guide(page).count(), 0, "Manual launch only");
  await settleFetches(page);
  const prior = fixture.requests.length;
  await launch(page);
  await shown(guide(page).getByText(/Needs your attention shows/));
  await shown(guide(page).getByText(/shortcuts on this page/));
  assert.equal(await guide(page).getByRole("button", { name: "Back" }).isEnabled(), false);
  await guide(page).getByRole("button", { name: "Next" }).click();
  await shown(guide(page).getByRole("heading", { name: "Portal navigation", exact: true }));
  await guide(page).getByRole("button", { name: "Back" }).click();
  await shown(guide(page).getByText("Step 1 of 5", { exact: true }));
  await guide(page).getByRole("button", { name: "Skip guide" }).click();
  await hidden(guide(page));
  await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
  await launch(page);
  await page.screenshot({ path: join(artifacts, "desktop-orientation.png") });
  await complete(page);
  await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
  assert.equal(fixture.requests.length, prior, "Tour progression introduces no API requests");
  assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem("compass.portal-orientation"))), { version: 1, status: "completed" });
  await navigate(page, "/portal/account/help");
  await shown(page.getByRole("button", { name: "Replay guide", exact: true }));
  await shown(page.getByText("Completed in this browser."));
  await page.screenshot({ path: join(artifacts, "help-guides-replay.png") });
  await page.getByRole("button", { name: "Replay guide", exact: true }).click();
  await shown(guide(page));
  await page.waitForFunction(() => document.activeElement?.matches("[data-orientation-next]"));
  assert.equal(new URL(page.url()).pathname, "/portal");
  await page.keyboard.press("Escape");
  await hidden(guide(page));
  await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
  await navigate(page, "/portal/account/help");
  await shown(page.getByRole("button", { name: "Replay guide", exact: true }));
  await navigate(page, "/portal");
  assert.equal(await guide(page).count(), 0, "Returning Home does not restart a closed guide");
});

for (const collapsed of [false, true]) {
  await check(`keyboard-desktop-${collapsed ? "collapsed" : "expanded"}-navigation-state`, "/portal", homeWorld().options(), async page => {
    await shown(page.locator('[data-orientation="guide-launch"]'));
    if (collapsed) await page.getByRole("button", { name: "Collapse navigation", exact: true }).click();
    const dock = page.locator("[data-dock]");
    const original = await dock.getAttribute("data-dock");
    await page.locator('[data-orientation="guide-launch"]').focus();
    await page.keyboard.press("Enter");
    await shown(guide(page));
    await page.waitForFunction(() => document.activeElement?.matches("[data-orientation-next]"));
    await page.keyboard.press(process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab");
    assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Skip guide");
    const ring = await page.evaluate(() => getComputedStyle(document.activeElement).boxShadow);
    assert.notEqual(ring, "none", "Keyboard focus is visible");
    await page.keyboard.press(process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Shift+Tab" : "Shift+Tab");
    await page.keyboard.press("Enter");
    await shown(guide(page).getByText(/Collapse navigation gives/));
    await bounds(page);
    assert.equal(await dock.getAttribute("data-dock"), original, "Guide does not expand or collapse navigation");
    await page.keyboard.press("Escape");
    await hidden(guide(page));
    await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
    assert.equal(await dock.getAttribute("data-dock"), original);
  });
}

for (const [width, height, text] of [[390, 844, 100], [320, 640, 200], [320, 420, 200], [1280, 420, 200], [1024, 600, 200]]) {
  await check(`responsive-${width}-${height}-${text}`, "/portal", homeWorld().options({ viewport: { width, height } }), async page => {
    await shown(page.locator('[data-orientation="guide-launch"]'));
    await page.evaluate(scale => { document.documentElement.style.fontSize = `${scale}%`; }, text);
    await launch(page);
    await bounds(page);
    await guide(page).getByRole("button", { name: "Next", exact: true }).click();
    await shown(guide(page).getByText(width < 1024 ? /Open portal navigation opens/ : /Collapse navigation gives/));
    await bounds(page);
    assert.equal(await page.getByRole("dialog", { name: "Portal navigation", exact: true }).count(), 0, "Mobile drawer stays closed");
    if (width === 390) await page.screenshot({ path: join(artifacts, "mobile-orientation.png") });
    await guide(page).getByRole("button", { name: "Exit guide", exact: true }).click();
    await hidden(guide(page));
    await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
    if (width < 1024) {
      await page.getByRole("button", { name: "Open portal navigation", exact: true }).click();
      await shown(page.getByRole("dialog", { name: "Portal navigation", exact: true }));
      await page.keyboard.press("Escape");
      await hidden(page.getByRole("dialog", { name: "Portal navigation", exact: true }));
    }
  });
}

for (const [name, profile] of Object.entries(profiles)) {
  await check(`supported-profile-${name}`, "/portal", navigationWorld(profile).options(), async (page, fixture) => {
    await launch(page);
    const text = await guide(page).innerText();
    if (profile.role === "FACULTY") assert.doesNotMatch(text, /Needs your attention|My work/);
    if (profile.role === "GUIDANCE_OFFICE_ASSISTANT" || profile.role === "COUNSELOR") assert.match(text, /My work/);
    await complete(page);
    assert.equal(fixture.requests.some(request => request.method !== "GET"), false, "The guide executes no consequential action");
  });
}

for (const [name, raw] of [["malformed", "{"], ["old-version", '{"version":0,"status":"completed"}'], ["future-version", '{"version":999,"status":"completed"}'], ["completed", '{"version":1,"status":"completed"}'], ["blocked", null]]) {
  const script = name === "blocked"
    ? 'Object.defineProperty(window, "localStorage", { get() { throw new Error("Storage blocked"); } });'
    : `localStorage.setItem("compass.portal-orientation", ${JSON.stringify(raw)});`;
  await check(`help-start-replay-storage-${name}`, "/portal/account/help", homeWorld().options({ initScripts: [script] }), async page => {
    const action = page.getByRole("button", { name: name === "completed" ? "Replay guide" : "Start guide", exact: true });
    await shown(action);
    assert.equal(await guide(page).count(), 0);
    await page.screenshot({ path: join(artifacts, `help-guides-${name}.png`) });
    await action.click();
    await shown(guide(page));
    await page.waitForFunction(() => document.activeElement?.matches("[data-orientation-next]"));
    assert.equal(new URL(page.url()).pathname, "/portal");
    await complete(page);
    if (name !== "blocked") assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem("compass.portal-orientation"))), { version: 1, status: "completed" });
  });
}

await check("capabilities-missing-targets-and-live-resize", "/portal", homeWorld({ capabilities: [], items: [] }).options(), async page => {
  await shown(page.locator('[data-orientation="guide-launch"]'));
  const before = await page.locator("aside a").evaluateAll(links => links.map(link => link.getAttribute("href")));
  await page.locator('[data-orientation="search"]').evaluate(element => element.removeAttribute("data-orientation"));
  await launch(page);
  assert.doesNotMatch(await guide(page).innerText(), /shortcuts on this page/);
  await shown(guide(page).getByText("Step 1 of 4", { exact: true }));
  await guide(page).getByRole("button", { name: "Next" }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await shown(guide(page).getByText(/Open portal navigation opens/));
  await bounds(page);
  await page.locator('[data-orientation="mobile-navigation"]').evaluate(element => element.removeAttribute("data-orientation"));
  await shown(guide(page).getByText("Step 2 of 3", { exact: true }));
  await guide(page).getByRole("button", { name: "Skip guide" }).click();
  await hidden(guide(page));
  assert.deepEqual(await page.locator("aside a").evaluateAll(links => links.map(link => link.getAttribute("href"))), before);
});

for (const motionSource of ["system", "compass"]) {
await check(`reduced-motion-${motionSource}-and-other-dialog-priority`, "/portal", homeWorld().options(motionSource === "compass" ? {
  initScripts: ['localStorage.setItem("compass-accessibility-v1", JSON.stringify({ reduceMotion: true }));'],
} : {}), async page => {
  await page.emulateMedia({ reducedMotion: motionSource === "system" ? "reduce" : "no-preference" });
  await launch(page);
  await guide(page).getByRole("button", { name: "Next" }).click();
  await bounds(page);
  await page.keyboard.press("Escape");
  await hidden(guide(page));
  await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="guide-launch"]'));
  await launch(page);
  await page.getByRole("button", { name: "Go to a COMPASS feature", exact: true }).click();
  await hidden(guide(page));
  const palette = page.getByRole("dialog", { name: "Go to a COMPASS feature", exact: true });
  await shown(palette);
  await page.keyboard.press("Escape");
  await hidden(palette);
  await page.waitForFunction(() => document.activeElement?.matches('button[aria-label="Go to a COMPASS feature"]'));
  await launch(page);
  await page.getByRole("button", { name: /Open user menu for/ }).click();
  await hidden(guide(page));
  await shown(page.getByRole("menu"));
  await page.getByRole("menuitem", { name: "Help & guides", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Help & guides", exact: true }));
  await shown(page.getByRole("link", { name: "Help & guides", exact: true }));
});
}

await check("mobile-drawer-and-native-dialog-keep-priority", "/portal", homeWorld().options({ viewport: { width: 390, height: 844 } }), async page => {
  await shown(page.locator('[data-orientation="guide-launch"]'));
  await page.getByRole("button", { name: "Open portal navigation", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Portal navigation", exact: true });
  await shown(drawer);
  await page.locator('[data-orientation="guide-launch"]').evaluate(element => element.click());
  assert.equal(await guide(page).count(), 0, "Launch leaves an open drawer alone");
  await shown(drawer);
  await drawer.getByRole("button", { name: "Close navigation", exact: true }).click();
  await hidden(drawer);
  await page.waitForFunction(() => document.activeElement?.matches('[data-orientation="mobile-navigation"]'));
  await launch(page);
  await page.evaluate(() => {
    const dialog = document.createElement("dialog");
    dialog.innerHTML = '<button autofocus>Close synthetic prompt</button>';
    document.body.append(dialog); dialog.showModal();
  });
  await hidden(guide(page));
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Close synthetic prompt");
  await page.locator("dialog[open]").evaluate(element => { element.close(); element.remove(); });
  await launch(page);
  await guide(page).getByRole("button", { name: "Skip guide", exact: true }).click();
  await hidden(guide(page));
  assert.equal(await drawer.count(), 0, "Guide exit keeps the original drawer state");
});

await check("missing-all-targets-does-not-block-home", "/portal", homeWorld().options(), async page => {
  await shown(page.locator('[data-orientation="guide-launch"]'));
  await page.locator("[data-orientation]").evaluateAll(elements => elements.forEach(element => element.removeAttribute("data-orientation")));
  const action = page.getByRole("button", { name: "Guide to getting around COMPASS", exact: true });
  await action.click();
  await page.waitForFunction(() => document.activeElement?.textContent?.trim() === "Guide to getting around COMPASS");
  assert.equal(await guide(page).count(), 0);
  await shown(page.getByRole("heading", { level: 1 }));
});

await check("active-maintenance-keeps-orientation-unmounted", "/portal", {
  overrides: { "GET /api/v1/platform/status": { status: "maintenance_active", starts_at: "2026-11-11T00:00:00Z", ends_at: null, message: "Synthetic maintenance in progress." } },
}, async page => {
  await shown(page.getByText("Synthetic maintenance in progress."));
  assert.equal(await page.locator('[data-orientation="guide-launch"]').count(), 0);
  assert.equal(await guide(page).count(), 0);
});

await check("help-navigation-keeps-unsaved-changes", `/portal/services/${serviceId}/edit`, {
  overrides: { [`GET /api/v1/services/${serviceId}`]: ({ reply }) => reply(service) },
}, async page => {
  const name = page.getByLabel("Name", { exact: true });
  await shown(name);
  await name.fill("Synthetic unsaved service");
  await page.getByRole("button", { name: /Open user menu for/ }).click();
  const question = new Promise(resolve => page.once("dialog", async dialog => { const message = dialog.message(); await dialog.dismiss(); resolve(message); }));
  await page.getByRole("menuitem", { name: "Help & guides", exact: true }).click();
  assert.equal(await question, "Discard your unsaved Service changes?");
  assert.match(page.url(), /\/edit$/);
  assert.equal(await name.inputValue(), "Synthetic unsaved service");
  assert.equal(await guide(page).count(), 0);
});

await finish();
