// COMPASS-UX-P1: synthetic-only visual and responsive checks for the dock and detail-page action rails.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { contextualAppointment, contextualRoutes, appointmentPath, appointmentId } from "./support/guidance-contextual-fixtures.mjs";
import { messagesAccount, createMessagesBackend, sessionFor, COUNSELOR, STUDENT, threadIds } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { worlds } from "./support/ux-hardening-fixtures.mjs";

const { check, shown, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness("ux-p1");

const syntheticStudent = { ...STUDENT, display_name: "Synthetic Student" };
const syntheticCounselor = { ...COUNSELOR, display_name: "Synthetic Counselor" };

function appointmentWorld({ role = "COUNSELOR", started = true, serviceCode = "COUNSELING", appointmentPatch = {} } = {}) {
  const account = messagesAccount(role, { first_name: "Synthetic", last_name: role === "STUDENT" ? "Student" : "Counselor" });
  const viewerId = role === "STUDENT" ? STUDENT.id : COUNSELOR.id;
  const backend = createMessagesBackend({ viewerId, viewerRole: role });
  if (started) {
    backend.addThread({ id: threadIds.counseling, kind: "COUNSELING", student: syntheticStudent, counselor: syntheticCounselor, appointment: appointmentId });
    backend.addMessage(threadIds.counseling, syntheticCounselor, "A synthetic message for layout review.", { at: backend.minutesAgo(30) });
    backend.addMessage(threadIds.counseling, syntheticStudent, "A second synthetic message.", { at: backend.minutesAgo(20) });
    backend.state.reads.set(threadIds.counseling, 2);
    backend.state.startable.clear();
  }
  const routes = contextualRoutes({ serviceCode });
  const appointment = { ...contextualAppointment({ serviceCode, studentName: "Synthetic Student", counselorName: "Synthetic Counselor" }), ...appointmentPatch };
  const handler = async (args) => {
    if (args.pathname === `/api/v1/appointments/${appointmentId}`) { await args.reply(appointment); return true; }
    if (args.pathname === `/api/v1/appointments/${appointmentId}/reminders`) { await args.reply({ items: [] }); return true; }
    return (await backend.handler(args)) || (await routes(args));
  };
  const overrides = {
    "/api/v1/auth/session": ({ reply }) => reply(sessionFor(account)),
    "/api/v1/me/profile": ({ reply }) => reply({ full_name: `Synthetic ${role === "STUDENT" ? "Student" : "Counselor"}`, photo: null }),
    "POST /api/v1/realtime/tickets": ({ reply }) => reply({ ticket: `synthetic-ticket-${role}`, expires_in_seconds: 30, user_id: account.id }),
  };
  const beforeNavigate = async ({ context }) => {
    await context.routeWebSocket(/\/api\/realtime\/v1\/socket/, (route) => {
      route.onMessage((message) => {
        if (JSON.parse(String(message)).type === "authenticate") route.send(JSON.stringify({ v: 1, type: "ready" }));
      });
    });
  };
  return { account, backend, handler, overrides, beforeNavigate, options: (extra = {}) => ({ handler, overrides, beforeNavigate, ...extra }) };
}

const counselorWorld = appointmentWorld();

await check("Appointment desktop contextual rail and Messages dock", appointmentPath, counselorWorld.options({ device: "desktop" }), async (page) => {
  await shown(page.getByRole("heading", { level: 1, name: "APT-CTX-0001", exact: true }));
  await shown(page.getByText("Scheduled", { exact: true }));
  const rail = page.getByRole("group", { name: "Appointment page actions", exact: true });
  await shown(rail);
  assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), "column");
  assert.equal(await rail.locator("button, a").count(), 3);
  for (const name of ["Open Counseling workspace", "Open E-Counseling", "Messages"]) await shown(rail.getByRole(name === "Messages" ? "button" : "link", { name, exact: true }));
  assert.equal(await page.locator("[data-page-header-actions]").count(), 0, "actions are rendered once outside the heading on desktop");
  const counselingLink = rail.getByRole("link", { name: "Open Counseling workspace", exact: true });
  assert.equal(await counselingLink.getAttribute("href"), `/portal/counseling/workspace/appointment/${appointmentId}`);
  const counselingSurface = counselingLink.locator("[data-page-action-surface]");
  const surfaceSize = await counselingSurface.boundingBox();
  assert.deepEqual({ width: surfaceSize.width, height: surfaceSize.height }, { width: 48, height: 48 });
  const labelSize = await counselingLink.locator("[data-page-action-label]").boundingBox();
  assert.ok(labelSize.height <= 44, "the visible desktop label takes no more than two lines");
  await noHorizontalOverflow(page);
  await screenshot(page, "appointment-desktop");

  await rail.getByRole("button", { name: "Messages", exact: true }).click();
  const messages = page.getByRole("complementary", { name: "Messages" });
  await shown(messages);
  const content = await page.locator("[data-page-action-layout='appointment']").boundingBox();
  const messagesBox = await messages.boundingBox();
  assert.ok(content.x + content.width < messagesBox.x, "the narrowed record and Messages panel remain side by side");
  await noHorizontalOverflow(page);
  await screenshot(page, "appointment-messages-open");
});

