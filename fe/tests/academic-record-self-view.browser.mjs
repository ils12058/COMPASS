// SAR-6 Student academic-record self-view. Synthetic session and record only.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { sessionFor } from "./support/guidance-messages-fixtures.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const h = await createBrowserHarness("academic-record-self-view");
const path = "/portal/academic-record";
const college = {
  id: "c0000000-0000-4000-8000-000000000001",
  code: "COMP",
  name: "College of Computing",
  is_active: true,
  resource_version: 1,
  campus: {
    id: "c0000000-0000-4000-8000-000000000002",
    code: "MAIN",
    name: "Main Campus",
    is_active: true,
    resource_version: 1,
  },
};
const student = {
  id: "student",
  full_name: "Maria Santos",
  institutional_id: "TEST-01",
  email: "maria.santos@example.test",
  is_active: true,
  role: "STUDENT",
};
const record = {
  student,
  lifecycle_status: "CURRENT",
  placement: { student, college, verification_status: "UNVERIFIED" },
  periods: [
    {
      id: "period-1",
      academic_year: {
        id: "a0000000-0000-4000-8000-000000000001",
        label: "2026-2027",
        is_current: true,
      },
      term: "FIRST_SEMESTER",
      college,
      year_level: 2,
      enrollment_status: "ENROLLED",
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-01T00:00:00Z",
    },
  ],
  graduation: null,
};

function selfFixture({ capabilities = ["student_academics.view_self"], role = "STUDENT", payload = record } = {}) {
  const account = { ...user(role), id: "student", role, capabilities };
  const requests = [];
  return {
    requests,
    handler: async ({ pathname, method, reply }) => {
      if (pathname === "/api/v1/auth/session") {
        await reply(sessionFor(account));
        return true;
      }
      if (pathname === "/api/v1/student-academics/me/record" && method === "GET") {
        requests.push({ pathname, method });
        await reply(payload);
        return true;
      }
      if (pathname.startsWith("/api/v1/student-academics/")) {
        requests.push({ pathname, method });
      }
      return false;
    },
  };
}

{
  const f = selfFixture();
  await h.check("01 Student sees their own placement and periods read-only", path, { handler: f.handler }, async (page) => {
    await h.shown(page.getByRole("heading", { name: "Academic record", exact: true }));
    await h.shown(page.getByText("Main Campus · College of Computing", { exact: true }));
    await h.shown(page.getByText("Unverified", { exact: true }));
    await h.shown(page.getByText("This placement is recorded by the institution. It does not by itself confirm enrollment.", { exact: true }));
    await h.shown(page.getByRole("rowheader", { name: "2026-2027", exact: true }));
    await h.shown(page.getByRole("cell", { name: "First Semester", exact: true }));
    await h.shown(page.getByText("No graduation recorded.", { exact: true }));
    await h.shown(page.getByText("If this information is incorrect, contact the Registrar or Guidance office.", { exact: true }));
    assert.equal(await page.getByRole("button", { name: /record|update|save|clear/i }).count(), 0);
    assert.equal(await page.getByRole("columnheader", { name: "Action", exact: true }).count(), 0);
    assert.equal(await page.getByRole("link", { name: "Academic Record", exact: true }).count(), 1);
    assert.deepEqual(f.requests, [{ pathname: "/api/v1/student-academics/me/record", method: "GET" }]);
  });
}

{
  const f = selfFixture({
    payload: { student, lifecycle_status: "CURRENT", placement: null, periods: [], graduation: null },
  });
  await h.check("02 Student without academic data gets empty states rather than an error", path, { handler: f.handler }, async (page) => {
    await h.shown(page.getByRole("heading", { name: "Academic record", exact: true }));
    await h.shown(page.getByText("No academic placement recorded.", { exact: true }));
    await h.shown(page.getByText("No academic periods recorded.", { exact: true }));
    await h.shown(page.getByText("No graduation recorded.", { exact: true }));
    assert.deepEqual(f.requests, [{ pathname: "/api/v1/student-academics/me/record", method: "GET" }]);
  });
}

{
  const f = selfFixture({ capabilities: [] });
  await h.check("03 Student without self-view capability is blocked and gets no navigation entry", path, { handler: f.handler }, async (page) => {
    await h.shown(page.getByRole("heading", { name: "Academic record unavailable", exact: true }));
    assert.equal(await page.getByRole("link", { name: "Academic Record", exact: true }).count(), 0);
    assert.deepEqual(f.requests, []);
  });
}

{
  const f = selfFixture({ capabilities: [], role: "COUNSELOR" });
  await h.check("04 Non-Student accounts cannot open the self-view", path, { handler: f.handler }, async (page) => {
    await h.shown(page.getByRole("heading", { name: "Academic record unavailable", exact: true }));
    assert.deepEqual(f.requests, []);
  });
}

await h.finish();
