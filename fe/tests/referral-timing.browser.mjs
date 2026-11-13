// CW-5 synthetic contract journeys. The external companion also runs with real Django.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { civilDays, emptyReferralTiming, manilaDay, reportedTimingFixture, timingVersion } from "./support/referral-timing-fixtures.mjs";

const { check, finish, shown, hidden, screenshot, noHorizontalOverflow } = await createBrowserHarness("referral-timing");
const id = "c5000000-0000-4000-8000-000000000010";
const source = `/api/v1/referrals/${id}`;
const path = `/portal/referrals/${id}`;
const tab = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
const account = { ...user(), capabilities: [...user().capabilities, "referrals.view", "referrals.manage", "call_slips.view", "call_slips.manage"] };
const student = { id: "c5000000-0000-4000-8000-000000000011", display_name: "Synthetic timing Student", institutional_id: "CW5-SYNTHETIC" };
const reported = reportedTimingFixture();
const ref = {
  id, reference_code: "REF-2026-000005", submission_channel: "GCO_RECORDED", submitted_at: null,
  administrative_state: "RECEIVED_BY_GCO", student, student_name_snapshot: student.display_name,
  course_year_block_snapshot: "BSIS 4A", form_revision: { id, official_code: "UCN-OP-GCO-01F3", official_revision: "1", internal_schema_version: 1 },
  referred_on: "2026-01-01", received_at: "2026-01-01T01:00:00Z", created_at: "2026-01-01T01:00:00Z", updated_at: timingVersion,
  recorded_by: { id: account.id, display_name: "Synthetic recorder" }, referrer_name: "Synthetic paper referrer",
  reason: "Synthetic confidential Referral reason", status_note: "", voided_at: null, voided_by: null, void_reason: "", actions: [],
};
function verification(note, index = 1) {
  return { id: `c5000000-0000-4000-8000-${String(100 + index).padStart(12, "0")}`, answer_kind: "NO_SUITABLE_TIME", windows: [],
    confirmation_source: "OFFICE_RECORD", note, author_id: account.id, author_name: "Synthetic verifier", created_at: `2026-11-13T02:0${index}:00Z` };
}
function fixture(options = {}) {
  const state = { reported, records: [], writes: [], readStatus: 200, canVerify: true, ...options };
  const facts = () => emptyReferralTiming(id, { timing_status: state.reported?.answer_kind ?? "NOT_PROVIDED", reported: state.reported,
    verifications: state.records, latest_verification_id: state.records[0]?.id ?? null, referral_updated_at: timingVersion,
    referral_closed: !!state.closed, can_verify: state.canVerify && !state.voided });
  return { state, facts, handler: async ({ pathname, method, reply, request, route }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(state.account ?? account)); return true; }
    if (pathname === source) { await reply({ ...ref, timing_status: facts().timing_status, administratively_closed_at: state.closed ? "2026-11-01T00:00:00Z" : null,
      voided_at: state.voided ? "2026-11-01T00:00:00Z" : null }); return true; }
    if (pathname === source + "/timing") {
      if (state.delay) await new Promise(resolve => setTimeout(resolve, state.delay));
      await reply(state.readStatus === 200 ? facts() : { error: { code: "referral_not_found", message: "Synthetic unavailable" } }, state.readStatus); return true;
    }
    if (pathname === source + "/timing/verifications" && method === "POST") {
      const body = request.postDataJSON(); state.writes.push(body);
      if (state.writeError === 422) {
        await reply({ error: { code: "validation_error", message: "Synthetic", details: [{ loc: ["body", "payload", "windows", "0", "end_time"], message: "End time must be after start time." }] } }, 422); return true;
      }
      if (state.writeError === 409) {
        state.records = [verification("Synthetic competing verification", 2), ...state.records];
        await reply({ error: { code: "referral_timing_changed", message: "Synthetic" } }, 409); return true;
      }
      if (state.writeError === 403) {
        state.canVerify = false; await reply({ error: { code: "referral_not_permitted", message: "Synthetic" } }, 403); return true;
      }
      if (state.writeError === "lost" || state.writeError === 500) {
        if (state.commitBeforeFailure) state.records = [verification(body.note, 3), ...state.records];
        if (state.writeError === "lost") await route.abort("failed");
        else await reply({ error: { code: "internal_error", message: "Synthetic" } }, 500);
        return true;
      }
      assert.equal(body.expected_latest_verification_id, state.records[0]?.id ?? null);
      assert.equal(body.expected_referral_updated_at, timingVersion, "Round-trip the exact microsecond token");
      const next = { ...verification(body.note, state.records.length + 1), ...body, windows: body.windows.map(window => ({ ...window, expired: false })) };
      delete next.expected_latest_verification_id; delete next.expected_referral_updated_at;
      state.records = [next, ...state.records]; await reply(facts(), 201); return true;
    }
    if (pathname === "/api/v1/call-slips") { await reply({ items: [], page: 1, page_size: 20, has_next: false }); return true; }
    if (pathname === "/api/v1/referrals") {
      if (method === "POST") {
        const body = request.postDataJSON(); state.writes.push(body);
        state.reported = reportedTimingFixture({ ...body.scheduling_statement, windows: body.scheduling_statement.windows.map(window => ({ ...window, expired: false })), submission_channel: "GCO_RECORDED", author_name: "Synthetic recorder" });
        await reply({ ...ref, timing_status: state.reported.answer_kind }, 201); return true;
      }
      await reply({ items: [{ ...ref, timing_status: facts().timing_status }], page: 1, page_size: 20, has_next: false, ordering: "REFERRED_DESC", filter_options: { form_revisions: [] } }); return true;
    }
    if (pathname === "/api/v1/referrals/students") { await reply({ items: [student], page: 1, page_size: 20, has_next: false }); return true; }
    return false;
  } };
}
const form = page => page.getByRole("form", { name: "Verify Referral availability", exact: true });
async function fillVerification(page, known = false) {
  const editor = form(page);
  await shown(editor);
  await editor.getByRole("radio", { name: known ? "Confirmed times" : "No suitable time confirmed", exact: true }).check();
  if (known) {
    await editor.getByRole("button", { name: "Add window", exact: true }).click();
    const row = editor.getByRole("group", { name: "Window 1 of 1", exact: true });
    await row.getByLabel("Date · Philippine Time", { exact: true }).fill(civilDays(manilaDay(), 2));
    await row.getByLabel("Start time · Philippine Time", { exact: true }).fill("10:00");
    await row.getByLabel("End time · Philippine Time", { exact: true }).fill("11:00");
  }
  await editor.getByLabel("Scheduling constraints note (optional)", { exact: true }).fill("Synthetic new verification constraint");
  await editor.getByLabel("Confirmation source", { exact: true }).selectOption("STUDENT_CONFIRMED");
}
async function reconnect(page) {
  await page.clock.install(); await page.clock.fastForward(31_000);
  await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
}

