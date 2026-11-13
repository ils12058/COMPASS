// CW-1/CW-2 journeys against the actual Next UI and synthetic canonical responses.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { appointmentCandidate, candidate, caseAppointment, casePath, casesAPI, casesFixture, detail, followup, ids, newPath, root, student, summary } from "./support/counseling-cases-fixtures.mjs";

const { check, shown, hidden, screenshot, noHorizontalOverflow, settleFetches, finish } = await createBrowserHarness("counseling-cases");
const casesHeading = (page) => page.getByRole("heading", { name: "My cases", exact: true });
const addTrigger = (page) => page.getByRole("button", { name: "Add recorded session", exact: true });
const addDialog = (page) => page.getByRole("dialog", { name: "Add a recorded session", exact: true });
const removeDialog = (page) => page.getByRole("alertdialog", { name: "Remove this session from the case?", exact: true });
const removeTrigger = (page, day = 6) => page.getByRole("button", { name: new RegExp(`^Remove the session of Jan ${day}, 2026`) });
const completedCount = (page) => page.locator('[aria-labelledby="case-details-heading"] dl > div').filter({ has: page.getByText("Completed sessions", { exact: true }) }).locator("dd");
const calls = (fixture, operationId) => fixture.operations.filter((operation) => operation.operationId === operationId);
const searchField = (page) => page.getByRole("search", { name: "My cases", exact: true }).getByRole("searchbox");
const staleMessage = "This case changed before your action completed. The latest details are now shown.";
// macOS WebKit uses Option-Tab to include links and buttons in keyboard navigation.
const tabKey = process.platform === "darwin" && process.env.COMPASS_UI_BROWSER === "webkit" ? "Alt+Tab" : "Tab";
function deferred() {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  return { promise, release };
}
async function focused(locator) {
  const target = await locator.elementHandle();
  assert.ok(target, "The expected focus target exists");
  await locator.page().waitForFunction((element) => element === document.activeElement, target, { timeout: 3000 });
}
// Keyboard passes never call focus(), click(), fill(), selectOption() or DOM event dispatch.
async function tabTo(page, locator, key = tabKey) {
  await shown(locator);
  const target = await locator.elementHandle();
  for (let count = 0; count < 100; count++) {
    if (await page.evaluate((element) => element === document.activeElement, target)) return;
    await page.keyboard.press(key);
  }
  throw new Error("The named control was not reachable with Tab");
}
async function keyboardActivate(page, locator) {
  await tabTo(page, locator);
  await page.keyboard.press("Enter");
}
async function pickCandidate(page) {
  const dialog = addDialog(page);
  await shown(dialog);
  await dialog.getByRole("button", { name: /Jan 8, 2026/ }).click();
  return dialog;
}
async function chooseRemovalReason(dialog, reason = "LINKED_BY_MISTAKE") {
  await dialog.getByLabel("Why it doesn't belong here", { exact: true }).selectOption(reason);
}

const loading = deferred();
const loadingFixture = casesFixture({ state: { listHold: loading.promise } });
await check("my-cases-loading-then-rows", root, { handler: loadingFixture.handler }, async (page) => {
  try {
    await shown(casesHeading(page));
    await shown(page.getByRole("status").filter({ hasText: "Loading your cases…" }));
    assert.equal(await page.getByText(/You have no cases yet/).count(), 0, "Loading is not an empty result");
    loading.release();
    await shown(page.getByRole("link", { name: student.display_name, exact: true }));
    assert.equal(await page.getByRole("link", { name: student.display_name, exact: true }).getAttribute("href"), `${casePath}?return_to=%2Fportal%2Fcounseling`);
    const row = page.locator("tbody tr");
    assert.match(await row.innerText(), /CASE-2026-000001/);
    assert.match(await row.innerText(), /Active/);
    assert.match(await row.innerText(), /CW1T-001/);
    assert.equal(await row.locator("td").nth(2).innerText(), "2");
    assert.equal(await page.locator("main h1").count(), 1);
    // The closed Filters dialog stays in the DOM; only the results heading is visible.
    assert.deepEqual(await page.locator("main").getByRole("heading", { level: 2 }).allTextContents(), ["My cases"]);
    assert.equal(await page.locator("main dialog h2").innerText(), "Filters");
    await screenshot(page, "my-cases-desktop");
  } finally { loading.release(); }
});

await check("my-cases-empty-retains-session-records", root, { handler: casesFixture({ list: [] }).handler }, async (page) => {
  await shown(page.getByText("You have no Active cases. Sessions you recorded earlier stay in Session records until you add them to a case.", { exact: true }));
  assert.equal(await page.getByRole("link", { name: "Session records", exact: true }).getAttribute("href"), `${root}/encounters`);
  assert.equal(await page.locator("table").count(), 0);
  assert.equal(await page.getByRole("navigation", { name: "Case results pages" }).count(), 0);
});

const searchFixture = casesFixture();
await check("my-cases-search-empty-and-clear", `${root}?search=no-match`, { handler: searchFixture.handler }, async (page) => {
  await shown(page.getByText("No cases match this search. Clear or change it to broaden the results.", { exact: true }));
  assert.equal(await searchField(page).inputValue(), "no-match");
  assert.equal(calls(searchFixture, "counselingListMyCases")[0].query.search, "no-match");
  // Status is now a structured filter, so Clear search is in the shared Filters panel.
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page.getByRole("button", { name: "Clear search", exact: true }).click();
  await shown(page.getByRole("link", { name: student.display_name, exact: true }));
  assert.equal(new URL(page.url()).searchParams.has("search"), false);
});

const retryFixture = casesFixture({ listError: true });
await check("my-cases-load-failure-retry", root, { handler: retryFixture.handler }, async (page) => {
  const alert = page.locator("main").getByRole("alert");
  await shown(alert);
  assert.match(await alert.innerText(), /Couldn't load your cases\./);
  assert.doesNotMatch(await page.locator("main").innerText(), /Private diagnostic/);
  const readsBeforeRetry = retryFixture.listReads;
  retryFixture.listError = false;
  await alert.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByRole("link", { name: student.display_name, exact: true }));
  assert.equal(retryFixture.listReads, readsBeforeRetry + 1, "Retry makes exactly one additional list request");
});

const sortFixture = casesFixture({ list: [
  summary(detail({ student: { ...student, display_name: "Zed Student" }, opened_at: "2026-11-02T00:00:00Z" })),
  summary(detail({ id: ids.otherCase, reference_code: "CASE-2026-000002", student: { ...student, id: ids.otherStudent, display_name: "Ana Student" }, opened_at: "2026-11-01T00:00:00Z" })),
] });
await check("my-cases-sort-select-and-column", root, { handler: sortFixture.handler }, async (page) => {
  await shown(page.getByRole("link", { name: "Zed Student", exact: true }));
  await page.getByLabel("Sort", { exact: true }).selectOption("STUDENT_ASC");
  await page.waitForURL((url) => url.searchParams.get("ordering") === "STUDENT_ASC");
  await settleFetches(page);
  await shown(page.locator("thead th[aria-sort='ascending']"));
  assert.match(await page.locator("tbody tr").first().innerText(), /Ana Student/);
  assert.equal(calls(sortFixture, "counselingListMyCases").at(-1).query.ordering, "STUDENT_ASC");
  await page.getByRole("button", { name: /Sort student z–a/i }).click();
  await page.waitForURL((url) => url.searchParams.get("ordering") === "STUDENT_DESC");
  await settleFetches(page);
  await shown(page.locator("thead th[aria-sort='descending']"));
  assert.match(await page.locator("tbody tr").first().innerText(), /Zed Student/);
  await page.getByLabel("Sort", { exact: true }).selectOption("OLDEST_OPENED");
  await page.waitForURL((url) => url.searchParams.get("ordering") === "OLDEST_OPENED");
  await settleFetches(page);
  assert.equal(calls(sortFixture, "counselingListMyCases").at(-1).query.ordering, "OLDEST_OPENED");
});

