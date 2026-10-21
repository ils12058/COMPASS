// Screenshot capture and browser regressions for Counselor Evaluation use only synthetic
// records. The shared harness blocks requests outside the local Next process.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import {
  counselorEvaluationFixture,
  evaluationFields,
  routineEvaluationPath,
  syntheticEncounter,
} from "./support/ux15-counselor-evaluation-fixtures.mjs";

const phase = process.env.COMPASS_UX15_EVALUATION_PHASE ?? "after";
const { check, finish, shown, screenshot, noHorizontalOverflow } = await createBrowserHarness(`ux15-counselor-evaluation-${phase}`);
const saveButtonName = phase === "before" ? "Save evaluation" : "Save Evaluation";

if (phase === "before") {
  for (const device of ["desktop", "phone"]) {
    const state = counselorEvaluationFixture();
    await check(`before-${device}-beginning`, routineEvaluationPath, { handler: state.handler, device }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.evaluate(() => document.fonts.ready);
      await noHorizontalOverflow(page);
      await screenshot(page, `before-${device}-beginning`);
      const firstGroup = page.getByRole("group", { name: "Academically" });
      await shown(firstGroup);
      await screenshot(page, `before-${device}-ratings`, firstGroup.locator(".."));
      await screenshot(page, `before-${device}-narrative`, page.locator("form"));
      await page.getByLabel("Special concern that needs attention", { exact: true }).fill("Synthetic unsaved concern.");
      await screenshot(page, `before-${device}-unsaved`);
      await page.getByRole("button", { name: saveButtonName, exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Evaluation progress saved." }));
      await screenshot(page, `before-${device}-saved`);
    });
  }
  for (const [name, fixtureOptions, interaction] of [
    ["linked", { linkedEncounter: syntheticEncounter("011") }, null],
    ["direct-selection", {}, "select"],
    ["no-eligible-encounter", { candidates: [] }, null],
    ["finalized", { linkedEncounter: syntheticEncounter("012"), evaluationStatus: "FINALIZED" }, null],
  ]) {
    const state = counselorEvaluationFixture(fixtureOptions);
    await check(`before-${name}`, routineEvaluationPath, { handler: state.handler, device: name === "direct-selection" ? "phone" : "desktop" }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      if (interaction === "select") {
        await page.getByRole("radio", { name: /2026/ }).check();
        await screenshot(page, "before-direct-selection");
        await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
        await screenshot(page, "before-finalization-ready");
        const dialog = page.getByRole("alertdialog");
        await shown(dialog);
        await screenshot(page, "before-finalization-confirmation", dialog);
        await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      }
      if (name === "finalized") {
        await shown(page.getByText(/Finalized.*Read-only\./).first());
        assert.equal(await page.getByRole("button", { name: saveButtonName, exact: true }).count(), 0);
      }
      await screenshot(page, `before-${name}`);
    });
  }
}

