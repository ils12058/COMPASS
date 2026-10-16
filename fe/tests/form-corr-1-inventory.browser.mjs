// FORM-CORR-1 PR 2 in a real browser: a Counselor names Individual Inventory answers to review in
// the existing reopen dialog, and the Student is taken to each one. Targets stay advisory: nothing is
// marked invalid and saving and resubmission work as before. Every API read and write is a synthetic
// fixture; no account or record is touched.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("form-corr-1-inventory");

const session = (account) => ({ authenticated: true, user: account, session: { id: `session-${account.id}`, expires_at: "2099-10-07T00:00:00Z", is_current: true } });
const year = { id: "year-2026", label: "2026-2027" };
const revision = { id: "inventory-revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" };
const requestedAt = "2026-10-16T01:00:00Z";
const focusedId = (page) => page.evaluate(() => document.activeElement?.id ?? "");
const activeDescription = (page) => page.evaluate(() => {
  const ids = (document.activeElement?.getAttribute("aria-describedby") ?? "").split(" ").filter(Boolean);
  return ids.map((id) => document.getElementById(id)?.textContent ?? `missing #${id}`).join(" ");
});

// --- Reviewer ---------------------------------------------------------------------------------

const recordId = "inventory-submitted";
const submittedRecord = {
  id: recordId, academic_year: year, status: "SUBMITTED", program: null, form_revision: revision,
  submitted_at: "2026-10-01T02:00:00Z", first_submitted_at: "2026-10-01T02:00:00Z", last_submitted_at: "2026-10-01T02:00:00Z",
  correction_pending: false, latest_correction: null,
  student: { id: "student", display_name: "Maria Santos", institutional_id: "TEST-01" },
  full_name: "Maria Santos", contact_number: "0917 000 0000", family_members: [], siblings: [], geographic_locations: [], transportation_entries: [], organization_memberships: [], education_entries: [],
};
const historyItem = {
  inventory_id: recordId, academic_year: year, status: "DRAFT", correction_pending: true, program: null, year_level: null,
  submitted_at: null, first_submitted_at: "2026-10-01T02:00:00Z", last_submitted_at: "2026-10-01T02:00:00Z",
};
const counselorBase = user("COUNSELOR");
const counselor = { ...counselorBase, capabilities: [...counselorBase.capabilities, "inventory.view", "inventory.reopen", "academic_years.view"] };
const viewOnlyCounselor = { ...counselorBase, capabilities: [...counselorBase.capabilities, "inventory.view", "academic_years.view"] };

function reviewerFixture({ account = counselor, reopen } = {}) {
  const requests = [];
  return {
    requests,
    overrides: {
      "GET /api/v1/auth/session": session(account),
      [`GET /api/v1/inventory/records/${recordId}`]: submittedRecord,
      "GET /api/v1/academic-years": { items: [{ ...year, is_current: true }] },
      "GET /api/v1/inventory/students": { items: [], page: 1, page_size: 20, has_next: false, ordering: "STUDENT_ASC" },
      [`POST /api/v1/inventory/records/${recordId}/reopen`]: (context) => {
        requests.push(JSON.parse(context.request.postData() ?? "{}"));
        return reopen ? reopen(context) : context.reply(historyItem);
      },
    },
  };
}

