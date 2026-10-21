// UX15 Student Routine Interview Intake regressions and synthetic visual evidence.
import assert from "node:assert/strict";
import { join } from "node:path";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import {
  blankRoutineIntake,
  routineIntakeFixture,
  routineIntakePath,
  syntheticCounselor,
  syntheticStudent,
} from "./support/ux15-routine-intake-fixtures.mjs";

const phase = process.env.COMPASS_UX15_ROUTINE_PHASE ?? "after";
const { check, finish, shown, hidden, noHorizontalOverflow, artifacts } =
  await createBrowserHarness(`ux15-routine-intake-${phase}`);

async function capture(page, name, target) {
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  if (target) {
    await target.scrollIntoViewIfNeeded();
    await target.screenshot({ path: join(artifacts, `${name}.png`), animations: "disabled" });
  } else {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: join(artifacts, `${name}.png`), animations: "disabled" });
  }
}

async function captureViewport(page, name, target) {
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  if (target) await target.evaluate((element) => element.scrollIntoView({ block: "center", inline: "nearest" }));
  await page.screenshot({ path: join(artifacts, `${name}.png`), animations: "disabled" });
}

function studentOptions(state, device) {
  return { role: "STUDENT", handler: state.handler, device };
}

function getSaveButton(page) {
  return page.getByRole("button", { name: /^Save (Progress|progress)$/ });
}

function getSubmitButton(page) {
  return page.getByRole("button", { name: "Submit Intake", exact: true });
}

function concernSection(page) {
  return page.locator("#routine-intake-section-4");
}

if (phase === "before" || phase === "after") {
  {
    const state = routineIntakeFixture();
    await check(`${phase} 768px tablet layout has no page-wide overflow`, routineIntakePath, {
      role: "STUDENT",
      handler: state.handler,
      viewport: { width: 768, height: 1024 },
    }, async (page) => {
      await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
      await noHorizontalOverflow(page);
      const panel = page.locator("[aria-labelledby='routine-student-intake-heading']");
      assert.ok(await panel.evaluate((element) => element.clientWidth > 0));
    });
  }

  for (const device of ["desktop", "phone"]) {
    const state = routineIntakeFixture();
    await check(`${phase} ${device} form beginning`, routineIntakePath, studentOptions(state, device), async (page) => {
      const title = page.getByRole("heading", { name: "Student Intake", exact: true });
      await shown(title);
      if (device === "desktop") await noHorizontalOverflow(page);
      await captureViewport(page, `${phase}-${device}-beginning`, title);
      if (phase === "after") {
        const sections = page.getByRole("navigation", { name: "Routine Interview sections" });
        await shown(sections);
        assert.equal(await sections.getByRole("link").count(), 7);
        for (const label of [
          "1. Coping with college", "2. College experience", "3. Family",
          "4. Current concerns", "5. College adjustment", "6. Academic goals", "7. Career goals",
        ]) await shown(sections.getByRole("link", { name: label, exact: true }));
        await captureViewport(page, `${phase}-${device}-section-navigation`, title);
        const group = concernSection(page);
        await shown(group);
        await capture(page, `${phase}-${device}-current-concerns`, group);
        if (device === "phone") await noHorizontalOverflow(page);
      } else {
        const group = page.locator("fieldset").filter({ hasText: "4. Current concerns" }).first();
        await shown(group);
        await captureViewport(page, `${phase}-${device}-section-navigation`, title);
        await capture(page, `${phase}-${device}-current-concerns`, group);
      }

      const other = page.getByLabel("Other", { exact: true });
      await other.check();
      const specification = page.getByLabel("Please specify the other concern", { exact: true });
      await specification.fill("Synthetic scheduling preference.");
      await shown(specification);
      assert.equal(await specification.inputValue(), "Synthetic scheduling preference.");
      await capture(page, `${phase}-${device}-other-explanation`, phase === "after" ? concernSection(page) : specification.locator("xpath=../.."));

      await page.locator("#routine-coping").fill("Synthetic response for the visual comparison.");
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      await captureViewport(page, `${phase}-${device}-unsaved-changes`, getSaveButton(page));
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.equal(state.writes.length, 1);
      await captureViewport(page, `${phase}-${device}-confirmed-saved`, getSaveButton(page));
      await captureViewport(page, `${phase}-${device}-submission-ready-actions`, getSubmitButton(page));
    });
  }

  {
    const state = routineIntakeFixture({
      submitted: true,
      intake: { ...blankRoutineIntake(), coping_with_college_challenges: "Synthetic response for review." },
    });
    await check(`${phase} submitted read-only response`, routineIntakePath, studentOptions(state, "phone"), async (page) => {
      await shown(page.getByText("Submitted responses are read-only."));
      await shown(page.getByText("Synthetic response for review.", { exact: true }));
      assert.equal(await getSaveButton(page).count(), 0);
      assert.equal(await getSubmitButton(page).count(), 0);
      await captureViewport(page, `${phase}-read-only-submitted`, page.getByText("Synthetic response for review.", { exact: true }));
    });
  }
}

