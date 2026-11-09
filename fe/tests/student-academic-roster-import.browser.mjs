// SAR-7 academic roster reconciliation. Synthetic sessions, catalogs, and CSVs only: no Django or
// institutional record is contacted.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const h = await createBrowserHarness("student-academic-roster-import");
const importPath = "/portal/organization/student-academics/import";
const staffPath = "/portal/organization/student-academics";
const mainCampus = {
  id: "c0000000-0000-4000-8000-000000000010",
  code: "MAIN",
  name: "Main Campus",
  is_active: true,
  resource_version: 1,
};
const engineering = {
  id: "c0000000-0000-4000-8000-000000000011",
  code: "ENG",
  name: "College of Engineering",
  is_active: true,
  resource_version: 1,
  campus: mainCampus,
};
const education = {
  id: "c0000000-0000-4000-8000-000000000012",
  code: "EDU",
  name: "College of Education",
  is_active: true,
  resource_version: 1,
  campus: mainCampus,
};
const emptyPlacements = { items: [], page: 1, page_size: 20, has_next: false };
const sessionWith = (capabilities) =>
  sessionFor({ ...user("IT_ADMIN"), capabilities, designations: [] });
// The import workspace is authorized by `.import`; the staff list also needs `.view`.
const importer = sessionWith([
  "organization.structure.view",
  "student_academics.view",
  "student_academics.manage",
  "student_academics.import",
]);
const viewer = sessionWith([
  "organization.structure.view",
  "student_academics.view",
  "student_academics.manage",
]);
const rosterCsv =
  "institutional_id,campus_code,college_code\n2026-0101,MAIN,ENG\n2026-0102,MAIN,EDU\n";

function handler({ session = importer, onImport = null } = {}) {
  return async ({ pathname, method, reply, request, url }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(session);
      return true;
    }
    if (pathname === "/api/v1/organization/campuses" && method === "GET") {
      await reply({ items: [mainCampus] });
      return true;
    }
    if (pathname === "/api/v1/organization/colleges" && method === "GET") {
      await reply({ items: [engineering, education] });
      return true;
    }
    if (pathname === "/api/v1/student-academics/placements" && method === "GET") {
      await reply(emptyPlacements);
      return true;
    }
    if (pathname === "/api/v1/student-academics/imports/csv" && method === "POST" && onImport) {
      await onImport({ url, request, reply });
      return true;
    }
    return false;
  };
}

function row(number, institutionalId, action, fields = {}) {
  return {
    row_number: number,
    institutional_id: institutionalId,
    student_id: `student-${institutionalId}`,
    student_name: `Student ${institutionalId}`,
    campus_code: "MAIN",
    college_code: "ENG",
    current_college_code: null,
    action,
    message: "",
    ...fields,
  };
}

function report(fields) {
  return {
    valid: true,
    committed: false,
    total_rows: fields.rows.length,
    set_count: 0,
    noop_count: 0,
    conflict_count: 0,
    invalid_count: 0,
    rows: fields.rows,
    ...fields,
  };
}

const mixedReport = report({
  valid: false,
  conflict_count: 1,
  set_count: 1,
  noop_count: 1,
  rows: [
    row(2, "2026-0101", "SET", {
      current_college_code: "EDU",
      campus_code: "MAIN",
      college_code: "ENG",
    }),
    row(3, "2026-0102", "NOOP", {
      current_college_code: "ENG",
      campus_code: "MAIN",
      college_code: "ENG",
    }),
    row(4, "2026-0103", "CONFLICT", {
      current_college_code: "ENG",
      campus_code: "MAIN",
      college_code: "EDU",
      message: "Current placement is VERIFIED and differs from this CSV.",
    }),
  ],
});