async function openReopenDialog(page) {
  await page.getByRole("button", { name: "Reopen for correction", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await shown(dialog);
  return dialog;
}

async function expandSection(dialog, label) {
  await dialog.locator("summary").filter({ hasText: label }).click();
}

{
  const fixture = reviewerFixture();
  await check("reviewer-chooses-sections-and-answers-and-sends-them-in-catalog-order", `/portal/inventory/records/${recordId}`, { overrides: fixture.overrides }, async (page) => {
    const dialog = await openReopenDialog(page);
    await shown(dialog.getByRole("group", { name: "Answers to review (optional)" }));
    await shown(dialog.getByText("Choose the parts of the form the Student should look at again. They will see these with your instructions.", { exact: true }));
    assert.equal(await dialog.locator("details[open]").count(), 0, "Every section starts collapsed");
    assert.equal(await dialog.getByRole("checkbox", { checked: true }).count(), 0, "Nothing is selected by default");
    await shown(dialog.getByText("None. The Student will see only your instructions.", { exact: true }));

    await expandSection(dialog, "Family & student support");
    assert.equal(await dialog.locator("details[open]").count(), 1);
    await dialog.getByRole("group", { name: "Father" }).getByRole("checkbox", { name: "Father's occupation" }).check();
    await dialog.getByRole("group", { name: "Father" }).getByRole("checkbox", { name: "Father's email address" }).check();
    // Opening another section closes the first, so the list never grows to every choice at once.
    await expandSection(dialog, "Personal & contact");
    await page.waitForFunction(() => document.querySelectorAll('[role="alertdialog"] details[open]').length === 1);
    assert.equal(await dialog.locator("details[open] summary").textContent(), "Personal & contact");
    await dialog.getByRole("checkbox", { name: "Contact number" }).check();
    await dialog.getByRole("checkbox", { name: /^Whole section/ }).check();
    await shown(dialog.getByText("4 of 30 selected", { exact: true }));
    await shown(dialog.locator("summary").filter({ hasText: "Family & student support" }).getByText("2 selected", { exact: true }));

    const selected = dialog.getByRole("list", { name: "Selected for review" });
    assert.deepEqual(await selected.getByRole("listitem").locator("span").allTextContents(), [
      "Whole section — Personal & contact",
      "Contact number — Personal & contact",
      "Father's occupation — Family & student support",
      "Father's email address — Family & student support",
    ], "The selection is listed in form order before confirming");

    // Remove one; focus moves to the next Remove button.
    await dialog.getByRole("button", { name: "Remove Father's occupation — Family & student support" }).click();
    assert.match(await page.evaluate(() => document.activeElement?.getAttribute("aria-label") ?? ""), /^Remove Father's email address/);
    await shown(dialog.getByText("3 of 30 selected", { exact: true }));

    // Instructions stay required.
    const confirm = dialog.getByRole("button", { name: "Reopen for correction", exact: true });
    assert.equal(await confirm.isDisabled(), true);
    await dialog.getByLabel(/Correction instructions/).fill("Please confirm your contact details and your father's email.");
    await confirm.click();
    await page.waitForURL(/\/portal\/inventory\?notice=reopened/);
    assert.deepEqual(fixture.requests, [{
      reason: "Please confirm your contact details and your father's email.",
      targets: ["section.personal", "personal.contact_number", "family.father.email_address"],
    }]);
  });
}

{
  const fixture = reviewerFixture();
  await check("reviewer-can-clear-and-send-a-reason-only-request", `/portal/inventory/records/${recordId}`, { overrides: fixture.overrides }, async (page) => {
    const dialog = await openReopenDialog(page);
    await expandSection(dialog, "Plans & counseling context");
    await dialog.getByRole("checkbox", { name: "Current fears" }).check();
    await dialog.getByRole("button", { name: "Clear selection", exact: true }).click();
    assert.equal(await focusedId(page), await dialog.getByText("Selected for review", { exact: true }).getAttribute("id"));
    assert.equal(await dialog.getByRole("checkbox", { checked: true }).count(), 0);
    await dialog.getByLabel(/Correction instructions/).fill("Synthetic reason only.");
    await dialog.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await page.waitForURL(/notice=reopened/);
    assert.deepEqual(fixture.requests, [{ reason: "Synthetic reason only." }], "Without targets the request is unchanged");
  });
}

{
  const fixture = reviewerFixture();
  await check("reviewer-selection-stops-at-thirty", `/portal/inventory/records/${recordId}`, { overrides: fixture.overrides }, async (page) => {
    const dialog = await openReopenDialog(page);
    await expandSection(dialog, "Family & student support");
    const boxes = dialog.locator("details[open] input[type=checkbox]");
    for (let index = 0; index < 30; index += 1) await boxes.nth(index).check();
    await shown(dialog.getByText("30 of 30 selected. Remove one to choose another.", { exact: true }));
    assert.equal(await boxes.nth(30).isDisabled(), true, "A 31st answer cannot be chosen");
    await expandSection(dialog, "Plans & counseling context");
    assert.equal(await dialog.getByRole("checkbox", { name: "Current fears" }).isDisabled(), true);
    await dialog.getByLabel(/Correction instructions/).fill("Synthetic limit check.");
    await dialog.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await page.waitForURL(/notice=reopened/);
    assert.equal(fixture.requests[0].targets.length, 30);
  });
}

{
  let release;
  const fixture = reviewerFixture({
    reopen: ({ reply }) => new Promise((resolve) => { release = () => resolve(reply({ error: { code: "synthetic_failure", message: "Synthetic" } }, 500)); }),
  });
  await check("reviewer-pending-and-failure-keep-the-selection", `/portal/inventory/records/${recordId}`, { overrides: fixture.overrides }, async (page) => {
    const dialog = await openReopenDialog(page);
    await expandSection(dialog, "Living conditions & health");
    await dialog.getByRole("checkbox", { name: "Height" }).check();
    await dialog.getByLabel(/Correction instructions/).fill("Synthetic pending check.");
    await dialog.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await shown(dialog.getByRole("button", { name: "Reopening…" }));
    assert.equal(await dialog.getByRole("checkbox", { name: "Height" }).isDisabled(), true, "The selection is locked while the request runs");
    release();
    await shown(dialog.getByText("This Individual Inventory could not be reopened.", { exact: true }));
    assert.equal(await dialog.getByRole("checkbox", { name: "Height" }).isChecked(), true, "The selection survives a failed request");
    assert.equal(await dialog.getByRole("checkbox", { name: "Height" }).isDisabled(), false);
    assert.deepEqual(fixture.requests.at(-1).targets, ["health.height"]);
  });
}

{
  const fixture = reviewerFixture({ account: viewOnlyCounselor });
  await check("view-only-counselor-has-no-reopen-or-target-controls", `/portal/inventory/records/${recordId}`, { overrides: fixture.overrides }, async (page) => {
    await shown(page.getByRole("heading", { name: "Maria Santos" }));
    assert.equal(await page.getByRole("button", { name: "Reopen for correction" }).count(), 0);
    assert.equal(await page.getByText("Answers to review", { exact: false }).count(), 0);
    assert.equal(await page.getByRole("checkbox").count(), 0);
  });
}

{
  const fixture = reviewerFixture();
  await check("reviewer-dialog-fits-a-phone", `/portal/inventory/records/${recordId}`, { mobile: true, overrides: fixture.overrides }, async (page) => {
    const dialog = await openReopenDialog(page);
    await expandSection(dialog, "Family & student support");
    await dialog.getByRole("checkbox", { name: "Mother's annual income from previous year" }).check();
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.width <= viewport.width && box.height <= viewport.height, "The dialog stays inside the screen");
    assert.equal(await dialog.evaluate((node) => getComputedStyle(node).overflowY), "auto", "The dialog scrolls instead of growing");
    await dialog.getByRole("list", { name: "Selected for review" }).scrollIntoViewIfNeeded();
    await noHorizontalOverflow(page);
    await screenshot(page, "reviewer-dialog-phone");
  });
}

// --- Student ----------------------------------------------------------------------------------

const base = user("STUDENT");
const student = { ...base, capabilities: [...base.capabilities, "inventory.view_self", "inventory.manage_self"] };

// Complete enough to submit, so a target can be shown never to block resubmission.
const answers = {
  full_name: "Maria Santos", student_number: "TEST-01", sex: "FEMALE", date_of_birth: "2005-01-15",
  civil_status_category: "SINGLE", current_religion_category: "NONE", contact_number: "0917 000 0000",
  geographic_locations: [{ kind: "CURRENT", not_specified: true }],
  parent_status_category: "MARRIED",
  support_profile: { four_ps_status: "NOT_BENEFICIARY", indigenous_peoples_status: "NOT_MEMBER", mother_life_status: "LIVING", father_life_status: "LIVING" },
  family_members: [
    { kind: "FATHER", occupation_category: "FARMER", annual_income_status: "NOT_SPECIFIED", email_address: "father@example.test" },
    { kind: "MOTHER", occupation_category: "NONE", annual_income_status: "NONE" },
  ],
  living_arrangement: "OWN_HOUSE", pwd_status: "NON_PWD", year_level: 2,
  siblings: [{ sort_order: 0, name: "Ana Santos" }, { sort_order: 1, name: "Maria Santos", is_self: true }],
  organization_memberships: [], transportation_entries: [{ mode: "BUS", frequency_category: "DAILY" }],
  prior_counseling_experience: true,
};
const allTargets = [
  "personal.contact_number", "family.father.email_address", "family.spouse.name", "family.parent_statuses",
  "background.siblings", "health.boarding_landlord_name", "education.history.senior_high", "section.interests",
  "organizations.inside_school", "organizations.transportation.bus", "organizations.transportation.van", "plans.prior_counseling",
];
function draftRecord(targets = allTargets, overrides = {}) {
  return {
    id: "inventory-reopened", academic_year: year, status: "DRAFT", program: null, form_revision: revision,
    submitted_at: null, first_submitted_at: "2026-10-01T02:00:00Z", last_submitted_at: "2026-10-01T02:00:00Z",
    correction_pending: true, latest_correction: { message: "Please review the answers listed below.", requested_at: requestedAt, targets },
    ...answers, ...overrides,
  };
}
function statusFor(record) {
  const { academic_year, status, form_revision, correction_pending, latest_correction, submitted_at, first_submitted_at, last_submitted_at } = record;
  return { academic_year, status, form_revision, correction_pending, latest_correction, submitted_at, first_submitted_at, last_submitted_at };
}
function studentFixture(record = draftRecord()) {
  const saved = [];
  const submitted = [];
  let current = record;
  return {
    saved,
    submitted,
    overrides: {
      "GET /api/v1/auth/session": session(student),
      "GET /api/v1/inventory/me/status": ({ reply }) => reply(statusFor(current)),
      "GET /api/v1/inventory/me/current": ({ reply }) => reply(current),
      "GET /api/v1/inventory/me/history": { items: [], page: 1, page_size: 20, has_next: false },
      "PUT /api/v1/inventory/me/current": ({ reply, request }) => {
        const body = JSON.parse(request.postData() ?? "{}");
        saved.push(body);
        current = { ...current, ...body };
        return reply(current);
      },
      "POST /api/v1/inventory/me/current/submit": ({ reply }) => {
        submitted.push(true);
        // Resubmission ends the pending correction; its targets stop appearing.
        current = { ...current, status: "SUBMITTED", submitted_at: "2026-10-16T03:00:00Z", last_submitted_at: "2026-10-16T03:00:00Z", correction_pending: false, latest_correction: null };
        return reply(current);
      },
    },
  };
}
const answerButton = (page, label) => page.getByRole("button", { name: label, exact: true });
const heading = (page) => page.locator("#inventory-editor-heading");

// [button label, editor section, element that should have focus, hint text that should describe it]
const navigationCases = [
  ["Contact number — Personal & contact", "Personal & contact", "inventory-contact-number", "You were asked to review this answer."],
  ["Father's email address — Family & student support", "Family & student support", "inventory-family-father-email", "You were asked to review this answer."],
  ["Spouse's name — Family & student support", "Family & student support", "inventory-spouse-add", "You were asked to review Spouse information. It appears after you choose Add optional Spouse details."],
  ["Additional parent circumstances — Family & student support", "Family & student support", null, "You were asked to review this answer."],
  ["Siblings — Siblings & background", "Siblings & background", "inventory-sibling-0-name", "You were asked to review this list."],
  ["Landlord or landlady name — Living conditions & health", "Living conditions & health", "inventory-living-arrangement", "You were asked to review boarding-house details. They appear when you choose Boarding house."],
  ["Educational history: Senior high — Educational background", "Educational background", "inventory-education-senior_high-school", "You were asked to review these answers."],
  ["Whole section — Interests & daily routine", "Interests & daily routine", "inventory-section-review", ""],
  ["Organizations inside the university — Organizations & transportation", "Organizations & transportation", "inventory-membership-inside_school-add", "You were asked to review this list."],
  ["Bus: frequency and fare — Organizations & transportation", "Organizations & transportation", "inventory-transport-bus-frequency-category", "You were asked to review these answers."],
  ["Van: frequency and fare — Organizations & transportation", "Organizations & transportation", null, "You were asked to review your Van details. They appear when you select Van."],
  ["Prior counseling experience — Plans & counseling context", "Plans & counseling context", null, "You were asked to review this answer."],
];

async function followEveryTarget(page, { mobile = false } = {}) {
  for (const [label, section, focusId, hint] of navigationCases) {
    // Back to the list at the top, as a Student would after reviewing an answer.
    await page.evaluate(() => window.scrollTo(0, 0));
    await answerButton(page, label).click();
    await shown(heading(page).filter({ hasText: section }));
    if (mobile) assert.equal(await page.locator("#inventory-section-select").evaluate((node) => node.selectedOptions[0].textContent), section);
    if (focusId) {
      await page.waitForFunction((id) => document.activeElement?.id === id, focusId);
    }
    const focus = await page.evaluate(() => {
      const node = document.activeElement;
      return { id: node?.id ?? "", type: node?.getAttribute("type"), name: node?.getAttribute("name"), checked: node?.checked, label: node?.closest("label")?.textContent?.trim(), invalid: node?.getAttribute("aria-invalid") };
    });
    if (label.startsWith("Additional parent")) {
      assert.equal(focus.type, "checkbox", "Focus enters the checkbox group");
      assert.equal(await page.locator("#inventory-parent-statuses").getAttribute("aria-describedby"), "inventory-parent-statuses-review");
    } else if (label.startsWith("Van")) {
      assert.equal(focus.label, "Tricycle", "A hidden mode leads to the mode choices");
      assert.match(await page.locator("#inventory-transport-modes").getAttribute("aria-describedby"), /inventory-transport-modes-review/);
    } else if (label.startsWith("Prior counseling")) {
      assert.deepEqual([focus.name, focus.checked, focus.label], ["inventory-prior-counseling", true, "Yes"], "A radio group is entered at its checked answer");
    } else {
      assert.equal(focus.id, focusId, `${label} focuses #${focusId}`);
    }
    assert.equal(focus.invalid, null, "A requested review never marks the answer invalid");
    if (hint) {
      if (!label.startsWith("Additional parent") && !label.startsWith("Van")) assert.ok((await activeDescription(page)).includes(hint), `${label} is described by its hint`);
      await shown(page.getByText(hint, { exact: true }).first());
    }
    const inView = await page.evaluate(() => {
      const rect = document.activeElement.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < window.innerHeight;
    });
    assert.ok(inView, `${label}: the focused control is on screen`);
  }
}

{
  const fixture = studentFixture();
  await check("student-follows-every-kind-of-target-on-desktop", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    const notice = page.getByRole("status").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Answers to review", { exact: true }));
    await shown(notice.getByText("Please review the answers listed below.", { exact: true }));
    for (const code of allTargets) assert.ok(!(await page.locator("main").textContent()).includes(code), `${code} is never shown`);
    await followEveryTarget(page);
    // The father's additional details opened for the named answer; the mother's stayed closed.
    await answerButton(page, "Father's email address — Family & student support").click();
    assert.equal(await page.locator("#inventory-family-father-details").evaluate((node) => node.open), true);
    assert.equal(await page.locator("#inventory-family-mother-details").evaluate((node) => node.open), false);
    await screenshot(page, "student-family-details-target");
    assert.equal(fixture.saved.length, 0, "Following targets never saves");
  });
}

{
  const fixture = studentFixture();
  await check("student-follows-every-kind-of-target-on-a-phone", "/portal/inventory/current", { mobile: true, overrides: fixture.overrides }, async (page) => {
    await shown(page.getByText("Answers to review", { exact: true }));
    await followEveryTarget(page, { mobile: true });
    await noHorizontalOverflow(page);
    await screenshot(page, "student-targets-phone");
  });
}

{
  const fixture = studentFixture();
  await check("keyboard-only-student-reaches-a-target-and-a-whole-section", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    await answerButton(page, "Whole section — Interests & daily routine").focus();
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.activeElement?.id === "inventory-section-review");
    assert.equal(await page.locator("#inventory-section-review").textContent(), "You were asked to review this section.");
    await answerButton(page, "Contact number — Personal & contact").focus();
    await page.keyboard.press("Space");
    await page.waitForFunction(() => document.activeElement?.id === "inventory-contact-number");
    // Typing goes straight into the answer.
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("0918 111 2222");
    assert.equal(await page.locator("#inventory-contact-number").inputValue(), "0918 111 2222");
  });
}

