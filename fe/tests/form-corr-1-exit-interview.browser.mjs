// FORM-CORR-1 PR 3 in a real browser: an authorized reviewer names Exit Interview answers to review
// in the existing two-step reopen flow, limited to the record's saved form, and the Student is taken
// to each one. Targets stay advisory: no answer changes, nothing is marked invalid, and saving and
// resubmission work as before. Every API read and write is a synthetic fixture.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`form-corr-1-exit-interview-${process.env.COMPASS_UI_BROWSER ?? "chromium"}`);

const session = (account) => ({ authenticated: true, user: account, session: { id: `session-${account.id}`, expires_at: "2099-10-07T00:00:00Z", is_current: true } });
const year = { id: "year-2026", label: "2026-2027" };
const selfCodes = ["PRIDE_CONFIDENCE_CNSC", "ACADEMIC_RECREATION_BALANCE", "HOLISTIC_PERSONAL_WELL_BEING", "INTEGRATE_KNOWLEDGE_EXPERIENCE", "CAREER_GOAL_CLARITY", "SELF_ESTEEM", "SELF_AWARENESS", "COPE_WITH_PRESSURES", "DEAL_WITH_DIFFERENT_WALKS", "LEADERSHIP", "COMMUNICATION_SKILLS", "CIVIC_MINDEDNESS", "INITIATIVE", "DECISION_MAKING", "RELATIONSHIP_WITH_GOD"];
const legacyCodes = ["DEAN_AVAILABILITY", "DEAN_OPEN_MINDEDNESS", "DEAN_CONCERN_FOR_STUDENTS", "DEAN_COMMITMENT", "DEAN_APPROACHABILITY", "PROGRAM_CHAIR_AVAILABILITY", "PROGRAM_CHAIR_APPROACHABILITY", "PROGRAM_CHAIR_CONCERN_FOR_STUDENTS", "FACULTY_AVAILABILITY", "FACULTY_APPROACHABILITY", "FACULTY_KNOWLEDGE_SUBJECT_MATTER", "FACULTY_TEACHING_SKILLS", "CURRICULUM_RELEVANCE_SUBJECTS", "CURRICULUM_SYSTEMATIC_SEQUENCING", "CURRICULUM_COMPLETENESS", "GUIDANCE_COUNSELOR_AVAILABILITY", "GUIDANCE_COUNSELOR_APPROACHABILITY", "GUIDANCE_COUNSELOR_CONCERN_FOR_STUDENTS", "GUIDANCE_COUNSELOR_EFFICIENCY", "OFFICE_STAFF_SERVICE_ORIENTED", "OFFICE_STAFF_AVAILABILITY", "OFFICE_STAFF_CONCERN_FOR_STUDENTS", "OFFICE_STAFF_APPROACHABILITY", "FACILITIES_MAINTENANCE_CONDITION", "FACILITIES_AVAILABILITY", "FACILITIES_COMPLETENESS"];
const f9Codes = legacyCodes.filter((code) => !code.startsWith("PROGRAM_CHAIR_"));
const focusedId = (page) => page.evaluate(() => document.activeElement?.id ?? "");
const activeDescription = (page) => page.evaluate(() => {
  const ids = (document.activeElement?.getAttribute("aria-describedby") ?? "").split(" ").filter(Boolean);
  return ids.map((id) => document.getElementById(id)?.textContent ?? `missing #${id}`).join(" ");
});

