// Real local Next UI, synthetic fixtures only. No guide selects a private record or writes data.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { guideWorld, referralId, opportunityId, exitId } from "./support/task-guide-fixtures.mjs";
import { navigationWorld, profiles } from "./support/f2-navigation-fixtures.mjs";
import { studentWorld, messagesAccount, sessionFor, threadIds } from "./support/guidance-messages-fixtures.mjs";
import { appointment, service } from "./support/ui-hierarchy-fixtures.mjs";
import { chooseAppointmentDate } from "./support/appointment-calendar.mjs";

const { check, shown, hidden, navigate, finish, artifacts, settleFetches } = await createBrowserHarness("task-guides");
const cases = [
  ["book-appointment", "Book an appointment", "/portal/appointments/book", 4],
  ["send-message", "Send a message", "/portal/messages", 4],
  ["my-appointments", "Manage my appointments", "/portal/appointments/my", 3],
  ["individual-inventory", "Complete Individual Inventory", "/portal/inventory/current", 4],
  ["good-moral", "Request Good Moral", "/portal/good-moral", 4],
  ["my-actions", "Use My actions", "/portal/actions", 3],
  ["exit-interview", "Complete Exit Interview", "/portal/exit-interviews", 4],
  ["graduate-tracer", "Complete Graduate Tracer", "/portal/graduate-tracer", 4],
  ["feedback", "Submit Feedback", "/portal/feedback", 4],
  ["faculty-submit", "Submit a Faculty Referral", "/portal/faculty/referrals/new", 4],
  ["faculty-track", "Track My Referrals", "/portal/faculty/referrals", 3],
];
const dialog = (page, title) => page.getByRole("dialog", { name: title, exact: true });
const launchControl = (page, id) => page.locator(`[data-guide-launch~="${id}"]`).filter({ visible: true }).first();
async function launch(page, id, title, keyboard = false) {
  const control = launchControl(page, id);
  await shown(control);
  const chooser = (await control.getAttribute("data-guide-launch")).split(" ").length > 1;
  if (keyboard) { await control.focus(); await page.keyboard.press("Enter"); } else await control.click();
  if (chooser) await page.getByRole("menuitem", { name: new RegExp(title) }).click();
  await shown(dialog(page, title));
  await page.waitForFunction(() => document.activeElement?.matches("[data-orientation-next]"));
}
async function bounds(page) {
  await shown(page.locator('[data-guide-placed="true"]'));
  const dimensions = await page.evaluate(() => {
    const panel = document.querySelector("[data-orientation-panel]").getBoundingClientRect();
    const target = document.querySelector("[data-orientation-highlight]")?.getBoundingClientRect();
    return { p: { left: panel.left, top: panel.top, right: panel.right, bottom: panel.bottom }, t: target ? { top: target.top, bottom: target.bottom, left: target.left, right: target.right } : null, width: innerWidth, height: innerHeight, doc: document.documentElement.scrollWidth };
  });
  const { p, width, height, doc } = dimensions;
  assert.ok(p.left >= -1 && p.top >= -1 && p.right <= width + 1 && p.bottom <= height + 1, JSON.stringify(dimensions));
  assert.ok(doc <= width + 1, "No horizontal overflow");
  if (dimensions.t) assert.ok(p.top >= dimensions.t.bottom - 1 || p.bottom <= dimensions.t.top + 1 || p.right <= dimensions.t.left + 1 || p.left >= dimensions.t.right - 1, `Panel clears target: ${JSON.stringify(dimensions)}`);
}
async function complete(page, title, count) {
  for (let step = 1; step < count; step++) {
    await dialog(page, title).getByRole("button", { name: "Next", exact: true }).click();
    await shown(dialog(page, title).getByText(`Step ${step + 1} of ${count}`, { exact: true }));
    await bounds(page);
  }
  await dialog(page, title).getByRole("button", { name: "Finish guide", exact: true }).click();
  await hidden(dialog(page, title));
}

