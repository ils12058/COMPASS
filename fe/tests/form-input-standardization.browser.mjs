// FORM-INPUT-1C in a real browser: Individual Inventory answers that COMPASS would refuse are caught
// at the field, keyboard focus moves there, and nothing is sent until they are fixed. Every API read
// and write is a synthetic fixture; no account or record is touched.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("form-input-standardization");

const academicYear = { id: "year-2026", label: "2026-2027" };
const revision = { id: "inventory-revision", family_key: "individual_inventory", internal_schema_version: 1, official_code: "UCN-OP-GCO-01F5", official_revision: "1" };
const record = {
  id: "inventory-form-input", academic_year: academicYear, status: "DRAFT", program: null, form_revision: revision,
  submitted_at: null, first_submitted_at: null, last_submitted_at: null, correction_pending: false, latest_correction: null,
  full_name: "Maria Santos", family_members: [], siblings: [], transportation_entries: [], geographic_locations: [],
};
const status = {
  academic_year: academicYear, status: "DRAFT", form_revision: revision, correction_pending: false, latest_correction: null,
  submitted_at: null, first_submitted_at: null, last_submitted_at: null,
};
const base = user("STUDENT");
const student = { ...base, capabilities: [...base.capabilities, "inventory.view_self", "inventory.manage_self"] };

function inventoryFixture() {
  const saved = [];
  return {
    saved,
    overrides: {
      "GET /api/v1/auth/session": { authenticated: true, user: student, session: { id: "session-form-input", expires_at: "2099-10-07T00:00:00Z", is_current: true } },
      "GET /api/v1/inventory/me/status": status,
      "GET /api/v1/inventory/me/current": record,
      "PUT /api/v1/inventory/me/current": ({ reply, request }) => {
        const body = JSON.parse(request.postData() ?? "{}");
        saved.push(body);
        return reply({ ...record, ...body });
      },
    },
  };
}

const focusedId = (page) => page.evaluate(() => document.activeElement?.id ?? "");

{
  const fixture = inventoryFixture();
  await check("reported-income-of-zero-is-caught-at-the-field-before-saving", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    await page.getByRole("button", { name: /Family & student support/ }).click();
    await page.locator("#inventory-family-father-income-status").selectOption("REPORTED");
    const amount = page.locator("#inventory-family-father-income-amount");
    await amount.fill("0");
    await page.getByRole("button", { name: "Save progress", exact: true }).click();

    const message = "Enter an amount greater than ₱0 for father's income.";
    await shown(page.getByRole("alert").filter({ hasText: message }).first());
    await shown(page.locator("#inventory-family-father-income-amount-error"));
    assert.equal(await amount.getAttribute("aria-invalid"), "true");
    assert.equal(await focusedId(page), "inventory-family-father-income-amount", "Focus moves to the amount that needs attention");
    assert.equal(fixture.saved.length, 0, "Nothing is sent while the amount would be refused");

    // Correct it with the keyboard from where focus landed.
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("150000.50");
    await hidden(page.locator("#inventory-family-father-income-amount-error"));
    await page.getByRole("button", { name: "Save progress", exact: true }).click();
    await shown(page.getByText("Progress saved.", { exact: true }));
    const father = fixture.saved.at(-1).family_members.find((member) => member.kind === "FATHER");
    assert.equal(father.annual_income_status, "REPORTED");
    assert.equal(father.annual_income_previous_year, "150000.50", "The amount is sent exactly as typed");
  });
}

{
  const fixture = inventoryFixture();
  await check("missing-transportation-frequency-is-listed-and-opens-the-row", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    await page.getByRole("button", { name: /Organizations & transportation/ }).click();
    await page.getByRole("checkbox", { name: "Bus", exact: true }).check();
    await page.getByRole("button", { name: /Review & submit/ }).click();

    const issue = page.getByRole("button", { name: "Choose how often you use the bus.", exact: true });
    await shown(issue);
    await issue.click();
    const frequency = page.locator("#inventory-transport-bus-frequency-category");
    await shown(frequency);
    assert.equal(await focusedId(page), "inventory-transport-bus-frequency-category", "Selecting the issue focuses the Bus frequency");
    await shown(page.locator("#inventory-transport-bus-frequency-category-error"));

    await frequency.selectOption("DAILY");
    await hidden(page.locator("#inventory-transport-bus-frequency-category-error"));
    // A draft without a frequency was always allowed, so saving still works.
    await page.getByRole("button", { name: "Save progress", exact: true }).click();
    await shown(page.getByText("Progress saved.", { exact: true }));
    assert.deepEqual(fixture.saved.at(-1).transportation_entries, [{ mode: "BUS", frequency_category: "DAILY", frequency: "" }]);
  });
}

{
  const fixture = inventoryFixture();
  await check("an-answer-that-reaches-its-limit-says-so", "/portal/inventory/current", { overrides: fixture.overrides }, async (page) => {
    const nickname = page.getByLabel("Nickname", { exact: true });
    await nickname.fill("N".repeat(99));
    assert.equal(await page.locator("#inventory-nickname-limit").textContent(), "");
    await nickname.press("End");
    await page.keyboard.type("NN");
    assert.equal((await nickname.inputValue()).length, 100, "Typing stops at the server limit");
    await shown(page.getByText("This field allows up to 100 characters.", { exact: true }));
    assert.match(await nickname.getAttribute("aria-describedby"), /inventory-nickname-limit/);
  });
}

{
  const fixture = inventoryFixture();
  await check("phone-layout-keeps-the-field-issue-readable", "/portal/inventory/current", { mobile: true, overrides: fixture.overrides }, async (page) => {
    await page.locator("#inventory-section-select").selectOption("organizations");
    await page.getByRole("checkbox", { name: "Tricycle", exact: true }).check();
    await page.locator("#inventory-transport-tricycle-fare").fill("12.345");
    await page.getByRole("button", { name: "Save progress", exact: true }).click();
    await shown(page.locator("#inventory-transport-tricycle-fare-error"));
    assert.equal(await page.locator("#inventory-transport-tricycle-fare-error").textContent(), "Use up to two decimal places for the tricycle fare.");
    assert.equal(await focusedId(page), "inventory-transport-tricycle-fare");
    await shown(page.getByText("In pesos (₱).", { exact: true }));
    await noHorizontalOverflow(page);
    await screenshot(page, "phone-fare-issue");
    assert.equal(fixture.saved.length, 0);
  });
}

await finish();
