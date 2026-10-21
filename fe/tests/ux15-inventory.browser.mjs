// Real Next UI; every API response and write is synthetic and local.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";

const phase = process.env.COMPASS_UX15_SCREENSHOTS ?? "after";
const { check, shown, hidden, screenshot, noHorizontalOverflow, finish } = await createBrowserHarness(`ux15-inventory-${phase}`);
const student = { ...user("STUDENT"), capabilities: ["inventory.view_self", "inventory.manage_self"] };
const revision = { id: "revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" };
function fixture({ incomplete = false } = {}) {
  let current = {
    id: "synthetic-inventory", academic_year: { id: "year", label: "2026–2027" }, status: "DRAFT", program: null, form_revision: revision,
    correction_pending: false, latest_correction: null, submitted_at: null, first_submitted_at: null, last_submitted_at: null,
    full_name: "Synthetic Student", student_number: "SYNTHETIC-01", sex: incomplete ? null : "FEMALE", date_of_birth: "2005-01-15",
    civil_status_category: "SINGLE", current_religion_category: "NONE", contact_number: "0917 000 0000",
    geographic_locations: [{ kind: "CURRENT", not_specified: true }], parent_status_category: "MARRIED",
    support_profile: { four_ps_status: "NOT_BENEFICIARY", indigenous_peoples_status: "NOT_MEMBER", mother_life_status: "LIVING", father_life_status: "LIVING" },
    family_members: [{ kind: "FATHER", occupation_category: "FARMER", annual_income_status: "NOT_SPECIFIED" }, { kind: "MOTHER", occupation_category: "NONE", annual_income_status: "NONE" }],
    living_arrangement: "OWN_HOUSE", pwd_status: "NON_PWD", year_level: 2, siblings: [], organization_memberships: [], transportation_entries: [],
  };
  const state = { writes: [], submissions: 0, failSave: false, holdSave: null, holdSubmit: null };
  state.handler = async ({ pathname, method, request, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(student)); return true; }
    if (pathname === "/api/v1/inventory/me/status") { await reply(current); return true; }
    if (pathname === "/api/v1/inventory/me/history") { await reply({ items: [], page: 1, page_size: 20, has_next: false }); return true; }
    if (pathname === "/api/v1/inventory/me/current") {
      if (method === "PUT") {
        state.writes.push(JSON.parse(request.postData()));
        if (state.holdSave) await state.holdSave;
        if (state.failSave) { await reply({ error: { code: "synthetic_failure", message: "Synthetic save failure" } }, 500); return true; }
        current = { ...current, ...state.writes.at(-1) };
      }
      await reply(current); return true;
    }
    if (pathname === "/api/v1/inventory/me/current/submit") {
      state.submissions++;
      if (state.holdSubmit) await state.holdSubmit;
      current = { ...current, status: "SUBMITTED", submitted_at: "2026-10-21T03:00:00Z" };
      await reply(current); return true;
    }
    return false;
  };
  return state;
}
const go = async (page, id, mobile = false) => (mobile || await page.locator("#inventory-section-select").isVisible())
  ? page.locator("#inventory-section-select").selectOption(id)
  : page.getByRole("navigation", { name: "Individual Inventory sections", exact: true }).getByRole("button").nth(["personal", "family", "background", "health", "education", "interests", "organizations", "plans", "review"].indexOf(id)).click();