const pageFixture = casesFixture({ list: Array.from({ length: 22 }, (_, index) => summary(detail({ id: `c2000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, reference_code: `CASE-2026-${String(index + 10).padStart(6, "0")}` }))) });
await check("my-cases-pagination-preserves-search-and-sort", `${root}?search=CW1T&ordering=LATEST_OPENED`, { handler: pageFixture.handler }, async (page) => {
  const pager = page.getByRole("navigation", { name: "Case results pages", exact: true });
  await shown(pager);
  assert.equal(await page.locator("tbody tr").count(), 20);
  assert.equal(await pager.getByRole("button", { name: "Previous", exact: true }).isDisabled(), true);
  await pager.getByRole("button", { name: "Next", exact: true }).click();
  await page.waitForURL((url) => url.searchParams.get("page") === "2");
  await shown(pager.getByText("Page 2", { exact: true }));
  assert.equal(await page.locator("tbody tr").count(), 2);
  assert.equal(await pager.getByRole("button", { name: "Next", exact: true }).isDisabled(), true);
  assert.deepEqual(calls(pageFixture, "counselingListMyCases").at(-1).query, { search: "CW1T", status: "ACTIVE", ordering: "LATEST_OPENED", page: "2", page_size: "20" });
  await pager.getByRole("button", { name: "Previous", exact: true }).click();
  await page.waitForURL((url) => !url.searchParams.has("page"));
  await shown(pager.getByText("Page 1", { exact: true }));
});

const intakeFixture = casesFixture({ list: [] });
await check("open-intake-student-search-review-zero-active", newPath, { handler: intakeFixture.handler }, async (page) => {
  await shown(page.getByRole("heading", { name: "Choose the Student", exact: true }));
  await page.getByLabel("Search for a Student", { exact: true }).fill("CW1T-001");
  await settleFetches(page);
  await page.getByRole("search", { name: "Students", exact: true }).getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("button", { name: new RegExp(student.display_name) }).click();
  await page.waitForURL((url) => url.searchParams.get("student") === ids.student);
  await shown(page.getByRole("heading", { name: "Your active cases with this Student", exact: true }));
  await shown(page.getByText("None. This will be your first active case with this Student.", { exact: true }));
  assert.match(await page.locator("main").innerText(), /Responsible counselor\s+You/);
  assert.match(await page.locator("main").innerText(), /Counseling intake/);
  assert.match(await page.locator("main").innerText(), /Session included\s+None yet/);
  await screenshot(page, "open-intake-review");
  await page.getByRole("button", { name: "Open case", exact: true }).click();
  await page.waitForURL((url) => url.pathname === `${root}/cases/${ids.openedCase}`);
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  assert.deepEqual(calls(intakeFixture, "counselingOpenCase").map(({ body }) => body), [{ origin: "INTAKE", student_id: ids.student, known_active_case_ids: [] }]);
  assert.equal(await completedCount(page).innerText(), "0");
});

const activeFixture = casesFixture({ active: [summary(detail()), summary(detail({ id: ids.otherCase, reference_code: "CASE-2026-000002" }))] });
await check("open-intake-existing-active-case-links-and-another-case", `${newPath}?student=${ids.student}`, { handler: activeFixture.handler }, async (page) => {
  for (const [name, id] of [["CASE-2026-000001", ids.case], ["CASE-2026-000002", ids.otherCase]]) {
    const link = page.getByRole("link", { name, exact: true });
    await shown(link);
    assert.equal(await link.getAttribute("href"), `${root}/cases/${id}`);
  }
  await shown(page.getByText("Open another case only for a different concern. To continue one of these, open it and add the session there.", { exact: true }));
  await page.getByRole("button", { name: "Open another case", exact: true }).click();
  await page.waitForURL((url) => url.pathname.endsWith(ids.openedCase));
  assert.deepEqual(calls(activeFixture, "counselingOpenCase")[0].body.known_active_case_ids, [ids.case, ids.otherCase]);
});

for (const [origin, source, label] of [["APPOINTMENT", ids.appointment, "Appointment"], ["ENCOUNTER", ids.session, "Recorded session"], ["ROUTINE_INTERVIEW", ids.routine, "Routine Interview"]]) {
  const fixture = casesFixture();
  await check(`open-${origin.toLowerCase()}-uses-url-origin-and-source`, `${newPath}?origin=${origin}&source=${source}`, { handler: fixture.handler }, async (page) => {
    await shown(page.getByRole("heading", { name: "Your active cases with this Student", exact: true }));
    assert.equal(await page.getByLabel("Search for a Student", { exact: true }).count(), 0, "The authorized source fixes the Student");
    assert.match(await page.locator("main").innerText(), new RegExp(label));
    assert.deepEqual(calls(fixture, "counselingGetCaseOpeningContext")[0].query, { origin, source_id: source });
    await page.getByRole("button", { name: "Open case", exact: true }).click();
    await page.waitForURL((url) => url.pathname.endsWith(ids.openedCase));
    await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
    assert.deepEqual(calls(fixture, "counselingOpenCase")[0].body, { origin, source_id: source, known_active_case_ids: [] });
    assert.equal(await completedCount(page).innerText(), origin === "APPOINTMENT" ? "0" : "1");
  });
}

const reviewFixture = casesFixture({ openMode: "review" });
await check("open-409-reloads-active-cases-without-resubmitting", `${newPath}?student=${ids.student}`, { handler: reviewFixture.handler }, async (page) => {
  await shown(page.getByRole("button", { name: "Open case", exact: true }));
  await settleFetches(page);
  const readsBefore = reviewFixture.contextReads;
  await page.getByRole("button", { name: "Open case", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "Your active cases for this Student changed. Review them before opening a case." }));
  await shown(page.getByRole("link", { name: "CASE-2026-000002", exact: true }));
  await settleFetches(page);
  assert.equal(reviewFixture.contextReads, readsBefore + 1, "The conflict causes exactly one context reload");
  assert.equal(calls(reviewFixture, "counselingOpenCase").length, 1);
  assert.equal(new URL(page.url()).pathname, newPath);
  await shown(page.getByRole("button", { name: "Open another case", exact: true }));
  assert.equal(await page.getByText(/Session recorded|Case opened successfully/).count(), 0);
});

for (const mode of ["network", "server"]) {
  const fixture = casesFixture({ openMode: mode });
  await check(`open-${mode}-failure-shows-unconfirmed-result`, `${newPath}?student=${ids.student}`, { handler: fixture.handler }, async (page) => {
    await page.getByRole("button", { name: "Open case", exact: true }).click();
    await shown(page.getByRole("alert").filter({ hasText: "Couldn't confirm whether the case was opened. Check your cases before trying again to avoid a duplicate." }));
    assert.equal(await page.getByRole("link", { name: "Check my cases", exact: true }).getAttribute("href"), root);
    assert.equal(await page.getByRole("button", { name: "Open case", exact: true }).count(), 0);
    assert.equal(calls(fixture, "counselingOpenCase").length, 1);
    assert.equal(new URL(page.url()).pathname, newPath);
    assert.equal(await page.getByRole("status").filter({ hasText: /opened|success/i }).count(), 0);
  });
}

await check("case-overview-facts-session-access-and-history", casePath, { handler: casesFixture().handler }, async (page) => {
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  assert.equal(await page.locator("main h1").count(), 1);
  assert.deepEqual(await page.locator("main h2").allTextContents(), ["Case", "Continuity", "Next actions", "Appointments", "Sessions", "Case history"]);
  assert.equal(await completedCount(page).innerText(), "2");
  assert.match(await page.locator('[aria-labelledby="case-details-heading"]').innerText(), /Synthetic CW-1 Counselor/);
  assert.match(await page.locator("main").innerText(), /CASE-2026-000001/);
  await shown(page.getByText("No upcoming appointment is linked to this case.", { exact: true }));
  await shown(page.getByText("No pending next action in this case.", { exact: true }));
  const session = page.getByRole("link", { name: /Jan 6, 2026/ });
  assert.equal(await session.getAttribute("href"), `${root}/encounters/${ids.session}?return_to=${encodeURIComponent(casePath)}`);
  const inaccessible = page.locator("tbody tr").filter({ hasText: "Synthetic Other Counselor" });
  assert.equal(await inaccessible.getByRole("link").count(), 0, "A case does not grant source-record access");
  assert.equal(await inaccessible.locator("td").nth(3).innerText(), "—", "The inaccessible Appointment reference is withheld");
  assert.doesNotMatch(await inaccessible.innerText(), /APT-/);
  const history = page.locator('[aria-labelledby="case-history-heading"]');
  assert.match(await history.innerText(), /Case opened from a Counseling intake/);
  assert.match(await history.innerText(), /added to the case/);
  assert.match(await history.innerText(), /removed from the case: it was added by mistake/);
  await screenshot(page, "case-overview-desktop");
});

const originFixture = casesFixture({ detail: { origin: "APPOINTMENT", source: { appointment: { id: ids.appointment, reference_code: "APT-CW1T-0001", starts_at: "2026-01-06T01:00:00Z", status: "SCHEDULED" }, encounter_id: null, routine_interview_id: null }, sessions: [], session_count: 0, latest_session_at: null, unlinked_origin_session: candidate() } });
await check("case-unlinked-origin-session-notice-and-add", casePath, { handler: originFixture.handler }, async (page) => {
  await shown(page.getByText(/for the Appointment this case started from isn't in a case yet\./));
  assert.equal(await completedCount(page).innerText(), "0");
  await page.getByRole("button", { name: "Add to this case", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "Session added to this case." }));
  assert.equal(await completedCount(page).innerText(), "1");
  assert.equal(await page.getByRole("button", { name: "Add to this case", exact: true }).count(), 0);
  assert.equal(await page.getByRole("link", { name: "Add next action", exact: true }).count(), 1);
  assert.equal(await page.getByRole("button", { name: "Link appointment", exact: true }).count(), 1);
  assert.deepEqual(calls(originFixture, "counselingLinkCaseSession")[0].body, { encounter_id: ids.candidate, expected_version: 4 });
});

const addFixture = casesFixture();
await check("add-recorded-session-candidates-required-selection-success", casePath, { handler: addFixture.handler }, async (page) => {
  await addTrigger(page).click();
  const dialog = addDialog(page);
  await shown(dialog);
  assert.equal(await dialog.getByRole("button", { name: "Add to case", exact: true }).isDisabled(), true);
  await pickCandidate(page);
  await dialog.getByRole("button", { name: "Add to case", exact: true }).click();
  await hidden(dialog);
  assert.equal(await completedCount(page).innerText(), "3");
  await shown(page.getByRole("status").filter({ hasText: "Session added to this case." }));
  assert.deepEqual(calls(addFixture, "counselingLinkCaseSession")[0].body, { encounter_id: ids.candidate, expected_version: 4 });
  await shown(page.getByRole("link", { name: /Jan 8, 2026/ }));
  assert.equal(calls(addFixture, "counselingListCaseSessionCandidates").length, 1);
});

await check("add-recorded-session-empty", casePath, { handler: casesFixture({ candidates: [] }).handler }, async (page) => {
  await addTrigger(page).click();
  const dialog = addDialog(page);
  await shown(dialog.getByText("Every session you recorded with this Student is already in a case.", { exact: true }));
  assert.equal(await dialog.getByRole("button", { name: "Add to case", exact: true }).isDisabled(), true);
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await hidden(dialog);
});

const candidateRetry = casesFixture({ state: { candidateError: true } });
await check("add-recorded-session-candidate-failure-retry", casePath, { handler: candidateRetry.handler }, async (page) => {
  await addTrigger(page).click();
  const dialog = addDialog(page);
  await shown(dialog.getByRole("alert"));
  assert.match(await dialog.getByRole("alert").innerText(), /Couldn't load your recorded sessions\./);
  candidateRetry.candidateError = false;
  await dialog.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(dialog.getByRole("button", { name: /Jan 8, 2026/ }));
  assert.equal(candidateRetry.candidateReads, 2);
});

const staleAdd = casesFixture({ linkMode: "changed" });
await check("add-409-closes-dialog-reloads-and-returns-focus", casePath, { handler: staleAdd.handler }, async (page) => {
  await shown(addTrigger(page));
  await settleFetches(page);
  const readsBefore = staleAdd.detailReads;
  await keyboardActivate(page, addTrigger(page));
  const dialog = await pickCandidate(page);
  await dialog.getByRole("button", { name: "Add to case", exact: true }).click();
  await hidden(dialog);
  await shown(page.getByRole("status").filter({ hasText: staleMessage }));
  await focused(addTrigger(page));
  await settleFetches(page);
  assert.equal(staleAdd.detailReads, readsBefore + 1, "The conflict causes exactly one case reload");
  assert.equal(calls(staleAdd, "counselingLinkCaseSession").length, 1);
  assert.equal(await completedCount(page).innerText(), "2");
});

const candidatePages = casesFixture({ candidates: Array.from({ length: 11 }, (_, index) => candidate({ encounter_id: `c3000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, started_at: `2026-01-${String(index + 8).padStart(2, "0")}T01:00:00Z`, ended_at: `2026-01-${String(index + 8).padStart(2, "0")}T02:00:00Z` })) });
await check("add-from-last-candidate-page-reopens-on-first-page", casePath, { handler: candidatePages.handler }, async (page) => {
  await addTrigger(page).click();
  const dialog = addDialog(page);
  const pager = dialog.getByRole("navigation", { name: "Recorded session pages", exact: true });
  await shown(pager);
  await pager.getByRole("button", { name: "Next", exact: true }).click();
  await shown(dialog.getByRole("button", { name: /Jan 18, 2026/ }));
  await dialog.getByRole("button", { name: /Jan 18, 2026/ }).click();
  await dialog.getByRole("button", { name: "Add to case", exact: true }).click();
  await hidden(dialog);
  await addTrigger(page).click();
  await shown(dialog.getByRole("button", { name: /Jan 8, 2026/ }));
  assert.equal(await dialog.getByRole("list", { name: "Recorded sessions not in a case", exact: true }).getByRole("button").count(), 10);
  assert.equal(calls(candidatePages, "counselingListCaseSessionCandidates").at(-1).query.page, "1");
});

const addPending = deferred();
const pendingAddFixture = casesFixture({ state: { linkHold: addPending.promise } });
await check("add-pending-prevents-dismissal-and-duplicate-save", casePath, { handler: pendingAddFixture.handler }, async (page) => {
  try {
    await addTrigger(page).click();
    const dialog = await pickCandidate(page);
    await dialog.getByRole("button", { name: "Add to case", exact: true }).click();
    await shown(dialog.getByRole("button", { name: "Adding session…", exact: true }));
    assert.equal(await dialog.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
    assert.equal(await dialog.getByRole("button", { name: "Close dialog", exact: true }).count(), 0);
    await page.keyboard.press("Escape");
    await shown(dialog);
    addPending.release();
    await hidden(dialog);
    assert.equal(calls(pendingAddFixture, "counselingLinkCaseSession").length, 1);
  } finally { addPending.release(); }
});

const removeFixture = casesFixture();
await check("remove-requires-reason-names-session-updates-count-and-history", casePath, { handler: removeFixture.handler }, async (page) => {
  await keyboardActivate(page, removeTrigger(page));
  const dialog = removeDialog(page);
  await shown(dialog);
  assert.match(await dialog.innerText(), /The session of Jan 6, 2026(?:,| at) 9:00\sAM will no longer count in this case\./);
  assert.match(await dialog.innerText(), /Its record, its author and any published Student Session Summary stay as they are\./);
  assert.equal(await dialog.getByRole("button", { name: "Remove from case", exact: true }).isDisabled(), true);
  assert.equal(calls(removeFixture, "counselingUnlinkCaseSession").length, 0);
  await chooseRemovalReason(dialog);
  await dialog.getByRole("button", { name: "Remove from case", exact: true }).click();
  await hidden(dialog);
  assert.equal(await completedCount(page).innerText(), "1");
  assert.equal(await page.getByRole("link", { name: /Jan 6, 2026/ }).count(), 0);
  assert.deepEqual(calls(removeFixture, "counselingUnlinkCaseSession")[0], { operationId: "counselingUnlinkCaseSession", encounterId: ids.session, body: { reason: "LINKED_BY_MISTAKE", expected_version: 4 } });
  await focused(page.locator("#case-sessions-heading"));
  await shown(page.getByRole("status").filter({ hasText: "Session removed from this case." }));
  assert.match(await page.locator('[aria-labelledby="case-history-heading"]').innerText(), /Session of Jan 6, 2026(?:,| at) 9:00\sAM removed from the case: it was added by mistake/);
});

const failedRemove = casesFixture({ unlinkMode: "failure" });
await check("remove-failure-keeps-dialog-and-reason", casePath, { handler: failedRemove.handler }, async (page) => {
  await removeTrigger(page).click();
  const dialog = removeDialog(page);
  await chooseRemovalReason(dialog, "NOT_PART_OF_THIS_CASE");
  await dialog.getByRole("button", { name: "Remove from case", exact: true }).click();
  await shown(dialog.getByRole("alert"));
  assert.equal(await dialog.getByLabel("Why it doesn't belong here", { exact: true }).inputValue(), "NOT_PART_OF_THIS_CASE");
  assert.equal(await dialog.getByRole("button", { name: "Remove from case", exact: true }).isEnabled(), true);
  assert.equal(await completedCount(page).innerText(), "2");
  assert.equal(calls(failedRemove, "counselingUnlinkCaseSession").length, 1);
  assert.equal(await page.getByRole("status").filter({ hasText: "Session removed from this case." }).count(), 0);
});

const removePending = deferred();
const pendingRemove = casesFixture({ state: { unlinkHold: removePending.promise } });
await check("remove-pending-keeps-confirmation-open", casePath, { handler: pendingRemove.handler }, async (page) => {
  try {
    await removeTrigger(page).click();
    const dialog = removeDialog(page);
    await chooseRemovalReason(dialog);
    await dialog.getByRole("button", { name: "Remove from case", exact: true }).click();
    await shown(dialog.getByRole("button", { name: "Removing session…", exact: true }));
    assert.equal(await dialog.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
    await page.keyboard.press("Escape");
    await shown(dialog);
    removePending.release();
    await hidden(dialog);
    assert.equal(calls(pendingRemove, "counselingUnlinkCaseSession").length, 1);
  } finally { removePending.release(); }
});

const staleRemove = casesFixture({ unlinkMode: "changed" });
await check("remove-409-closes-and-reloads-without-resubmitting", casePath, { handler: staleRemove.handler }, async (page) => {
  await shown(removeTrigger(page));
  await settleFetches(page);
  const readsBefore = staleRemove.detailReads;
  await removeTrigger(page).click();
  const dialog = removeDialog(page);
  await chooseRemovalReason(dialog);
  await dialog.getByRole("button", { name: "Remove from case", exact: true }).click();
  await hidden(dialog);
  await shown(page.getByRole("status").filter({ hasText: staleMessage }));
  await settleFetches(page);
  assert.equal(staleRemove.detailReads, readsBefore + 1, "The conflict causes exactly one case reload");
  assert.equal(calls(staleRemove, "counselingUnlinkCaseSession").length, 1);
  assert.equal(await completedCount(page).innerText(), "2");
});

await check("dialog-cancel-returns-focus-to-each-opener", casePath, { handler: casesFixture().handler }, async (page) => {
  await keyboardActivate(page, addTrigger(page));
  const add = addDialog(page);
  await shown(add);
  await page.keyboard.press("Escape");
  await hidden(add);
  await focused(addTrigger(page));
  await keyboardActivate(page, removeTrigger(page));
  const remove = removeDialog(page);
  await shown(remove);
  await keyboardActivate(page, remove.getByRole("button", { name: "Cancel", exact: true }));
  await hidden(remove);
  await focused(removeTrigger(page));
});

const recordingFixture = casesFixture();
await check("record-from-case-fixes-student-and-sends-case-id", casePath, { handler: recordingFixture.handler }, async (page) => {
  await page.getByRole("button", { name: "Record session for this case", exact: true }).click();
  await page.getByRole("button", { name: "Walk-in / called-in / referred", exact: true }).click();
  await shown(page.getByLabel("Actual start", { exact: true }));
  assert.equal(await page.getByLabel("Search for a Student", { exact: true }).count(), 0);
  assert.equal(await page.getByRole("list", { name: "Students", exact: true }).count(), 0);
  const form = page.locator("form").filter({ has: page.getByRole("group", { name: "Actual counseling interaction", exact: true }) });
  assert.match(await form.innerText(), new RegExp(student.display_name));
  await form.getByLabel("Actual start", { exact: true }).fill("2026-01-09T09:00");
  await form.getByLabel("Actual end", { exact: true }).fill("2026-01-09T10:00");
  await form.getByRole("button", { name: "Record encounter", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "Session recorded and added to this case." }));
  assert.equal(await completedCount(page).innerText(), "3");
  assert.deepEqual(calls(recordingFixture, "counselingCreateEncounter")[0].body, { student_id: ids.student, entry_mode: "WALK_IN", delivery_mode: "IN_PERSON", case_id: ids.case, started_at: "2026-01-09T01:00:00.000Z", ended_at: "2026-01-09T02:00:00.000Z" });
  assert.equal(new URL(page.url()).pathname, casePath);
});

const recordsFixture = casesFixture();
await check("session-records-case-column-and-case-filter", `${root}/encounters`, { handler: recordsFixture.handler }, async (page, { requests }) => {
  await shown(page.getByRole("heading", { name: "Session records", exact: true }));
  await shown(page.getByRole("columnheader", { name: "Case", exact: true }));
  const caseLink = page.getByRole("link", { name: "CASE-2026-000001", exact: true });
  assert.equal(await caseLink.getAttribute("href"), casePath);
  await shown(page.getByText("In another case", { exact: true }));
  await shown(page.getByRole("table").getByText("Not in a case", { exact: true }));
  await settleFetches(page);
  await page.getByRole("button", { name: "Filters", exact: true }).click();
  await page.getByLabel("Case", { exact: true }).selectOption("UNLINKED");
  await page.getByRole("button", { name: "Apply filters", exact: true }).click();
  await page.waitForURL((url) => url.searchParams.get("case_link") === "UNLINKED");
  await shown(page.getByRole("table").getByText("Not in a case", { exact: true }));
  assert.equal(await page.locator("tbody tr").count(), 1);
  assert.equal(new URLSearchParams(requests.filter((request) => request.pathname === "/api/v1/counseling/me/encounters").at(-1).search).get("case_link"), "UNLINKED");
  await page.getByRole("button", { name: /^Filters/ }).click();
  await page.getByLabel("Case", { exact: true }).selectOption("LINKED");
  await page.getByRole("button", { name: "Apply filters", exact: true }).click();
  await page.waitForURL((url) => url.searchParams.get("case_link") === "LINKED");
  await shown(page.getByText("In another case", { exact: true }));
  assert.equal(await page.locator("tbody tr").count(), 2);
});

const noView = { ...user(), capabilities: user().capabilities.filter((capability) => capability !== "counseling.view_assigned") };
for (const [name, account] of [["non-counselor", user("GUIDANCE_OFFICE_ASSISTANT")], ["counselor-without-view", noView]]) {
  for (const [screen, path] of [["my-cases", root], ["overview", casePath]]) {
    const fixture = casesFixture({ account });
    await check(`access-${name}-${screen}-unavailable`, path, { handler: fixture.handler }, async (page, { requests }) => {
      await shown(page.getByText("You don't have access to Counseling.", { exact: true }));
      await settleFetches(page);
      assert.equal(requests.filter((request) => request.pathname.startsWith(casesAPI)).length, 0, "Unavailable pages make no case request");
      assert.equal(await page.getByRole("button", { name: /Record session|Add recorded session|Remove the session/ }).count(), 0);
    });
  }
}

await check("access-non-counselor-cannot-open-case", `${newPath}?student=${ids.student}`, { handler: casesFixture({ account: user("GUIDANCE_OFFICE_ASSISTANT") }).handler }, async (page, { requests }) => {
  await shown(page.getByText("You don't have access to open Counseling cases.", { exact: true }));
  await settleFetches(page);
  assert.equal(requests.filter((request) => request.pathname.startsWith(casesAPI)).length, 0);
});

await check("case-404-shows-no-access-without-case-facts", casePath, { handler: casesFixture({ caseError: "counseling_case_not_found" }).handler }, async (page) => {
  await shown(page.getByRole("alert").filter({ hasText: "You don't have access to this case." }));
  assert.equal(await page.getByRole("heading", { name: student.display_name, exact: true }).count(), 0);
  assert.equal(await page.getByText("CASE-2026-000001", { exact: true }).count(), 0);
  assert.equal(await page.getByRole("table").count(), 0);
  assert.equal(await addTrigger(page).count(), 0);
});

await check("case-read-only-hides-record-add-remove-and-origin-add", casePath, { handler: casesFixture({ detail: { can_manage: false, unlinked_origin_session: candidate() } }).handler }, async (page) => {
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  await shown(page.getByRole("table", { name: "Completed sessions in this case", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Record session for this case", exact: true }).count(), 0);
  assert.equal(await addTrigger(page).count(), 0);
  assert.equal(await page.getByRole("button", { name: /^Remove the session/ }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Add to this case", exact: true }).count(), 0);
  assert.equal(await page.getByRole("link", { name: "Add next action", exact: true }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Link appointment", exact: true }).count(), 0);
  assert.equal(await completedCount(page).innerText(), "2");
});

async function phoneTableAndActions(page, width) {
  await noHorizontalOverflow(page);
  const scroller = page.getByRole("table").locator("..");
  const tableGeometry = await scroller.evaluate((element) => ({ width: element.clientWidth, scroll: element.scrollWidth, overflow: getComputedStyle(element).overflowX }));
  assert.equal(tableGeometry.overflow, "auto", "The wide table owns its horizontal scroller");
  assert.ok(tableGeometry.scroll > tableGeometry.width, "The table retains readable columns on phones");
  const allActions = await page.locator("main [data-page-action-label]").evaluateAll((labels) => labels.map((label) => {
    const control = label.closest("a, button");
    const box = control.getBoundingClientRect();
    return { name: label.textContent, x: box.x, right: box.right, top: box.top, height: box.height };
  }));
  const actions = await page.locator("main [data-page-header-actions] [data-page-action-label]").evaluateAll((labels) => labels.map((label) => {
    const box = label.closest("a, button").getBoundingClientRect();
    return { top: box.top, height: box.height };
  }));
  assert.equal(actions.length, 2, "The page retains its two primary commands");
  for (const action of allActions) {
    assert.ok(action.x >= 0 && action.right <= width + 1, `Page action ${action.name} stays inside the phone`);
    assert.ok(action.height >= 44, "Page actions retain their touch targets");
  }
  if (width === 320) assert.ok(actions[1].top >= actions[0].top + actions[0].height, "Page actions wrap at narrow phone width");
}

for (const [device, width] of [["phone", 390], ["narrowPhone", 320]]) {
  await check(`my-cases-${width}-table-actions-and-reachable-floating-search`, root, { device, handler: casesFixture().handler }, async (page) => {
    await shown(page.getByRole("link", { name: student.display_name, exact: true }));
    await phoneTableAndActions(page, width);
    const search = searchField(page);
    await tabTo(page, search);
    await focused(search);
    const geometry = await search.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { x: box.x, right: box.right, top: box.top, bottom: box.bottom, height: innerHeight, hit: element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)) };
    });
    assert.ok(geometry.x >= 0 && geometry.right <= width + 1 && geometry.top >= 0 && geometry.bottom <= geometry.height, "Floating search stays inside the viewport");
    assert.equal(geometry.hit, true, "The floating search is not covered by another control");
    await screenshot(page, `my-cases-${width}`);
  });

  await check(`case-overview-${width}-table-actions-and-dialogs`, casePath, { device, handler: casesFixture().handler }, async (page) => {
    await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
    await phoneTableAndActions(page, width);
    await screenshot(page, `case-overview-${width}`);
    await addTrigger(page).click();
    await shown(addDialog(page));
    await noHorizontalOverflow(page);
    assert.ok(await addDialog(page).evaluate((element) => element.scrollWidth <= element.clientWidth + 1), "Add dialog has no horizontal overflow");
    await screenshot(page, `add-session-${width}`);
    await addDialog(page).getByRole("button", { name: "Cancel", exact: true }).click();
    await removeTrigger(page).click();
    await shown(removeDialog(page));
    await noHorizontalOverflow(page);
    assert.ok(await removeDialog(page).evaluate((element) => element.scrollWidth <= element.clientWidth + 1), "Remove dialog has no horizontal overflow");
    await screenshot(page, `remove-session-${width}`);
  });
}

const keyboardFixture = casesFixture({ list: [] });
await check("keyboard-only-intake-open-add-remove-and-dialog-focus", root, { handler: keyboardFixture.handler }, async (page) => {
  await keyboardActivate(page, page.getByRole("link", { name: "Open case", exact: true }));
  await page.waitForURL((url) => url.pathname === newPath);
  const search = page.getByLabel("Search for a Student", { exact: true });
  await tabTo(page, search);
  await page.keyboard.type("CW1T-001");
  await settleFetches(page);
  await keyboardActivate(page, page.getByRole("search", { name: "Students", exact: true }).getByRole("button", { name: "Search", exact: true }));
  await keyboardActivate(page, page.getByRole("list", { name: "Students", exact: true }).getByRole("button", { name: new RegExp(student.display_name) }));
  await page.waitForURL((url) => url.searchParams.get("student") === ids.student);
  await shown(page.getByRole("heading", { name: "Your active cases with this Student", exact: true }));
  await keyboardActivate(page, page.getByRole("button", { name: "Open case", exact: true }));
  await page.waitForURL((url) => url.pathname.endsWith(ids.openedCase));
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  assert.equal(await completedCount(page).innerText(), "0");

  await keyboardActivate(page, addTrigger(page));
  await shown(addDialog(page));
  await page.keyboard.press("Escape");
  await hidden(addDialog(page));
  await focused(addTrigger(page));
  await keyboardActivate(page, addTrigger(page));
  await keyboardActivate(page, addDialog(page).getByRole("button", { name: /Jan 8, 2026/ }));
  await keyboardActivate(page, addDialog(page).getByRole("button", { name: "Add to case", exact: true }));
  await hidden(addDialog(page));
  await focused(addTrigger(page));
  assert.equal(await completedCount(page).innerText(), "1");

  await keyboardActivate(page, removeTrigger(page, 8));
  await shown(removeDialog(page));
  await keyboardActivate(page, removeDialog(page).getByRole("button", { name: "Cancel", exact: true }));
  await hidden(removeDialog(page));
  await focused(removeTrigger(page, 8));
  await keyboardActivate(page, removeTrigger(page, 8));
  await tabTo(page, removeDialog(page).getByLabel("Why it doesn't belong here", { exact: true }), "Tab");
  await page.keyboard.press("i");
  await page.keyboard.press("Tab");
  const selectedReason = await removeDialog(page).getByLabel("Why it doesn't belong here", { exact: true }).inputValue();
  assert.equal(selectedReason, "BELONGS_TO_ANOTHER_CASE", `Keyboard selected removal reason; received ${JSON.stringify(selectedReason)}`);
  await keyboardActivate(page, removeDialog(page).getByRole("button", { name: "Remove from case", exact: true }));
  await hidden(removeDialog(page));
  await focused(page.locator("#case-sessions-heading"));
  assert.equal(await completedCount(page).innerText(), "0");
  assert.equal(await page.getByRole("link", { name: /Jan 8, 2026/ }).count(), 0);
  assert.deepEqual(calls(keyboardFixture, "counselingOpenCase")[0].body, { origin: "INTAKE", student_id: ids.student, known_active_case_ids: [] });
  assert.deepEqual(calls(keyboardFixture, "counselingLinkCaseSession")[0].body, { encounter_id: ids.candidate, expected_version: 1 });
  assert.deepEqual(calls(keyboardFixture, "counselingUnlinkCaseSession")[0].body, { reason: "BELONGS_TO_ANOTHER_CASE", expected_version: 2 });
  await screenshot(page, "keyboard-case-after-removal");
});

const appointmentDialog = page => page.getByRole("dialog", { name: "Link appointment", exact: true });
const unlinkAppointmentDialog = page => page.getByRole("alertdialog", { name: "Unlink this appointment from the case?", exact: true });
const appointmentPanel = page => page.locator('[aria-labelledby="case-appointments-heading"]');
const actionsPanel = page => page.locator('[aria-labelledby="case-next-actions-heading"]');
const linkAppointmentTrigger = page => appointmentPanel(page).getByRole("button", { name: "Link appointment", exact: true });
const unlinkAppointmentTrigger = page => appointmentPanel(page).getByRole("button", { name: "Unlink appointment APT-CW2T-0002", exact: true });
const returnedPath = (path, returnTo) => `${path}${path.includes("?") ? "&" : "?"}return_to=${encodeURIComponent(returnTo)}`;
async function fillAction(page, title = "Arrange a progress check") {
  await page.getByLabel("Action title", { exact: true }).fill(title);
  await page.getByLabel("Responsible staff member", { exact: true }).selectOption(ids.counselor);
  await page.getByLabel("Due date and time (Philippine Time)", { exact: true }).fill("2099-01-07T10:00");
  await page.getByRole("button", { name: "Create Follow-Up", exact: true }).click();
  await shown(page.getByRole("heading", { name: title, exact: true }));
}
async function selectAppointment(page) {
  await linkAppointmentTrigger(page).click();
  await shown(appointmentDialog(page));
  await appointmentDialog(page).getByLabel("Appointment", { exact: true }).selectOption(ids.nextAppointment);
}

const factsTask = followup();
const factsAppointment = appointmentCandidate();
const factsFixture = casesFixture({
  detail: { appointments: [caseAppointment()], next_appointment: factsAppointment },
  followups: [
    followup({ id: ids.successor, title: "Later pending action", due_at: "2099-01-09T02:00:00Z" }),
    followup({ id: "c2000000-0000-4000-8000-000000000001", title: null, status: "CANCELLED", updated_at: "2026-11-12T01:00:00Z" }),
    factsTask,
    followup({ id: "c2000000-0000-4000-8000-000000000002", title: "Completed action", status: "COMPLETED", updated_at: "2026-11-13T01:00:00Z" }),
  ],
});
await check("cw2-authorized-next-facts-panel-order-statuses-and-deadlines", casePath, { handler: factsFixture.handler, timezoneId: "America/Los_Angeles" }, async page => {
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  const facts = page.locator('[aria-labelledby="case-details-heading"]');
  assert.match(await facts.innerText(), /Next appointment\s+Jan 8, 2099(?:,| at) 9:00\sAM · APT-CW2T-0002/);
  assert.match(await facts.innerText(), /Next action\s+Check progress with Student\s+Due Jan 7, 2099(?:,| at) 10:00\sAM · Synthetic CW-1 Counselor/);
  assert.deepEqual(await actionsPanel(page).locator("li a").allTextContents(), ["Check progress with Student", "Later pending action", "Completed action", "Counseling Follow-Up"]);
  assert.deepEqual(await actionsPanel(page).locator("li").allTextContents().then(rows => rows.map(row => /Cancelled/.test(row) ? "Cancelled" : /Completed/.test(row) ? "Completed" : "Pending")), ["Pending", "Pending", "Completed", "Cancelled"]);
  assert.equal(await page.getByRole("link", { name: "Protected synthetic task detail", exact: true }).count(), 0);
  assert.equal(await page.getByText("Protected synthetic task detail", { exact: true }).count(), 0);
  assert.equal(await page.getByRole("button", { name: "Schedule session", exact: true }).count(), 0);
  assert.deepEqual(await page.locator('[data-page-header] [data-page-action-label]').allTextContents(), ["Record session for this case", "Close case"]);
  assert.equal(await actionsPanel(page).getByRole("link", { name: "Add next action", exact: true }).count(), 1, "Add next action moves into its own panel");
  assert.equal(await appointmentPanel(page).getByRole("button", { name: "Link appointment", exact: true }).count(), 1);
  assert.equal(await page.locator('[aria-labelledby="case-sessions-heading"]').getByRole("button", { name: "Add recorded session", exact: true }).count(), 1);
  await screenshot(page, "cw2-next-facts-desktop");
});

await check("cw2-empty-next-facts-and-unavailable-task-permission", casePath, { handler: casesFixture({ detail: { next_actions_available: false, can_add_next_action: false } }).handler }, async page => {
  await shown(page.getByText("No upcoming appointment is linked to this case.", { exact: true }));
  await shown(actionsPanel(page).getByText("Next actions are unavailable to your account.", { exact: true }));
  assert.equal(await page.getByRole("link", { name: "Add next action", exact: true }).count(), 0);
  assert.equal(await actionsPanel(page).getByRole("link").count(), 0);
});

for (const device of ["desktop", "narrowPhone"]) {
  const fixture = casesFixture();
  await check(`cw2-add-case-task-and-create-successor-${device}`, casePath, { device, handler: fixture.handler }, async page => {
    await page.getByRole("link", { name: "Add next action", exact: true }).click();
    await page.waitForURL(url => url.pathname === "/portal/follow-ups/new");
    await shown(page.getByText(student.display_name, { exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("case_id"), ids.case);
    assert.equal(new URL(page.url()).searchParams.get("return_to"), casePath);
    assert.equal(await page.getByLabel("Category", { exact: true }).inputValue(), "COUNSELING");
    assert.equal(await page.getByLabel("Linked case", { exact: true }).inputValue(), ids.case);
    assert.equal(await page.getByLabel("Linked case", { exact: true }).isDisabled(), true);
    assert.equal(await page.locator("#followup-student").count(), 0);
    await noHorizontalOverflow(page);
    await screenshot(page, `cw2-add-case-task-${device}`);
    await fillAction(page);
    assert.deepEqual(calls(fixture, "guidanceFollowupsCreate")[0].body, { student_id: ids.student, assigned_to_id: ids.counselor, category: "COUNSELING", title: "Arrange a progress check", due_at: "2099-01-07T02:00:00.000Z", description: null, case_id: ids.case, predecessor_id: null });
    await page.getByRole("link", { name: "Create next action", exact: true }).click();
    await page.waitForURL(url => url.pathname === "/portal/follow-ups/new");
    assert.equal(new URL(page.url()).searchParams.get("predecessor_id"), ids.action);
    assert.equal(new URL(page.url()).searchParams.has("student_name"), false);
    await shown(page.getByText(student.display_name, { exact: true }));
    assert.equal(await page.getByLabel("Linked case", { exact: true }).inputValue(), ids.case);
    assert.equal(await page.getByLabel("Action title", { exact: true }).inputValue(), "", "Confidential action content is not copied");
    assert.equal(await page.getByLabel("Task description (optional)", { exact: true }).inputValue(), "");
    await fillAction(page, "Continue the progress check");
    assert.equal(calls(fixture, "guidanceFollowupsCreate")[1].body.predecessor_id, ids.action);
    assert.equal(calls(fixture, "guidanceFollowupsCreate")[1].body.case_id, ids.case);
    const caseLink = page.getByRole("link", { name: "Case CASE-2026-000001", exact: true });
    await caseLink.click();
    await shown(actionsPanel(page).getByRole("link", { name: "Arrange a progress check", exact: true }));
    await shown(actionsPanel(page).getByRole("link", { name: "Continue the progress check", exact: true }));
    assert.equal(fixture.followups.length, 2);
    await noHorizontalOverflow(page);
  });
}

for (const removeCase of [false, true]) {
  const fixture = casesFixture();
  await check(`cw2-source-case-is-visible-preselected-and-${removeCase ? "removable" : "retained"}`, `/portal/follow-ups/new?source_kind=COUNSELING_ENCOUNTER&source_id=${ids.session}`, { handler: fixture.handler }, async page => {
    const choice = page.getByLabel("Linked case (optional)", { exact: true });
    await shown(choice);
    assert.equal(await choice.inputValue(), ids.case);
    assert.equal(await choice.isEnabled(), true);
    if (removeCase) await choice.selectOption("");
    await fillAction(page);
    const body = calls(fixture, "guidanceFollowupsCreate")[0].body;
    assert.equal(body.case_id, removeCase ? null : ids.case);
    assert.equal(body.source_kind, "COUNSELING_ENCOUNTER");
    assert.equal(body.source_id, ids.session);
    assert.equal(calls(fixture, "guidanceFollowupsEligibleStudents").length, 0);
  });
}

for (const origin of ["work", "follow-ups"]) {
  const listPath = origin === "work" ? "/portal/work?page=2" : "/portal/follow-ups?status=all&ordering=LATEST_DUE&page=2&page_size=1";
  const fixture = casesFixture({ followups: [followup({ id: ids.successor, title: "Other action", due_at: "2099-01-09T02:00:00Z" }), followup()] });
  await check(`cw2-${origin}-case-task-return-preserves-originating-filters`, listPath, { handler: fixture.handler }, async page => {
    if (origin === "work") {
      await shown(page.getByRole("link", { name: "View all Follow-Ups", exact: true }));
      assert.equal(await page.getByRole("link", { name: "View all Follow-Ups", exact: true }).getAttribute("href"), returnedPath("/portal/follow-ups", listPath));
      await page.getByRole("link", { name: "Open Follow-Up", exact: true }).last().click();
      await shown(page.getByRole("heading", { name: "Check progress with Student", exact: true }));
    } else {
      await shown(page.getByRole("link", { name: "Check progress with Student", exact: true }));
      assert.deepEqual(await page.locator("thead th").allTextContents(), ["Next action", "Due", "Student", "Responsible staff member", "Status", "Category"]);
      assert.match(await page.locator("tbody tr").innerText(), new RegExp(student.display_name));
      await page.getByRole("link", { name: "Check progress with Student", exact: true }).click();
      await shown(page.getByRole("heading", { name: "Check progress with Student", exact: true }));
    }
    const taskPath = `${new URL(page.url()).pathname}${new URL(page.url()).search}`;
    assert.equal(new URL(page.url()).searchParams.get("return_to"), listPath);
    await page.getByRole("link", { name: "Case CASE-2026-000001", exact: true }).click();
    await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("return_to"), taskPath);
    const caseReturnPath = `${new URL(page.url()).pathname}${new URL(page.url()).search}`;
    await page.locator('[aria-labelledby="case-details-heading"]').getByRole("link", { name: "Check progress with Student", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Check progress with Student", exact: true }));
    assert.equal(new URL(page.url()).searchParams.get("return_to"), caseReturnPath);
    await page.getByRole("link", { name: "Back to case", exact: true }).click();
    await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
    await page.getByRole("link", { name: "Back to Follow-Ups", exact: true }).click();
    await shown(page.getByRole("heading", { name: "Check progress with Student", exact: true }));
    await page.getByRole("link", { name: origin === "work" ? "Back to My work" : "Back to Follow-Ups", exact: true }).click();
    await page.waitForURL(url => `${url.pathname}${url.search}` === listPath);
    assert.equal(calls(fixture, "guidanceFollowupsCreate").length, 0);
  });
}

await check("cw2-counselor-followups-is-under-more-and-destination-search", casePath, { handler: casesFixture().handler }, async page => {
  const nav = page.getByRole("navigation", { name: "Portal navigation", exact: true });
  await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
  assert.equal(await nav.getByRole("link", { name: "Follow-ups", exact: true }).count(), 0);
  await nav.getByRole("button", { name: /^More,/ }).click();
  await shown(nav.getByRole("link", { name: "Follow-ups", exact: true }));
  await page.getByRole("button", { name: "Go to a COMPASS feature", exact: true }).click();
  const search = page.getByRole("dialog", { name: "Go to a COMPASS feature", exact: true });
  await shown(search);
  await search.getByRole("combobox").fill("Follow");
  const destination = search.getByRole("option").filter({ has: page.getByText("Follow-ups", { exact: true }) });
  await shown(destination);
  assert.equal(await destination.getAttribute("href"), "/portal/follow-ups");
  await page.keyboard.press("Escape");
});

for (const device of ["desktop", "narrowPhone"]) {
  const fixture = casesFixture();
  await check(`cw2-link-unlink-retains-provenance-and-focus-${device}`, casePath, { device, handler: fixture.handler }, async page => {
    await selectAppointment(page);
    await noHorizontalOverflow(page);
    await screenshot(page, `cw2-link-appointment-${device}`);
    await appointmentDialog(page).getByRole("button", { name: "Link to case", exact: true }).click();
    await hidden(appointmentDialog(page));
    await shown(page.getByRole("status").filter({ hasText: "Appointment linked to this case." }));
    await shown(unlinkAppointmentTrigger(page));
    assert.deepEqual(calls(fixture, "counselingLinkCaseAppointment")[0].body, { appointment_id: ids.nextAppointment, expected_version: 4 });
    assert.equal(await completedCount(page).innerText(), "2", "A scheduled Appointment is not a completed session");
    assert.match(await appointmentPanel(page).innerText(), /Linked by Synthetic CW-1 Counselor/);
    await unlinkAppointmentTrigger(page).click();
    const dialog = unlinkAppointmentDialog(page);
    await shown(dialog);
    assert.equal(await dialog.getByRole("button", { name: "Unlink appointment", exact: true }).isDisabled(), true);
    await chooseRemovalReason(dialog);
    await noHorizontalOverflow(page);
    await screenshot(page, `cw2-unlink-appointment-${device}`);
    await dialog.getByRole("button", { name: "Unlink appointment", exact: true }).click();
    await hidden(dialog);
    await focused(page.locator("#case-appointments-heading"));
    await shown(page.getByText("No upcoming appointment is linked to this case.", { exact: true }));
    assert.match(await appointmentPanel(page).innerText(), /Removed by Synthetic CW-1 Counselor.*Linked by mistake/s);
    assert.equal(fixture.detail.appointments.length, 1, "The removed link is retained");
    assert.equal(fixture.detail.appointments[0].appointment.status, "SCHEDULED", "Unlink never changes a meeting");
    assert.equal(await unlinkAppointmentTrigger(page).count(), 0);
    assert.deepEqual(calls(fixture, "counselingUnlinkCaseAppointment")[0].body, { reason: "LINKED_BY_MISTAKE", expected_version: 5 });
  });
}

for (const action of ["link", "unlink"]) for (const mode of ["changed", "failure"]) {
  const fixture = casesFixture({ detail: action === "unlink" ? { appointments: [caseAppointment()], next_appointment: appointmentCandidate() } : {}, [action === "link" ? "appointmentLinkMode" : "appointmentUnlinkMode"]: mode });
  await check(`cw2-appointment-${action}-${mode}-recovery`, casePath, { handler: fixture.handler }, async page => {
    await shown(page.getByRole("heading", { name: student.display_name, exact: true }));
    await settleFetches(page);
    const readsBefore = fixture.detailReads;
    if (action === "link") await selectAppointment(page);
    else { await unlinkAppointmentTrigger(page).click(); await chooseRemovalReason(unlinkAppointmentDialog(page)); }
    const dialog = action === "link" ? appointmentDialog(page) : unlinkAppointmentDialog(page);
    await dialog.getByRole("button", { name: action === "link" ? "Link to case" : "Unlink appointment", exact: true }).click();
    if (mode === "changed") {
      await hidden(dialog);
      await shown(page.getByRole("status").filter({ hasText: staleMessage }));
      await settleFetches(page);
      assert.equal(fixture.detailReads, readsBefore + 1);
    } else {
      await shown(dialog.getByRole("alert"));
      assert.equal(await dialog.getByLabel(action === "link" ? "Appointment" : "Why it doesn't belong here", { exact: true }).inputValue(), action === "link" ? ids.nextAppointment : "LINKED_BY_MISTAKE");
      assert.doesNotMatch(await dialog.innerText(), /Private diagnostic text/);
    }
    assert.equal(calls(fixture, action === "link" ? "counselingLinkCaseAppointment" : "counselingUnlinkCaseAppointment").length, 1, "Recovery never resubmits the action");
  });
}

for (const action of ["link", "unlink"]) {
  const pending = deferred();
  const fixture = casesFixture({ detail: action === "unlink" ? { appointments: [caseAppointment()], next_appointment: appointmentCandidate() } : {}, state: { [action === "link" ? "appointmentLinkHold" : "appointmentUnlinkHold"]: pending.promise } });
  await check(`cw2-appointment-${action}-pending-stable-dialog`, casePath, { handler: fixture.handler }, async page => {
    try {
      if (action === "link") await selectAppointment(page);
      else { await unlinkAppointmentTrigger(page).click(); await chooseRemovalReason(unlinkAppointmentDialog(page)); }
      const dialog = action === "link" ? appointmentDialog(page) : unlinkAppointmentDialog(page);
      await dialog.getByRole("button", { name: action === "link" ? "Link to case" : "Unlink appointment", exact: true }).click();
      await shown(dialog.getByRole("button", { name: action === "link" ? "Linking appointment…" : "Unlinking appointment…", exact: true }));
      assert.equal(await dialog.getByRole("button", { name: "Cancel", exact: true }).isDisabled(), true);
      assert.equal(await dialog.getByRole("button", { name: "Close dialog", exact: true }).count(), 0);
      await page.keyboard.press("Escape");
      await shown(dialog);
      pending.release();
      await hidden(dialog);
      assert.equal(calls(fixture, action === "link" ? "counselingLinkCaseAppointment" : "counselingUnlinkCaseAppointment").length, 1);
    } finally { pending.release(); }
  });
}

const appointmentLoading = deferred();
const appointmentLoadingFixture = casesFixture({ state: { appointmentCandidateHold: appointmentLoading.promise } });
await check("cw2-appointment-candidates-loading-then-empty", casePath, { handler: appointmentLoadingFixture.handler }, async page => {
  try {
    await linkAppointmentTrigger(page).click();
    const dialog = appointmentDialog(page);
    await shown(dialog.getByRole("status").filter({ hasText: "Loading appointments" }));
    assert.equal(await dialog.getByText("No eligible scheduled appointments are available to link.", { exact: true }).count(), 0);
    appointmentLoadingFixture.appointmentCandidates = [];
    appointmentLoading.release();
    await shown(dialog.getByText("No eligible scheduled appointments are available to link.", { exact: true }));
    assert.equal(await dialog.getByRole("button", { name: "Link to case", exact: true }).isDisabled(), true);
  } finally { appointmentLoading.release(); }
});

const appointmentRetryFixture = casesFixture({ state: { appointmentCandidateError: true } });
await check("cw2-appointment-candidates-error-retry-and-keyboard-focus", casePath, { handler: appointmentRetryFixture.handler }, async page => {
  await keyboardActivate(page, linkAppointmentTrigger(page));
  const dialog = appointmentDialog(page);
  await shown(dialog.getByRole("alert"));
  appointmentRetryFixture.appointmentCandidateError = false;
  await dialog.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(dialog.getByLabel("Appointment", { exact: true }));
  assert.equal(calls(appointmentRetryFixture, "counselingListCaseAppointmentCandidates").length, 2);
  await page.keyboard.press("Escape");
  await hidden(dialog);
  await focused(linkAppointmentTrigger(page));
});

const canonicalPredecessorFixture = casesFixture({ followups: [followup()] });
await check("cw2-case-only-predecessor-ignores-unrelated-url-source", `/portal/follow-ups/new?predecessor_id=${ids.action}&source_kind=COUNSELING_ENCOUNTER&source_id=${ids.inaccessibleSession}`, { handler: canonicalPredecessorFixture.handler }, async page => {
  await shown(page.getByText(student.display_name, { exact: true }));
  await fillAction(page);
  assert.equal(calls(canonicalPredecessorFixture, "guidanceFollowupsGetContext").length, 0);
  const body = calls(canonicalPredecessorFixture, "guidanceFollowupsCreate")[0].body;
  assert.equal(body.predecessor_id, ids.action);
  assert.equal(body.source_id, undefined);
  assert.equal(body.source_kind, undefined);
});

const offeredSession = candidate({ appointment: { id: ids.nextAppointment, reference_code: "APT-CW2T-0002" } });
const offerFixture = casesFixture({ candidates: [], detail: { origin: "APPOINTMENT", unlinked_origin_session: offeredSession, unlinked_appointment_sessions: [offeredSession], appointments: [caseAppointment({ appointment: appointmentCandidate({ status: "COMPLETED" }) })] } });
await check("cw2-recorded-linked-appointment-session-is-offered-once-and-linked-explicitly", casePath, { handler: offerFixture.handler }, async page => {
  await shown(page.getByText(/for Appointment APT-CW2T-0002 isn't in a case yet/));
  assert.equal(await page.getByRole("button", { name: "Add to this case", exact: true }).count(), 1, "The origin and linked Appointment offer the same session only once");
  assert.equal(calls(offerFixture, "counselingLinkCaseSession").length, 0);
  assert.equal(await completedCount(page).innerText(), "2");
  await shown(page.getByText("No upcoming appointment is linked to this case.", { exact: true }));
  await page.getByRole("button", { name: "Add to this case", exact: true }).click();
  await shown(page.getByRole("status").filter({ hasText: "Session added to this case." }));
  assert.equal(await completedCount(page).innerText(), "3");
  assert.equal(await page.getByRole("button", { name: "Add to this case", exact: true }).count(), 0);
  assert.deepEqual(calls(offerFixture, "counselingLinkCaseSession")[0].body, { encounter_id: ids.candidate, expected_version: 4 });
});

await finish();
