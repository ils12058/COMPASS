import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { exitFixture, exitPath } from "./support/ux15-exit-fixtures.mjs";
const phase = process.env.COMPASS_UX15_EXIT_PHASE ?? "after";
const { check, shown, hidden, noHorizontalOverflow, screenshot, artifacts, finish } = await createBrowserHarness(`ux15-exit-${phase}`);
async function capture(page, name, element) {
  await page.addStyleTag({ content: "nextjs-portal { display:none !important; }" });
  if (element) await screenshot(page, name, element);
  else await page.screenshot({ path: join(artifacts, `${name}.png`), animations: "disabled" });
}
for (const device of ["desktop", "phone"]) {
  const fixture = exitFixture();
  await check(`${phase} ${device} representative visual states`, exitPath, { handler: fixture.handler, device }, async page => {
    await shown(page.locator("#exit-student-name"));
    await noHorizontalOverflow(page);
    await capture(page, `${phase}-${device}-beginning`);
    await capture(page, `${phase}-${device}-self`, page.locator("#exit-interview-self-assessment").locator("xpath=ancestor::section[1]"));
    const college = page.locator("#exit-interview-college-feedback").locator("xpath=ancestor::section[1]");
    await capture(page, `${phase}-${device}-college`, college.locator("section").first());
    const save = page.getByRole("button", { name: "Save draft", exact: true });
    await save.scrollIntoViewIfNeeded();
    await capture(page, `${phase}-${device}-ready`);
    await page.locator("#exit-contact-number").fill("0918 111 2222");
    await save.scrollIntoViewIfNeeded();
    await capture(page, `${phase}-${device}-unsaved`);
    assert.equal(fixture.writes.length, 0);
  });
  const missing = exitFixture({ missing: true });
  await check(`${phase} ${device} missing rating visual state`, exitPath, { handler: missing.handler, device }, async page => {
    const summary = page.locator("summary").filter({ hasText: "required ratings still need" });
    await summary.click();
    await capture(page, `${phase}-${device}-missing`);
  });
}
{
  const fixture = exitFixture({ correction: true });
  await check(`${phase} correction visual state`, exitPath, { handler: fixture.handler, device: "phone" }, async page => {
    await shown(page.getByRole("heading", { name: "Correction requested", exact: true }));
    await capture(page, `${phase}-phone-correction`, page.locator('aside[aria-labelledby="exit-interview-correction-heading"]'));
  });
}
if (phase !== "before") {
  for (const [device, viewport] of [["desktop", { width: 1920, height: 1080 }], ["tablet", { width: 768, height: 1024 }], ["narrowPhone", undefined]]) {
    const state = exitFixture();
    await check(`Continuous sections, matrix scrolling and reflow at ${device}`, exitPath, { handler: state.handler, device, viewport }, async page => {
      await shown(page.locator("#exit-student-name"));
      const inputs = await page.locator("form input").count();
      const nav = page.getByRole("navigation", { name: "Exit Interview sections", exact: true });
      const links = nav.getByRole("link");
      for (let index = 0; index < 6; index++) {
        const href = await links.nth(index).getAttribute("href");
        await links.nth(index).focus(); await page.keyboard.press("Enter");
        assert.equal(await page.evaluate(() => document.activeElement?.id), href.slice(1));
        const top = await page.locator(href).evaluate(el => el.getBoundingClientRect().top);
        assert.ok(top >= 55, "Explicit destination stays below the portal header");
        assert.equal(await page.locator("form input").count(), inputs, "All sections stay mounted");
        await noHorizontalOverflow(page);
      }
      const matrix = page.getByRole("region", { name: "Self-Assessment rating choices", exact: true });
      const label = matrix.locator("tbody label").first();
      const size = await label.boundingBox(); assert.ok(size.width >= 44 && size.height >= 44);
      if (device !== "desktop" && await matrix.evaluate(el => el.scrollWidth > el.clientWidth)) {
        await matrix.focus(); await page.keyboard.press("ArrowRight");
        await page.waitForFunction(() => document.querySelector('[aria-label="Self-Assessment rating choices"]').scrollLeft > 0);
        await page.keyboard.press("ArrowLeft");
        await page.waitForFunction(() => document.querySelector('[aria-label="Self-Assessment rating choices"]').scrollLeft < 1);
        const choices = page.locator("#exit-rating-self-self-esteem input");
        await choices.first().focus(); await page.keyboard.press("ArrowRight");
        assert.equal(await choices.nth(1).isChecked(), true, "Radio-group arrow selection remains native");
        await page.keyboard.press("ArrowLeft");
        assert.equal(await choices.first().isChecked(), true);
      }
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      // Intentional matrix scroll is local. The existing global top bar at 320px/200% is outside
      // this assertion; never hide or crop the form to make overflow checks pass.
      const outside = await page.locator("main form").evaluate(el => [...el.querySelectorAll("*")].filter(child => !child.closest('[role="region"]') && child.getBoundingClientRect().width && child.getBoundingClientRect().right > innerWidth + 1).map(child => child.id || child.tagName));
      assert.deepEqual(outside, []);
      const navOverflow = await nav.evaluate(el => el.getBoundingClientRect().right > innerWidth + 1 || el.scrollWidth > el.clientWidth + 1);
      assert.equal(navOverflow, false);
      await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
      await page.getByRole("link", { name: "Back to sections", exact: true }).click();
      assert.equal(await page.evaluate(() => document.activeElement?.id), "exit-interview-section-links");
      assert.equal(state.writes.length, 0); assert.equal(state.submissions, 0);
    });
  }
  {
    const state = exitFixture({ missing: true });
    await check("Missing ratings focus the original controls, announce errors and preserve zero", exitPath, { handler: state.handler, device: "phone" }, async page => {
      await page.locator("summary").filter({ hasText: "required ratings still need" }).click();
      const issue = page.getByRole("button", { name: "Self-Assessment — Self Esteem", exact: true });
      await issue.focus(); await page.keyboard.press("Enter");
      const row = page.locator("#exit-rating-self-self-esteem");
      const focused = row.locator("input").first();
      assert.equal(await focused.evaluate(el => document.activeElement === el), true);
      assert.match(await focused.getAttribute("aria-describedby"), /exit-rating-self-self-esteem-error/);
      await row.locator('input[value="4"]').check();
      await page.getByRole("button", { name: "College Feedback — Guidance Counselor — Efficiency", exact: true }).click();
      const college = page.locator("#exit-rating-college-guidance-counselor-efficiency");
      await college.locator('input[value="0"]').check();
      await shown(page.getByText("Self-Assessment: 15 of 15 answered", { exact: true }));
      await shown(page.getByText("College Feedback: 23 of 23 answered", { exact: true }));
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Draft saved." }));
      assert.equal(state.writes.at(-1).college_feedback_ratings.find(row => row.item_code === "GUIDANCE_COUNSELOR_EFFICIENCY").rating, 0);
    });
  }
  {
    const state = exitFixture();
    await check("Conditional validation, failed save and pending save retain the draft", exitPath, { handler: state.handler, device: "phone" }, async page => {
      const save = page.getByRole("button", { name: "Save draft", exact: true });
      await page.getByRole("radio", { name: "With some delay", exact: true }).check();
      await save.click();
      await shown(page.getByRole("region", { name: "Answers to review", exact: true }));
      await capture(page, "after-phone-conditional-error");
      const error = page.getByRole("button", { name: "Enter the number of extra terms as a positive whole number.", exact: true });
      await error.focus(); await page.keyboard.press("Enter");
      assert.equal(await page.evaluate(() => document.activeElement?.id), "exit-extra-terms");
      assert.equal(state.writes.length, 0);
      await page.locator("#exit-extra-terms").fill("2");
      await page.locator("#exit-delay-other").check();
      await page.locator("#exit-delay-other-detail").fill("Synthetic reason for delay.");
      state.failSave = true;
      await save.click();
      await shown(page.getByRole("alert").filter({ hasText: "draft could not be saved" }));
      assert.equal(await page.locator("#exit-delay-other-detail").inputValue(), "Synthetic reason for delay.");
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      state.failSave = false;
      let release; state.holdSave = new Promise(resolve => { release = resolve; });
      await save.click();
      await shown(page.getByRole("status").filter({ hasText: "Saving…" }));
      assert.equal(await page.getByRole("button", { name: "Saving…", exact: true }).isDisabled(), true);
      assert.equal(await page.locator("#exit-contact-number").isDisabled(), true);
      release();
      await shown(page.getByRole("status").filter({ hasText: "Draft saved." }));
      assert.equal(state.writes.length, 2);
      assert.equal(state.writes.at(-1).extra_terms_count, 2);
      assert.equal(state.writes.at(-1).delay_other, "Synthetic reason for delay.");
      // Native requiredness is unchanged and still prevents final confirmation for a missing
      // conditional answer, even after that answer has been saved as an incomplete draft.
      await page.locator("#exit-delay-other-detail").fill("");
      state.holdSave = null; await save.click();
      await shown(page.getByRole("status").filter({ hasText: "Draft saved." }));
      await page.getByRole("button", { name: "Submit Exit Interview", exact: true }).click();
      assert.equal(await page.locator("#exit-delay-other-detail").evaluate(el => el.validity.valueMissing), true);
      await hidden(page.getByRole("alertdialog"));
      assert.equal(state.submissions, 0);
    });
  }
  for (const submitMode of ["ok", "unknown-committed", "unknown-draft"]) {
    const state = exitFixture(); state.submitMode = submitMode;
    await check(`Submission confirmation and reconciliation: ${submitMode}`, exitPath, { handler: state.handler }, async page => {
      const submit = page.getByRole("button", { name: "Submit Exit Interview", exact: true });
      await shown(submit); await submit.click();
      const dialog = page.getByRole("alertdialog");
      await shown(dialog); await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(state.submissions, 0);
      await submit.click();
      let release; state.holdSubmit = new Promise(resolve => { release = resolve; });
      await dialog.getByRole("button", { name: "Submit Exit Interview", exact: true }).click();
      const sending = dialog.getByRole("button", { name: "Submitting…", exact: true });
      await shown(sending); assert.equal(await sending.isDisabled(), true); release();
      await hidden(dialog);
      if (submitMode === "ok") {
        await hidden(page.getByRole("button", { name: "Save draft", exact: true }));
      } else {
        const refresh = page.getByRole("button", { name: "Refresh Exit Interview", exact: true });
        await shown(refresh);
        assert.equal(await submit.isDisabled(), true);
        assert.equal(await page.getByRole("button", { name: "Save draft", exact: true }).isDisabled(), true);
        await shown(page.getByRole("status").filter({ hasText: "Submission status unconfirmed" }));
        state.failRefresh = true; await refresh.click();
        await shown(page.getByText("The Exit Interview could not be refreshed. Retry before submitting again.", { exact: true }));
        assert.equal(state.submissions, 1);
        assert.equal(await submit.isDisabled(), true);
        state.failRefresh = false; await refresh.click();
        if (submitMode === "unknown-committed") {
          await hidden(page.getByRole("button", { name: "Save draft", exact: true }));
        } else {
          await hidden(refresh); assert.equal(await submit.isEnabled(), true);
          assert.equal(state.submissions, 1, "Refresh never replays submission");
          state.submitMode = "ok"; state.holdSubmit = null;
          await submit.click(); await dialog.getByRole("button", { name: "Submit Exit Interview", exact: true }).click();
          await hidden(page.getByRole("button", { name: "Save draft", exact: true }));
          assert.equal(state.submissions, 2, "A confirmed draft is resubmitted only after deliberate confirmation");
        }
      }
      assert.equal(state.writes.length, 0);
    });
  }
  {
    const state = exitFixture({ correction: true });
    await check("Latest correction targets coexist with section links and historical events", exitPath, { handler: state.handler }, async page => {
      const correction = page.locator('aside[aria-labelledby="exit-interview-correction-heading"]');
      await shown(page.getByText("Earlier synthetic request.", { exact: true }));
      await correction.getByRole("button", { name: "Program completion — Number of extra terms", exact: true }).click();
      assert.equal(await page.evaluate(() => document.activeElement?.name), "exit-program-completion");
      await page.getByRole("radio", { name: "With some delay", exact: true }).check();
      await correction.getByRole("button", { name: "Program completion — Number of extra terms", exact: true }).click();
      assert.equal(await page.evaluate(() => document.activeElement?.id), "exit-extra-terms");
      await page.locator("#exit-extra-terms").fill("1");
      await correction.getByRole("button", { name: "Self-Assessment — Self Esteem", exact: true }).click();
      assert.equal(await page.evaluate(() => document.activeElement?.value), "5");
      await shown(page.getByRole("heading", { name: "Correction history", exact: true }));
      assert.equal(await page.locator('[aria-invalid="true"]').count(), 0, "Review hints are advisory");
      await page.getByRole("navigation", { name: "Exit Interview sections" }).getByRole("link", { name: "Suggestions / Recommendations" }).click();
      await correction.getByRole("button", { name: "Suggestions / Recommendations (whole section)", exact: true }).click();
      assert.equal(await page.evaluate(() => document.activeElement?.id), "exit-interview-suggestions-review");
      assert.equal(state.writes.length, 0);
    });
  }
  {
    const state = exitFixture();
    await check("Unsaved Exit Interview guards internal navigation, Back and unload", "/portal/exit-interviews", { handler: state.handler }, async page => {
      await page.getByRole("link", { name: "Continue Exit Interview", exact: true }).click();
      await page.locator("#exit-contact-number").fill("0919 111 2222");
      const dialogs = [];
      page.on("dialog", async dialog => { dialogs.push(dialog.type()); await dialog.dismiss(); });
      await page.getByRole("link", { name: "Back to Exit Interviews", exact: true }).click();
      assert.equal(dialogs.length, 1);
      await page.goBack({ timeout: 2000 }).catch(() => null);
      await page.waitForURL(/exit-interviews\/exit-1b$/); assert.equal(dialogs.length, 2);
      await page.locator("#exit-contact-number").click();
      const unload = page.waitForEvent("dialog", { predicate: dialog => dialog.type() === "beforeunload" });
      await page.close({ runBeforeUnload: true }); await unload;
      assert.equal(await page.locator("#exit-contact-number").inputValue(), "0919 111 2222");
      await page.getByRole("button", { name: "Save draft", exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Draft saved." }));
      const count = dialogs.length;
      await page.getByRole("link", { name: "Back to Exit Interviews", exact: true }).click();
      await page.waitForURL(/\/portal\/exit-interviews$/); assert.equal(dialogs.length, count);
    });
  }
}
await finish();
