// Local synthetic API fixtures; real HTTP/DB scenarios live in the separate live runner.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { assessmentWorld, content, head, record, recordId, typeId } from "./support/assessment-records-fixtures.mjs";

const harness = await createBrowserHarness("assessment-records");
const { check, shown, hidden, finish, noHorizontalOverflow, screenshot } = harness;
const root = "/portal/assessment-records";
const detail = `${root}/${recordId}`;
const save = (page) => page.getByRole("button", { name: "Save record", exact: true });
const text = (page) => page.locator("main").innerText();
async function fill(page) {
  await shown(page.getByRole("radio", { name: /Maria Assessment/ }));
  await page.getByRole("radio", { name: /Maria Assessment/ }).check();
  await page.getByLabel("Assessment Type", { exact: true }).selectOption(typeId);
  await page.getByLabel("Administered on", { exact: true }).fill("2020-01-01");
  await page.getByLabel("Score / rating", { exact: true }).fill("88/100");
  await page.getByLabel("Result", { exact: true }).fill("Source result");
}
async function refreshSession(page) {
  await page.clock.fastForward(31_000);
  await page.evaluate(() => { window.dispatchEvent(new Event("offline")); window.dispatchEvent(new Event("online")); });
}

for (const width of [320, 375, 390, 430, 768, 1440]) {
  const world = assessmentWorld();
  await check(`${width}px list detail editor catalog and long confidential text wrap`, root, world.options({ viewport: { width, height: 900 } }), async (page) => {
    await shown(page.getByRole("link", { name: "Maria Assessment Student", exact: true }));
    for (const value of Object.values(content)) assert.ok(!(await text(page)).includes(value));
    await noHorizontalOverflow(page);
    await page.getByRole("button", { name: /Filters/ }).click();
    await shown(page.getByRole("dialog")); await noHorizontalOverflow(page);
    await page.keyboard.press("Escape");
    await page.getByRole("link", { name: "Maria Assessment Student", exact: true }).click();
    await shown(page.getByText(content.score, { exact: true }));
    world.records[0].interpretation = "LONG-CONFIDENTIAL-".repeat(150);
    await page.reload(); await shown(page.getByText(world.records[0].interpretation, { exact: true }));
    await noHorizontalOverflow(page);
    await page.getByRole("link", { name: /Edit assessment record/ }).click();
    await shown(page.getByRole("button", { name: "Save corrections" }));
    await noHorizontalOverflow(page);
    await page.getByRole("link", { name: "Back to Assessment Record", exact: true }).click();
    await page.getByRole("link", { name: "Back to Assessment Records", exact: true }).click();
    await page.getByRole("link", { name: /Record assessment result/ }).click();
    await shown(page.getByRole("radio", { name: /Maria Assessment/ })); await noHorizontalOverflow(page);
    await page.getByRole("link", { name: "Back to Assessment Records", exact: true }).click();
    await page.getByRole("link", { name: /Manage assessment types/ }).click();
    await shown(page.getByRole("button", { name: "Deactivate Career Aptitude Test", exact: true }));
    await noHorizontalOverflow(page);
    await page.getByRole("button", { name: "Deactivate Career Aptitude Test", exact: true }).click();
    await shown(page.getByRole("alertdialog")); await noHorizontalOverflow(page);
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    if (width === 320 || width === 1440) await screenshot(page, `${width}px-catalog`);
  });
}

