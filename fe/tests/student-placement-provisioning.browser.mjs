// SAR-4 synthetic browser checks. No live institutional account or record is touched.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, finish, shown, artifacts } = await createBrowserHarness("student-placement-provisioning");
const mainCampusId = "c0000000-0000-4000-8000-000000000010";
const northCampusId = "c0000000-0000-4000-8000-000000000020";
const engineeringId = "c0000000-0000-4000-8000-000000000011";
const educationId = "c0000000-0000-4000-8000-000000000012";
const nursingId = "c0000000-0000-4000-8000-000000000021";
const createdId = "s0000000-0000-4000-8000-000000000001";
const colleges = [
  { id: engineeringId, code: "ENG", name: "College of Engineering", campus_id: mainCampusId, campus_code: "MAIN", campus_name: "Main Campus" },
  { id: educationId, code: "EDU", name: "College of Education", campus_id: mainCampusId, campus_code: "MAIN", campus_name: "Main Campus" },
  { id: nursingId, code: "NUR", name: "College of Nursing", campus_id: northCampusId, campus_code: "NORTH", campus_name: "North Campus" },
];
const createdStudent = {
  id: createdId, institutional_id: "2026-0101", email: "student@synthetic.invalid", first_name: "Synthetic", middle_name: "", last_name: "Student", suffix: "", full_name: "Synthetic Student",
  role: "STUDENT", student_lifecycle_status: "CURRENT", designations: [], is_active: true, password_configured: false, email_verified: false, email_verified_at: null,
  created_at: "2026-11-04T00:00:00Z", updated_at: "2026-11-04T00:00:00Z", mfa_enabled: false, profile_photo_url: null, profile_photo_updated_at: null, faculty_affiliation: null,
};
const sessionWith = (capabilities) => sessionFor({ ...user("IT_ADMIN"), capabilities, designations: [] });
const manager = sessionWith(["accounts.manage", "accounts.view", "student_academics.manage"]);
const limitedManager = sessionWith(["accounts.manage", "accounts.view"]);
const csvReport = {
  valid: true, committed: false, total_rows: 2, create_count: 1, skip_count: 1, conflict_count: 0, invalid_count: 0,
  rows: [
    { row_number: 1, institutional_id: "2026-0101", email: "student@synthetic.invalid", action: "CREATE", message: "", faculty_college_id: null, campus_code: "MAIN", college_code: "ENG" },
    { row_number: 2, institutional_id: "2026-0102", email: "existing@synthetic.invalid", action: "SKIP", message: "", faculty_college_id: null, campus_code: null, college_code: null },
  ],
};

function handler({ session = manager, onCreate = null, onImport = null } = {}) {
  return async ({ pathname, method, reply, request, url }) => {
    if (pathname === "/api/v1/auth/session") { await reply(session); return true; }
    if (pathname === "/api/v1/accounts/faculty-colleges") { await reply(colleges); return true; }
    if (pathname === "/api/v1/accounts" && method === "POST" && onCreate) { await onCreate(request.postDataJSON(), reply); return true; }
    if (pathname === "/api/v1/accounts/imports/csv" && method === "POST" && onImport) { await onImport({ body: request.postData(), url }, reply); return true; }
    if (pathname === `/api/v1/accounts/${createdId}`) { await reply(createdStudent); return true; }
    return false;
  };
}