function record({ legacy = false, status = "SUBMITTED", ...overrides } = {}) {
  const codes = legacy ? legacyCodes : f9Codes;
  return {
    id: "exit-corr", academic_year: year, status, can_edit: status === "DRAFT", inventory_id: "inventory",
    student: { id: "student", display_name: "Maria Santos", institutional_id: "TEST-01" }, student_name: "Maria Santos",
    form_revision: legacy ? null : { id: "ucn-f9", official_code: "UCN-OP-GCO-01F9", official_revision: "1", internal_schema_version: 2 },
    college_feedback_item_codes: codes,
    contact_number: "0917 000 0000", program_completion: "ACCORDING_TO_SCHEDULE", career_modes: ["WORK"], work_choices: ["RELATED_FIELD"],
    self_assessment_ratings: selfCodes.map((item_code) => ({ item_code, item_label: item_code, rating: item_code === "SELF_ESTEEM" ? 4 : 5 })),
    // 0 is a saved answer with no defined meaning; it must stay exactly 0.
    college_feedback_ratings: codes.map((item_code) => ({ item_code, category: "Synthetic", item_label: item_code, rating: item_code === "GUIDANCE_COUNSELOR_EFFICIENCY" ? 0 : 4 })),
    guidance_counselor_comments: "Synthetic comment.",
    reopen_events: [], created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-02T00:00:00Z",
    first_submitted_at: "2026-10-01T06:00:00Z", last_submitted_at: "2026-10-01T06:00:00Z",
    ...overrides,
  };
}

// --- Reviewer ---------------------------------------------------------------------------------

const reviewerBase = user("COUNSELOR");
const reviewer = { ...reviewerBase, capabilities: [...reviewerBase.capabilities, "exit_interviews.view", "exit_interviews.reopen"] };
const viewOnly = { ...reviewerBase, capabilities: [...reviewerBase.capabilities, "exit_interviews.view"] };

function reviewerFixture({ legacy = false, account = reviewer, reopen } = {}) {
  const requests = [];
  return {
    requests,
    overrides: {
      "GET /api/v1/auth/session": session(account),
      "GET /api/v1/exit-interviews/exit-corr": record({ legacy }),
      "POST /api/v1/exit-interviews/exit-corr/reopen": (context) => {
        requests.push(JSON.parse(context.request.postData() ?? "{}"));
        return reopen ? reopen(context) : context.reply({ ...record({ legacy, status: "DRAFT" }), can_edit: false });
      },
    },
  };
}

async function openChooser(page) {
  await page.getByRole("button", { name: "Reopen for correction" }).click();
  const dialog = page.getByRole("dialog");
  await shown(dialog.getByRole("group", { name: "Answers to review (optional)" }));
  return dialog;
}

async function expand(page, dialog, title) {
  await dialog.locator("summary").filter({ hasText: title }).click();
  await page.waitForFunction((text) => document.querySelector('[role="dialog"] details[open] summary')?.textContent?.startsWith(text), title);
}

{
  const fixture = reviewerFixture();
  await check("reviewer-chooses-f9-answers-reviews-them-and-sends-them", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    assert.equal(await dialog.locator("details[open]").count(), 0, "Every section starts collapsed");
    assert.equal(await dialog.getByRole("checkbox", { checked: true }).count(), 0, "Nothing is selected by default");

    await expand(page, dialog, "Section III — College Feedback");
    assert.equal(await dialog.getByText("Program Chair", { exact: false }).count(), 0, "UCN F9 offers no Program Chair target");
    const counselor = dialog.getByRole("group", { name: "Guidance Counselor", exact: true });
    await counselor.getByRole("checkbox", { name: "Efficiency" }).check();
    await counselor.getByRole("checkbox", { name: "Comments about the Guidance Counselor" }).check();
    await expand(page, dialog, "Section I — Program completion and plans");
    await dialog.getByRole("group", { name: "Program completion", exact: true }).getByRole("checkbox", { name: "Program completion" }).check();
    await expand(page, dialog, "Section II — Self-Assessment");
    await dialog.getByRole("checkbox", { name: /^Whole section/ }).check();
    await shown(dialog.getByText("4 of 30 selected", { exact: true }));

    // The reason stays required.
    const review = dialog.getByRole("button", { name: "Review reopening" });
    assert.equal(await review.isDisabled(), true);
    await dialog.getByLabel("Reason for correction").fill("Please review the answers listed.");
    await shown(dialog.getByText("33 / 1000 characters", { exact: true }));
    await review.click();

    // The existing review step shows the reason and the answers, in form order.
    const confirm = page.getByRole("alertdialog");
    await shown(confirm.getByText("Please review the answers listed.", { exact: true }));
    assert.deepEqual(await confirm.getByRole("listitem").allTextContents(), [
      "Program completion",
      "Section II — Self-Assessment (whole section)",
      "College Feedback — Guidance Counselor — Efficiency",
      "College Feedback — Comments about the Guidance Counselor",
    ]);
    await confirm.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await page.waitForURL(/\/portal\/exit-interviews\?notice=reopened/);
    assert.deepEqual(fixture.requests, [{
      reason: "Please review the answers listed.",
      targets: ["completion.program_completion", "section.self_assessment", "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY", "college_feedback.comments.guidance_counselor"],
    }]);
  });
}