if (phase === "after") {
  for (const device of ["desktop", "phone"]) {
    const state = counselorEvaluationFixture();
    await check("after-" + device + "-visual-and-save", routineEvaluationPath, { handler: state.handler, device }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.evaluate(() => document.fonts.ready);
      if (device !== "phone") await noHorizontalOverflow(page);
      await screenshot(page, "after-" + device + "-beginning");
      const firstGroup = page.getByRole("group", { name: "Academically" });
      await shown(firstGroup);
      await screenshot(page, "after-" + device + "-ratings", firstGroup.locator(".."));
      await screenshot(page, "after-" + device + "-narrative", page.locator("form"));
      const specialConcern = "Exact wording: trailing spaces  \nsecond line\n";
      await page.getByLabel("Special concern that needs attention", { exact: true }).fill(specialConcern);
      await screenshot(page, "after-" + device + "-unsaved");
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      await page.getByRole("button", { name: saveButtonName, exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Evaluation progress saved." }));
      await screenshot(page, "after-" + device + "-saved");
      assert.equal(state.writes.length, 1);
      assert.deepEqual(state.writes[0], { ...evaluationFields, special_concern: specialConcern });
      assert.equal(state.finalizations.length, 0, "Saving remains separate from finalization");
    });
  }

  {
    const state = counselorEvaluationFixture();
    await check("after-rating-scale-null-and-keyboard", routineEvaluationPath, { handler: state.handler, device: "phone" }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      for (const label of ["Academically", "Physically", "Socially", "Spiritually", "Financially", "Emotionally"]) {
        const group = page.getByRole("group", { name: label });
        const radios = group.getByRole("radio");
        assert.equal(await radios.count(), 11, label + " keeps Not rated and all ten values");
        assert.equal(await group.getAttribute("aria-describedby"), "routine-evaluation-scale-description");
        assert.equal(await radios.first().getAttribute("value"), "null");
        assert.equal(await radios.nth(10).getAttribute("value"), "10");
        assert.equal(await radios.nth(10).getAttribute("aria-describedby"), "routine-evaluation-scale-description");
        const target = group.locator("label").nth(1);
        const box = await target.boundingBox();
        assert.ok(box.width >= 44 && box.height >= 44, label + " has a comfortable touch target");
      }
      const academic = page.getByRole("group", { name: "Academically" });
      const seven = academic.getByRole("radio", { name: "Academically: 7" });
      await seven.focus();
      await page.keyboard.press("ArrowRight");
      assert.equal(await academic.getByRole("radio", { name: "Academically: 8" }).isChecked(), true);
      await academic.getByRole("radio", { name: "Not rated", exact: true }).check();
      assert.equal(await academic.getByRole("radio", { name: "Not rated", exact: true }).isChecked(), true);
      const expectedValues = ["null", ...Array.from({ length: 10 }, (_, index) => String(index + 1))];
      for (const label of ["Academically", "Physically", "Socially", "Spiritually", "Financially", "Emotionally"]) {
        const values = await page.getByRole("group", { name: label }).getByRole("radio").evaluateAll((inputs) => inputs.map((input) => input.value));
        assert.deepEqual(values, expectedValues, label + " exposes the complete source scale");
      }
      const concern = "Rating payload keeps exact note  \nincluding its final line\n";
      await page.getByRole("group", { name: "Socially" }).locator("label").nth(10).click();
      await page.getByLabel("Special concern that needs attention", { exact: true }).fill(concern);
      assert.equal(state.writes.length, 0, "Changing ratings and text does not save implicitly");
      await page.getByRole("button", { name: saveButtonName, exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Evaluation progress saved." }));
      assert.deepEqual(state.writes[0], {
        ...evaluationFields,
        academic_adjustment_rating: null,
        social_adjustment_rating: 10,
        special_concern: concern,
      });
      assert.equal(state.finalizations.length, 0);
    });
  }

  {
    const state = counselorEvaluationFixture();
    await check("after-unsaved-navigation-protection", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.getByLabel("Recommendations", { exact: true }).fill("Synthetic unsaved recommendation.");
      const originalUrl = page.url();
      const prompts = [];
      page.on("dialog", async (dialog) => { prompts.push(dialog.message()); await dialog.dismiss(); });
      await page.getByRole("link", { name: "Overview", exact: true }).first().click();
      assert.equal(prompts.length, 1);
      assert.match(prompts[0], /unsaved Counselor Evaluation changes/);
      assert.equal(page.url(), originalUrl, "Dismissal keeps the Counselor in the draft");
      assert.equal(await page.getByLabel("Recommendations", { exact: true }).inputValue(), "Synthetic unsaved recommendation.");
      assert.equal(state.writes.length, 0);
    });
  }

  {
    const state = counselorEvaluationFixture();
    state.saveFailure = 503;
    await check("after-save-failure-keeps-draft-editable", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      const text = "Synthetic failed-save text.";
      await page.getByLabel("Other adjustment", { exact: true }).fill(text);
      await page.getByRole("button", { name: saveButtonName, exact: true }).click();
      await shown(page.getByRole("alert").filter({ hasText: "The Counselor Evaluation could not be saved." }));
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      assert.equal(await page.getByLabel("Other adjustment", { exact: true }).inputValue(), text);
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isDisabled(), true);
      assert.equal(state.finalizations.length, 0);
    });
  }

  {
    let releaseSave;
    let notifyWriteStarted;
    const state = counselorEvaluationFixture();
    state.holdSave = new Promise((resolve) => { releaseSave = resolve; });
    const writeStarted = new Promise((resolve) => { notifyWriteStarted = resolve; });
    state.onWrite = notifyWriteStarted;
    await check("after-pending-save-protects-fields", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.getByLabel("Recommendations", { exact: true }).fill("Pending synthetic save.");
      const saveButton = page.getByRole("button", { name: saveButtonName, exact: true });
      await saveButton.click();
      await shown(page.getByRole("status").filter({ hasText: "Saving…" }));
      assert.equal(await saveButton.isDisabled(), true);
      assert.equal(await page.getByLabel("Recommendations", { exact: true }).isDisabled(), true);
      await writeStarted;
      assert.equal(state.writes.length, 1, "One canonical save request is pending");
      assert.equal(state.finalizations.length, 0);
      releaseSave();
      await shown(page.getByRole("status").filter({ hasText: "Evaluation progress saved." }));
    });
  }

  {
    const state = counselorEvaluationFixture();
    await check("after-direct-finalization-cancel-and-success", routineEvaluationPath, { handler: state.handler, device: "phone" }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      const candidates = page.getByRole("group", { name: "Select the completed Encounter for this interaction" });
      await candidates.getByRole("radio").first().check();
      await screenshot(page, "after-direct-selection");
      const finalizeButton = page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true });
      await screenshot(page, "after-finalization-ready");
      await finalizeButton.click();
      const dialog = page.getByRole("alertdialog");
      await shown(dialog);
      await screenshot(page, "after-finalization-confirmation", dialog);
      assert.match(await dialog.innerText(), /makes the Evaluation read-only/);
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(state.finalizations.length, 0, "Cancel does not finalize");
      await finalizeButton.click();
      await dialog.getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      await shown(page.getByText(/Finalized.*Read-only\./).first());
      assert.equal(state.finalizations.length, 1);
      assert.equal(state.finalizations[0].encounter_id, syntheticEncounter("001").id);
      assert.equal(await page.getByRole("button", { name: saveButtonName, exact: true }).count(), 0);
      await screenshot(page, "after-finalized");
    });
  }

  {
    const state = counselorEvaluationFixture({ linkedEncounter: syntheticEncounter("011") });
    await check("after-linked-encounter-needs-no-choice", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByText("Encounter already linked", { exact: true }));
      await screenshot(page, "after-linked");
      assert.equal(await page.getByRole("radio", { name: /2026/ }).count(), 0);
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isEnabled(), true);
    });
  }

  {
    const state = counselorEvaluationFixture({ entryMode: "APPOINTMENT", candidates: [syntheticEncounter("021", "APPOINTMENT")] });
    await check("after-appointment-finalization-is-server-resolved", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByText(/Finalization will link it to this Routine Interview/));
      assert.equal(await page.getByRole("radio", { name: /2026/ }).count(), 0);
      await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      await shown(page.getByText(/Finalized.*Read-only\./).first());
      assert.equal(state.finalizations.length, 1);
      assert.equal(state.finalizations[0].encounter_id, null);
    });
  }

  {
    const state = counselorEvaluationFixture({ candidates: [] });
    await check("after-no-eligible-encounter-blocks-finalization", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByText("No eligible completed Encounter is available yet.", { exact: true }));
      await screenshot(page, "after-no-eligible-encounter");
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isDisabled(), true);
      assert.equal(state.finalizations.length, 0);
    });
  }

  {
    const state = counselorEvaluationFixture();
    state.detail = {
      ...state.detail,
      evaluation: {
        ...evaluationFields,
        academic_adjustment_rating: null,
        physical_adjustment_rating: null,
        social_adjustment_rating: null,
        spiritual_adjustment_rating: null,
        financial_adjustment_rating: null,
        emotional_adjustment_rating: null,
        other_adjustment: "",
        special_concern: "",
        recommendations: "",
      },
    };
    await check("after-empty-evaluation-retains-current-optional-behavior", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      assert.equal(await page.locator("main form [required]").count(), 0, "The presentation adds no required evaluation fields");
      assert.equal(await page.getByRole("group", { name: "Academically" }).getByRole("radio", { name: "Not rated", exact: true }).isChecked(), true);
      assert.equal(await page.getByLabel("Other adjustment", { exact: true }).inputValue(), "");
      assert.equal(await page.getByRole("button", { name: saveButtonName, exact: true }).isDisabled(), true);
      await page.getByRole("group", { name: "Select the completed Encounter for this interaction" }).getByRole("radio").first().check();
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isEnabled(), true);
      await screenshot(page, "after-empty-evaluation-ready");
      assert.equal(state.writes.length, 0);
      assert.equal(state.finalizations.length, 0);
    });
  }

  {
    const state = counselorEvaluationFixture({
      candidateFailurePages: [1],
      candidates: Array.from({ length: 21 }, (_, index) => syntheticEncounter(String(index + 1).padStart(3, "0"))),
    });
    await check("after-candidate-retry-and-pagination", routineEvaluationPath, { handler: state.handler, device: "phone" }, async (page) => {
      const candidateError = page.getByRole("alert").filter({ hasText: "Completed Counseling interactions could not be loaded." });
      await shown(candidateError);
      await candidateError.getByRole("button", { name: "Retry", exact: true }).click();
      const group = page.getByRole("group", { name: "Select the completed Encounter for this interaction" });
      await shown(group.getByRole("radio").first());
      assert.equal(await group.getByRole("radio").first().isChecked(), false, "The first candidate is never selected automatically");
      await page.getByRole("button", { name: "Next", exact: true }).click();
      await shown(page.getByText("Page 2", { exact: true }));
      assert.ok(state.candidateRequests.some((search) => search.includes("page=2")));
      assert.equal(await group.getByRole("radio").count(), 1);
      assert.equal(await group.getByRole("radio").first().isChecked(), false);
      assert.equal(state.finalizations.length, 0);
    });
  }

  {
    const state = counselorEvaluationFixture();
    state.finalizeMode = "mismatch";
    await check("after-stale-encounter-reconciles-before-retry", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.getByRole("group", { name: "Select the completed Encounter for this interaction" }).getByRole("radio").first().check();
      await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      await shown(page.getByText(/The latest Evaluation is still a draft/));
      assert.equal(state.detailReads, 2, "Initial read and reconciliation each fetch canonical status");
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isDisabled(), true);
      assert.equal(await page.getByRole("radio", { name: /2026/ }).first().isChecked(), false);
      assert.equal(state.finalizations.length, 1);
    });
  }

  {
    const state = counselorEvaluationFixture();
    state.finalizeMode = "uncertain-draft";
    await check("after-uncertain-finalization-requires-status-check", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.getByRole("group", { name: "Select the completed Encounter for this interaction" }).getByRole("radio").first().check();
      state.detail = {
        ...state.detail,
        evaluation: { ...state.detail.evaluation, special_concern: "Latest canonical professional note." },
      };
      state.failDetailReads = 1;
      await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
      const dialog = page.getByRole("alertdialog");
      await dialog.getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      const checkStatus = page.getByRole("button", { name: "Check current status", exact: true });
      await shown(checkStatus);
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isDisabled(), true);
      assert.equal(state.finalizations.length, 1, "An uncertain request is not replayed automatically");
      await checkStatus.click();
      await shown(page.getByText(/The latest Evaluation is still a draft/));
      assert.equal(await page.getByLabel("Special concern that needs attention", { exact: true }).inputValue(), "Latest canonical professional note.");
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isDisabled(), true);
      await page.getByRole("radio", { name: /2026/ }).first().check();
      assert.equal(await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).isEnabled(), true);
      state.finalizeMode = "ok";
      await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      await shown(page.getByText(/Finalized.*Read-only\./).first());
      assert.equal(state.finalizations.length, 2, "The retry requires a fresh deliberate confirmation");
    });
  }

  {
    const state = counselorEvaluationFixture();
    state.finalizeMode = "uncertain-committed";
    await check("after-uncertain-committed-finalization-becomes-read-only", routineEvaluationPath, { handler: state.handler }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      await page.getByRole("group", { name: "Select the completed Encounter for this interaction" }).getByRole("radio").first().check();
      await page.getByRole("button", { name: "Finalize Counselor Evaluation", exact: true }).click();
      await page.getByRole("alertdialog").getByRole("button", { name: "Finalize evaluation", exact: true }).click();
      await shown(page.getByText(/Finalized.*Read-only\./).first());
      assert.equal(state.finalizations.length, 1, "The GET reconciliation confirms success without a duplicate POST");
      assert.equal(state.detailReads, 2, "The canonical read confirms the uncertain finalization");
    });
  }

  for (const device of ["narrowPhone", "phone", "tablet"]) {
    const state = counselorEvaluationFixture();
    await check("after-responsive-keyboard-and-text-reflow-" + device, routineEvaluationPath, { handler: state.handler, device }, async (page) => {
      await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
      const form = page.locator("main form");
      const dimensions = await form.evaluate((element) => ({ width: element.clientWidth, scroll: element.scrollWidth }));
      assert.ok(dimensions.width > 0 && dimensions.scroll <= dimensions.width + 1, "The form fits its viewport without internal horizontal scrolling");
      if (device === "phone") await noHorizontalOverflow(page);
      await page.getByLabel("Other adjustment", { exact: true }).focus();
      assert.equal(await page.evaluate(() => document.activeElement?.id), "routine-evaluation-other_adjustment");
      await page.keyboard.type("Keyboard input remains available.");
      assert.match(await page.getByLabel("Other adjustment", { exact: true }).inputValue(), /Keyboard input/);
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      const overflowing = await form.evaluate((element) => [...element.querySelectorAll("*")]
        .filter((child) => {
          const rect = child.getBoundingClientRect();
          return rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1);
        })
        .map((child) => {
          const rect = child.getBoundingClientRect();
          return { tag: child.tagName, id: child.id, text: child.textContent?.trim().slice(0, 70), left: rect.left, right: rect.right };
        }));
      if (overflowing.length) console.log("overflow at 200% " + device + ": " + JSON.stringify(overflowing));
      assert.deepEqual(overflowing, [], "The form reflows at 200% text size");
      assert.equal(state.writes.length, 0);
      assert.equal(state.finalizations.length, 0);
    });
  }
}

await finish();