await check("Appointment mobile actions stay labeled in the header area", appointmentPath, counselorWorld.options({ device: "phone" }), async (page) => {
  const rail = page.getByRole("group", { name: "Appointment page actions", exact: true });
  await shown(rail);
  assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), "row");
  assert.equal(await rail.locator("button, a").count(), 3);
  for (const command of await rail.locator("button, a").all()) {
    await shown(command);
    await shown(command.locator("[data-page-action-label]"));
    const size = await command.boundingBox();
    assert.ok(size.width >= 48 && size.height >= 68, "touch controls keep their 48px icon and visible label");
  }
  await noHorizontalOverflow(page);
  await screenshot(page, "appointment-mobile");
});

const blockedActions = {
  cancel: { allowed: false, blocker: "ECOUNSELING_ROOM_LINKED", consequences: [] },
  reschedule: { allowed: false, blocker: "CUTOFF_PASSED", consequences: [] },
  reassign: { allowed: false, blocker: "NOT_STARTED", consequences: [] },
  complete: { allowed: false, blocker: "ECOUNSELING_ACCESS_OPEN", consequences: [] },
  mark_no_show: { allowed: false, blocker: "ECOUNSELING_ACCESS_OPEN", consequences: [] },
};
const blockedWorld = appointmentWorld({ appointmentPatch: { actions: blockedActions } });
await check("Appointment unavailable action reasons stay discoverable", appointmentPath, blockedWorld.options({ device: "desktop" }), async (page) => {
  const disclosure = page.getByRole("button", { name: /Unavailable actions/ });
  await shown(disclosure);
  assert.equal(await disclosure.getAttribute("aria-expanded"), "false");
  assert.match(await disclosure.innerText(), /5 actions/);
  await disclosure.click();
  await shown(page.getByText("Cancel: An E-Counseling room is already linked to this Appointment.", { exact: true }));
  await shown(page.getByText("Reschedule: The deadline to change this appointment has passed.", { exact: true }));
  await shown(page.getByText(/Complete: Wait until the online counseling access or rejoin period has ended\./));
  await noHorizontalOverflow(page);
});

const referralStudent = { id: "student", display_name: "Synthetic Student", institutional_id: "TEST-0001" };
const syntheticReferral = {
  ...worlds["/api/v1/referrals/long"],
  reference_code: "UX-P1-TEST-01",
  student: referralStudent,
  student_name_snapshot: "Synthetic Student",
  course_year_block_snapshot: "Synthetic Program / Year 4",
  referrer_name: "Synthetic Referrer",
  reason: "Synthetic referral used only to review the page layout.",
};
const referralReader = { ...user(), first_name: "Synthetic", last_name: "Counselor", capabilities: [...user().capabilities, "referrals.view"] };
const referralOverrides = {
  ...worlds,
  "/api/v1/auth/session": { user: referralReader, session: { id: "synthetic", expires_at: "2099-01-01T00:00:00Z", is_current: true } },
  "/api/v1/referrals/long": syntheticReferral,
};
let releasePdf;
let startPdf;
const pdfStarted = new Promise((resolve) => { startPdf = resolve; });
const pdfGate = new Promise((resolve) => { releasePdf = resolve; });
const referralHandler = async ({ pathname, method, route }) => {
  if (method === "GET" && pathname === "/api/v1/referrals/long/pdf") {
    startPdf();
    await pdfGate;
    await route.fulfill({ status: 200, contentType: "application/pdf", headers: { "content-disposition": 'attachment; filename="Synthetic-Referral-Slip.pdf"' }, body: "%PDF-1.4\nsynthetic test" });
    return true;
  }
  return false;
};