for (const width of [320, 390, 1440]) for (const scale of [100, 200]) {
  const f = fixture({ records: [verification("Synthetic newest confirmation", 2), verification("Synthetic earlier confirmation")] });
  await check(`staff-reported-expired-history-${width}-${scale}`, path, { handler: f.handler, viewport: { width, height: 1000 }, timezoneId: "America/Los_Angeles" }, async page => {
    await shown(page.getByRole("heading", { name: "Reported by the referrer", exact: true }));
    await shown(page.getByText("This time has passed", { exact: true }));
    await shown(page.getByText(/No longer valid after/));
    await shown(page.getByRole("heading", { name: "Earlier verifications", exact: true }));
    await shown(page.getByText(/Synthetic newest confirmation/));
    await shown(page.getByText(/Synthetic earlier confirmation/));
    await shown(page.getByText(/Reported by Synthetic Faculty on/));
    await page.evaluate(scale => { document.documentElement.style.fontSize = `${scale}%`; }, scale);
    await noHorizontalOverflow(page); await screenshot(page, `staff-timing-${width}-${scale}`);
  });
}
for (const known of [false, true]) for (const width of [320, 1440]) {
  const f = fixture();
  await check(`append-verification-${known}-${width}`, path, { handler: f.handler, viewport: { width, height: 1000 } }, async page => {
    await fillVerification(page, known);
    await form(page).getByRole("button", { name: "Add verification", exact: true }).click();
    await shown(page.getByRole("status").filter({ hasText: "Availability verification added." }));
    await shown(page.locator('[aria-labelledby="verified-referral-timing"]').getByText("Student confirmed", { exact: true }));
    assert.equal(f.state.writes.length, 1);
    assert.equal(f.state.writes[0].windows.length, known ? 1 : 0);
    assert.deepEqual(f.state.reported, reported, "The referrer's original is never overwritten");
    assert.equal(await form(page).getByLabel("Scheduling constraints note (optional)").count(), 0);
    await noHorizontalOverflow(page);
  });
}
await check("validation-focus-keyboard-window-source", path, { handler: fixture().handler, mobile: true }, async page => {
  const editor = form(page); await shown(editor);
  await editor.getByRole("button", { name: "Add verification", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "verification-timing-answer_kind");
  await page.keyboard.press("Space");
  await page.locator("#verification-timing-add-window").focus(); await page.keyboard.press("Enter");
  const row = editor.getByRole("group", { name: "Window 1 of 1", exact: true });
  await row.getByLabel("Date · Philippine Time", { exact: true }).fill(civilDays(manilaDay(), 1));
  await row.getByLabel("Start time · Philippine Time", { exact: true }).fill("10:00");
  await row.getByLabel("End time · Philippine Time", { exact: true }).fill("09:00");
  await editor.getByRole("button", { name: "Add verification", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "verification-timing-window-1-end_time");
  await row.getByLabel("End time · Philippine Time", { exact: true }).fill("11:00");
  await editor.getByRole("button", { name: "Add verification", exact: true }).click();
  await page.waitForFunction(() => document.activeElement?.id === "verification-timing-confirmation_source");
  await page.keyboard.press(tab); await noHorizontalOverflow(page);
});
for (const writeError of [409, 422, 500, "lost", 403]) {
  const f = fixture({ writeError, commitBeforeFailure: true });
  await check(`failed-verification-${writeError}`, path, { handler: f.handler }, async page => {
    await fillVerification(page, writeError === 422);
    await form(page).getByRole("button", { name: "Add verification", exact: true }).click();
    if (writeError === 403) { await hidden(form(page)); }
    else {
      await shown(form(page).getByRole("alert"));
      assert.equal(await form(page).getByLabel("Scheduling constraints note (optional)").inputValue(), "Synthetic new verification constraint");
      if (writeError === 422) {
        assert.equal(await page.locator("#verification-timing-window-1-end_time").evaluate(element => element === document.activeElement), true);
      } else {
        await shown(form(page).getByRole("button", { name: "Use latest details", exact: true }));
        assert.equal(await form(page).getByRole("button", { name: "Add verification", exact: true }).isDisabled(), true);
      }
    }
    assert.equal(f.state.writes.length, 1, "Never automatically replay an unsafe request");
    assert.equal(await page.getByText("Availability verification added.", { exact: true }).count(), 0);
  });
}
const refreshFixture = fixture();
await check("background-refresh-keeps-draft-explicit-review", path, { handler: refreshFixture.handler }, async page => {
  const f = refreshFixture;
  await fillVerification(page);
  f.state.records = [verification("Synthetic background confirmation", 2)];
  await reconnect(page);
  await shown(page.getByText(/Synthetic background confirmation/));
  assert.equal(await form(page).getByLabel("Scheduling constraints note (optional)").inputValue(), "Synthetic new verification constraint");
  assert.equal(await form(page).getByRole("button", { name: "Add verification", exact: true }).isDisabled(), true);
  await form(page).getByRole("button", { name: "Use latest details", exact: true }).click();
  await form(page).getByRole("button", { name: "Add verification", exact: true }).click();
  await shown(page.getByText("Availability verification added.", { exact: true }));
  assert.equal(f.state.writes.length, 1);
});
for (const readStatus of [403, 404, 500]) {
  await check(`timing-read-unavailable-${readStatus}`, path, { handler: fixture({ readStatus }).handler }, async page => {
    await shown(page.getByRole("button", { name: "Retry timing", exact: true }));
    assert.equal(await form(page).count(), 0);
    assert.equal(await page.getByText(/Synthetic reported scheduling constraints/).count(), 0);
  });
}
await check("timing-loading", path, { handler: fixture({ delay: 1500 }).handler }, async page => {
  await shown(page.getByRole("status").filter({ hasText: "Loading Referral timing…" }));
  await shown(form(page));
});
const failedRefreshFixture = fixture();
await check("failed-refresh-keeps-confirmed-data-disables-write", path, { handler: failedRefreshFixture.handler }, async page => {
  const f = failedRefreshFixture; await fillVerification(page);
  f.state.readStatus = 500; await reconnect(page);
  await shown(page.getByText(/Couldn't refresh Referral timing/));
  await shown(page.getByText(/Synthetic reported scheduling constraints/));
  assert.equal(await form(page).getByRole("button", { name: "Add verification", exact: true }).isDisabled(), true);
  assert.equal(await form(page).getByLabel("Scheduling constraints note (optional)").inputValue(), "Synthetic new verification constraint");
});
for (const state of ["closed", "voided", "read-only", "absent", "unknown"]) {
  const f = fixture({ closed: state === "closed", voided: state === "voided", canVerify: state !== "read-only",
    account: state === "read-only" ? { ...account, capabilities: account.capabilities.filter(code => code !== "referrals.manage") } : account,
    reported: state === "absent" ? null : state === "unknown" ? reportedTimingFixture({ answer_kind: "UNKNOWN", windows: [], note: "" }) : reported });
  await check(`record-state-${state}`, path, { handler: f.handler }, async page => {
    await shown(page.getByRole("heading", { name: "Reported by the referrer", exact: true }));
    if (state === "closed") {
      await shown(page.getByText("Referral closed", { exact: true })); await fillVerification(page);
      await form(page).getByRole("button", { name: "Add verification", exact: true }).click();
      await shown(page.getByText("Availability verification added.", { exact: true }));
    } else if (state === "voided" || state === "read-only") assert.equal(await form(page).count(), 0);
    else await shown(page.getByText(state === "absent" ? "Timing: Not provided. Timing information was not asked for on this Referral." : "Unknown / needs confirmation", { exact: true }));
  });
}
await check("verification-navigation-draft-guard", path, { handler: fixture().handler }, async page => {
  await form(page).getByRole("radio", { name: "Confirmed times", exact: true }).check();
  await form(page).getByRole("button", { name: "Add window", exact: true }).click();
  await form(page).getByLabel("Start time · Philippine Time", { exact: true }).fill("10:00");
  const dialogs = []; page.on("dialog", async dialog => { dialogs.push(dialog.message()); await dialog.dismiss(); });
  await page.getByRole("link", { name: "Back to Referrals", exact: true }).click();
  assert.equal(dialogs.length, 1); assert.match(dialogs[0], /unsaved availability verification/);
  assert.equal(new URL(page.url()).pathname, path);
  assert.equal(await form(page).getByLabel("Start time · Philippine Time", { exact: true }).inputValue(), "10:00");
});
for (const width of [320, 1440]) {
  await check(`call-slip-context-no-prefill-${width}`, `${path}/issue-call-slip`, { handler: fixture({ records: [verification("Synthetic verified Call Slip context")] }).handler, viewport: { width, height: 1000 } }, async (page, observed) => {
    await shown(page.getByLabel("Report date and time", { exact: true }));
    assert.equal(await page.getByLabel("Report date and time", { exact: true }).inputValue(), "");
    await shown(page.getByRole("heading", { name: "Reported by the referrer", exact: true }));
    await shown(page.getByText(/Synthetic verified Call Slip context/));
    assert.equal(await form(page).count(), 0);
    assert.equal(observed.requests.some(request => /appointments|booking|availability/.test(request.pathname)), false);
    assert.equal(observed.requests.some(request => request.method !== "GET"), false);
    await noHorizontalOverflow(page); await screenshot(page, `call-slip-timing-${width}`);
  });
}
for (const known of [false, true]) {
  const f = fixture();
  await check(`gco-required-timing-${known}`, "/portal/referrals/new", { handler: f.handler, mobile: true }, async page => {
    await page.getByRole("radio", { name: /Synthetic timing Student/ }).check();
    await page.getByLabel("Course / Year / Block", { exact: true }).fill("BSIS 4A");
    await page.getByLabel("Reason for Referral", { exact: true }).fill("Synthetic reason");
    await page.getByLabel("Referrer name", { exact: true }).fill("Synthetic paper referrer");
    await page.getByLabel("Date referred", { exact: true }).fill(manilaDay());
    const recordButton = page.getByRole("button", { name: "Record Referral", exact: true });
    await recordButton.focus(); await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.activeElement?.id === "gco-timing-answer_kind");
    assert.equal(f.state.writes.length, 0, "A UI answer is required even though the API remains optional");
    await page.getByRole("radio", { name: known ? "Known times" : "Unknown / needs confirmation", exact: true }).check();
    if (known) {
      await page.getByRole("button", { name: "Add window", exact: true }).click();
      await page.getByLabel("Date · Philippine Time", { exact: true }).fill(civilDays(manilaDay(), 1));
      await page.getByLabel("Start time · Philippine Time", { exact: true }).fill("09:00");
      await page.getByLabel("End time · Philippine Time", { exact: true }).fill("10:00");
    }
    await recordButton.focus(); await page.keyboard.press("Enter");
    await shown(page.getByRole("heading", { name: "Reported by the referrer", exact: true }));
    assert.equal(f.state.writes.length, 1);
    assert.equal(f.state.writes[0].scheduling_statement.answer_kind, known ? "KNOWN" : "UNKNOWN");
    await shown(page.getByText(/Reported by the referrer, recorded by Synthetic recorder on/));
  });
}
await finish();
