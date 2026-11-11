// Synthetic browser checks; the backend tests exercise real authorization independently.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { user } from "./support/ui-hierarchy-fixtures.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, shown, hidden, noHorizontalOverflow, finish } = await createBrowserHarness(`privacy-authorization-${engine}`);
const noticeView = "privacy_governance.notices.view";
const noticeManage = "privacy_governance.notices.manage";
const activityView = "privacy_governance.activity.view";
const activityExport = "privacy_governance.activity.export";
const accounts = {
  it: { ...user("IT_ADMIN"), capabilities: [noticeView, noticeManage, activityView, activityExport] },
  head: { ...user("COUNSELOR"), designations: ["HEAD_GUIDANCE_COUNSELOR"], capabilities: [activityView] },
  officer: { ...user("INSTITUTIONAL_OFFICER"), designations: [], capabilities: [] },
  counselor: { ...user("COUNSELOR"), designations: [], capabilities: [] },
  noticesOnly: { ...user("IT_ADMIN"), capabilities: [noticeView] },
};
const empty = { items: [], page: 1, page_size: 20, has_next: false };
const session = (account) => ({ user: account, session: { id: "synthetic-privacy", expires_at: "2099-10-07T00:00:00Z", is_current: true } });
for (const width of [390, 1440]) {
  for (const [name, account] of Object.entries(accounts)) {
    const notices = account.capabilities.includes(noticeView);
    const activity = account.capabilities.includes(activityView);
    const overrides = {
      "/api/v1/auth/session": session(account),
      "/api/v1/privacy/notices": empty,
      "/api/v1/privacy/activity": empty,
    };
    await check(`${name}-landing-${width}`, "/portal/privacy", { role: account.role, viewport: { width, height: 900 }, overrides }, async (page, { requests }) => {
      if (notices || activity) {
        await shown(page.getByRole("heading", { name: "Privacy governance", exact: true }));
        assert.equal(await page.locator('main a[href="/portal/privacy/notices"]').count() > 0, notices);
        assert.equal(await page.locator('main a[href="/portal/privacy/activity"]').count() > 0, activity);
      } else await shown(page.getByRole("heading", { name: "Access restricted", exact: true }));
      assert.ok(!requests.some((r) => r.pathname === "/api/v1/privacy/notices" || r.pathname === "/api/v1/privacy/activity"), "landing requests no administrative records");
      await noHorizontalOverflow(page);
    });
    for (const [path, allowed, heading] of [["/portal/privacy/notices", notices, "Privacy notices"], ["/portal/privacy/activity", activity, "Privacy and security activity"]]) {
      await check(`${name}-${path.split("/").at(-1)}-${width}`, path, { role: account.role, viewport: { width, height: 900 }, overrides }, async (page, { requests }) => {
        await shown(page.getByRole("heading", { name: allowed ? heading : "Access restricted", exact: true }));
        const requested = requests.filter((r) => r.pathname === "/api/v1/privacy/notices" || r.pathname === "/api/v1/privacy/activity");
        assert.equal(requested.length > 0, allowed);
        if (allowed && activity && path.endsWith("activity") && account.capabilities.includes(activityExport)) await shown(page.getByRole("button", { name: "Export CSV", exact: true }));
        else await hidden(page.getByRole("button", { name: "Export CSV", exact: true }));
        await noHorizontalOverflow(page);
      });
    }
  }
}
for (const path of ["/portal/privacy/notices/synthetic", "/portal/privacy/notice-revisions/synthetic", "/portal/privacy/notices/new"]) {
  await check(`head-direct-${path.split("/").slice(3).join("-")}`, path, { role: "COUNSELOR", overrides: { "/api/v1/auth/session": session(accounts.head) } }, async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Access restricted", exact: true }));
    assert.ok(!requests.some((r) => /^\/api\/v1\/privacy\/(notices|notice-revisions)/.test(r.pathname)));
  });
}
for (const path of ["/portal/privacy/retention", "/portal/privacy/retention/rules"]) {
  await check(`removed-${path.split("/").at(-1)}`, path, { role: "IT_ADMIN", overrides: { "/api/v1/auth/session": session(accounts.it) } }, async (page, { requests }) => {
    await shown(page.getByRole("heading", { name: "Page not found", exact: true }));
    assert.equal(new URL(page.url()).pathname, path);
    assert.ok(!requests.some((r) => r.pathname.startsWith("/api/v1/privacy/retention")));
  });
}
await finish();