{
  const fixture = reviewerFixture({ legacy: true });
  await check("reviewer-keeps-program-chair-targets-for-a-legacy-record", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    await expand(page, dialog, "Section III — College Feedback");
    const chair = dialog.getByRole("group", { name: "Program Chair", exact: true });
    assert.equal(await chair.getByRole("checkbox").count(), 4, "Three legacy Program Chair ratings and the comment");
    await chair.getByRole("checkbox", { name: "Concern for Students" }).check();
    await chair.getByRole("checkbox", { name: "Comments about the Program Chair" }).check();
    await dialog.getByLabel("Reason for correction").fill("Legacy synthetic reason.");
    await dialog.getByRole("button", { name: "Review reopening" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await page.waitForURL(/notice=reopened/);
    assert.deepEqual(fixture.requests[0].targets, ["college_feedback.PROGRAM_CHAIR_CONCERN_FOR_STUDENTS", "college_feedback.comments.program_chair"]);
  });
}

{
  const fixture = reviewerFixture();
  await check("reviewer-reason-only-request-is-unchanged", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    await dialog.getByLabel("Reason for correction").fill("Synthetic reason only.");
    await dialog.getByRole("button", { name: "Review reopening" }).click();
    const confirm = page.getByRole("alertdialog");
    await shown(confirm.getByText("None. The Student will see only the reason.", { exact: true }));
    await confirm.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await page.waitForURL(/notice=reopened/);
    assert.deepEqual(fixture.requests, [{ reason: "Synthetic reason only." }]);
  });
}

{
  const fixture = reviewerFixture();
  await check("reviewer-selection-stops-at-thirty", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    await expand(page, dialog, "Section II — Self-Assessment");
    const boxes = dialog.locator("details[open] input[type=checkbox]");
    for (let index = 0; index < 16; index += 1) await boxes.nth(index).check();
    await expand(page, dialog, "Section III — College Feedback");
    for (let index = 0; index < 14; index += 1) await boxes.nth(index).check();
    await shown(dialog.getByText("30 of 30 selected. Remove one to choose another.", { exact: true }));
    assert.equal(await boxes.nth(14).isDisabled(), true, "A 31st answer cannot be chosen");
    // Removing one frees a place.
    await dialog.getByRole("button", { name: "Remove Section II — Self-Assessment (whole section)", exact: true }).click();
    assert.equal(await boxes.nth(14).isDisabled(), false);
  });
}

{
  let attempts = 0;
  const fixture = reviewerFixture({
    reopen: ({ reply }) => {
      attempts += 1;
      return reply({ error: { code: "invalid_exit_interview_request", message: "Synthetic" } }, 422);
    },
  });
  await check("reviewer-rejected-request-keeps-the-reason-and-selection", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    await expand(page, dialog, "General information");
    await dialog.getByRole("checkbox", { name: "Contact Number" }).check();
    await dialog.getByLabel("Reason for correction").fill("Synthetic rejected request.");
    await dialog.getByRole("button", { name: "Review reopening" }).click();
    const confirm = page.getByRole("alertdialog");
    await confirm.getByRole("button", { name: "Reopen for correction", exact: true }).click();
    await shown(confirm.getByText("This correction request could not be saved. Check the reason and the answers to review, then try again.", { exact: true }));
    assert.equal(attempts, 1);
    // Back to the first step: nothing was lost.
    await confirm.getByRole("button", { name: "Cancel" }).click();
    await page.getByRole("button", { name: "Reopen for correction" }).click();
    const again = page.getByRole("dialog");
    assert.equal(await again.getByLabel("Reason for correction").inputValue(), "Synthetic rejected request.");
    await shown(again.getByRole("button", { name: "Remove General information — Contact Number" }));
    assert.deepEqual(fixture.requests[0].targets, ["general.contact_number"]);
  });
}