for (const [id, title, path, count] of cases) {
  const f = guideWorld(id);
  await check(`${id}-page-controls-replay-and-no-guide-requests`, path, f.options, async (page, observed) => {
    await shown(launchControl(page, id));
    await settleFetches(page);
    const before = observed.requests.length;
    const values = await page.locator("input,textarea,select").evaluateAll(elements => elements.map(element => element.value));
    await page.emulateMedia({ reducedMotion: "reduce" });
    await launch(page, id, title, true);
    await bounds(page);
    await page.screenshot({ path: join(artifacts, `${id}.png`) });
    await dialog(page, title).getByRole("button", { name: "Next", exact: true }).click();
    await dialog(page, title).getByRole("button", { name: "Back", exact: true }).click();
    await shown(dialog(page, title).getByText(`Step 1 of ${count}`, { exact: true }));
    await page.keyboard.press("Escape");
    await hidden(dialog(page, title));
    await page.waitForFunction(() => document.activeElement?.matches("[data-guide-launch]"));
    await launch(page, id, title);
    await complete(page, title, count);
    assert.deepEqual(await page.evaluate(id => JSON.parse(localStorage.getItem(`compass.task-guide.${id}`)), id), { version: 1, status: "completed" });
    assert.equal(await page.evaluate(() => localStorage.getItem("compass.portal-orientation")), null);
    assert.deepEqual(await page.locator("input,textarea,select").evaluateAll(elements => elements.map(element => element.value)), values);
    assert.equal(observed.requests.length, before, "Progression introduces no API requests");
    await launch(page, id, title);
    await dialog(page, title).getByRole("button", { name: "Skip guide", exact: true }).click();
    await hidden(dialog(page, title));
    assert.equal(await page.evaluate(id => JSON.parse(localStorage.getItem(`compass.task-guide.${id}`)).status, id), "completed");
    await navigate(page, "/portal/account/help");
    await shown(page.locator(`[data-guide-catalog="${id}"]`).getByText("Replay", { exact: true }));
    await page.locator(`[data-guide-catalog="${id}"]`).click();
    await shown(dialog(page, title));
    await page.keyboard.press("Escape");
  });
}

for (const [id, mode] of [["book-appointment", "empty"], ["my-appointments", "empty"], ["my-actions", "empty"], ["individual-inventory", "empty"], ["individual-inventory", "completed"], ["individual-inventory", "read-only"], ["exit-interview", "ineligible"], ["graduate-tracer", "empty"], ["graduate-tracer", "completed"], ["graduate-tracer", "read-only"], ["feedback", "empty"], ["feedback", "completed"], ["faculty-submit", "ineligible"], ["faculty-track", "empty"]]) {
  const [, title, path, count] = cases.find(row => row[0] === id);
  await check(`${id}-${mode}-finishable`, path, guideWorld(id, mode).options, async page => {
    await launch(page, id, title);
    await complete(page, title, count);
  });
}

for (const [width, height, textSize] of [[390, 844, 100], [320, 640, 200], [1280, 420, 200]]) {
  await check(`narrow-short-enlarged-${width}-${textSize}`, "/portal/faculty/referrals/new", { ...guideWorld("faculty-submit").options, viewport: { width, height } }, async page => {
    await page.evaluate(scale => { document.documentElement.style.fontSize = `${scale}%`; }, textSize);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByLabel("Referral reason", { exact: true }).fill("Synthetic unsaved draft");
    await launch(page, "faculty-submit", "Submit a Faculty Referral", true);
    await complete(page, "Submit a Faculty Referral", 4);
    assert.equal(await page.getByLabel("Referral reason", { exact: true }).inputValue(), "Synthetic unsaved draft");
  });
}

