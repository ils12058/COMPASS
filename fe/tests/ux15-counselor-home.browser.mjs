// Synthetic Counselor and Head Home journeys. Every API is intercepted; no institutional records are read.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import {
  counselorAppointment,
  counselorDate,
  counselorWorld,
  workItem,
} from "./support/ux15-counselor-home-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("ux15-counselor-home");
const agenda = (page) => page.locator('section[aria-labelledby="counselor-agenda-heading"]');
const work = (page) => page.locator('section[aria-labelledby="counselor-work-heading"]');
const appointmentsToday = [
  counselorAppointment(1, { hour: 10, studentName: "AlexandriaMariaCatherineJohnsonWilliams" }),
  counselorAppointment(2, { hour: 11 }),
  counselorAppointment(3, { hour: 12, status: "CANCELLED" }),
  counselorAppointment(4, { hour: 13, startsAt: "2026-10-23T09:00:00+08:00", endsAt: "2026-10-23T10:00:00+08:00" }),
].map((item, index) => index === 0 ? { ...item, private_purpose: "Synthetic confidential counseling narrative" } : item);
const canonicalWork = [
  workItem("GUIDANCE_FOLLOW_UP", 1, "ACTION_REQUIRED", { due_at: "2026-10-23T09:00:00+08:00" }),
  workItem("ROUTINE_EVALUATION", 2, "TIME_SENSITIVE", { due_at: "2026-10-22T08:30:00+08:00" }),
  workItem("GUIDANCE_MESSAGE_REPLY", 3),
  workItem("GOOD_MORAL_ISSUANCE", 4),
  workItem("CALL_SLIP_DUE", 5),
  workItem("GUIDANCE_FOLLOW_UP", 6),
];
const responsiveMeasurements = [];