await check("Referral desktop action rail keeps the PDF command and its pending state", "/portal/referrals/long", { device: "desktop", overrides: referralOverrides, handler: referralHandler }, async (page) => {
  await shown(page.getByRole("heading", { level: 1, name: "UX-P1-TEST-01", exact: true }));
  await shown(page.getByText("Referral", { exact: true }).first());
  const rail = page.getByRole("group", { name: "Referral page actions", exact: true });
  await shown(rail);
  assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), "column", "desktop referral actions form a vertical rail");
  assert.equal(await page.locator("[data-page-header-actions]").count(), 0, "PDF download is outside the page header actions");
  const download = rail.getByRole("button", { name: "Download Referral Slip", exact: true });
  await shown(download);
  const visibleLabel = await download.locator("[data-page-action-label]").evaluate((element) =>
    Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent)
      .join("")
      .trim(),
  );
  assert.equal(visibleLabel, "Download", "short visible download label");
  const size = await download.locator("[data-page-action-surface]").boundingBox();
  assert.deepEqual({ width: size.width, height: size.height }, { width: 48, height: 48 }, "PDF action keeps its 48px square icon surface");
  await noHorizontalOverflow(page);
  await screenshot(page, "referral-desktop");

  const downloadEvent = page.waitForEvent("download");
  await download.focus();
  await download.press("Enter");
  await pdfStarted;
  const pending = rail.getByRole("button", { name: "Preparing… Referral Slip", exact: true });
  await shown(pending);
  assert.equal(await pending.isDisabled(), true, "pending PDF action is disabled");
  releasePdf();
  assert.equal((await downloadEvent).suggestedFilename(), "Synthetic-Referral-Slip.pdf", "PDF response supplies the synthetic filename");
  await shown(rail.getByRole("button", { name: "Download Referral Slip", exact: true }));
});
releasePdf();

await check("Referral mobile keeps its labeled download near the heading", "/portal/referrals/long", { device: "phone", overrides: referralOverrides }, async (page) => {
  const rail = page.getByRole("group", { name: "Referral page actions", exact: true });
  await shown(rail);
  assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), "row");
  const download = rail.getByRole("button", { name: "Download Referral Slip", exact: true });
  await shown(download);
  assert.equal(await download.locator("[data-page-action-label]").isVisible(), true);
  assert.equal(await page.getByRole("button", { name: "Void Referral", exact: true }).count(), 0, "read-only access keeps operational actions hidden");
  await noHorizontalOverflow(page);
  await screenshot(page, "referral-mobile");
});

for (const width of [320, 768, 1024, 1280, 1440]) {
  const viewport = { width, height: 900 };
  await check(`Appointment action layout has no overflow at ${width}px`, appointmentPath, counselorWorld.options({ viewport }), async (page) => {
    await shown(page.getByRole("heading", { level: 1, name: "APT-CTX-0001", exact: true }));
    await noHorizontalOverflow(page);
  });
  await check(`Referral action layout has no overflow at ${width}px`, "/portal/referrals/long", { viewport, overrides: referralOverrides }, async (page) => {
    await shown(page.getByRole("heading", { level: 1, name: "UX-P1-TEST-01", exact: true }));
    await noHorizontalOverflow(page);
  });
}

const nonCounselingWorld = appointmentWorld({ serviceCode: "GM-OTHER" });
await check("non-Counseling Appointment hides contextual Messages and E-Counseling", appointmentPath, nonCounselingWorld.options({ device: "desktop" }), async (page) => {
  await shown(page.getByRole("heading", { level: 1, name: "APT-CTX-0001", exact: true }));
  const rail = page.getByRole("group", { name: "Appointment page actions", exact: true });
  await shown(rail);
  assert.equal(await rail.getByRole("button", { name: /^Messages/ }).count(), 0);
  assert.equal(await rail.getByRole("link", { name: "Open E-Counseling", exact: true }).count(), 0);
  await noHorizontalOverflow(page);
});

await finish();
