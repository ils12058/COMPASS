import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, finish } = await createBrowserHarness("academic-years");
const institutionYear = Number(
  new Intl.DateTimeFormat("en", { timeZone: "Asia/Manila", year: "numeric" }).format(new Date()),
);
const label = `${institutionYear}-${institutionYear + 1}`;
const head = {
  ...user("COUNSELOR"),
  id: "head-academic-years",
  designations: ["HEAD_GUIDANCE_COUNSELOR"],
  capabilities: [...user("COUNSELOR").capabilities, "academic_years.view", "academic_years.manage"],
};

{
  const years = [{ id: "legacy-year", label: "AY 2023", is_current: false }];
  const overrides = {
    "/api/v1/auth/session": ({ reply }) => reply({
      user: head,
      session: { id: "head-session", expires_at: "2099-10-07T00:00:00Z", is_current: true },
    }),
    "/api/v1/academic-years": ({ reply }) => reply({ items: years }),
    "POST /api/v1/academic-years": ({ reply, request }) => {
      const payload = JSON.parse(request.postData() ?? "{}");
      if (years.some((year) => year.label === payload.label)) {
        return reply({ error: { code: "academic_year_conflict", message: "Duplicate" } }, 409);
      }
      const created = { id: "new-year", label: payload.label, is_current: false };
      years.push(created);
      return reply(created, 201);
    },
  };

  await check("Academic Year dropdown derives a controlled label and leaves the new year inactive", "/portal/academic-years", { overrides }, async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Academic Years", exact: true }));
    await shown(page.getByText("AY 2023", { exact: true }));
    await page.getByRole("button", { name: "Add Academic Year" }).click();

    const startYear = page.getByLabel("Starting year");
    await shown(startYear);
    await startYear.selectOption(String(institutionYear));
    await shown(page.getByText(`Academic Year to be added: ${label}`, { exact: true }));
    await page.getByRole("button", { name: "Add Academic Year", exact: true }).last().click();

    await shown(page.getByText(`${label} was added. Set it as current separately when appropriate.`, { exact: true }));
    await shown(page.getByText(label, { exact: true }));
    await shown(page.getByText("The current academic year has not been set.", { exact: true }));
    assert.equal(years.find((year) => year.label === label)?.is_current, false);
    const createRequest = requests.find((request) => request.method === "POST" && request.pathname === "/api/v1/academic-years");
    assert.deepEqual(JSON.parse(createRequest.body), { label });

    await page.getByRole("button", { name: "Add Academic Year" }).click();
    const duplicateOption = startYear.locator(`option[value="${institutionYear}"]`);
    assert.equal(await duplicateOption.isDisabled(), true, "An existing label is not offered as a creatable choice");
  });
}

await finish();
