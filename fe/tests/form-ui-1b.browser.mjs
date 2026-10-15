// Actual Next UI with synthetic accounts, drafts and responses only.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { exitRecord } from "./support/form-ui-1b-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`form-ui-1b-exit-${process.env.COMPASS_UI_BROWSER ?? "chromium"}`);
const contract = JSON.parse(readFileSync(new URL("../../contracts/openapi.json", import.meta.url), "utf8"));
const feedbackCodes = contract.components.schemas.CollegeFeedbackItemValue.enum;
const selfCodes = contract.components.schemas.SelfAssessmentItemValue.enum;
const student = { ...user("STUDENT"), capabilities: ["exit_interviews.view_self", "exit_interviews.manage_self"], exit_interview_workspace_available: true };
for (const device of ["desktop", "phone"]) for (const legacy of [false, true]) {
  let detail = exitRecord(feedbackCodes, selfCodes, legacy);
  const saved = [];
  const canonicalResponse = () => ({ ...detail,
    self_assessment_ratings: detail.self_assessment_ratings.map(row => ({ ...row, item_label: row.item_code })),
    college_feedback_ratings: detail.college_feedback_ratings.map(row => ({ ...row, item_label: row.item_code, category: "Synthetic" })),
  });
  const handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(student)); return true; }
    if (pathname === "/api/v1/exit-interviews/me/exit-1b") {
      if (method === "PUT") { const body = JSON.parse(request.postData()); saved.push(body); detail = { ...detail, ...body }; }
      await reply(canonicalResponse()); return true;
    }
    if (pathname === "/api/v1/exit-interviews/me/exit-1b/submit") { detail = { ...detail, status: "SUBMITTED", can_edit: false }; await reply(canonicalResponse()); return true; }
    return false;
  };
  await check(`Exit ${legacy ? "legacy" : "UCN"} ${device} limits labels draft save and submission`, "/portal/exit-interviews/exit-1b", { handler, device }, async page => {
    await shown(page.getByLabel("Student name", { exact: true }));
    const limits = { "exit-student-name": 200, "exit-civil-status": 80, "exit-course": 180, "exit-major": 180, "exit-email-address": 320, "exit-contact-number": 64, "exit-home-address": 2000, "exit-suggestions-recommendations": 4000 };
    for (const [id, max] of Object.entries(limits)) assert.equal(await page.locator(`#${id}`).getAttribute("maxlength"), String(max));
    const contact = page.getByLabel("Contact Number", { exact: true });
    await contact.fill("1".repeat(63)); await contact.press("End"); await page.keyboard.type("11");
    assert.equal((await contact.inputValue()).length, 64);
    await shown(page.locator("#exit-contact-number-limit"));
    assert.match(await contact.getAttribute("aria-describedby"), /exit-contact-number-hint.*exit-contact-number-limit/);
    await contact.fill("0917 123 4567");
    await page.getByRole("radio", { name: "With some delay", exact: true }).check();
    await page.getByRole("spinbutton", { name: "Number of extra terms", exact: true }).fill("1");
    await page.locator("#exit-delay-other").check();
    const delay = page.getByRole("textbox", { name: "Specify other reason", exact: true });
    assert.equal(await delay.getAttribute("id"), "exit-delay-other-detail");
    await delay.fill("D".repeat(1000)); await shown(page.locator("#exit-delay-other-detail-limit"));
    await page.locator("#exit-learning-other").check();
    const learning = page.getByRole("textbox", { name: "Specify other experience", exact: true });
    assert.equal(await learning.getAttribute("maxlength"), "1000"); await learning.fill("Synthetic learning");
    const chair = page.locator("#exit-comment-programChairComments");
    if (legacy) { assert.equal(await chair.inputValue(), "SYNTHETIC LEGACY CHAIR CONTENT"); assert.equal(await chair.getAttribute("maxlength"), "4000"); } else await hidden(chair);
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    await shown(page.getByText("Draft saved.", { exact: true }));
    assert.equal(saved.at(-1).delay_other.length, 1000);
    assert.equal(saved.at(-1).college_feedback_ratings.length, legacy ? 26 : 23);
    if (legacy) assert.equal(saved.at(-1).program_chair_comments, "SYNTHETIC LEGACY CHAIR CONTENT");
    assert.ok(saved.at(-1).college_feedback_ratings.every(r => r.rating === 0));
    await noHorizontalOverflow(page); await screenshot(page, `exit-${legacy ? "legacy" : "ucn"}-${device}`);
    await page.getByRole("button", { name: "Submit Exit Interview", exact: true }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Submit Exit Interview", exact: true }).click();
    await hidden(page.getByRole("button", { name: "Save draft", exact: true }));
    await shown(page.getByRole("heading", { name: "Section III — College Feedback", exact: true }));
  });
}
{
  const long = `${"L".repeat(4000)}END-OF-LEGACY-CHAIR`;
  const detail = { ...exitRecord(feedbackCodes, selfCodes, true), program_chair_comments: long };
  let attempted;
  const handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(student)); return true; }
    if (pathname === "/api/v1/exit-interviews/me/exit-1b") {
      if (method === "PUT") { attempted = JSON.parse(request.postData()); await reply({ error: { code: "invalid_exit_interview", message: "Synthetic current write validation" } }, 422); }
      else await reply(detail);
      return true;
    }
    return false;
  };
  await check("Exit overlong saved legacy comment stays whole after an unrelated edit and failed save", "/portal/exit-interviews/exit-1b", { handler, mobile: true }, async page => {
    const chair = page.getByLabel("Comments about the Program Chair", { exact: true });
    await shown(chair); assert.equal(await chair.inputValue(), long);
    await shown(page.locator("#exit-comment-programChairComments-limit"));
    await page.getByLabel("Major", { exact: true }).fill("Synthetic correction");
    await page.getByRole("button", { name: "Save draft", exact: true }).click();
    await shown(page.getByRole("main").getByRole("alert"));
    assert.equal(attempted.program_chair_comments, long); assert.equal(await chair.inputValue(), long);
    assert.equal(await page.getByLabel("Major", { exact: true }).inputValue(), "Synthetic correction");
    await noHorizontalOverflow(page);
  });
}
{
  const record = { id: "inventory-review-copy", academic_year: { id: "year-1b", label: "2026-2027" }, status: "DRAFT",
    form_revision: { id: "f5", family_key: "individual_inventory", official_code: "UCN-OP-GCO-01F5", official_revision: "1", internal_schema_version: 1 },
    full_name: "Synthetic Student", program: null, family_members: [], siblings: [], geographic_locations: [], transportation_entries: [],
    correction_pending: false, latest_correction: null, submitted_at: null, first_submitted_at: null, last_submitted_at: null };
  const account = { ...user("STUDENT"), capabilities: ["inventory.view_self", "inventory.manage_self"] };
  await check("Inventory review uses plain copy and still focuses unanswered questions", "/portal/inventory/current", {
    mobile: true,
    overrides: { "GET /api/v1/auth/session": sessionFor(account), "GET /api/v1/inventory/me/status": record, "GET /api/v1/inventory/me/current": record },
  }, async page => {
    await page.getByLabel("Inventory section", { exact: true }).selectOption("review");
    await shown(page.getByRole("group", { name: "Before you submit", exact: true }));
    await shown(page.getByText("Complete these answers", { exact: true }));
    assert.doesNotMatch(await page.getByRole("main").textContent(), /Submission readiness|No required-field issues|Official PDF capacity/);
    await noHorizontalOverflow(page); await screenshot(page, "inventory-review-plain-copy-phone");
    await page.getByRole("button", { name: "Choose a sex response.", exact: true }).click();
    await shown(page.locator("#inventory-sex"));
    assert.equal(await page.locator("#inventory-sex").evaluate(node => node === document.activeElement), true);
  });
}
await finish();
