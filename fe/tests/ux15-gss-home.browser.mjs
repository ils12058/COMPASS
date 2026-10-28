// Synthetic Guidance Services Home journeys. Every API call is intercepted by the shared harness.
import assert from "node:assert/strict";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";
import { counselorWorld, counselorAppointment, workItem } from "./support/ux15-counselor-home-fixtures.mjs";
import { gssHomeDate, gssWorld, managedAppointment } from "./support/ux15-gss-home-fixtures.mjs";

const {
  check,
  shown,
  hidden,
  screenshot,
  noHorizontalOverflow,
  settleFetches,
  finish,
  artifacts,
} = await createBrowserHarness("ux15-gss-home");
const workPanel = (page) => page.locator('section[aria-labelledby="gss-work-heading"]');
const schedulePanel = (page) => page.locator('section[aria-labelledby="gss-schedule-heading"]');
const operationsPanel = (page) => page.locator('section[aria-labelledby="gss-operations-heading"]');
const responsiveMeasurements = [];

await check("GSS desktop canonical work, managed schedule and scoped operations", "/portal", gssWorld().options(), async (page, { requests }) => {
  await shown(page.getByRole("heading", { name: "Guidance Services Home", exact: true }));
  await shown(workPanel(page).getByRole("heading", { name: "My work", exact: true }));
  await shown(schedulePanel(page).getByRole("heading", { name: "Today's managed Appointments", exact: true }));
  await shown(operationsPanel(page).getByRole("heading", { name: "Office workload", exact: true }));
  assert.deepEqual(await workPanel(page).locator("h3").allTextContents(), [
    "Review Guidance follow-up",
    "Reply to Guidance Message",
    "Prepare Good Moral request",
    "Review Call Slip",
    "Review Guidance follow-up",
  ], "The Home keeps the canonical Work Queue order and shows a bounded five-item preview");
  assert.equal(await schedulePanel(page).locator("ul > li").count(), 5, "Only the first five managed Appointments are shown");
  await shown(schedulePanel(page).getByRole("link", { name: "Open managed appointment with Alexandria Maria Catherine Johnson Williams" }));
  await shown(schedulePanel(page).getByText("Counselor: Sam Counselor 1", { exact: true }));
  await shown(schedulePanel(page).getByText("Showing the first 5 scheduled Appointments. Open the full schedule to see more.", { exact: true }));
  await shown(operationsPanel(page).getByText("Messages awaiting reply", { exact: true }));
  await shown(operationsPanel(page).getByText("Good Moral requests awaiting Counselor issuance", { exact: true }));
  await shown(page.locator('section[aria-labelledby="gss-destinations-heading"]').getByRole("link", { name: /Referrals/ }));
  assert.equal(await operationsPanel(page).getByText("Routine evaluations pending", { exact: true }).count(), 0, "Null Counselor-only metrics stay unavailable");
  assert.equal(await page.getByText("Upcoming managed appointments", { exact: true }).count(), 0, "The operational snapshot does not repeat the managed schedule count");
  assert.equal(await page.getByText("Synthetic confidential counseling narrative", { exact: true }).count(), 0, "Confidential purpose text is never presented");
  assert.equal(await page.getByRole("link", { name: "Issue Good Moral certificate", exact: true }).count(), 0, "GSS does not receive a Good Moral issuance action");
  const targetLinks = [
    workPanel(page).getByRole("link", { name: "View all work", exact: true }),
    workPanel(page).getByRole("link", { name: "Open follow-up", exact: true }).first(),
    schedulePanel(page).getByRole("link", { name: "View full schedule", exact: true }),
    page.getByRole("link", { name: /Manage Appointments/ }),
  ];
  for (const link of targetLinks) {
    const box = await link.boundingBox();
    assert.ok(box && box.height >= 44, "Primary Home links preserve the established 44px target height");
  }
  const firstWorkAction = workPanel(page).getByRole("link", { name: "Open follow-up", exact: true }).first();
  await firstWorkAction.focus();
  const focusState = await firstWorkAction.evaluate((node) => ({
    active: node === document.activeElement,
    visibleRing: getComputedStyle(node).boxShadow !== "none",
  }));
  assert.equal(focusState.active, true);
  assert.equal(focusState.visibleRing, true, "Work links keep visible keyboard focus");
  const appointmentRead = requests.find((request) => request.pathname === "/api/v1/appointments");
  assert.ok(appointmentRead, "The schedule uses the managed Appointment endpoint");
  const params = new URLSearchParams(appointmentRead.search);
  assert.equal(params.get("status"), "SCHEDULED");
  assert.equal(params.get("from_date"), gssHomeDate, "The range begins on the Asia/Manila date");
  assert.equal(params.get("to_date"), gssHomeDate, "The range ends on the Asia/Manila date");
  assert.equal(params.get("ordering"), "EARLIEST_START");
  assert.equal(params.get("page"), "1");
  assert.equal(params.get("page_size"), "5");
  assert.equal(requests.some((request) => request.pathname === "/api/v1/appointments/me"), false, "GSS never uses the Counselor self agenda");
  assert.equal(requests.some((request) => request.pathname === "/api/v1/overview"), false, "GSS does not fetch duplicate Overview counts it does not present");
  assert.equal(requests.filter((request) => request.method !== "GET").length, 0, "Home adds no workflow mutations");
  await screenshot(page, "after-gss-desktop-work-operations");
  await screenshot(page, "after-gss-desktop-managed-appointments", schedulePanel(page));
  await shown(page.getByRole("button", { name: "Collapse navigation", exact: true }));
  await page.getByRole("button", { name: "Collapse navigation", exact: true }).click();
  await shown(page.getByRole("button", { name: "Expand navigation", exact: true }));
  await noHorizontalOverflow(page);
  await shown(schedulePanel(page).getByRole("link", { name: "Open managed appointment with Alexandria Maria Catherine Johnson Williams" }));
  await screenshot(page, "after-gss-desktop-work-operations-dock-collapsed");
  await page.getByRole("button", { name: "Expand navigation", exact: true }).click();
});

