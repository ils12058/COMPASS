// Batch term-record and graduation imports. Synthetic sessions, catalogs and CSVs only: no Django
// or institutional record is contacted.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const h = await createBrowserHarness("student-academic-batch-import");
const base = "/portal/organization/student-academics/import";
const termsPath = `${base}/terms`;
const graduationsPath = `${base}/graduations`;
const mainCampus = { id: "c0000000-0000-4000-8000-000000000010", code: "MAIN", name: "Main Campus", is_active: true, resource_version: 1 };
const engineering = { id: "c0000000-0000-4000-8000-000000000011", code: "ENG", name: "College of Engineering", is_active: true, resource_version: 1, campus: mainCampus };
const years = {
  items: [
    { id: "a0000000-0000-4000-8000-000000000001", label: "2026-2027", is_current: true },
    { id: "a0000000-0000-4000-8000-000000000002", label: "2025-2026", is_current: false },
  ],
};
const importer = sessionFor({
  ...user("IT_ADMIN"),
  designations: [],
  capabilities: ["organization.structure.view", "academic_years.view", "student_academics.view", "student_academics.import"],
});
const termCsv = "institutional_id,campus_code,college_code,year_level,enrollment_status\n2026-0101,MAIN,ENG,2,ENROLLED\n2026-0102,MAIN,ENG,3,\n";
const gradCsv = "institutional_id,campus_code,college_code,graduation_date\n2026-0101,MAIN,ENG,2026-06-30\n2026-0102,MAIN,ENG,2026-06-30\n";

function handler({ periods = null, graduations = null } = {}) {
  return async ({ pathname, method, reply, request, url }) => {
    if (pathname === "/api/v1/auth/session") return reply(importer).then(() => true);
    if (pathname === "/api/v1/academic-years" && method === "GET") return reply(years).then(() => true);
    if (pathname === "/api/v1/organization/campuses") return reply({ items: [mainCampus] }).then(() => true);
    if (pathname === "/api/v1/organization/colleges") return reply({ items: [engineering] }).then(() => true);
    if (pathname === "/api/v1/student-academics/imports/periods/csv" && periods) return periods({ url, request, reply }).then(() => true);
    if (pathname === "/api/v1/student-academics/imports/graduations/csv" && graduations) return graduations({ url, request, reply }).then(() => true);
    return false;
  };
}