for (const [id, title, path, count] of cases) for (const [width, height, scale] of [[390, 700, 100], [1280, 480, 200]]) {
  await check(`${id}-layout-${width}-${scale}`, path, { ...guideWorld(id).options, viewport: { width, height } }, async page => {
    await page.evaluate(value => { document.documentElement.style.fontSize = `${value}%`; }, scale);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await launch(page, id, title);
    await bounds(page);
    await complete(page, title, count);
  });
}
for (const [id, title, path, count, mode] of [
  ["good-moral", "Request Good Moral", "/portal/good-moral/request", 4, "available"],
  ["feedback", "Submit Feedback", `/portal/feedback/customer-feedback?opportunity=${opportunityId}`, 4, "available"],
  ["feedback", "Submit Feedback", `/portal/feedback/csm?opportunity=${opportunityId}`, 4, "available"],
  ["exit-interview", "Complete Exit Interview", `/portal/exit-interviews/${exitId}`, 4, "form"],
  ["faculty-track", "Track My Referrals", `/portal/faculty/referrals/${referralId}`, 3, "available"],
]) await check(`${id}-detail-form-${mode}-${path.split("/").at(-1)}`, path, guideWorld(id, mode).options, async (page, observed) => {
  await shown(launchControl(page, id));
  await settleFetches(page);
  const before = observed.requests.filter(request => request.method !== "GET").length;
  await launch(page, id, title);
  await complete(page, title, count);
  assert.equal(observed.requests.filter(request => request.method !== "GET").length, before);
});
await check("route-change-dismissal", "/portal/actions", guideWorld("my-actions").options, async page => {
  await launch(page, "my-actions", "Use My actions");
  // An existing navigation link invalidates the guide, with no task action executed.
  await page.getByRole("link", { name: "Home", exact: true }).click();
  await hidden(dialog(page, "Use My actions"));
});

for (const [path, readonly] of [["/portal/messages/new", false], [`/portal/messages/${threadIds.office}`, false], [`/portal/messages/${threadIds.resolved}`, true]]) {
  const backend = studentWorld();
  // Opening history owns read state; seed it read so this check isolates guide activity.
  for (const [id, messages] of backend.state.messages) backend.state.reads.set(id, messages.length);
  const account = messagesAccount("STUDENT");
  const handler = async args => {
    if (args.pathname === "/api/v1/auth/session") { await args.reply(sessionFor(account)); return true; }
    if (args.method !== "GET") { await args.reply({ error: { code: "synthetic_write_blocked" } }, 405); return true; }
    return backend.handler(args);
  };
  await check(`message-layout-${path.split("/").at(-1)}-retains-draft`, path, { handler, viewport: { width: 390, height: 500 } }, async (page, observed) => {
    await shown(launchControl(page, "send-message"));
    const composer = page.getByPlaceholder("Write a message…", { exact: true });
    if (!readonly) {
      if (path.endsWith("new")) await page.getByRole("radio", { name: /Guidance Office/ }).check();
      await shown(composer);
      await composer.fill("Synthetic retained message draft");
    }
    await settleFetches(page);
    const writes = observed.requests.filter(request => request.method !== "GET").length;
    await launch(page, "send-message", "Send a message", true);
    await complete(page, "Send a message", 4);
    if (!readonly) assert.equal(await composer.inputValue(), "Synthetic retained message draft");
    assert.equal(observed.requests.filter(request => request.method !== "GET").length, writes, "No send, typing, or read request from the guide");
  });
}