{
  const fixture = reviewerFixture({ account: viewOnly });
  await check("reviewer-without-reopen-capability-has-no-target-controls", "/portal/exit-interviews/exit-corr", { overrides: fixture.overrides }, async (page) => {
    await shown(page.getByRole("heading", { name: "Maria Santos" }));
    assert.equal(await page.getByRole("button", { name: "Reopen for correction" }).count(), 0);
    assert.equal(await page.getByRole("checkbox").count(), 0);
  });
}

{
  const fixture = reviewerFixture({ legacy: true });
  await check("reviewer-dialog-fits-a-phone", "/portal/exit-interviews/exit-corr", { mobile: true, overrides: fixture.overrides }, async (page) => {
    const dialog = await openChooser(page);
    await expand(page, dialog, "Section III — College Feedback");
    await dialog.getByRole("group", { name: "Program Chair", exact: true }).getByRole("checkbox", { name: "Availability" }).check();
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize();
    assert.ok(box.width <= viewport.width && box.height <= viewport.height, "The dialog stays inside the screen");
    assert.equal(await dialog.evaluate((node) => getComputedStyle(node).overflowY), "auto");
    await noHorizontalOverflow(page);
    await screenshot(page, "reviewer-dialog-phone");
  });
}

// --- Student ----------------------------------------------------------------------------------

const student = { ...user("STUDENT"), capabilities: ["exit_interviews.view_self", "exit_interviews.manage_self"], exit_interview_workspace_available: true };
const reopenEvent = (id, reason, at, targets) => ({ id, reason, reopened_at: at, reopened_by: { id: "reviewer", display_name: "Carlo Reviewer" }, ...(targets ? { targets } : {}) });
const allTargets = [
  "general.contact_number", "completion.program_completion", "completion.extra_terms_count", "career.work",
  "self_assessment.SELF_ESTEEM", "section.self_assessment", "college_feedback.GUIDANCE_COUNSELOR_EFFICIENCY", "college_feedback.comments.guidance_counselor",
];

function studentFixture({ legacy = false, targets = allTargets, events } = {}) {
  const saves = [];
  let submitted = 0;
  let current = record({
    legacy, status: "DRAFT",
    reopen_events: events ?? [
      reopenEvent("earlier", "Earlier synthetic request.", "2026-09-20T02:00:00Z", ["general.major"]),
      reopenEvent("latest", "Please review the answers listed below.", "2026-10-02T02:00:00Z", targets),
    ],
  });
  async function handler({ pathname, method, request, reply }) {
    if (pathname === "/api/v1/exit-interviews/me/exit-corr") {
      if (method === "PUT") {
        const body = JSON.parse(request.postData() ?? "{}");
        saves.push(body);
        // The API answers with full rating rows, as the response view expects.
        const row = (rating) => ({ ...rating, category: "Synthetic", item_label: rating.item_code });
        current = { ...current, ...body, college_feedback_ratings: body.college_feedback_ratings.map(row), self_assessment_ratings: body.self_assessment_ratings.map(row) };
      }
      await reply(current);
      return true;
    }
    if (pathname === "/api/v1/exit-interviews/me/exit-corr/submit") {
      submitted += 1;
      current = { ...current, status: "SUBMITTED", can_edit: false, last_submitted_at: "2026-10-16T03:00:00Z" };
      await reply(current);
      return true;
    }
    return false;
  }
  return { handler, saves, submitted: () => submitted, overrides: { "GET /api/v1/auth/session": session(student) } };
}