await check("desktop-agenda-and-canonical-work", "/portal", counselorWorld({ appointments: appointmentsToday, work: canonicalWork }).options(), async (page, { requests }) => {
  await shown(agenda(page).getByRole("heading", { name: "Today's appointments", exact: true }));
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  await shown(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
  assert.deepEqual(await work(page).locator("h3").allTextContents(), [
    "Review Guidance follow-up",
    "Review Routine Interview",
    "Reply to Guidance Message",
    "Issue Good Moral certificate",
    "Review Call Slip",
  ]);
  assert.equal(await agenda(page).locator("li").count(), 2, "Cancelled and next-day appointments are excluded by the source filters");
  assert.match(await agenda(page).innerText(), /10:00/);
  assert.match(await agenda(page).innerText(), /11:00/);
  assert.equal(await agenda(page).getByText("Synthetic confidential counseling narrative", { exact: true }).count(), 0, "Private purpose fields are not presented");
  assert.equal(await page.getByText("Synthetic confidential counseling narrative", { exact: true }).count(), 0, "Private purpose fields are not in Home's accessible text");
  const firstAgendaHref = await agenda(page).locator("li a").first().getAttribute("href");
  assert.equal(firstAgendaHref, "/portal/appointments/c0000000-0000-4000-8000-000000000501", `Agenda opens the matching self Appointment record (actual: ${firstAgendaHref})`);
  assert.equal(await agenda(page).locator("li").filter({ hasText: "Counseling service" }).count(), 2, "Only the authorized service label is shown for each self Appointment");
  assert.equal(await work(page).getByText("Showing the first 5 items. More work is available in the full queue.", { exact: true }).count(), 1, "Work preview announces the available next page");

  const appointmentRead = requests.find((request) => request.pathname === "/api/v1/appointments/me");
  assert.ok(appointmentRead, "Home uses the self Appointment endpoint");
  const appointmentQuery = new URLSearchParams(appointmentRead.search);
  assert.equal(appointmentQuery.get("status"), "SCHEDULED", "Agenda filters out cancelled and completed records");
  assert.equal(appointmentQuery.get("from_date"), counselorDate, "Agenda starts at the current institutional date");
  assert.equal(appointmentQuery.get("to_date"), counselorDate, "Agenda ends at the current institutional date");
  assert.equal(appointmentQuery.get("ordering"), "EARLIEST_START", "Agenda requests canonical chronological order");
  assert.equal(appointmentQuery.get("page"), "1", "Agenda reads only its first bounded page");
  assert.equal(appointmentQuery.get("page_size"), "5", "Agenda keeps its preview bounded");
  assert.equal(requests.some((request) => request.pathname === "/api/v1/appointments"), false, "Home never switches to the managed Appointment population");
  assert.equal(requests.filter((request) => request.method !== "GET").length, 0, "Home does not mutate work");
  await screenshot(page, "after-counselor-desktop-agenda-work");
});

await check("confirmed-empty-agenda-keeps-work-visible", "/portal", counselorWorld({ appointments: [], work: canonicalWork.slice(0, 1) }).options(), async (page) => {
  await shown(agenda(page).getByText("No scheduled appointments today.", { exact: true }));
  await shown(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
  assert.equal(await page.getByRole("heading", { name: "No items currently need attention in My work.", exact: true }).count(), 0);
});

await check("confirmed-empty-work-keeps-agenda-and-destinations", "/portal", counselorWorld({ appointments: appointmentsToday.slice(0, 2), work: [] }).options(), async (page) => {
  await shown(agenda(page).getByRole("heading", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  await shown(work(page).getByText("No items currently need attention in My work.", { exact: true }));
  await shown(page.locator("#counselor-continuation-heading"));
  await screenshot(page, "after-counselor-desktop-no-work");
});

await check("head-oversight-links-require-real-capabilities", "/portal", counselorWorld({
  head: true,
  capabilities: [
    "appointments.view_self", "appointments.manage", "reports.view", "organization.manage",
    "availability.manage", "services.manage", "services.catalog.view", "guidance_messages.view",
    "routine_interviews.view_assigned", "counseling.view_assigned", "guidance_followups.view",
  ],
  appointments: appointmentsToday.slice(0, 2),
  work: canonicalWork.slice(0, 2),
}).options(), async (page, { requests }) => {
  const oversight = page.locator('section[aria-labelledby="head-guidance-oversight-heading"]');
  await shown(agenda(page));
  await shown(work(page));
  await shown(oversight.getByRole("link", { name: "Reports" }));
  await shown(oversight.getByRole("link", { name: "Organization" }));
  await shown(oversight.getByRole("link", { name: "Availability" }));
  await shown(oversight.getByRole("link", { name: "Services" }));
  await shown(oversight.getByRole("link", { name: "Manage appointments" }));
  assert.equal(await page.getByText(/confidential narrative|assessment findings|handoff summary/i).count(), 0);
  assert.equal(requests.some((request) => request.pathname.startsWith("/api/v1/appointments/") && request.pathname !== "/api/v1/appointments/me"), false);
  await screenshot(page, "after-head-authorized-oversight");
});

await check("head-designation-alone-adds-no-oversight-destination", "/portal", counselorWorld({
  head: true,
  capabilities: ["appointments.view_self"],
  appointments: appointmentsToday.slice(0, 1),
  work: canonicalWork.slice(0, 1),
}).options(), async (page) => {
  await shown(agenda(page));
  await shown(work(page));
  await hidden(page.locator("#head-guidance-oversight-heading"));
  assert.equal(await page.locator('main a[href="/portal/reports"]').count(), 0);
  assert.equal(await page.locator('main a[href="/portal/organization"]').count(), 0);
  await screenshot(page, "after-head-without-optional-capabilities");
});

await check("unauthorized-self-agenda-is-not-presented-as-empty", "/portal", counselorWorld({
  head: true,
  capabilities: [],
  appointments: appointmentsToday.slice(0, 1),
  work: canonicalWork.slice(0, 1),
}).options(), async (page, { requests }) => {
  await hidden(page.locator("#counselor-agenda-heading"));
  await shown(work(page));
  assert.equal(requests.some((request) => request.pathname === "/api/v1/appointments/me"), false);
  assert.equal(await page.locator("#head-guidance-oversight-heading").count(), 0);
});

// Partial failure and stale-data cases need to mutate their synthetic API state after the first read.
const partial = counselorWorld({ appointments: appointmentsToday.slice(0, 1), work: canonicalWork.slice(0, 1) });
partial.appointmentsStatus = 500;
partial.workStatus = 500;
await check("partial-failure-keeps-independent-projection-usable", "/portal", partial.options(), async (page) => {
  await shown(agenda(page).getByRole("alert"));
  await shown(work(page).getByRole("alert"));
  assert.equal(await agenda(page).getByText("No scheduled appointments today.", { exact: true }).count(), 0);
  assert.equal(await work(page).getByText("No items currently need attention in My work.", { exact: true }).count(), 0);
  partial.appointmentsStatus = 200;
  partial.workStatus = 200;
  await agenda(page).getByRole("button", { name: "Retry", exact: true }).click();
  await work(page).getByRole("button", { name: "Retry", exact: true }).click();
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  await shown(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
});

const stale = counselorWorld({ appointments: appointmentsToday.slice(0, 1), work: canonicalWork.slice(0, 1) });
await check("stale-agenda-retains-confirmed-items-and-denial-hides-them", "/portal", stale.options(), async (page) => {
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  stale.appointmentsStatus = 500;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await shown(agenda(page).getByText("Today’s schedule could not be refreshed. Showing the last confirmed appointments.", { exact: true }));
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  await screenshot(page, "after-stale-agenda");
  stale.appointmentsStatus = 403;
  await agenda(page).getByRole("button", { name: "Retry", exact: true }).click();
  await shown(agenda(page).getByRole("alert"));
  await hidden(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  assert.equal(await agenda(page).getByText("No scheduled appointments today.", { exact: true }).count(), 0);
});

const changed = counselorWorld({ appointments: appointmentsToday.slice(0, 1), work: [] });
await check("cancelled-or-rescheduled-appointments-disappear-after-authoritative-refresh", "/portal", changed.options(), async (page) => {
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  changed.appointments = [counselorAppointment(1, { hour: 10, status: "CANCELLED" })];
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await shown(agenda(page).getByText("No scheduled appointments today.", { exact: true }));
  await hidden(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
});

const switched = counselorWorld({
  head: true,
  capabilities: ["appointments.view_self", "reports.view", "organization.manage"],
  appointments: appointmentsToday.slice(0, 1),
  work: canonicalWork.slice(0, 1),
});
await check("account-switch-removes-counselor-private-projections", "/portal", switched.options(), async (page) => {
  await shown(agenda(page).getByRole("link", { name: "Open appointment with AlexandriaMariaCatherineJohnsonWilliams" }));
  await shown(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
  switched.account = {
    ...switched.account,
    id: "synthetic-student-account-B",
    role: "STUDENT",
    first_name: "Blair",
    designations: [],
    student_lifecycle_status: "CURRENT",
    capabilities: [],
  };
  switched.summary = { ...switched.summary, guidance: null, student: null };
  switched.appointments = [];
  switched.work = [];
  switched.items = [];
  await page.clock.fastForward(31_000);
  await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
  await shown(page.getByRole("heading", { level: 1, name: "Good morning, Blair", exact: true }));
  await hidden(agenda(page));
  await hidden(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
  await hidden(page.getByText("AlexandriaMariaCatherineJohnsonWilliams", { exact: true }));
  assert.equal(await page.locator("#head-guidance-oversight-heading").count(), 0);
});

await check("keyboard-order-follows-agenda-before-work", "/portal", counselorWorld({
  appointments: appointmentsToday.slice(0, 2),
  work: canonicalWork,
}).options(), async (page) => {
  const appointmentLinks = agenda(page).locator("li a");
  const viewAllWork = page.getByRole("link", { name: "View all work" });
  if (process.env.COMPASS_UI_BROWSER === "webkit") {
    // macOS WebKit does not include links in Tab navigation by default. Match the established
    // Student Home check: verify each authored link's focusability and visible focus treatment.
    await page.locator("main").focus();
    await page.keyboard.press("Tab");
    for (const link of [appointmentLinks.first(), appointmentLinks.nth(1), viewAllWork]) {
      await link.focus();
      const state = await link.evaluate((node) => ({ active: node === document.activeElement,
        tabIndex: node.tabIndex, ring: getComputedStyle(node).boxShadow !== "none" }));
      assert.equal(state.active, true, "Each Counselor Home link can receive focus in content order");
      assert.ok(state.tabIndex >= 0 && state.ring, "Each Counselor Home link retains a visible focus ring");
    }
    return;
  }
  await appointmentLinks.first().focus();
  await page.keyboard.press("Tab");
  assert.equal(await appointmentLinks.nth(1).evaluate((node) => node === document.activeElement), true, "Tab follows chronological agenda order");
  assert.equal(await appointmentLinks.nth(1).evaluate((node) => node.matches(":focus-visible")), true, "Keyboard focus remains visible on the next appointment");
  await page.keyboard.press("Tab");
  assert.equal(await viewAllWork.evaluate((node) => node === document.activeElement), true, "The agenda precedes the work panel in the tab sequence");
});

await check("responsive-home-reflows-at-requested-widths-and-enlarged-text", "/portal", counselorWorld({
  appointments: appointmentsToday.slice(0, 2),
  work: canonicalWork,
}).options(), async (page) => {
  await shown(agenda(page));
  await shown(work(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }));
  for (const width of [320, 360, 390, 768, 1024, 1440]) {
    for (const enlarged of [false, true]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate((scale) => { document.documentElement.style.fontSize = scale ? "200%" : "100%"; }, enlarged);
      await page.evaluate(() => document.fonts.ready);
      await noHorizontalOverflow(page);
      const result = await page.evaluate(() => {
        const main = document.querySelector("main");
        const rect = (node) => {
          const box = node.getBoundingClientRect();
          return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, height: box.height };
        };
        const panels = [...main.querySelectorAll('section[aria-labelledby]')];
        const links = [...main.querySelectorAll("a")].filter((node) => node.getClientRects().length);
        const linkBoxes = links.map((node) => ({ name: node.textContent.trim(), ...rect(node), tabIndex: node.tabIndex }));
        const collisions = linkBoxes.flatMap((a, index) => linkBoxes.slice(index + 1)
          .filter((b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1)
          .map((b) => [a.name, b.name]));
        const root = parseFloat(getComputedStyle(document.documentElement).fontSize);
        const actionTargets = [...main.querySelectorAll('section[aria-labelledby="counselor-agenda-heading"] a, section[aria-labelledby="counselor-work-heading"] a')]
          .filter((node) => node.getClientRects().length).map((node) => rect(node));
        return {
          viewport: innerWidth,
          document: document.documentElement.scrollWidth,
          rootText: getComputedStyle(document.documentElement).fontSize,
          panels: panels.map((node) => ({ id: node.getAttribute("aria-labelledby"), scroll: node.scrollWidth, client: node.clientWidth })),
          links: linkBoxes,
          collisions,
          actionTargets,
          minimumTarget: 2.75 * root,
        };
      });
      assert.equal(result.collisions.length, 0, `${width}px ${enlarged ? "200%" : "100%"}: Home links do not overlap`);
      assert.ok(result.panels.every((panel) => panel.scroll <= panel.client + 1), `${width}px ${enlarged ? "200%" : "100%"}: Home panels reflow internally`);
      assert.ok(result.links.every((link) => link.left >= -1 && link.right <= width + 1 && link.tabIndex >= 0), `${width}px ${enlarged ? "200%" : "100%"}: links remain visible and focusable`);
      assert.ok(result.actionTargets.every((target) => target.height >= result.minimumTarget - 1), `${width}px ${enlarged ? "200%" : "100%"}: primary links retain rem-scaled touch targets`);
      responsiveMeasurements.push({
        width,
        enlarged,
        document: result.document,
        rootText: result.rootText,
        panelsFit: result.panels.every((panel) => panel.scroll <= panel.client + 1),
        linksInBounds: result.links.every((link) => link.left >= -1 && link.right <= width + 1 && link.tabIndex >= 0),
        overlappingLinks: result.collisions.length,
        smallestAgendaOrWorkTarget: result.actionTargets.length
          ? Math.min(...result.actionTargets.map((target) => target.height))
          : null,
        minimumTarget: result.minimumTarget,
      });
      if (width === 390 && !enlarged) await screenshot(page, "after-counselor-mobile-390");
      if (width === 320 && enlarged) await screenshot(page, "after-counselor-320-200-text");
      if (width === 1440 && !enlarged) await page.getByRole("button", { name: "Collapse navigation" }).click();
    }
  }
  assert.deepEqual(await page.locator("main h2").allTextContents(), [
    "Today's appointments", "My work", "Continue in your workspace", "At a glance", "Announcements",
  ]);
});

if (responsiveMeasurements.length > 0) {
  const artifactsRoot = process.env.COMPASS_UI_ARTIFACTS ?? "/tmp";
  await writeFile(join(artifactsRoot, "ux15-counselor-home", "geometry.json"), `${JSON.stringify(responsiveMeasurements, null, 2)}\n`);
}

for (const role of ["IT_ADMIN"]) {
  const state = homeWorld({ role, items: [] });
  await check(`non-counselor-${role}-keeps-existing-overview`, "/portal", state.options(), async (page) => {
    await shown(page.getByRole("heading", { name: "Needs your attention", exact: true }));
    await shown(page.getByRole("heading", { name: "At a glance", exact: true }));
    await shown(page.locator("#overview-announcements-heading"));
    assert.equal(await page.locator("#counselor-agenda-heading, #counselor-work-heading, #head-guidance-oversight-heading").count(), 0);
  });
}

await finish();