{
  const fixture = studentFixture();
  await check("targets-never-block-saving-or-resubmission", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    // Review an answer and change it; save sends only answers.
    await answerButton(page, "Contact number — Personal & contact").click();
    await page.locator("#inventory-contact-number").fill("0918 111 2222");
    await page.getByRole("button", { name: "Save progress", exact: true }).click();
    await shown(page.getByText("Progress saved.", { exact: true }));
    const body = fixture.saved.at(-1);
    assert.equal(body.contact_number, "0918 111 2222");
    for (const key of ["latest_correction", "correction_pending", "targets", "id", "status"]) assert.ok(!(key in body), `${key} is not sent`);
    // Other targeted answers are left unchanged, and the Inventory still submits.
    await page.getByRole("button", { name: /Review & submit/ }).click();
    const submit = page.getByRole("button", { name: "Submit Individual Inventory", exact: true });
    assert.equal(await submit.isDisabled(), false, "Unchanged targeted answers do not block resubmission");
    await submit.click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Submit Individual Inventory", exact: true }).click();
    await page.waitForFunction(() => !document.body.textContent.includes("Answers to review"));
    assert.equal(fixture.submitted.length, 1);
    await shown(page.getByText("Submitted", { exact: true }).first());
    assert.equal(await page.getByText("Correction requested").count(), 0, "After resubmission the targets are no longer pending");
  });
}