const answer = (page, title) => page.getByRole("button", { name: title, exact: true });

// [answer, element that should have focus (or a description of it), hint that should describe it]
const navigationCases = [
  ["General information — Contact Number", "exit-contact-number", "You were asked to review this answer."],
  ["Program completion", "radio:ACCORDING_TO_SCHEDULE", "You were asked to review this answer."],
  ["Program completion — Number of extra terms", "radio:ACCORDING_TO_SCHEDULE", "You were asked to review the delay details. They appear when you choose With some delay."],
  ["Career plans — Work", "exit-career-work", null],
  ["Self-Assessment — Self Esteem", "rating:4", "You were asked to review this answer."],
  ["Section II — Self-Assessment (whole section)", "exit-interview-self-assessment-review", null],
  ["College Feedback — Guidance Counselor — Efficiency", "rating:0", "You were asked to review this answer."],
  ["College Feedback — Comments about the Guidance Counselor", "exit-comment-guidanceCounselorComments", "You were asked to review this answer."],
];

async function followEveryTarget(page) {
  for (const [title, expected, hint] of navigationCases) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await answer(page, title).click();
    const focus = await page.evaluate(() => {
      const node = document.activeElement;
      return { id: node?.id ?? "", type: node?.getAttribute("type"), value: node?.getAttribute("value"), checked: node?.checked, invalid: node?.getAttribute("aria-invalid"), name: node?.getAttribute("name") };
    });
    if (expected.startsWith("radio:")) {
      assert.deepEqual([focus.name, focus.value, focus.checked], ["exit-program-completion", expected.slice(6), true], `${title}: the checked Program completion answer has focus`);
    } else if (expected.startsWith("rating:")) {
      assert.deepEqual([focus.type, focus.value, focus.checked], ["radio", expected.slice(7), true], `${title}: the saved rating has focus`);
    } else {
      assert.equal(focus.id, expected, `${title}: #${expected} has focus`);
    }
    assert.equal(focus.invalid, null, "A requested review never marks the answer invalid");
    if (hint) assert.ok((await activeDescription(page)).includes(hint), `${title} is described by its hint`);
    const inView = await page.evaluate(() => {
      const rect = document.activeElement.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < window.innerHeight;
    });
    assert.ok(inView, `${title}: the focused control is on screen`);
  }
}

for (const device of ["desktop", "phone"]) {
  const fixture = studentFixture();
  await check(`student-follows-every-kind-of-target-${device}`, "/portal/exit-interviews/exit-corr", { handler: fixture.handler, overrides: fixture.overrides, mobile: device === "phone" }, async (page) => {
    const notice = page.getByRole("complementary").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Answers to review", { exact: true }));
    await shown(notice.getByText("Carlo Reviewer reopened this Exit Interview for correction.", { exact: true }));
    for (const code of allTargets) assert.ok(!(await page.locator("main").textContent()).includes(code), `${code} is never shown`);
    await followEveryTarget(page);
    // Nothing moved: the saved ratings are exactly as loaded, including 0.
    assert.equal(await page.locator('input[name="College Feedback Guidance Counselor-GUIDANCE_COUNSELOR_EFFICIENCY"]:checked').getAttribute("value"), "0");
    assert.equal(await page.locator('input[name="Self-Assessment-SELF_ESTEEM"]:checked').getAttribute("value"), "4");
    assert.equal(await page.getByText("Unsaved changes. Save your draft before submitting.").count(), 0, "Following targets changes no answer");
    // The earlier request is history: plain text, not actionable.
    const history = page.getByRole("region", { name: "Correction history" });
    await shown(history.getByText("General information — Major", { exact: true }));
    assert.equal(await history.getByRole("button").count(), 0);
    if (device === "phone") await noHorizontalOverflow(page);
    await screenshot(page, `student-targets-${device}`);
    assert.equal(fixture.saves.length, 0);
  });
}