await check("GSS empty work stays separate from available schedule and zero metrics", "/portal", gssWorld({
  work: [],
  appointments: [managedAppointment(1)],
  operations: {
    generated_at: "2026-10-22T01:30:00Z",
    backlog: {
      guidance_messages: { count: 0, oldest_waiting_since: null },
      routine_evaluations: null,
      good_moral_preparation: { count: 0, oldest_waiting_since: null },
      good_moral_issuance: null,
      call_slips_due: { count: 0, oldest_due_at: null },
    },
    schedule: { upcoming_self_appointments_count: null, upcoming_managed_appointments_count: 1, active_call_slips_count: 0 },
  },
}).options(), async (page) => {
  await shown(workPanel(page).getByText("No items currently need attention in My work.", { exact: true }));
  await shown(schedulePanel(page).getByRole("link", { name: "Open managed appointment with Synthetic GSS Student 1" }));
  await shown(operationsPanel(page).getByText("No work is currently waiting in the returned office metrics.", { exact: true }));
  assert.equal(await operationsPanel(page).getByText("Good Moral requests awaiting Counselor issuance", { exact: true }).count(), 0, "Null is not presented as a zero count");
  await screenshot(page, "after-gss-desktop-no-work");
});

await check("GSS restricted account omits the managed schedule and its request", "/portal", gssWorld({ capabilities: [], work: [] }).options(), async (page, { requests }) => {
  await shown(page.getByRole("heading", { name: "Guidance Services Home", exact: true }));
  await hidden(schedulePanel(page));
  assert.equal(requests.some((request) => request.pathname === "/api/v1/appointments"), false, "No managed Appointment request is sent without appointments.manage");
  assert.equal(await page.getByRole("link", { name: "Manage Appointments", exact: true }).count(), 0);
  await shown(page.getByRole("link", { name: "Guidance operations", exact: true }));
  await screenshot(page, "after-gss-restricted-capabilities");
});

await check("GSS confirmed empty schedule is distinct from restricted access", "/portal", gssWorld({ appointments: [] }).options(), async (page, { requests }) => {
  await shown(schedulePanel(page).getByText("No scheduled managed Appointments today.", { exact: true }));
  assert.equal(requests.some((request) => request.pathname === "/api/v1/appointments"), true);
});

const failed = gssWorld();
failed.workStatus = 500;
failed.appointmentsStatus = 500;
failed.operationsStatus = 500;
await check("GSS independent initial failures do not become empty states and can retry", "/portal", failed.options(), async (page) => {
  await shown(workPanel(page).getByRole("alert"));
  await shown(schedulePanel(page).getByRole("alert"));
  await shown(operationsPanel(page).getByRole("alert"));
  assert.equal(await workPanel(page).getByText("No items currently need attention in My work.", { exact: true }).count(), 0);
  assert.equal(await schedulePanel(page).getByText("No scheduled managed Appointments today.", { exact: true }).count(), 0);
  failed.workStatus = 200;
  failed.appointmentsStatus = 200;
  failed.operationsStatus = 200;
  await workPanel(page).getByRole("button", { name: "Retry", exact: true }).click();
  await schedulePanel(page).getByRole("button", { name: "Retry", exact: true }).click();
  await operationsPanel(page).getByRole("button", { name: "Retry", exact: true }).click();
  await shown(workPanel(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }).first());
  await shown(schedulePanel(page).getByRole("link", { name: "Open managed appointment with Alexandria Maria Catherine Johnson Williams" }));
});