await check("manager-with-student-academics-manage-reviews-and-posts-student-placement", "/portal/accounts/new", {
  viewport: { width: 390, height: 1000 }, handler: handler({
    onCreate: async (body, reply) => {
      assert.equal(body.role, "STUDENT");
      assert.equal(body.student_campus_id, northCampusId);
      assert.equal(body.student_college_id, nursingId);
      await reply(createdStudent, 201);
    },
  }),
}, async (page) => {
  await shown(page.getByRole("heading", { name: "Create account", exact: true }));
  const placement = page.getByRole("group", { name: "Initial academic placement (optional)", exact: true });
  await shown(placement);
  await shown(placement.getByText(/This placement is unverified and doesn't confirm enrollment\./));
  await page.getByLabel("Institutional ID", { exact: true }).fill("2026-0101");
  await page.getByLabel("Email", { exact: true }).fill("student@synthetic.invalid");
  await page.getByLabel("First name", { exact: true }).fill("Synthetic");
  await page.getByLabel("Last name", { exact: true }).fill("Student");
  const campus = page.getByLabel("Campus", { exact: true });
  const college = page.getByLabel("College", { exact: true });
  assert.equal(await college.isDisabled(), true);
  await campus.selectOption(mainCampusId);
  assert.equal(await college.isDisabled(), false);
  const mainOptions = await college.locator("option").allTextContents();
  assert.ok(mainOptions.includes("ENG · College of Engineering"));
  assert.ok(mainOptions.includes("EDU · College of Education"));
  assert.equal(mainOptions.some((option) => option.includes("Nursing")), false);
  await page.getByRole("button", { name: "Review account", exact: true }).click();
  await shown(page.getByRole("alert").filter({ hasText: "Select both Campus and College, or neither." }));
  assert.equal(await page.getByRole("alertdialog").count(), 0);
  await college.selectOption(engineeringId);
  await campus.selectOption(northCampusId);
  assert.equal(await college.inputValue(), "");
  const northOptions = await college.locator("option").allTextContents();
  assert.ok(northOptions.includes("NUR · College of Nursing"));
  assert.equal(northOptions.some((option) => option.includes("Engineering")), false);
  await college.selectOption(nursingId);
  await page.getByRole("button", { name: "Review account", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await shown(dialog);
  await shown(dialog.getByText("North Campus · College of Nursing"));
  await shown(dialog.getByText("Initial academic placement is recorded as unverified and does not confirm enrollment."));
  await page.screenshot({ path: join(artifacts, "placement-review-phone.png"), fullPage: true });
  await dialog.getByRole("button", { name: "Create account", exact: true }).click();
  await page.waitForURL(new RegExp(`/portal/accounts/${createdId}$`));
});

await check("manager-without-placement-capability-cannot-see-or-post-placement", "/portal/accounts/new", {
  handler: handler({
    session: limitedManager,
    onCreate: async (body, reply) => {
      assert.equal(body.role, "STUDENT");
      assert.equal(body.student_campus_id ?? null, null);
      assert.equal(body.student_college_id ?? null, null);
      await reply(createdStudent, 201);
    },
  }),
}, async (page, fixture) => {
  await shown(page.getByRole("heading", { name: "Create account", exact: true }));
  assert.equal(await page.getByRole("group", { name: "Initial academic placement (optional)" }).count(), 0);
  await page.getByLabel("Institutional ID", { exact: true }).fill("2026-0101");
  await page.getByLabel("Email", { exact: true }).fill("student@synthetic.invalid");
  await page.getByLabel("First name", { exact: true }).fill("Synthetic");
  await page.getByLabel("Last name", { exact: true }).fill("Student");
  assert.equal(fixture.requests.some((request) => request.pathname === "/api/v1/accounts/faculty-colleges"), false);
  await page.getByRole("button", { name: "Review account", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await shown(dialog);
  await shown(dialog.getByText("Not assigned", { exact: true }));
  await dialog.getByRole("button", { name: "Create account", exact: true }).click();
  await page.waitForURL(new RegExp(`/portal/accounts/${createdId}$`));
});

await check("csv-import-documents-and-previews-placement-code-columns", "/portal/accounts/import", { handler: handler({
  onImport: async ({ url }, reply) => {
    assert.equal(url.searchParams.get("dry_run"), "true");
    await reply(csvReport);
  },
}) }, async (page) => {
  await shown(page.getByRole("heading", { name: "Import accounts", exact: true }));
  const template = page.getByRole("link", { name: "Download headers-only template", exact: true });
  const href = await template.getAttribute("href");
  assert.ok(href);
  assert.ok(decodeURIComponent(href).includes("institutional_id,email,first_name,middle_name,last_name,suffix,role,faculty_college_id,campus_code,college_code"));
  await shown(page.getByText(/program_code is not supported/));
  await page.getByText("College references for CSV", { exact: true }).click();
  await shown(page.getByRole("columnheader", { name: "campus_code", exact: true }));
  await shown(page.getByRole("columnheader", { name: "college_code", exact: true }));
  await shown(page.getByRole("cell", { name: "MAIN", exact: true }).first());
  assert.equal(await page.getByRole("cell", { name: "MAIN", exact: true }).count(), 2);
  await shown(page.getByRole("cell", { name: "ENG", exact: true }));
  await shown(page.getByRole("cell", { name: engineeringId, exact: true }));
  await page.getByLabel("CSV file", { exact: true }).setInputFiles({
    name: "accounts.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("institutional_id,email,first_name,last_name,role,campus_code,college_code\n2026-0101,student@synthetic.invalid,Synthetic,Student,STUDENT,MAIN,ENG\n"),
  });
  await page.getByRole("button", { name: "Validate CSV", exact: true }).click();
  await shown(page.getByRole("columnheader", { name: "Placement", exact: true }));
  const createRow = page.getByRole("row", { name: /2026-0101/ });
  await shown(createRow.getByRole("cell", { name: "MAIN · ENG", exact: true }));
  const skipRow = page.getByRole("row", { name: /2026-0102/ });
  assert.equal(await skipRow.locator("td").nth(3).textContent(), "—");
  await page.screenshot({ path: join(artifacts, "csv-placement-preview.png"), fullPage: true });
});

await check("placement-authorization-failure-uses-placement-message", "/portal/accounts/new", { handler: handler({
  onCreate: async (_body, reply) => {
    await reply({ error: { code: "academic_placement_permission_denied", message: "You don't have permission to assign a Student's first academic placement." } }, 403);
  },
}) }, async (page) => {
  await shown(page.getByRole("heading", { name: "Create account", exact: true }));
  await page.getByLabel("Institutional ID", { exact: true }).fill("2026-0101");
  await page.getByLabel("Email", { exact: true }).fill("student@synthetic.invalid");
  await page.getByLabel("First name", { exact: true }).fill("Synthetic");
  await page.getByLabel("Last name", { exact: true }).fill("Student");
  await page.getByLabel("Campus", { exact: true }).selectOption(mainCampusId);
  await page.getByLabel("College", { exact: true }).selectOption(engineeringId);
  await page.getByRole("button", { name: "Review account", exact: true }).click();
  const dialog = page.getByRole("alertdialog");
  await shown(dialog);
  await dialog.getByRole("button", { name: "Create account", exact: true }).click();
  await shown(dialog.getByText("You don't have permission to assign a Student placement."));
});

await finish();