if (phase === "before") {
  {
    const state = routineIntakeFixture();
    await check("before 320px at 200% text layout measurement", routineIntakePath, studentOptions(state, "narrowPhone"), async (page) => {
      await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      const dimensions = await page.evaluate(() => {
        const panel = document.querySelector("[aria-labelledby='routine-student-intake-heading']");
        return {
          pageScrollWidth: document.documentElement.scrollWidth,
          viewportWidth: document.documentElement.clientWidth,
          panelScrollWidth: panel?.scrollWidth ?? 0,
          panelClientWidth: panel?.clientWidth ?? 0,
        };
      });
      console.log("Baseline 320px/200% text dimensions", dimensions);
    });
  }
  const state = routineIntakeFixture();
  await check("before empty submission validation", routineIntakePath, studentOptions(state, "phone"), async (page) => {
    await getSubmitButton(page).click();
    await shown(page.getByRole("alert").filter({ hasText: "Add at least one response or select a concern" }));
    await captureViewport(page, "before-submission-validation", getSubmitButton(page));
  });
  await finish();
} else if (phase === "after") {
  {
    const state = routineIntakeFixture();
    await check("after empty submission validation summary", routineIntakePath, studentOptions(state, "phone"), async (page) => {
      await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
      await getSubmitButton(page).click();
      await shown(page.getByRole("alert").filter({ hasText: "Add at least one written response or select a concern" }));
      assert.equal(state.submissions, 0);
      await captureViewport(page, "after-submission-validation", getSubmitButton(page));
    });
  }

  {
    const state = routineIntakeFixture();
    await check("seven continuous groups, keyboard section links and mobile fit", routineIntakePath, studentOptions(state, "narrowPhone"), async (page) => {
      await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
      const form = page.locator("form");
      const requiredCount = await form.locator("textarea[required], input[required]").count();
      if (requiredCount !== 0) throw new Error(`Individual questions remain optional; found ${requiredCount} required controls.`);
      const links = page.getByRole("navigation", { name: "Routine Interview sections" }).getByRole("link");
      const linkCount = await links.count();
      if (linkCount !== 7) throw new Error(`Expected seven section links, found ${linkCount}.`);
      const concernLabels = await page.locator("#routine-intake-section-4 label:has(input[type='checkbox'])").evaluateAll((labels) => labels.map((label) => label.innerText.trim()));
      assert.deepEqual(concernLabels, [
        "Family", "Financial", "Academic", "Friends", "Classmates", "Vices",
        "Love life", "Sleeping problems", "Suicidal thought/tendency",
        "Dorm / boarding house", "Past painful experience", "Other",
      ], "the complete concern option set is preserved");
      const target = page.locator("#routine-intake-section-6");
      await links.nth(5).focus();
      await page.keyboard.press("Enter");
      await shown(target);
      const focusedId = await page.evaluate(() => document.activeElement?.id);
      if (focusedId !== "routine-intake-section-6") {
        throw new Error(`Section link should focus its destination; focused ${focusedId}`);
      }
      const top = await target.evaluate((element) => element.getBoundingClientRect().top);
      assert.ok(top >= 0 && top < 220, `The destination is visible below the portal header (${top}px).`);
      for (const id of [1, 2, 3, 4, 5, 6, 7]) {
        const count = await page.locator(`#routine-intake-section-${id}`).count();
        if (count !== 1) throw new Error(`Expected one continuous section ${id}, found ${count}.`);
      }
      const concern = page.getByLabel("Other", { exact: true });
      const label = page.locator("label").filter({ has: concern });
      const box = await label.boundingBox();
      assert.ok(box.height >= 44, `Concern target is at least 44px high (${box.height}px).`);
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      const panel = page.locator("[aria-labelledby='routine-student-intake-heading']");
      const panelWidths = await panel.evaluate((element) => ({ scroll: element.scrollWidth, client: element.clientWidth }));
      const pageWidths = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
      console.log("After 320px/200% text dimensions", { page: pageWidths, form: panelWidths });
      assert.ok(panelWidths.scroll <= panelWidths.client + 1, `The form has no horizontal overflow at 200% text (${JSON.stringify(panelWidths)}).`);
      if (!(await getSaveButton(page).isVisible())) throw new Error("Save Progress should remain visible at 200% text.");
      if (!(await getSubmitButton(page).isVisible())) throw new Error("Submit Intake should remain visible at 200% text.");
    });
  }

  {
    const state = routineIntakeFixture();
    await check("optional answers, minimum meaningful response, explicit exact draft save", routineIntakePath, studentOptions(state, "desktop"), async (page) => {
      assert.equal(await page.locator("form textarea[required], form input[required]").count(), 0);
      assert.equal(await getSaveButton(page).isDisabled(), true, "an untouched draft does not write");
      await getSubmitButton(page).click();
      const summary = page.getByRole("alert").filter({ hasText: "Add at least one written response or select a concern" });
      await shown(summary);
      assert.equal(state.submissions, 0, "validation never submits");
      const answer = "Synthetic exact answer  \nwith a second line\n";
      await page.locator("#routine-family").fill(answer);
      await hidden(summary);
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      assert.equal(await getSubmitButton(page).isDisabled(), true, "unsaved answers cannot be submitted");
      assert.equal(state.writes.length, 0, "typing does not save implicitly");
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.equal(state.writes.length, 1);
      assert.deepEqual(state.writes[0], { ...blankRoutineIntake(), family_description: answer });
      assert.equal(await page.locator("#routine-family").inputValue(), answer);
      assert.equal(await getSubmitButton(page).isEnabled(), true);
      assert.equal(state.submissions, 0, "Save Progress remains separate from submission");
    });
  }

  {
    const state = routineIntakeFixture();
    await check("one concern alone satisfies the meaningful-response rule", routineIntakePath, studentOptions(state, "phone"), async (page) => {
      await page.getByLabel("Family", { exact: true }).check();
      assert.equal(await page.locator("#routine-coping").inputValue(), "");
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.deepEqual(state.writes[0].concerns, ["FAMILY"]);
      await getSubmitButton(page).click();
      await shown(page.getByRole("alertdialog"));
      assert.equal(state.submissions, 0);
      await page.getByRole("alertdialog").getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(state.submissions, 0);
    });
  }

  {
    const state = routineIntakeFixture();
    await check("Other concern, linked validation focus and existing clearing behavior", routineIntakePath, studentOptions(state, "phone"), async (page) => {
      const other = page.getByLabel("Other", { exact: true });
      await other.focus();
      await page.keyboard.press("Space");
      assert.equal(await other.isChecked(), true, "the native Other checkbox remains keyboard-operable");
      const specification = page.getByLabel("Please specify the other concern", { exact: true });
      await shown(specification);
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.deepEqual(state.writes.at(-1).concerns, ["OTHER"]);
      await getSubmitButton(page).click();
      const issueButton = page.getByRole("button", { name: "Please specify the other concern before submitting.", exact: true });
      await shown(issueButton);
      assert.equal(await specification.getAttribute("aria-invalid"), "true");
      assert.equal(await specification.getAttribute("aria-describedby"), "routine-other-concern-error");
      assert.equal(await page.evaluate(() => document.activeElement?.id), "routine-other-concern-specification");
      await issueButton.click();
      assert.equal(await page.evaluate(() => document.activeElement?.id), "routine-other-concern-specification");
      await specification.fill("Synthetic scheduling preference.");
      assert.equal(await specification.inputValue(), "Synthetic scheduling preference.");
      await capture(page, "after-phone-other-explanation", concernSection(page));
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.equal(state.writes.at(-1).other_concern_specification, "Synthetic scheduling preference.");
      await hidden(issueButton);
      await other.focus();
      await page.keyboard.press("Space");
      await hidden(specification);
      await other.focus();
      await page.keyboard.press("Space");
      assert.equal(await page.getByLabel("Please specify the other concern", { exact: true }).inputValue(), "");
      assert.equal(state.submissions, 0);
    });
  }

  {
    const state = routineIntakeFixture();
    let release;
    let observeWrite;
    const writeObserved = new Promise((resolve) => { observeWrite = resolve; });
    state.holdSave = new Promise((resolve) => { release = resolve; });
    state.onWrite = observeWrite;
    await check("pending Save Progress protects the draft and failure keeps the answer", routineIntakePath, studentOptions(state, "phone"), async (page) => {
      const answer = "Synthetic answer retained through a pending save.";
      await page.locator("#routine-coping").fill(answer);
      await getSaveButton(page).click();
      await writeObserved;
      const saving = page.getByRole("button", { name: "Saving…", exact: true });
      await shown(saving);
      assert.equal(await saving.isDisabled(), true);
      assert.equal(await page.locator("#routine-coping").isDisabled(), true);
      assert.equal(await getSubmitButton(page).isDisabled(), true);
      assert.equal(state.writes.length, 1);
      release();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.equal(await page.locator("#routine-coping").inputValue(), answer);
      assert.equal(state.submissions, 0);
    });

    const failed = routineIntakeFixture();
    failed.failSave = true;
    await check("save failure preserves unsaved response and dirty-navigation warning", routineIntakePath, studentOptions(failed, "phone"), async (page) => {
      const answer = "Synthetic response after a failed save.";
      await page.locator("#routine-coping").fill(answer);
      await getSaveButton(page).click();
      await shown(page.getByRole("alert").filter({ hasText: "could not be saved" }));
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      assert.equal(await page.locator("#routine-coping").inputValue(), answer);
      assert.equal(await getSubmitButton(page).isDisabled(), true);
      const originalURL = page.url();
      const prompts = [];
      page.on("dialog", async (dialog) => { prompts.push(dialog.message()); await dialog.dismiss(); });
      await page.getByRole("link", { name: "COMPASS Portal Overview", exact: true }).first().click();
      assert.equal(prompts.length, 1);
      assert.match(prompts[0], /unsaved Routine Interview Intake changes/);
      assert.equal(page.url(), originalURL);
      assert.equal(await page.locator("#routine-coping").inputValue(), answer);
      assert.equal(failed.submissions, 0);
    });
  }

  {
    const state = routineIntakeFixture();
    state.failSubmit = true;
    await check("submission failure retains the saved draft and does not retry", routineIntakePath, studentOptions(state, "desktop"), async (page) => {
      const answer = "Synthetic answer retained after submission failure.";
      await page.locator("#routine-coping").fill(answer);
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      await getSubmitButton(page).click();
      const dialog = page.getByRole("alertdialog");
      await shown(dialog);
      await dialog.getByRole("button", { name: "Submit Intake", exact: true }).click();
      await shown(dialog.getByRole("alert").filter({ hasText: "could not be confirmed" }));
      if (state.submissions !== 1) throw new Error(`The failed action must not replay; got ${state.submissions} submissions.`);
      const retainedAnswer = await page.locator("#routine-coping").inputValue();
      if (retainedAnswer !== answer) throw new Error("The saved response must remain available after submission failure.");
      const staleSavedMessages = await page.getByText("Progress saved.").count();
      if (staleSavedMessages !== 0) throw new Error("A prior save confirmation must clear when submission starts.");
      const formSubmitButtons = await page.locator("form button[type='button']").count();
      if (formSubmitButtons !== 1) throw new Error(`The form should remain available after failure; found ${formSubmitButtons} submit actions.`);
    });
  }

  {
    const state = routineIntakeFixture();
    let release;
    state.holdSubmit = new Promise((resolve) => { release = resolve; });
    await check("confirmation cancellation, pending submission, and read-only transition", routineIntakePath, studentOptions(state, "phone"), async (page) => {
      await page.locator("#routine-coping").fill("Synthetic answer for deliberate submission.");
      assert.equal(await getSubmitButton(page).isDisabled(), true);
      await getSaveButton(page).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      await getSubmitButton(page).click();
      const dialog = page.getByRole("alertdialog");
      await shown(dialog);
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(state.submissions, 0);
      await hidden(dialog);
      await getSubmitButton(page).click();
      await dialog.getByRole("button", { name: "Submit Intake", exact: true }).click();
      const submitting = dialog.getByRole("button", { name: "Submitting…", exact: true });
      await shown(submitting);
      assert.equal(await submitting.isDisabled(), true);
      await page.keyboard.press("Escape");
      await shown(dialog);
      assert.equal(state.submissions, 1);
      release();
      await shown(page.getByText("Submitted responses are read-only."));
      await shown(page.getByText("Synthetic answer for deliberate submission.", { exact: true }));
      await hidden(page.locator("form"));
      assert.equal(state.submissions, 1, "one deliberate action submits once");
      await captureViewport(page, "after-read-only-submitted", page.getByText("Synthetic answer for deliberate submission.", { exact: true }));
    });
  }

  for (const workflowState of ["CLOSED_APPOINTMENT_CANCELLED", "CLOSED_APPOINTMENT_NO_SHOW"]) {
    const state = routineIntakeFixture({ workflowState });
    await check(`historical ${workflowState} remains read-only`, routineIntakePath, studentOptions(state, "desktop"), async (page) => {
      await shown(page.getByText("The record remains available as historical context."));
      await shown(page.getByText("This draft is preserved for history and is now read-only."));
      assert.equal(await getSaveButton(page).count(), 0);
      assert.equal(await getSubmitButton(page).count(), 0);
    });
  }

  {
    const state = routineIntakeFixture({
      account: syntheticCounselor(),
      counselorDraft: true,
    });
    await check("Counselor cannot see Student draft Intake content", routineIntakePath, { role: "COUNSELOR", handler: state.handler }, async (page) => {
      await shown(page.getByText("Student Intake is still a draft."));
      assert.equal(await page.getByText("Synthetic response for review.", { exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Save Progress", exact: true }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Submit Intake", exact: true }).count(), 0);
    });
  }

  {
    const state = routineIntakeFixture({
      account: syntheticStudent({ current: false }),
      intake: { ...blankRoutineIntake(), coping_with_college_challenges: "Synthetic historical draft." },
    });
    await check("non-current Student can view but cannot edit a preserved draft", routineIntakePath, studentOptions(state, "desktop"), async (page) => {
      await shown(page.getByText("You can view your draft, but your current Student status does not allow Intake changes."));
      await shown(page.getByText("Synthetic historical draft.", { exact: true }));
      assert.equal(await page.locator("form").count(), 0);
      assert.equal(await page.getByRole("button", { name: "Save Progress", exact: true }).count(), 0);
    });
  }

  {
    const state = routineIntakeFixture({ account: syntheticStudent({ canView: false, canManage: false }) });
    await check("Student without Routine Interview view capability sees unavailable state", routineIntakePath, studentOptions(state, "desktop"), async (page) => {
      await shown(page.getByText("This Routine Interview is unavailable.", { exact: true }));
      assert.equal(state.reads, 0, "the unavailable route does not request the detail");
      assert.equal(await page.getByRole("button", { name: "Save Progress", exact: true }).count(), 0);
    });
  }
}

await finish();
