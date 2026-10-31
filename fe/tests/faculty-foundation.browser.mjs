// FAC-1 synthetic browser checks. No live institutional account or record is touched.
import assert from "node:assert/strict";
import { join } from "node:path";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, finish, shown, artifacts } = await createBrowserHarness("faculty-foundation");
const collegeId = "c0000000-0000-4000-8000-000000000001";
const facultyId = "f0000000-0000-4000-8000-000000000001";
const college = { id: collegeId, code: "FAC", name: "Faculty College", campus_code: "MAIN", campus_name: "Main Campus", campus_id: "c0000000-0000-4000-8000-000000000002" };
const faculty = { ...user("STUDENT"), id: facultyId, role: "FACULTY", capabilities: [], designations: [], student_lifecycle_status: null, faculty_affiliation: null };
const facultyHandler = async ({ pathname, reply }) => {
  if (pathname === "/api/v1/auth/session") { await reply(sessionFor(faculty)); return true; }
  return false;
};
const protectedRead = (request) => /\/api\/v1\/(?:referrals|counseling|assessment-records|routine-interviews|inventory|appointments|accounts|overview|work-queue|guidance-operations)(?:\/|$)/.test(request.pathname);

for (const [width, scale] of [[1440, 100], [390, 100], [320, 200]]) {
  await check(`faculty-home-${width}-${scale}`, "/portal", { handler: facultyHandler, viewport: { width, height: 950 } }, async (page, fixture) => {
    await shown(page.getByRole("heading", { name: "Faculty", exact: true }));
    await page.evaluate((value) => { document.documentElement.style.fontSize = `${value}%`; }, scale);
    await shown(page.getByText("Your Faculty account is active. Digital Student Referrals are not available yet."));
    await shown(page.getByText("Not assigned", { exact: true }));
    assert.equal(await page.locator('a[href^="/portal/referrals"],a[href^="/portal/appointments"],a[href^="/portal/accounts"]').count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    assert.equal(fixture.requests.some(protectedRead), false);
    await page.screenshot({ path: join(artifacts, `faculty-home-${width}-${scale}.png`), fullPage: true });
    await page.getByRole("button", { name: "Go to a COMPASS feature" }).click();
    const dialog = page.getByRole("dialog");
    await shown(dialog);
    await page.keyboard.type("referral");
    assert.equal(await dialog.getByRole("link", { name: /referral/i }).count(), 0);
    await page.keyboard.press("Escape");
  });
}
for (const path of ["/portal/referrals/new", "/portal/appointments/book", "/portal/accounts", "/portal/counseling", "/portal/follow-ups"]) {
  await check(`faculty-deep-link-${path.split("/").slice(2).join("-")}`, path, { handler: facultyHandler }, async (page, fixture) => {
    await shown(page.getByRole("heading", { name: "Workspace unavailable" }));
    assert.equal(fixture.requests.some(protectedRead), false, "Blocked workspace must never mount protected queries");
    await page.getByRole("link", { name: "Return to Overview" }).click();
    await shown(page.getByRole("heading", { name: "Faculty", exact: true }));
  });
}
const managed = {
  id: facultyId, institutional_id: "FAC-001", email: "faculty@synthetic.invalid", first_name: "Synthetic", middle_name: "", last_name: "Faculty", suffix: "", full_name: "Synthetic Faculty",
  role: "FACULTY", student_lifecycle_status: null, designations: [], is_active: true, password_configured: false, email_verified: false, email_verified_at: null,
  created_at: "2026-10-31T00:00:00Z", updated_at: "2026-10-31T00:00:00Z", mfa_enabled: false, profile_photo_url: null, profile_photo_updated_at: null,
  faculty_affiliation: { college_id: collegeId, college_name: college.name, campus_id: college.campus_id, campus_name: college.campus_name, active: true, resource_version: 1, assigned_at: "2026-10-31T00:00:00Z", assigned_by_id: "admin" },
};
function managerHandler(onCreate = null, onAffiliation = null) {
  return async ({ pathname, method, reply, request }) => {
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor({ ...user("IT_ADMIN"), capabilities: ["accounts.manage", "accounts.view"] })); return true; }
    if (pathname === "/api/v1/accounts/faculty-colleges") { await reply([college]); return true; }
    if (pathname === "/api/v1/accounts" && method === "POST" && onCreate) { await onCreate(request.postDataJSON(), reply); return true; }
    if (pathname === `/api/v1/accounts/${facultyId}/faculty-affiliation` && onAffiliation) { await onAffiliation(request.postDataJSON(), reply); return true; }
    if (pathname === `/api/v1/accounts/${facultyId}`) { await reply(managed); return true; }
    if (pathname === `/api/v1/accounts/${facultyId}/email-change`) { await reply({ request: null }); return true; }
    return false;
  };
}
await check("administrator-provisions-faculty-with-reviewed-home-college", "/portal/accounts/new", {
  viewport: { width: 390, height: 1000 }, handler: managerHandler(async (body, reply) => {
    assert.equal(body.role, "FACULTY"); assert.equal(body.faculty_college_id, collegeId);
    await reply(managed, 201);
  }),
}, async (page) => {
  await shown(page.getByRole("heading", { name: "Create account", exact: true }));
  await page.getByLabel("Institutional ID", { exact: true }).fill("FAC-001");
  await page.getByLabel("Email", { exact: true }).fill("faculty@synthetic.invalid");
  await page.getByLabel("First name", { exact: true }).fill("Synthetic");
  await page.getByLabel("Last name", { exact: true }).fill("Faculty");
  await page.getByLabel("Role", { exact: true }).selectOption("FACULTY");
  await page.getByLabel("Faculty home College", { exact: true }).selectOption(collegeId);
  await page.getByRole("button", { name: "Review account", exact: true }).click();
  await shown(page.getByRole("alertdialog").getByText(/Main Campus · Faculty College/));
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Faculty affiliation", exact: true }));
  await page.screenshot({ path: join(artifacts, "faculty-managed-phone.png"), fullPage: true });
});
await check("administrator-affiliation-conflict-requires-fresh-review", `/portal/accounts/${facultyId}`, {
  handler: managerHandler(null, async (_body, reply) => {
    managed.faculty_affiliation = { ...managed.faculty_affiliation, resource_version: 2 };
    await reply({ error: { code: "organization_relationship_conflict", message: "Synthetic version conflict" } }, 409);
  }),
}, async (page) => {
  await shown(page.getByRole("heading", { name: "Faculty affiliation", exact: true }));
  await page.getByLabel("Faculty home College", { exact: true }).selectOption("");
  await page.getByLabel("Institutional assignment basis", { exact: true }).fill("Synthetic reassignment");
  await page.getByRole("button", { name: "Review affiliation", exact: true }).click();
  await page.getByRole("button", { name: "Save affiliation", exact: true }).click();
  await shown(page.getByRole("button", { name: "Review latest assignment", exact: true }));
  assert.equal(await page.getByRole("button", { name: "Review affiliation", exact: true }).isDisabled(), true);
  await page.getByRole("button", { name: "Review latest assignment", exact: true }).click();
  assert.equal(await page.getByLabel("Faculty home College", { exact: true }).inputValue(), collegeId);
});
await check("csv-exposes-active-faculty-college-references", "/portal/accounts/import", { handler: managerHandler() }, async (page) => {
  await shown(page.getByRole("heading", { name: "Import accounts", exact: true }));
  await page.getByText("Faculty College references for CSV", { exact: true }).click();
  await shown(page.getByRole("cell", { name: collegeId, exact: true }));
});
await finish();