for (const emptySlots of [false, true]) {
  const f = guideWorld("book-appointment");
  const handler = async args => {
    if (args.pathname === "/api/v1/appointments/booking/services") { await args.reply({ items: [{ ...service, requires_current_inventory: true }] }); return true; }
    if (args.pathname === "/api/v1/appointments/booking/counselors") { await args.reply({ items: [{ ...appointment.provider, is_default: true }] }); return true; }
    if (args.pathname === "/api/v1/appointments/booking/slots") {
      const date = args.url.searchParams.get("date");
      await args.reply({ timezone: "Asia/Manila", duration_minutes: 60, items: emptySlots ? [] : [{ starts_at: `${date}T02:00:00Z`, ends_at: `${date}T03:00:00Z` }] }); return true;
    }
    return f.handler(args);
  };
  await check(`booking-${emptySlots ? "no-slots" : "review-prerequisite"}-retains-choices`, "/portal/appointments/book", { handler }, async (page, observed) => {
    await page.getByRole("button", { name: /^Counseling/ }).click();
    await page.getByRole("radio", { name: "In person", exact: true }).check();
    await shown(page.getByRole("group", { name: "Appointment date", exact: true }));
    await chooseAppointmentDate(page, "2027-01-05");
    if (!emptySlots) {
      await page.getByRole("group", { name: "Available Appointment times" }).getByRole("button").first().click();
      await shown(page.getByRole("button", { name: "Book Appointment", exact: true }));
      assert.equal(await page.getByRole("button", { name: "Book Appointment", exact: true }).isEnabled(), false);
    }
    await settleFetches(page);
    const before = observed.requests.length;
    const values = await page.locator("input,textarea,select").evaluateAll(elements => elements.map(element => ({ value: element.value, checked: element.checked })));
    await launch(page, "book-appointment", "Book an appointment");
    await complete(page, "Book an appointment", 4);
    assert.deepEqual(await page.locator("input,textarea,select").evaluateAll(elements => elements.map(element => ({ value: element.value, checked: element.checked }))), values);
    assert.equal(observed.requests.length, before);
  });
}

await check("my-appointments-calendar-target", "/portal/appointments/my", guideWorld("my-appointments").options, async page => {
  await page.getByRole("button", { name: "Calendar", exact: true }).click();
  await shown(page.locator('[data-guide-target="appointments-list"]').filter({ visible: true }));
  await launch(page, "my-appointments", "Manage my appointments");
  await complete(page, "Manage my appointments", 3);
});

for (const unavailable of [false, true]) {
  const id = "a3000000-0000-4000-8000-000000000001";
  const f = guideWorld("my-appointments");
  const handler = async args => {
    if (args.pathname === `/api/v1/appointments/${id}`) { await args.reply({ ...appointment, id, actions: unavailable ? Object.fromEntries(Object.keys(appointment.actions).map(name => [name, { allowed: false, blocker: "NOT_AVAILABLE", consequences: [] }])) : appointment.actions }); return true; }
    if (args.pathname.startsWith(`/api/v1/appointments/${id}/`)) { await args.reply({ items: [] }); return true; }
    return f.handler(args);
  };
  await check(`appointment-detail-actions-${unavailable ? "unavailable" : "available"}`, `/portal/appointments/${id}`, { handler }, async (page, observed) => {
    await launch(page, "my-appointments", "Manage my appointments");
    await complete(page, "Manage my appointments", 3);
    assert.equal(observed.requests.some(request => request.method !== "GET"), false);
  });
}

for (const change of ["session", "access"]) {
  const f = guideWorld("my-actions");
  let replace = false;
  const handler = async args => {
    if (args.pathname === "/api/v1/auth/session") {
      const session = sessionFor(replace && change === "access" ? { ...f.world.account, capabilities: [] } : f.world.account);
      session.session.id = replace && change === "session" ? "synthetic-replacement-session" : "synthetic-original-session";
      session.session.expires_at = replace ? "2099-01-01T00:00:00Z" : new Date(Date.now() + 6000).toISOString();
      await args.reply(session); return true;
    }
    return f.handler(args);
  };
  await check(`${change}-change-dismissal`, "/portal/actions", { handler }, async page => {
    await launch(page, "my-actions", "Use My actions");
    replace = true; // The existing session boundary revalidates; no guide-owned fetch.
    await hidden(dialog(page, "Use My actions"));
    assert.equal(await page.locator('[data-orientation-panel]').count(), 0);
  });
}