const cleanReport = report({
  set_count: 2,
  noop_count: 1,
  rows: [
    row(2, "2026-0101", "SET", {
      current_college_code: "EDU",
      campus_code: "MAIN",
      college_code: "ENG",
    }),
    row(3, "2026-0102", "SET", {
      current_college_code: null,
      campus_code: "MAIN",
      college_code: "EDU",
    }),
    row(4, "2026-0103", "NOOP", {
      current_college_code: "ENG",
      campus_code: "MAIN",
      college_code: "ENG",
    }),
  ],
});

const allNoopReport = report({
  noop_count: 2,
  rows: [
    row(2, "2026-0101", "NOOP", { current_college_code: "ENG" }),
    row(3, "2026-0102", "NOOP", { current_college_code: "ENG" }),
  ],
});

async function upload(page, csv = rosterCsv) {
  await page.getByLabel("CSV file", { exact: true }).setInputFiles({
    name: "roster.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
}

await h.check(
  "01 staff page shows Import only for an account with the import capability",
  staffPath,
  { handler: handler() },
  async (page) => {
    await h.shown(page.getByRole("heading", { name: "Student academic records", exact: true }));
    const link = page.getByRole("link", { name: "Import academic roster", exact: true });
    await h.shown(link);
    assert.equal(await link.getAttribute("href"), importPath);
  },
);

await h.check(
  "02 staff page hides Import from a view-only account",
  staffPath,
  { handler: handler({ session: viewer }) },
  async (page) => {
    await h.shown(page.getByRole("heading", { name: "Student academic records", exact: true }));
    assert.equal(
      await page.getByRole("link", { name: "Import academic roster", exact: true }).count(),
      0,
    );
  },
);

await h.check(
  "03 import page documents headers, validates with dry_run, and reports SET/NOOP/CONFLICT",
  importPath,
  {
    handler: handler({
      onImport: async ({ url, request, reply }) => {
        assert.equal(url.searchParams.get("dry_run"), "true");
        assert.match(request.postData() ?? "", /name="file"; filename="roster\.csv"/);
        await reply(mixedReport);
      },
    }),
  },
  async (page) => {
    await h.shown(page.getByRole("heading", { name: "Import academic roster", exact: true }));
    assert.equal(
      await page.getByText(/does not create or update accounts/).count(),
      1,
    );
    const template = page.getByRole("link", {
      name: "Download headers-only template",
      exact: true,
    });
    const href = await template.getAttribute("href");
    assert.ok(href?.startsWith("data:text/csv"));
    const templateCsv = decodeURIComponent(href.slice(href.indexOf(",") + 1));
    assert.equal(templateCsv.split("\n")[0], "institutional_id,campus_code,college_code");
    assert.equal(
      await page.getByText("institutional_id,campus_code,college_code", { exact: true }).count(),
      1,
    );

    await page.getByText("Active campus and College codes", { exact: true }).click();
    await h.shown(page.getByRole("columnheader", { name: "campus_code", exact: true }));
    await h.shown(page.getByRole("columnheader", { name: "college_code", exact: true }));
    await h.shown(page.getByRole("cell", { name: "MAIN", exact: true }).first());
    await h.shown(page.getByRole("cell", { name: "ENG", exact: true }));
    await h.shown(page.getByRole("cell", { name: "EDU", exact: true }));

    await h.shown(page.getByLabel("CSV file", { exact: true }));
    await upload(page);
    await h.shown(page.getByRole("heading", { name: "Validation report", exact: true }));
    assert.deepEqual(
      await page.locator("dl").first().locator("dd").allTextContents(),
      ["3", "1", "1", "1", "0"],
    );

    const setRow = page.getByRole("row", { name: /2026-0101/ });
    await h.shown(setRow.getByRole("cell", { name: "EDU", exact: true }));
    await h.shown(setRow.getByRole("cell", { name: "MAIN · ENG", exact: true }));
    await h.shown(setRow.getByRole("cell", { name: "Set", exact: true }));
    const noopRow = page.getByRole("row", { name: /2026-0102/ });
    await h.shown(noopRow.getByRole("cell", { name: "ENG", exact: true }));
    await h.shown(noopRow.getByRole("cell", { name: "No change", exact: true }));
    const conflictRow = page.getByRole("row", { name: /2026-0103/ });
    await h.shown(conflictRow.getByRole("cell", { name: "MAIN · EDU", exact: true }));
    await h.shown(conflictRow.getByRole("cell", { name: "Conflict", exact: true }));
    await h.shown(
      conflictRow.getByText("Current placement is VERIFIED and differs from this CSV.", {
        exact: true,
      }),
    );
    await h.screenshot(page, "roster-validation-conflict");

    assert.equal(
      await page.getByRole("button", { name: "Import placements", exact: true }).count(),
      0,
    );
  },
);

await h.check(
  "04 clean report opens commit review, posts the commit, and shows the committed result",
  importPath,
  {
    handler: handler({
      onImport: async ({ url, reply }) => {
        if (url.searchParams.get("dry_run") === "true") {
          await reply(cleanReport);
          return;
        }
        assert.equal(url.searchParams.get("dry_run"), "false");
        await reply({ ...cleanReport, committed: true });
      },
    }),
  },
  async (page) => {
    await h.shown(page.getByRole("heading", { name: "Import academic roster", exact: true }));
    await upload(page);
    await h.shown(page.getByRole("heading", { name: "Validation report", exact: true }));
    assert.deepEqual(
      await page.locator("dl").first().locator("dd").allTextContents(),
      ["3", "2", "1", "0", "0"],
    );
    const commitButton = page.getByRole("button", { name: "Import placements", exact: true });
    await h.shown(commitButton);
    await commitButton.click();

    const dialog = page.getByRole("alertdialog");
    await h.shown(dialog);
    await h.shown(dialog.getByRole("heading", { name: "Import 2 placements?", exact: true }));
    await h.shown(
      dialog.getByText("2 Student placements will be set from this CSV. 1 matching row will not change.", {
        exact: true,
      }),
    );
    await h.screenshot(page, "roster-commit-review");
    await dialog.getByRole("button", { name: "Import placements", exact: true }).click();

    await h.shown(
      page.getByText("Academic roster import completed. Review the committed result below.", {
        exact: true,
      }),
    );
    await h.shown(page.getByRole("heading", { name: "Import result", exact: true }));
    const committed = page.getByRole("row", { name: /2026-0102/ });
    await h.shown(committed.getByRole("cell", { name: "MAIN · EDU", exact: true }));
    assert.equal(
      await page.getByRole("button", { name: "Import placements", exact: true }).count(),
      0,
    );
    await h.screenshot(page, "roster-committed-result");
  },
);

await h.check(
  "05 all-NOOP report needs no commit",
  importPath,
  {
    handler: handler({
      onImport: async ({ url, reply }) => {
        assert.equal(url.searchParams.get("dry_run"), "true");
        await reply(allNoopReport);
      },
    }),
  },
  async (page) => {
    await h.shown(page.getByRole("heading", { name: "Import academic roster", exact: true }));
    await upload(page);
    await h.shown(page.getByRole("heading", { name: "Validation report", exact: true }));
    await h.shown(page.getByText("No placement changes are needed.", { exact: true }));
    assert.equal(
      await page.getByRole("button", { name: "Import placements", exact: true }).count(),
      0,
    );
    assert.equal(await page.getByRole("alertdialog").count(), 0);
  },
);

await h.check(
  "06 direct route shows the unavailable gate to a view-only account",
  importPath,
  { handler: handler({ session: viewer }) },
  async (page, fixture) => {
    await h.shown(page.getByRole("heading", { name: "Access restricted", exact: true }));
    await h.shown(page.getByText("You don’t have access to import academic rosters.", { exact: true }));
    assert.equal(
      fixture.requests.filter((request) => request.pathname === "/api/v1/student-academics/imports/csv").length,
      0,
    );
  },
);

await h.finish();
