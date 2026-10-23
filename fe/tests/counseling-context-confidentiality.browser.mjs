// CONT-1A: synthetic API responses only; real authorization/decryption is covered by Django tests.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { appointmentId, encounterId, summaryId, counselor, session, overview, encounter, recorded, summary, priorSummary, privateBody } from "./support/cont1a-summary-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const harness = await createBrowserHarness("cont1a-summary-confidentiality");
const { check, shown, hidden, finish, settleFetches } = harness;
const contextPath = `/portal/counseling/workspace/appointment/${appointmentId}`;
const encounterAPI = `/api/v1/counseling/encounters/${encounterId}`;
const oldReads = (requests) => requests.filter(({ pathname }) => /\/counseling\/context\/.*\/shared-summar/.test(pathname));
const error = { error: { code: "counseling_context_not_found", message: "Counseling information unavailable." } };

// The shared harness requires a true result when its custom handler answered a route.
const handledReply = (reply) => async (...args) => {
  await reply(...args);
  return true;
};

function contextFixture({ anchor = "APPOINTMENT", summaries = true, hasEncounter = false, canonical = "own" } = {}) {
  const direct = anchor !== "APPOINTMENT";
  const anchorType = direct ? "ROUTINE_INTERVIEW" : "APPOINTMENT";
  const id = direct ? `cont1a-${anchor.toLowerCase()}` : appointmentId;
  const root = `/api/v1/counseling/context/${anchorType}/${id}`;
  const state = { denied: false };
  return {
    state, root, path: `/portal/counseling/workspace/${direct ? "routine-interview" : "appointment"}/${id}`,
    overrides: { "/api/v1/auth/session": session(counselor(summaries)) },
    handler({ pathname, reply: respond }) {
      const reply = handledReply(respond);
      // If an old/background query is accidentally reintroduced, it returns a sentinel and
      // the test fails both its no-request and no-render assertions.
      if (pathname.startsWith(root) && pathname.includes("shared-summar")) {
        return reply({ items: [priorSummary] });
      }
      if (pathname === root) return reply(overview({
        source_type: anchorType, source_id: id, entry_mode: anchor,
        matching_encounter: hasEncounter ? recorded : null,
        routine_interview: direct ? { id, entry_mode: anchor, intake_status: "SUBMITTED", evaluation_status: "DRAFT" } : null,
      }));
      if (pathname === root + "/inventory") return reply({ inventory_source_status: "MISSING", available: false, inventory: null });
      if (pathname === root + "/support-indicators") return reply({ academic_year: { id: "cont1a-year", label: "2026-2027" }, inventory_source_status: "SUBMITTED", available: true, indicators: [{ code: "PWD", label: "Synthetic protected support indicator" }] });
      if (pathname === root + "/history") return state.denied ? reply(error, 404) : reply({ items: [], limit: 20 });
      if (pathname === encounterAPI) return canonical === "denied"
        ? reply({ error: { code: "counseling_not_found", message: "Encounter unavailable." } }, 404)
        : reply(encounter(canonical === "other" ? { counselor: { id: "other-counselor", display_name: "Other" } } : {}));
      return false;
    },
  };
}

for (const anchor of ["APPOINTMENT", "WALK_IN", "CALLED_IN", "REFERRED"]) {
  for (const summaries of [true, false]) {
    const fixture = contextFixture({ anchor, summaries });
    await check(`${anchor}-no-summary-tab-or-background-query-capabilities-${summaries}`, fixture.path, fixture, async (page, { requests }) => {
      await shown(page.getByRole("heading", { name: "Counseling workspace", exact: true }));
      const tabs = page.getByRole("tablist", { name: "Counseling context sections" });
      await shown(tabs.getByRole("tab", { name: "Overview", exact: true }));
      assert.equal(await tabs.getByRole("tab", { name: /summar/i }).count(), 0);
      if (anchor !== "APPOINTMENT") await shown(tabs.getByRole("tab", { name: "Routine Interview", exact: true }));
      await tabs.getByRole("tab", { name: "Inventory", exact: true }).click();
      await shown(page.getByText("No current submitted Individual Inventory is available for this student.", { exact: true }));
      await tabs.getByRole("tab", { name: "Support", exact: true }).click();
      await shown(page.getByText("Synthetic protected support indicator", { exact: true }));
      await tabs.getByRole("tab", { name: "History", exact: true }).click();
      await shown(page.getByText("No contextual history is available.", { exact: true }));
      await tabs.getByRole("tab", { name: "History", exact: true }).press("Home");
      assert.equal(await tabs.getByRole("tab", { name: "Overview", exact: true }).getAttribute("aria-selected"), "true");
      await settleFetches(page);
      assert.equal(oldReads(requests).length, 0);
      if (anchor === "APPOINTMENT" && summaries) await harness.screenshot(page, "context-without-summary-history");
      assert.ok(!(await page.locator("body").innerText()).includes(privateBody));
      assert.equal(await page.getByRole("heading", { name: "Previous published summaries" }).count(), 0);
    });
  }
}