{
  const fixture = studentFixture({ legacy: true, targets: ["college_feedback.PROGRAM_CHAIR_AVAILABILITY", "college_feedback.comments.program_chair"] });
  await check("legacy-student-reaches-program-chair-targets", "/portal/exit-interviews/exit-corr", { handler: fixture.handler, overrides: fixture.overrides }, async (page) => {
    await answer(page, "College Feedback — Program Chair — Availability").click();
    const focus = await page.evaluate(() => ({ name: document.activeElement?.getAttribute("name"), checked: document.activeElement?.checked }));
    assert.deepEqual(focus, { name: "College Feedback Program Chair-PROGRAM_CHAIR_AVAILABILITY", checked: true });
    await answer(page, "College Feedback — Comments about the Program Chair").click();
    assert.equal(await focusedId(page), "exit-comment-programChairComments");
  });
}

{
  const fixture = studentFixture();
  await check("keyboard-only-student-reaches-a-rating-and-keeps-it", "/portal/exit-interviews/exit-corr", { handler: fixture.handler, overrides: fixture.overrides }, async (page) => {
    await answer(page, "College Feedback — Guidance Counselor — Efficiency").focus();
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.activeElement?.getAttribute("value") === "0" && document.activeElement?.checked);
    await answer(page, "General information — Contact Number").focus();
    await page.keyboard.press("Space");
    await page.waitForFunction(() => document.activeElement?.id === "exit-contact-number");
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("0918 111 2222");
    assert.equal(await page.locator("#exit-contact-number").inputValue(), "0918 111 2222");
  });
}

{
  const fixture = studentFixture();
  await check("targets-never-block-saving-or-resubmission", "/portal/exit-interviews/exit-corr", { handler: fixture.handler, overrides: fixture.overrides }, async (page) => {
    await answer(page, "General information — Contact Number").click();
    await page.locator("#exit-contact-number").fill("0918 111 2222");
    await page.getByRole("button", { name: "Save draft" }).click();
    await shown(page.getByText("Draft saved.", { exact: true }));
    const body = fixture.saves.at(-1);
    assert.equal(body.contact_number, "0918 111 2222");
    for (const key of ["targets", "reopen_events", "status", "id"]) assert.ok(!(key in body), `${key} is not sent`);
    assert.deepEqual(body.college_feedback_ratings.find((row) => row.item_code === "GUIDANCE_COUNSELOR_EFFICIENCY"), { item_code: "GUIDANCE_COUNSELOR_EFFICIENCY", rating: 0 }, "The targeted 0 is saved unchanged");
    // Unchanged targeted answers do not block resubmission.
    await page.getByRole("button", { name: "Submit Exit Interview" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Submit Exit Interview" }).click();
    await page.waitForFunction(() => !document.body.textContent.includes("Answers to review") || !document.body.textContent.includes("Correction requested"));
    assert.equal(fixture.submitted(), 1);
    assert.equal(await page.getByText("Correction requested").count(), 0, "After resubmission no request is shown as pending");
    // The completed requests stay readable as history, without navigation.
    const history = page.getByRole("region", { name: "Correction history" });
    await shown(history.getByText("College Feedback — Guidance Counselor — Efficiency", { exact: true }));
    assert.equal(await history.getByRole("button").count(), 0);
  });
}

{
  const fixture = studentFixture({ events: [reopenEvent("only", "Please update your contact details.", "2026-10-02T02:00:00Z")] });
  await check("legacy-reason-only-correction-is-unchanged", "/portal/exit-interviews/exit-corr", { handler: fixture.handler, overrides: fixture.overrides }, async (page) => {
    const notice = page.getByRole("complementary").filter({ hasText: "Correction requested" });
    await shown(notice.getByText("Please update your contact details.", { exact: false }));
    assert.equal(await notice.getByText("Answers to review").count(), 0);
    assert.equal(await page.locator('[id$="-review"]').count(), 0, "No answer is marked");
  });
}

await finish();
