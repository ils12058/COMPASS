// Batch term-record and graduation imports. Synthetic sessions, catalogs and CSVs only: no Django
// or institutional record is contacted.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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
const gradCsv = "institutional_id,campus_code,college_code,graduation_date,program_code\n2026-0101,MAIN,ENG,2026-06-30,BSCE\n2026-0102,MAIN,ENG,2026-06-30,\n";
const termHeaders = termCsv.split("\n")[0].split(",");
const gradHeaders = gradCsv.split("\n")[0].split(",");
const digest = (csv) => createHash("sha256").update(csv).digest("hex");

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
  const row = {
    row_number: number, institutional_id: id, student_id: `student-${id}`, student_name: `Student ${id}`,
    campus_code: "MAIN", college_code: "ENG", year_level: 2, enrollment_status: "ENROLLED",
    current_college_code: null, current_year_level: null, current_enrollment_status: null, action, message: "", ...fields,
  };
  return { ...row, values: fields.values ?? [id, row.campus_code, row.college_code, String(row.year_level), row.enrollment_status === "UNKNOWN" ? "" : row.enrollment_status] };
}
const periodReport = (fields) => ({
  valid: true, committed: false, total_rows: fields.rows.length, create_count: 0, update_count: 0, noop_count: 0,
  conflict_count: 0, invalid_count: 0, preview_fingerprint: "fp-terms", file_hash: digest(termCsv),
  headers: termHeaders, selected_count: fields.rows.length, not_selected_count: 0, ...fields,
});
const cleanTerms = periodReport({
  create_count: 1, update_count: 1,
  rows: [
    periodRow(2, "2026-0101", "CREATE"),
    periodRow(3, "2026-0102", "UPDATE", { year_level: 3, enrollment_status: "UNKNOWN", current_college_code: "ENG", current_year_level: 2, current_enrollment_status: "ENROLLED" }),
  ],
});

function gradRow(number, id, action, fields = {}) {
  const row = {
    row_number: number, institutional_id: id, student_id: `student-${id}`, student_name: `Student ${id}`,
    campus_code: "MAIN", college_code: "ENG", graduation_date: "2026-06-30", program_code: id === "2026-0101" ? "BSCE" : "", previous_program_code: null, lifecycle_status: "CURRENT",
    current_placement_college_code: "ENG", previous_college_code: null, previous_graduation_date: null, action, message: "", ...fields,
  };
  return { ...row, values: fields.values ?? [id, row.campus_code, row.college_code, row.graduation_date, row.program_code] };
}
const cleanGrads = {
  valid: true, committed: false, total_rows: 2, graduate_count: 2, update_count: 0, noop_count: 0, conflict_count: 0,
  invalid_count: 0, write_count: 2, placement_cleared_count: 2, preview_fingerprint: "fp-grads",
  file_hash: digest(gradCsv), headers: gradHeaders, selected_count: 2, not_selected_count: 0,
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
      assert.equal(field(body, "file_hash"), digest(termCsv));
      assert.deepEqual(JSON.parse(field(body, "selected_rows")), [2, 3]);
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
  await h.shown(changed.getByRole("cell", { name: "Ready", exact: true }));
  assert.equal(await page.getByRole("checkbox", { name: "Select row 2", exact: true }).isChecked(), true);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 3", exact: true }).isChecked(), true);
  await h.shown(page.getByText("Import 2 of 2 rows", { exact: true }));
  await h.screenshot(page, "terms-preview");

  await page.getByRole("button", { name: "Import selected", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Import 2 term records?", exact: true }));
  await dialog.getByRole("button", { name: "Import term records", exact: true }).click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("2 term records imported, 0 already existed, 0 rows not selected.", { exact: true }));
});