{
  const fixture = studentFixture(draftRecord([]));
  await check("legacy-reason-only-correction-is-unchanged", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    const notice = page.getByRole("status").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Please review the answers listed below.", { exact: true }));
    assert.equal(await notice.getByText("Answers to review").count(), 0);
    assert.equal(await page.locator('[id$="-review"]').count(), 0, "No answer is marked");
  });
}

{
  const record = draftRecord(["personal.contact_number", "section.plans"]);
  await check("inventory-home-lists-targets-as-plain-text", "/portal/inventory", {
    overrides: {
      "GET /api/v1/auth/session": session(student),
      "GET /api/v1/inventory/me/status": statusFor(record),
      "GET /api/v1/inventory/me/history": { items: [], page: 1, page_size: 20, has_next: false },
    },
  }, async (page) => {
    const notice = page.getByRole("status").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Contact number — Personal & contact", { exact: true }));
    await shown(notice.getByText("Whole section — Plans & counseling context", { exact: true }));
    assert.equal(await notice.getByRole("button").count(), 0, "Only the editor offers navigation");
    await shown(page.getByRole("link", { name: "Continue Individual Inventory" }));
  });
}

{
  // A reopened draft left in an Academic Year that is no longer current cannot be edited.
  const stranded = { ...draftRecord(["family.guardian_name"]), id: "inventory-stranded", academic_year: { id: "year-2025", label: "2025-2026" } };
  await check("a-stranded-past-year-draft-shows-targets-without-links", "/portal/inventory/history/inventory-stranded", {
    overrides: {
      "GET /api/v1/auth/session": session(student),
      "GET /api/v1/inventory/me/inventory-stranded": stranded,
    },
  }, async (page) => {
    const notice = page.getByRole("status").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Guardian name — Family & student support", { exact: true }));
    assert.equal(await notice.getByRole("button").count(), 0);
    assert.equal(await page.getByRole("textbox").count(), 0, "The record stays read-only");
  });
}

await finish();