for (const device of ["desktop", "phone"]) {
  const state = fixture();
  await check(`Inventory ${phase} ${device} screenshots`, "/portal/inventory/current", { handler: state.handler, device }, async page => {
    await shown(page.locator("#inventory-full-name"));
    await noHorizontalOverflow(page);
    await screenshot(page, `${phase}-${device}-personal`);
    await go(page, "review", device === "phone");
    await shown(page.getByText("Before you submit", { exact: true }));
    await noHorizontalOverflow(page);
    // The same action slot changes from secondary Save & continue to primary Submit. Capture
    // its settled colors rather than the first frame of that transition.
    await page.getByRole("button", { name: "Submit Individual Inventory", exact: true }).evaluate(async el => {
      await Promise.all(el.getAnimations().map(animation => animation.finished.catch(() => {})));
    });
    await screenshot(page, `${phase}-${device}-review`);
  });
}
if (phase !== "before") {
  for (const device of ["desktop", "narrowPhone"]) {
    const state = fixture();
    await check(`Section jumps, Back and Continue preserve unsaved answers on ${device}`, "/portal/inventory/current", { handler: state.handler, device }, async page => {
      await shown(page.locator("#inventory-full-name"));
      await page.locator("#inventory-full-name").fill("Synthetic changed name");
      const next = page.getByRole("button", { name: "Continue", exact: true });
      await next.focus(); await page.keyboard.press("Enter");
      await page.waitForFunction(() => document.activeElement?.id === "inventory-section-start");
      assert.match(await page.locator("#inventory-editor-heading").textContent(), /Family/);
      await page.getByRole("button", { name: "Back", exact: true }).click();
      assert.equal(await page.locator("#inventory-full-name").inputValue(), "Synthetic changed name");
      // Free jumping never saves or submits, including a jump to the last section.
      await go(page, "plans", device !== "desktop");
      await shown(page.getByRole("button", { name: "Review answers", exact: true }));
      await page.getByRole("button", { name: "Review answers", exact: true }).click();
      await shown(page.getByRole("button", { name: "Save progress before submit", exact: true }));
      await page.getByRole("button", { name: "Review Personal & contact", exact: true }).click();
      assert.equal(await page.locator("#inventory-full-name").inputValue(), "Synthetic changed name");
      assert.equal(state.writes.length, 0); assert.equal(state.submissions, 0);
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      await noHorizontalOverflow(page);
      if (device !== "desktop") {
        // The mobile section selector remains usable from the keyboard and retains focus.
        const select = page.getByLabel("Inventory section", { exact: true });
        await select.focus(); await page.keyboard.press("ArrowDown"); await page.keyboard.press("Enter");
        assert.equal(await select.evaluate(el => document.activeElement === el), true);
      }
    });
  }
  for (const device of ["desktop", "narrowPhone"]) {
    const state = fixture();
    await check(`Every section fits ${device}, including larger text`, "/portal/inventory/current", { handler: state.handler, device }, async page => {
      await shown(page.locator("#inventory-full-name"));
      for (const id of ["personal", "family", "background", "health", "education", "interests", "organizations", "plans", "review"]) {
        await go(page, id, device !== "desktop");
        await noHorizontalOverflow(page).catch(async error => {
          console.error("Overflow section", id, await page.evaluate(() => [...document.querySelectorAll("main *")].filter(el => el.getBoundingClientRect().right > innerWidth + 1).slice(-12).map(el => ({ tag: el.tagName, id: el.id, class: el.className, width: el.getBoundingClientRect().width }))));
          throw error;
        });
      }
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      for (const id of ["personal", "family", "review"]) {
        await go(page, id, device !== "desktop");
        // Check the pilot's reflow independently of the existing global top bar, whose controls
        // exceed 320px at 200% text. Default-size checks above still assert the whole page.
        const overflow = await page.locator('section[aria-labelledby="inventory-editor-heading"]').evaluate(el => [...el.querySelectorAll("*")].filter(child => child.getBoundingClientRect().width && child.getBoundingClientRect().right > innerWidth + 1).map(child => ({ tag: child.tagName, id: child.id })));
        assert.deepEqual(overflow, [], `${id} form content reflows at 200% text`);
      }
      assert.equal(state.writes.length, 0); assert.equal(state.submissions, 0);
    });
  }
  {
    const state = fixture();
    await check("Failed save retains edits; pending save prevents duplicates; Save & continue persists once", "/portal/inventory/current", { handler: state.handler }, async page => {
      await page.locator("#inventory-contact-number").fill("0918 111 2222");
      state.failSave = true;
      await page.getByRole("button", { name: "Save & continue", exact: true }).click();
      await shown(page.getByRole("alert").filter({ hasText: "could not be saved" }));
      assert.equal(await page.locator("#inventory-contact-number").inputValue(), "0918 111 2222");
      assert.equal(await page.locator("#inventory-editor-heading").textContent(), "Personal & contact");
      await shown(page.getByRole("status").filter({ hasText: "Unsaved changes" }));
      state.failSave = false;
      let release;
      state.holdSave = new Promise(resolve => { release = resolve; });
      await page.getByRole("button", { name: "Save & continue", exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Saving…" }));
      assert.equal(await page.locator("#inventory-contact-number").isDisabled(), true);
      assert.equal(await page.getByRole("button", { name: "Continue", exact: true }).isDisabled(), true);
      release();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      assert.equal(await page.locator("#inventory-editor-heading").textContent(), "Family & student support");
      assert.equal(state.writes.length, 2);
      assert.equal(state.writes.at(-1).contact_number, "0918 111 2222");
      assert.equal(state.submissions, 0);
      await go(page, "personal");
      assert.equal(await page.locator("#inventory-contact-number").inputValue(), "0918 111 2222");
    });
  }
  for (const device of ["desktop", "phone"]) {
    const state = fixture({ incomplete: true });
    await check(`Validation summary focuses original error and final review submits once on ${device}`, "/portal/inventory/current", { handler: state.handler, device }, async page => {
      await shown(page.locator("#inventory-full-name"));
      await go(page, "review", device === "phone");
      const summary = page.getByRole("region", { name: "Complete these answers", exact: true });
      await shown(summary);
      const issue = summary.getByRole("button", { name: "Choose a sex response.", exact: true });
      await issue.focus(); await page.keyboard.press("Enter");
      await page.waitForFunction(() => document.activeElement?.id === "inventory-sex");
      assert.equal(await page.locator("#inventory-sex").getAttribute("aria-invalid"), "true");
      await page.locator("#inventory-sex").selectOption("FEMALE");
      await page.getByRole("button", { name: "Save progress", exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      await go(page, "review", device === "phone");
      await hidden(summary);
      const submit = page.getByRole("button", { name: "Submit Individual Inventory", exact: true });
      assert.equal(await submit.isEnabled(), true);
      assert.equal(state.submissions, 0);
      await screenshot(page, `after-${device}-review-ready`);
      await submit.click();
      const dialog = page.getByRole("alertdialog");
      await shown(dialog);
      await shown(dialog.getByText(/After submission, this Inventory becomes read-only/));
      await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
      assert.equal(state.submissions, 0);
      await submit.click();
      let release;
      state.holdSubmit = new Promise(resolve => { release = resolve; });
      await dialog.getByRole("button", { name: "Submit Individual Inventory", exact: true }).click();
      const pending = dialog.getByRole("button", { name: "Submitting…", exact: true });
      await shown(pending); assert.equal(await pending.isDisabled(), true);
      release();
      await hidden(dialog);
      await hidden(page.getByRole("button", { name: "Save progress", exact: true }));
      assert.equal(state.writes.length, 1); assert.equal(state.submissions, 1);
      await noHorizontalOverflow(page);
    });
  }
  {
    const state = fixture();
    await check("Inventory protects sidebar navigation, browser Back and unload; saved work leaves without warning", "/portal/inventory", { handler: state.handler }, async page => {
      await page.getByRole("link", { name: "Continue Individual Inventory", exact: true }).click();
      await shown(page.locator("#inventory-full-name"));
      await page.locator("#inventory-full-name").fill("Unsaved synthetic name");
      const dialogs = [];
      page.on("dialog", async dialog => { dialogs.push({ type: dialog.type(), message: dialog.message() }); await dialog.dismiss(); });
      await page.getByRole("link", { name: "Individual Inventory", exact: true }).click();
      assert.equal(dialogs.length, 1);
      assert.match(dialogs[0].message, /Discard your unsaved Individual Inventory changes/);
      await page.waitForURL(/inventory\/current$/);
      await page.goBack({ timeout: 2000 }).catch(() => null);
      assert.equal(dialogs.length, 2);
      await page.waitForURL(/inventory\/current$/);
      await page.locator("#inventory-full-name").click();
      const unload = page.waitForEvent("dialog", { predicate: dialog => dialog.type() === "beforeunload" });
      await page.close({ runBeforeUnload: true });
      await unload;
      assert.equal(dialogs.at(-1).type, "beforeunload");
      assert.equal(await page.locator("#inventory-full-name").inputValue(), "Unsaved synthetic name");
      const beforeSave = dialogs.length;
      await page.getByRole("button", { name: "Save progress", exact: true }).click();
      await shown(page.getByRole("status").filter({ hasText: "Progress saved." }));
      await page.getByRole("link", { name: "Individual Inventory", exact: true }).click();
      await page.waitForURL(/\/portal\/inventory$/);
      assert.equal(dialogs.length, beforeSave);
    });
  }
}
await finish();