await h.check("terms: changing the term after a preview requires validating again", termsPath, {
  handler: handler({ periods: async ({ reply }) => reply(cleanTerms) }),
}, async (page, fixture) => {
  await chooseFile(page, "terms.csv", termCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByRole("button", { name: "Import selected", exact: true }));
  await page.getByLabel("Term", { exact: true }).selectOption("SECOND_SEMESTER");
  assert.equal(await page.getByRole("button", { name: "Import selected", exact: true }).count(), 0);
  assert.equal(await page.getByRole("heading", { name: "Preview", exact: true }).count(), 0);
  assert.equal(await page.getByRole("checkbox").count(), 0);
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  assert.equal(fixture.requests.filter((request) => request.search === "?dry_run=false").length, 0);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByText("Import 2 of 2 rows", { exact: true }));
  assert.equal(fixture.requests.filter((request) => request.search === "?dry_run=true").length, 2);
});

await h.check("terms: a stale apply keeps nothing and asks for a new preview", termsPath, {
  handler: handler({
    periods: async ({ url, reply }) => {
      if (url.searchParams.get("dry_run") === "true") return reply(cleanTerms);
      return reply({ error: { code: "csv_import_stale", message: "Records changed after the preview. Validate the CSV again." } }, 409);
    },
  }),
}, async (page, fixture) => {
  await chooseFile(page, "terms.csv", termCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await page.getByRole("button", { name: "Import selected", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await dialog.getByRole("button", { name: "Import term records", exact: true }).click();
  await h.shown(dialog.getByText("Records changed after the preview. Validate the CSV again.", { exact: true }));
  assert.equal(await dialog.getByRole("button", { name: "Import term records", exact: true }).isDisabled(), true);
  await page.keyboard.press("Escape");
  await h.shown(page.getByText("Validate the CSV again before importing.", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Import selected", exact: true }).isDisabled(), true);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 2", exact: true }).isDisabled(), true);
  assert.equal(await page.getByRole("heading", { name: "Import result", exact: true }).count(), 0);
  assert.equal(fixture.requests.filter((request) => request.search === "?dry_run=false").length, 1, "no automatic retry after stale apply");
});

const problemTermCsv = termCsv + "2026-0103,MAIN,ENG,bad,ENROLLED\n";
const problemTerms = periodReport({
  ...cleanTerms, valid: false, total_rows: 3, selected_count: 3, invalid_count: 1, file_hash: digest(problemTermCsv),
  rows: [...cleanTerms.rows, periodRow(4, "2026-0103", "INVALID", {
    message: "year_level must be between 1 and 8",
    values: ["2026-0103", "MAIN", "ENG", "bad", "ENROLLED"],
  })],
});
await h.check("terms: ready selection, disabled problems, filters, counts and correction download", termsPath, {
  handler: handler({
    periods: async ({ url, request, reply }) => {
      if (url.searchParams.get("dry_run") === "true") return reply(problemTerms);
      const body = request.postData() ?? "";
      assert.deepEqual(JSON.parse(field(body, "selected_rows")), [2]);
      assert.equal(field(body, "file_hash"), digest(problemTermCsv));
      assert.equal(field(body, "preview_fingerprint"), "fp-terms");
      return reply({
        ...problemTerms, valid: true, committed: true, update_count: 0, invalid_count: 0,
        selected_count: 1, not_selected_count: 2, rows: [problemTerms.rows[0]],
      });
    },
  }),
}, async (page) => {
  await chooseFile(page, "terms.csv", problemTermCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await h.shown(page.getByText("Import 2 of 3 rows", { exact: true }));
  const problem = page.getByRole("checkbox", { name: "Select row 4", exact: true });
  assert.equal(await problem.isDisabled(), true);
  assert.equal(await problem.isChecked(), false);
  await h.shown(page.getByText("Year level must be between 1 and 8", { exact: true }));
  await page.getByRole("button", { name: "Clear selection", exact: true }).click();
  await h.shown(page.getByText("Import 0 of 3 rows", { exact: true }));
  assert.equal(await page.getByRole("button", { name: "Import selected", exact: true }).isDisabled(), true);
  await page.getByRole("button", { name: "Select all ready", exact: true }).click();
  await h.shown(page.getByText("Import 2 of 3 rows", { exact: true }));
  await page.getByRole("checkbox", { name: "Select row 3", exact: true }).uncheck();
  await h.shown(page.getByText("Import 1 of 3 rows", { exact: true }));
  await page.getByLabel("Status", { exact: true }).selectOption("problems");
  assert.equal(await page.getByRole("checkbox").count(), 1);
  assert.equal(await problem.isDisabled(), true);
  await page.getByLabel("Status", { exact: true }).selectOption("ready");
  assert.equal(await page.getByRole("checkbox").count(), 2);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 2", exact: true }).isChecked(), true);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 3", exact: true }).isChecked(), false);
  const download = page.getByRole("link", { name: "Download rows with problems", exact: true });
  const href = await download.getAttribute("href");
  assert.equal(decodeURIComponent(href.slice(href.indexOf(",") + 1)),
    '"institutional_id","campus_code","college_code","year_level","enrollment_status","problem"\r\n' +
    '"2026-0103","MAIN","ENG","bad","ENROLLED","Year level must be between 1 and 8"\r\n');
  await page.getByRole("button", { name: "Import selected", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Import 1 term record?", exact: true }));
  await dialog.getByRole("button", { name: "Import term records", exact: true }).click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("1 term records imported, 0 already existed, 2 rows not selected.", { exact: true }));
  assert.equal(await download.getAttribute("href"), href);
});

await h.check("graduations: source is required, consequences are stated, and the typed count gates the import", graduationsPath, {
  handler: handler({
    graduations: async ({ url, request, reply }) => {
      const body = request.postData() ?? "";
      assert.equal(field(body, "verification_source"), "Registrar list 2026");
      if (url.searchParams.get("dry_run") === "true") return reply(cleanGrads);
      assert.equal(field(body, "preview_fingerprint"), "fp-grads");
      assert.equal(field(body, "confirmed_count"), "2");
      assert.equal(field(body, "file_hash"), digest(gradCsv));
      assert.deepEqual(JSON.parse(field(body, "selected_rows")), [2, 3]);
      return reply({ ...cleanGrads, committed: true });
    },
  }),
}, async (page, fixture) => {
  await h.shown(page.getByRole("heading", { name: "Import graduations", exact: true }));
  await h.shown(page.getByText(/There is no batch undo\./).first());
  await h.shown(page.getByText(/Optional column: program_code/));
  await chooseFile(page, "grads.csv", gradCsv);
  const validate = page.getByRole("button", { name: "Validate CSV", exact: true });
  assert.equal(await validate.isDisabled(), true, "the verification source comes first");
  await page.getByLabel("Verification source").fill("Registrar list 2026");
  await validate.click();
  await h.shown(page.getByText("2 Students will become Graduated; 2 Students will leave their current College placement.", { exact: true }));
  await h.shown(page.getByRole("row", { name: /2026-0101/ }).getByRole("cell", { name: "Ready", exact: true }));
  assert.equal(await page.getByRole("checkbox", { name: "Select row 2", exact: true }).isChecked(), true);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 3", exact: true }).isChecked(), true);
  await h.shown(page.getByText("Import 2 of 2 rows", { exact: true }));
  await h.screenshot(page, "graduations-preview");

  await page.getByRole("button", { name: "Import selected", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Record 2 graduations?", exact: true }));
  const confirm = dialog.getByRole("button", { name: "Import graduations", exact: true });
  assert.equal(await confirm.isDisabled(), true);
  await dialog.getByLabel("Type 2 to confirm").fill("3");
  assert.equal(await confirm.isDisabled(), true);
  assert.equal(fixture.requests.filter((request) => request.search === "?dry_run=false").length, 0, "an incorrect typed count cannot submit");
  await dialog.getByLabel("Type 2 to confirm").fill("2");
  await confirm.click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("2 graduations imported, 0 already existed, 0 rows not selected.", { exact: true }));
});

const problemGradCsv = gradCsv.replace("2026-0102,MAIN,ENG,2026-06-30,", "2026-0102,MAIN,ENG,invalid-date,");
const problemGrads = {
  ...cleanGrads, valid: false, graduate_count: 1, write_count: 1, placement_cleared_count: 1, invalid_count: 1,
  file_hash: digest(problemGradCsv),
  rows: [
    cleanGrads.rows[0],
    gradRow(3, "2026-0102", "INVALID", {
      graduation_date: "", message: "graduation_date must be a real date as YYYY-MM-DD",
      values: ["2026-0102", "MAIN", "ENG", "invalid-date", ""],
    }),
  ],
};
await h.check("graduations: problem rows stay disabled while selected ready rows require the typed count", graduationsPath, {
  handler: handler({
    graduations: async ({ url, request, reply }) => {
      if (url.searchParams.get("dry_run") === "true") return reply(problemGrads);
      const body = request.postData() ?? "";
      assert.deepEqual(JSON.parse(field(body, "selected_rows")), [2], "the invalid row is never submitted");
      assert.equal(field(body, "file_hash"), digest(problemGradCsv));
      assert.equal(field(body, "preview_fingerprint"), "fp-grads");
      assert.equal(field(body, "confirmed_count"), "1", "the count confirms selected writes only");
      return reply({
        ...problemGrads, valid: true, committed: true, invalid_count: 0, selected_count: 1, not_selected_count: 1,
        rows: [problemGrads.rows[0]],
      });
    },
  }),
}, async (page, fixture) => {
  await page.getByLabel("Verification source").fill("Registrar list 2026");
  await chooseFile(page, "grads.csv", problemGradCsv);
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  const problem = page.getByRole("row", { name: /2026-0102/ });
  await h.shown(problem.getByRole("cell", { name: "Has problems", exact: true }));
  await h.shown(problem.getByText("Graduation date must be a real date as YYYY-MM-DD", { exact: true }));
  const invalidCheckbox = problem.getByRole("checkbox", { name: "Select row 3", exact: true });
  assert.equal(await invalidCheckbox.isDisabled(), true);
  assert.equal(await invalidCheckbox.isChecked(), false);
  assert.equal(await page.getByRole("checkbox", { name: "Select row 2", exact: true }).isChecked(), true);
  await h.shown(page.getByText("Import 1 of 2 rows", { exact: true }));
  const download = page.getByRole("link", { name: "Download rows with problems", exact: true });
  const downloadHref = await download.getAttribute("href");
  assert.equal(decodeURIComponent(downloadHref.slice(downloadHref.indexOf(",") + 1)),
    '"institutional_id","campus_code","college_code","graduation_date","program_code","problem"\r\n' +
    '"2026-0102","MAIN","ENG","invalid-date","","Graduation date must be a real date as YYYY-MM-DD"\r\n');
  assert.equal(await download.getAttribute("download"), "compass-rows-with-problems.csv");
  await page.getByRole("button", { name: "Import selected", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await h.shown(dialog.getByRole("heading", { name: "Record 1 graduation?", exact: true }));
  await h.shown(dialog.getByText("1 Student will become Graduated; 1 Student will leave their current College placement. There is no batch undo.", { exact: true }));
  const confirm = dialog.getByRole("button", { name: "Import graduations", exact: true });
  assert.equal(await confirm.isDisabled(), true);
  await dialog.getByLabel("Type 1 to confirm").fill("2");
  assert.equal(await confirm.isDisabled(), true);
  assert.equal(fixture.requests.filter((request) => request.search === "?dry_run=false").length, 0);
  await dialog.getByLabel("Type 1 to confirm").fill("1");
  await confirm.click();
  await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
  await h.shown(page.getByText("1 graduations imported, 0 already existed, 1 rows not selected.", { exact: true }));
  assert.equal(await download.getAttribute("href"), downloadHref, "the correction download survives a selected import");
  assert.equal(await page.getByRole("row", { name: /2026-0102/ }).count(), 0, "problem rows were left out of the committed selection");
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