await check("task-guide-blocked-storage-and-compass-motion", "/portal/actions", { ...guideWorld("my-actions").options, initScripts: ['localStorage.setItem("compass-accessibility-v1", JSON.stringify({reduceMotion:true})); Object.defineProperty(window,"localStorage",{get(){throw new Error("Blocked");}});'] }, async page => {
  await launch(page, "my-actions", "Use My actions", true);
  await complete(page, "Use My actions", 3);
  await launch(page, "my-actions", "Use My actions");
  await page.keyboard.press("Escape");
  await hidden(dialog(page, "Use My actions"));
});

await check("missing-targets-storage-version-and-independent-completion", "/portal/actions", { ...guideWorld("my-actions").options, initScripts: ['if (!sessionStorage.getItem("task-guide-fixture-seeded")) { sessionStorage.setItem("task-guide-fixture-seeded", "1"); localStorage.setItem("compass.task-guide.my-actions", "{broken"); localStorage.setItem("compass.task-guide.good-moral", JSON.stringify({version:0,status:"completed"})); localStorage.setItem("compass.portal-orientation", JSON.stringify({version:1,status:"completed"})); }'] }, async page => {
  await shown(launchControl(page, "my-actions"));
  await page.locator("[data-guide-target]").evaluateAll(elements => elements.forEach(element => element.removeAttribute("data-guide-target")));
  await launch(page, "my-actions", "Use My actions");
  await complete(page, "Use My actions", 3);
  await navigate(page, "/portal/account/help");
  await shown(page.locator('[data-guide-catalog="my-actions"]').getByText("Replay"));
  await shown(page.locator('[data-guide-catalog="good-moral"]').getByText("Start"));
  await shown(page.getByRole("button", { name: "Replay guide", exact: true }));
});

for (const profileName of ["Student", "Alumni", "Faculty", "Counselor", "IT Admin"]) {
  const profile = profiles[profileName];
  if (!profile) continue;
  await check(`catalog-access-${profileName}`, "/portal/account/help", navigationWorld(profile).options(), async page => {
    await shown(page.getByRole("heading", { name: "Help & guides", exact: true }));
    const ids = await page.locator("[data-guide-catalog]").evaluateAll(elements => elements.map(element => element.dataset.guideCatalog));
    if (profileName === "Faculty") assert.deepEqual(ids.sort(), ["faculty-submit", "faculty-track", "send-message"].sort());
    if (profileName === "IT Admin") assert.deepEqual(ids, []);
    if (profileName === "Student") assert.ok(!ids.includes("graduate-tracer") && !ids.includes("faculty-submit"));
    if (profileName === "Alumni") assert.ok(ids.includes("graduate-tracer") && !ids.includes("book-appointment"));
  });
}
for (const width of [1440, 390]) await check(`catalog-screenshot-${width}`, "/portal/account/help", { ...guideWorld("book-appointment").options, viewport: { width, height: 1000 } }, async page => {
  await shown(page.getByRole("heading", { name: "Help & guides", exact: true }));
  await page.screenshot({ path: join(artifacts, `catalog-${width}.png`), fullPage: true });
});

await check("catalog-navigation-guard-and-competing-dialog", "/portal/faculty/referrals/new", guideWorld("faculty-submit").options, async page => {
  await page.getByLabel("Referral reason", { exact: true }).fill("Synthetic retained draft");
  // Opening Help itself uses the existing navigation guard; reject it and keep the draft.
  page.once("dialog", modal => modal.dismiss());
  await page.getByRole("button", { name: /Open user menu/ }).click();
  await page.getByRole("menuitem", { name: "Help & guides", exact: true }).click();
  assert.equal(new URL(page.url()).pathname, "/portal/faculty/referrals/new");
  assert.equal(await page.getByLabel("Referral reason", { exact: true }).inputValue(), "Synthetic retained draft");
  await launch(page, "faculty-submit", "Submit a Faculty Referral");
  await page.getByRole("button", { name: /Open user menu/ }).click();
  await hidden(dialog(page, "Submit a Faculty Referral"));
  await page.keyboard.press("Escape");
});

await finish();