for (const role of ["STUDENT", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
  const world = assessmentWorld({ account: { ...head(), role } });
  await check(`${role} override cannot open direct confidential route`, detail, world.options(), async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    assert.ok(!requests.some((item) => item.pathname.startsWith("/api/v1/assessment-records")));
    assert.ok(!(await text(page)).includes(content.score));
    assert.equal(await page.getByRole("link", { name: "Assessment Records", exact: true }).count(), 0);
  });
}
for (const path of [root, root + "/new", root + "/types", detail]) {
  const world = assessmentWorld({ account: { ...head(), capabilities: [], designations: [] } });
  await check(`Ordinary Counselor baseline direct route ${path}`, path, world.options(), async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    assert.ok(!requests.some((item) => item.pathname.startsWith("/api/v1/assessment-records")));
  });
}
{
  const world = assessmentWorld({ account: { ...head(), capabilities: ["assessment_records.view"], designations: [] } });
  await check("View-only Counselor has Records without correction or catalog actions", root, world.options(), async (page) => {
    await shown(page.getByRole("link", { name: "Maria Assessment Student" }));
    await hidden(page.getByRole("link", { name: /Record assessment result|Manage assessment types/ }));
    await page.getByRole("link", { name: "Maria Assessment Student" }).click();
    await shown(page.getByText(content.result, { exact: true }));
    await hidden(page.getByRole("link", { name: /Edit assessment record/ }));
  });
}
{
  const world = assessmentWorld({ account: { ...head(), designations: [] } });
  await check("Overridden Counselor manager cannot open Head catalog", root + "/types", world.options(), async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    assert.ok(!requests.some((item) => item.pathname.endsWith("/types")));
  });
}
{
  const world = assessmentWorld({ records: [] });
  await check("Empty catalog and empty record list remain usable", root, world.options(), async (page) => {
    await shown(page.getByText("No assessment results have been recorded."));
    world.types = []; await page.reload(); await shown(page.getByText("No assessment results have been recorded.")); await page.getByRole("link", { name: /Record assessment result/ }).click();
    await shown(page.getByText(/No active Assessment Types/));
    await page.getByLabel("Score / rating", { exact: true }).fill("draft source");
    assert.equal(await page.getByLabel("Score / rating", { exact: true }).getAttribute("type"), null);
  });
}
for (const status of [403, 404, 500]) {
  const world = assessmentWorld({ detailFailure: { status, code: status === 500 ? "assessment_record_content_unavailable" : "permission_denied" } });
  await check(`Detail ${status} safe error and retry`, detail, world.options(), async (page) => {
    await shown(page.getByRole("alert")); assert.ok(!(await text(page)).includes("PRIVATE-ERROR-SENTINEL"));
    assert.ok(!(await text(page)).includes(content.score));
    await shown(page.getByRole("button", { name: "Retry", exact: true }));
    world.detailFailure = null; await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByText(content.score, { exact: true }));
  });
}
{
  const world = assessmentWorld({ listFailure: { status: 503 } });
  await check("List failure retry and loading conceal confidential content", root, world.options(), async (page) => {
    await shown(page.getByRole("button", { name: "Retry", exact: true }));
    await page.waitForTimeout(300); world.listFailure = null;
    await page.getByRole("button", { name: "Retry", exact: true }).click();
    await shown(page.getByRole("link", { name: "Maria Assessment Student" }));
    assert.ok(!(await text(page)).includes(content.score));
  });
}
{
  const world = assessmentWorld();
  await check("Search draft applies only on submit and invalid dates stay in Filters", root, world.options(), async (page, { requests }) => {
    await shown(page.getByRole("link", { name: "Maria Assessment Student" }));
    const before = requests.filter((item) => item.pathname === "/api/v1/assessment-records").length;
    const search = page.getByRole("searchbox", { name: "Search Students or Assessment Types" });
    await search.fill("No match"); await page.waitForTimeout(300);
    assert.equal(requests.filter((item) => item.pathname === "/api/v1/assessment-records").length, before);
    await search.press("Enter"); await shown(page.getByText("No assessment records match these filters."));
    assert.equal(await search.inputValue(), "No match");
    await page.getByRole("button", { name: /Filters/ }).click();
    await page.getByLabel("Administered from").fill("2020-02-02");
    await page.getByLabel("Administered to").fill("2020-01-01");
    await page.getByRole("dialog").getByRole("button", { name: "Apply filters", exact: true }).click();
    await shown(page.getByText("From date must not follow To date."));
    assert.ok(!new URL(page.url()).searchParams.has("administered_from"));
  });
}
{
  const world = assessmentWorld({ records: Array.from({ length: 21 }, (_, index) => ({ ...record, id: `record-${index}`, student: { ...record.student, display_name: `Student ${index + 1}` } })) });
  await check("Bounded paging uses has_next without inventing a total", root, world.options(), async (page) => {
    await shown(page.getByRole("link", { name: "Student 1", exact: true }));
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await shown(page.getByRole("link", { name: "Student 21", exact: true }));
    await hidden(page.getByRole("link", { name: "Student 1", exact: true }));
    assert.equal(await page.getByRole("button", { name: "Next", exact: true }).isDisabled(), true);
  });
}
{
  const world = assessmentWorld(); let release;
  await check("Create validates blank result prevents duplicate save and uses narrow Student picker", root + "/new", world.options(), async (page, { requests }) => {
    await shown(page.getByRole("radio", { name: /Maria Assessment/ }));
    await page.getByRole("radio", { name: /Maria Assessment/ }).check();
    await page.getByLabel("Assessment Type", { exact: true }).selectOption(typeId);
    await page.getByLabel("Administered on", { exact: true }).fill("2020-01-01");
    await save(page).click(); await shown(page.getByText(/Record at least one/));
    assert.equal(world.mutations.length, 0);
    await page.getByLabel("Score / rating", { exact: true }).fill("88/100");
    world.waitForSave = new Promise((resolve) => { release = resolve; });
    await save(page).click(); await shown(page.getByRole("button", { name: "Saving…" }));
    assert.equal(await page.getByRole("button", { name: "Saving…" }).isDisabled(), true);
    release(); await shown(page.getByRole("heading", { name: "Assessment Record", exact: true }));
    await shown(page.getByText("88/100", { exact: true }));
    assert.equal(world.mutations.length, 1); assert.equal(world.mutations[0].body.score, "88/100");
    assert.ok(!requests.some((item) => item.pathname.startsWith("/api/v1/accounts")));
  });
}
{
  const world = assessmentWorld({ saveFailure: { status: 422 } });
  await check("Create validation failure keeps draft and unsaved navigation guard", root + "/new", world.options(), async (page) => {
    await fill(page); await save(page).click(); await shown(page.getByRole("alert"));
    assert.equal(await page.getByLabel("Score / rating", { exact: true }).inputValue(), "88/100");
    let warned = false;
    page.once("dialog", async (dialog) => { warned = true; assert.match(dialog.message(), /not been saved/); await dialog.dismiss(); });
    await page.getByRole("link", { name: "Back to Assessment Records", exact: true }).click();
    assert.equal(warned, true);
    assert.ok(page.url().endsWith("/new"));
  });
}
{
  const world = assessmentWorld();
  await check("Correction keeps Student immutable and sends textual source values", detail + "/edit", world.options(), async (page) => {
    await shown(page.getByRole("button", { name: "Save corrections" }));
    assert.equal(await page.getByRole("radio").count(), 0);
    await page.getByLabel("Score / rating", { exact: true }).fill("High — source rating");
    await page.getByRole("button", { name: "Save corrections" }).click();
    await shown(page.getByRole("heading", { name: "Assessment Record", exact: true }));
    await shown(page.getByText("High — source rating", { exact: true }));
    assert.equal(world.mutations[0].method, "PATCH"); assert.ok(!("student_id" in world.mutations[0].body));
  });
}
{
  const world = assessmentWorld();
  await check("Head catalog creates updates deactivates and reactivates without delete", root + "/types", world.options(), async (page) => {
    await shown(page.getByRole("button", { name: "Create type", exact: true }));
    await page.getByLabel("Name", { exact: true }).fill("Source Ability Assessment");
    await page.getByLabel("Description (optional)").fill("Institutional catalog description");
    await page.getByRole("button", { name: "Create type", exact: true }).click();
    await shown(page.getByRole("button", { name: "Edit Source Ability Assessment", exact: true }));
    await page.getByRole("button", { name: "Edit Source Ability Assessment", exact: true }).click();
    await page.getByLabel("Name", { exact: true }).fill("Source Ability Result");
    await page.getByRole("button", { name: "Save type", exact: true }).click();
    await shown(page.getByRole("button", { name: "Deactivate Source Ability Result", exact: true }));
    await page.getByRole("button", { name: "Deactivate Source Ability Result", exact: true }).click();
    await page.getByRole("button", { name: "Deactivate type", exact: true }).click();
    await shown(page.getByRole("button", { name: "Reactivate Source Ability Result", exact: true }));
    await page.getByRole("button", { name: "Reactivate Source Ability Result", exact: true }).click();
    await page.getByRole("button", { name: "Reactivate type", exact: true }).click();
    await shown(page.getByRole("button", { name: "Deactivate Source Ability Result", exact: true }));
    assert.ok(!world.mutations.some((item) => item.method === "DELETE"));
  });
}
{
  const world = assessmentWorld({ saveFailure: { status: 409 } });
  await check("Duplicate catalog name fails safely and retains the correction draft", root + "/types", world.options(), async (page) => {
    await shown(page.getByRole("button", { name: "Create type", exact: true }));
    await page.getByLabel("Name", { exact: true }).fill("Career Aptitude Test");
    await page.getByRole("button", { name: "Create type", exact: true }).click();
    await shown(page.getByText(/already exists/));
    assert.equal(await page.getByLabel("Name", { exact: true }).inputValue(), "Career Aptitude Test");
  });
}
{
  const world = assessmentWorld();
  await check("Account switch conceals previously decrypted content and removes Records navigation", detail, world.options({ beforeNavigate: async ({ page }) => { await page.clock.install(); } }), async (page) => {
    await shown(page.getByText(content.score, { exact: true }));
    world.account = { ...head(), id: "different-account", role: "STUDENT", designations: [], capabilities: [] };
    await refreshSession(page);
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    await hidden(page.getByText(content.score, { exact: true }));
  });
}
{
  const world = assessmentWorld();
  await check("Lost capability in same session conceals confidential projection", detail, world.options({ beforeNavigate: async ({ page }) => { await page.clock.install(); } }), async (page) => {
    await shown(page.getByText(content.score, { exact: true }));
    world.account = { ...world.account, capabilities: [] }; await refreshSession(page);
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    await hidden(page.getByText(content.score, { exact: true }));
  });
}

{
  const world = assessmentWorld({ saveFailure: { status: 403, code: "csrf_failed" } });
  await check("Expired CSRF keeps the source draft and permits a safe retry", root + "/new", world.options(), async (page) => {
    await fill(page); await save(page).click();
    await shown(page.getByText("The security check expired. Try saving again."));
    assert.equal(await page.getByLabel("Score / rating", { exact: true }).inputValue(), "88/100");
    world.saveFailure = null; await save(page).click();
    await shown(page.getByRole("heading", { name: "Assessment Record", exact: true }));
    await shown(page.getByText("88/100", { exact: true }));
  });
}
{
  const world = assessmentWorld({ saveFailure: { status: 403, code: "permission_denied" } });
  await check("Revoked manage authority during save conceals the draft", root + "/new", world.options(), async (page) => {
    await fill(page); world.account = { ...world.account, capabilities: [] };
    await save(page).click();
    await shown(page.getByRole("heading", { name: "Assessment Records unavailable" }));
    assert.ok(!(await text(page)).includes("88/100"));
    await hidden(page.getByLabel("Score / rating", { exact: true }));
  });
}
await finish();