for (const device of ["desktop", "phone"]) {
  const fixture = contextFixture();
  await check(`denied-section-clears-protected-context-${device}`, fixture.path, { ...fixture, device }, async (page, { requests }) => {
    const tabs = page.getByRole("tablist", { name: "Counseling context sections" });
    await tabs.getByRole("tab", { name: "Support", exact: true }).click();
    const sensitive = page.getByText("Synthetic protected support indicator", { exact: true });
    await shown(sensitive);
    if (device === "phone") {
      await harness.noHorizontalOverflow(page);
      await harness.screenshot(page, "phone-context-support");
    }
    fixture.state.denied = true;
    await tabs.getByRole("tab", { name: "History", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Counseling information unavailable", exact: true }));
    await hidden(sensitive);
    assert.equal(await page.getByRole("tablist", { name: "Counseling context sections" }).count(), 0);
    assert.ok(!(await page.locator("body").innerText()).includes(privateBody));
    assert.equal(oldReads(requests).length, 0);
  });
}

for (const canonical of ["denied", "other"]) {
  const fixture = contextFixture({ hasEncounter: true, canonical });
  await check(`unconfirmed-ownership-hides-authoring-link-${canonical}`, fixture.path, fixture, async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Counseling workspace", exact: true }));
    await settleFetches(page);
    assert.ok(requests.some(({ pathname }) => pathname === encounterAPI));
    assert.equal(await page.getByRole("link", { name: "View encounter", exact: true }).count(), 0);
    assert.equal(oldReads(requests).length, 0);
  });
}

await check("own-encounter-editor-save-publish-remains-functional", contextPath, (() => {
  const fixture = contextFixture({ hasEncounter: true });
  let saved = summary();
  const contextHandler = fixture.handler;
  return { ...fixture, handler(args) {
    const reply = handledReply(args.reply);
    if (args.pathname === encounterAPI + "/shared-summary" && args.method === "GET") return reply(saved);
    if (args.pathname === encounterAPI + "/shared-summary" && args.method === "PUT") {
      saved = { ...saved, content: JSON.parse(args.request.postData()).content };
      return reply(saved);
    }
    if (args.pathname === encounterAPI + "/shared-summary/publish" && args.method === "POST") {
      saved = { ...saved, published_at: new Date().toISOString() };
      return reply(saved);
    }
    return contextHandler(args);
  } };
})(), async (page, { requests }) => {
  const link = page.getByRole("link", { name: "View encounter", exact: true });
  await shown(link);
  await link.click();
  const draft = page.getByRole("textbox", { name: "Shared Summary draft", exact: true });
  await shown(draft);
  await draft.fill("Synthetic takeaways deliberately published to the Student.");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  const publish = page.getByRole("button", { name: "Publish to Student", exact: true });
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some((button) => button.textContent === "Publish to Student" && !button.disabled));
  await publish.click();
  const dialog = page.getByRole("alertdialog", { name: "Publish this Shared Summary to the Student?", exact: true });
  await shown(dialog);
  await dialog.getByRole("button", { name: "Publish summary", exact: true }).click();
  await hidden(dialog);
  await shown(page.getByText(/^Published to Student/));
  await harness.screenshot(page, "author-published-summary");
  await hidden(draft);
  await shown(page.getByText("Synthetic takeaways deliberately published to the Student.", { exact: true }));
  await settleFetches(page);
  await page.reload({ waitUntil: "domcontentloaded" });
  await shown(page.getByText(/^Published to Student/));
  assert.equal(await page.getByRole("button", { name: "Publish to Student", exact: true }).count(), 0);
  assert.equal(requests.filter(({ pathname, method }) => pathname === encounterAPI + "/shared-summary" && method === "PUT").length, 1);
  assert.equal(requests.filter(({ pathname, method }) => pathname === encounterAPI + "/shared-summary/publish" && method === "POST").length, 1);
  assert.equal(oldReads(requests).length, 0);
});

for (const allowed of [true, false]) {
  const studentActor = { ...user("STUDENT"), capabilities: [...user("STUDENT").capabilities, "shared_summaries.view_self"] };
  await check(`student-published-detail-${allowed ? "own" : "unavailable-draft-or-other-student"}`, `/portal/counseling/summaries/${summaryId}`, {
    role: "STUDENT",
    overrides: {
      "/api/v1/auth/session": session(studentActor),
      [`/api/v1/counseling/me/shared-summaries/${summaryId}`]: ({ reply }) => allowed
        ? reply({ id: summaryId, content: "Synthetic Student-visible published takeaways.", published_at: "2026-01-06T02:00:00Z", counseling_ended_at: encounter().ended_at, delivery_mode: "IN_PERSON" })
        : reply({ error: { code: "shared_summary_not_found", message: "This summary is unavailable." } }, 404),
    },
  }, async (page, { requests }) => {
    if (allowed) await shown(page.getByText("Synthetic Student-visible published takeaways.", { exact: true }));
    else {
      // Existing ordinary API error-code copy remains unchanged in CONT-1A.
      await shown(page.getByText("No Shared Summary has been drafted yet.", { exact: true }));
      assert.ok(!(await page.locator("body").innerText()).includes("Synthetic Student-visible published takeaways."));
    }
    assert.ok(!(await page.locator("body").innerText()).includes(privateBody));
    assert.equal(oldReads(requests).length, 0);
  });
}

await finish();