const stale = gssWorld();
await check("GSS transient refresh failure retains confirmed data with a freshness notice", "/portal", stale.options(), async (page) => {
  await shown(workPanel(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }).first());
  await shown(schedulePanel(page).getByRole("link", { name: "Open managed appointment with Alexandria Maria Catherine Johnson Williams" }));
  stale.workStatus = 500;
  stale.appointmentsStatus = 500;
  stale.operationsStatus = 500;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await shown(workPanel(page).getByText("My work could not be refreshed. Showing the last confirmed items.", { exact: true }));
  await shown(schedulePanel(page).getByText("Today's managed Appointments could not be refreshed. Showing the last confirmed schedule.", { exact: true }));
  await shown(operationsPanel(page).getByText("Guidance Operations could not be refreshed. Showing the last confirmed office workload.", { exact: true }));
  await shown(workPanel(page).getByRole("heading", { name: "Review Guidance follow-up", exact: true }).first());
  await screenshot(page, "after-gss-partial-stale-data");
});

for (const width of [320, 360, 390, 768, 1024, 1440]) {
  await check(`GSS responsive ${width}px`, "/portal", gssWorld({ appointments: [managedAppointment(1)] }).options({
    viewport: { width, height: 1000 },
    mobile: width <= 390,
  }), async (page) => {
    await shown(workPanel(page).getByRole("heading", { name: "My work", exact: true }));
    await shown(operationsPanel(page).getByRole("heading", { name: "Office workload", exact: true }));
    await noHorizontalOverflow(page);
    responsiveMeasurements.push(await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      rootFontSize: getComputedStyle(document.documentElement).fontSize,
    })));
    if (width === 390) await screenshot(page, "after-gss-mobile-390");
  });
}

await check("GSS 320px at simulated 200 percent root text reflows without overflow", "/portal", gssWorld({
  appointments: [managedAppointment(1, { studentName: "Alexandria Maria Catherine Johnson Williams" })],
}).options({ viewport: { width: 320, height: 900 }, mobile: true }), async (page) => {
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  await shown(schedulePanel(page).getByText("Alexandria Maria Catherine Johnson Williams", { exact: true }));
  await noHorizontalOverflow(page);
  responsiveMeasurements.push(await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    rootFontSize: getComputedStyle(document.documentElement).fontSize,
  })));
  await screenshot(page, "after-gss-320-200-text");
});

const switching = gssWorld();
await check("switching from GSS to Student removes GSS work and destinations", "/portal", switching.options(), async (page, { requests }) => {
  await shown(page.getByText("Synthetic Work Student 1", { exact: true }));
  const requestCount = requests.length;
  switching.account = homeWorld({ role: "STUDENT" }).account;
  // Let Next's route prefetches finish before the full reload; WebKit reports canceled RSC fetches
  // as page errors even though the account switch itself succeeds.
  await settleFetches(page);
  await page.reload({ waitUntil: "domcontentloaded" });
  await hidden(page.getByRole("heading", { name: "Guidance Services Home", exact: true }));
  await hidden(page.getByText("Synthetic Work Student 1", { exact: true }));
  assert.equal(await page.getByRole("link", { name: "Manage Appointments", exact: true }).count(), 0);
  assert.equal(requests.slice(requestCount).some((request) => request.pathname === "/api/v1/appointments"), false);
});

await check("Counselor Home remains unchanged", "/portal", counselorWorld({
  appointments: [counselorAppointment(1, { hour: 10 })],
  work: [workItem("ROUTINE_EVALUATION", 1)],
}).options(), async (page) => {
  await shown(page.getByRole("heading", { name: "Today's appointments", exact: true }));
  await shown(page.getByRole("heading", { name: "My work", exact: true }));
  await screenshot(page, "after-counselor-non-regression");
});

await check("Student Home remains unchanged", "/portal", homeWorld({ role: "STUDENT" }).options(), async (page) => {
  await shown(page.getByRole("heading", { level: 1 }));
  await shown(page.getByText("At a glance", { exact: true }));
  await screenshot(page, "after-student-non-regression");
});

await writeFile(join(artifacts, "geometry.json"), `${JSON.stringify(responsiveMeasurements, null, 2)}\n`);
await finish();