const field = (body, name) => body.match(new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)`))?.[1];

function periodRow(number, id, action, fields = {}) {
  return {
    row_number: number, institutional_id: id, student_id: `student-${id}`, student_name: `Student ${id}`,
    campus_code: "MAIN", college_code: "ENG", year_level: 2, enrollment_status: "ENROLLED",
    current_college_code: null, current_year_level: null, current_enrollment_status: null, action, message: "", ...fields,
  };
}
const periodReport = (fields) => ({
  valid: true, committed: false, total_rows: fields.rows.length, create_count: 0, update_count: 0, noop_count: 0,
  conflict_count: 0, invalid_count: 0, preview_fingerprint: "fp-terms", ...fields,
});
const cleanTerms = periodReport({
  create_count: 1, update_count: 1,
  rows: [
    periodRow(2, "2026-0101", "CREATE"),
    periodRow(3, "2026-0102", "UPDATE", { year_level: 3, enrollment_status: "UNKNOWN", current_college_code: "ENG", current_year_level: 2, current_enrollment_status: "ENROLLED" }),
  ],
});

function gradRow(number, id, action, fields = {}) {
  return {
    row_number: number, institutional_id: id, student_id: `student-${id}`, student_name: `Student ${id}`,
    campus_code: "MAIN", college_code: "ENG", graduation_date: "2026-06-30", lifecycle_status: "CURRENT",
    current_placement_college_code: "ENG", previous_college_code: null, previous_graduation_date: null, action, message: "", ...fields,
  };
}
const cleanGrads = {
  valid: true, committed: false, total_rows: 2, graduate_count: 2, update_count: 0, noop_count: 0, conflict_count: 0,
  invalid_count: 0, write_count: 2, placement_cleared_count: 2, preview_fingerprint: "fp-grads",
  rows: [gradRow(2, "2026-0101", "GRADUATE", { message: "will become Graduated and leave the ENG placement" }), gradRow(3, "2026-0102", "GRADUATE")],
};

async function chooseFile(page, name, csv) {
  await page.getByLabel("CSV file", { exact: true }).setInputFiles({ name, mimeType: "text/csv", buffer: Buffer.from(csv) });
}

await h.check("terms: tabs, template, current year default and a clean preview then import", termsPath, {
  handler: handler({
    periods: async ({ url, request, reply }) => {
      const body = request.postData() ?? "";
      assert.equal(field(body, "academic_year_id"), years.items[0].id, "the current academic year is preselected");
      assert.equal(field(body, "term"), "SECOND_SEMESTER");
      if (url.searchParams.get("dry_run") === "true") {
        assert.equal(field(body, "preview_fingerprint"), undefined);
        await reply(cleanTerms);
        return;
      }
      assert.equal(field(body, "preview_fingerprint"), "fp-terms", "apply confirms the shown preview");
      await reply({ ...cleanTerms, committed: true });
    },
  }),
}, async (page) => {
  await h.shown(page.getByRole("heading", { name: "Import term records", exact: true }));
  const tabs = page.getByRole("navigation", { name: "Academic import navigation" });
  assert.equal(await tabs.getByRole("link", { name: "Term records" }).getAttribute("aria-current"), "page");
  await h.shown(tabs.getByRole("link", { name: "College placement" }));
  const href = await page.getByRole("link", { name: "Download CSV template", exact: true }).getAttribute("href");
  assert.equal(decodeURIComponent(href.slice(href.indexOf(",") + 1)).split("\n")[0], "institutional_id,campus_code,college_code,year_level,enrollment_status");
  assert.equal(await page.getByLabel("Academic year", { exact: true }).inputValue(), years.items[0].id);
  await page.getByLabel("Term", { exact: true }).selectOption("SECOND_SEMESTER");
  await chooseFile(page, "terms.csv", termCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByRole("heading", { name: "Preview", exact: true }));
  const changed = page.getByRole("row", { name: /2026-0102/ });
  await h.shown(changed.getByRole("cell", { name: "Year 2 · Enrolled", exact: true }));
  await h.shown(changed.getByRole("cell", { name: "Year 3 · Unknown", exact: true }));
  await h.shown(changed.getByRole("cell", { name: "Will change", exact: true }));
  await h.screenshot(page, "terms-preview");

  await page.getByRole("button", { name: "Import term records", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Import 2 term records?", exact: true }));
  await dialog.getByRole("button", { name: "Import term records", exact: true }).click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("Term records imported.", { exact: true }));
});

await h.check("terms: changing the term after a preview requires validating again", termsPath, {
  handler: handler({ periods: async ({ reply }) => reply(cleanTerms) }),
}, async (page) => {
  await chooseFile(page, "terms.csv", termCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByRole("button", { name: "Import term records", exact: true }));
  await page.getByLabel("Term", { exact: true }).selectOption("SECOND_SEMESTER");
  assert.equal(await page.getByRole("button", { name: "Import term records", exact: true }).count(), 0);
  assert.equal(await page.getByRole("heading", { name: "Preview", exact: true }).count(), 0);
});

await h.check("terms: a stale apply keeps nothing and asks for a new preview", termsPath, {
  handler: handler({
    periods: async ({ url, reply }) => {
      if (url.searchParams.get("dry_run") === "true") return reply(cleanTerms);
      return reply({ error: { code: "csv_import_stale", message: "Records changed after the preview. Validate the CSV again." } }, 409);
    },
  }),
}, async (page) => {
  await chooseFile(page, "terms.csv", termCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await page.getByRole("button", { name: "Import term records", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Import term records", exact: true }).click();
  await h.shown(dialog.getByText("Records changed after the preview. Validate the CSV again.", { exact: true }));
  await page.keyboard.press("Escape");
  await h.shown(page.getByText("Validate the CSV again before importing.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Import term records", exact: true }).count(), 0);
});

await h.check("graduations: source is required, consequences are stated, and the typed count gates the import", graduationsPath, {
  handler: handler({
    graduations: async ({ url, request, reply }) => {
      const body = request.postData() ?? "";
      assert.equal(field(body, "verification_source"), "Registrar list 2026");
      if (url.searchParams.get("dry_run") === "true") return reply(cleanGrads);
      assert.equal(field(body, "preview_fingerprint"), "fp-grads");
      assert.equal(field(body, "confirmed_count"), "2");
      return reply({ ...cleanGrads, committed: true });
    },
  }),
}, async (page) => {
  await h.shown(page.getByRole("heading", { name: "Import graduations", exact: true }));
  await h.shown(page.getByText(/There is no batch undo\./).first());
  await chooseFile(page, "grads.csv", gradCsv);
  const validate = page.getByRole("button", { name: "Validate CSV", exact: true });
  assert.equal(await validate.isDisabled(), true, "the verification source comes first");
  await page.getByLabel("Verification source").fill("Registrar list 2026");
  await validate.click();
  await h.shown(page.getByText("2 Students will become Graduated; 2 Students will leave their current College placement.", { exact: true }));
  await h.shown(page.getByRole("row", { name: /2026-0101/ }).getByRole("cell", { name: "Will graduate", exact: true }));
  await h.screenshot(page, "graduations-preview");

  await page.getByRole("button", { name: "Import graduations", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Record 2 graduations?", exact: true }));
  const confirm = dialog.getByRole("button", { name: "Import graduations", exact: true });
  assert.equal(await confirm.isDisabled(), true);
  await dialog.getByLabel("Type 2 to confirm").fill("3");
  assert.equal(await confirm.isDisabled(), true);
  await dialog.getByLabel("Type 2 to confirm").fill("2");
  await confirm.click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("Graduations imported.", { exact: true }));
});

await h.check("graduations: problem rows block the import", graduationsPath, {
  handler: handler({
    graduations: async ({ reply }) =>
      reply({ ...cleanGrads, valid: false, graduate_count: 1, write_count: 1, invalid_count: 1,
        rows: [gradRow(2, "2026-0101", "GRADUATE"), gradRow(3, "2026-0102", "INVALID", { graduation_date: "", message: "graduation_date must be a real date as YYYY-MM-DD" })] }),
  }),
}, async (page) => {
  await page.getByLabel("Verification source").fill("Registrar list 2026");
  await chooseFile(page, "grads.csv", gradCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByText("Fix the rows marked Problem, then validate again.", { exact: true }));
  await h.shown(page.getByRole("row", { name: /2026-0102/ }).getByRole("cell", { name: "Problem", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Import graduations", exact: true }).count(), 0);
});

for (const width of [320, 390]) {
  await h.check(`graduations: phone ${width}px has no page overflow`, graduationsPath, {
    handler: handler({ graduations: async ({ reply }) => reply(cleanGrads) }),
    viewport: { width, height: 844 },
  }, async (page) => {
    await page.getByLabel("Verification source").fill("Registrar list 2026");
    await chooseFile(page, "grads.csv", gradCsv);
    await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
    await h.shown(page.getByRole("heading", { name: "Preview", exact: true }));
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), "no horizontal page scroll");
  });
}

await h.finish();
