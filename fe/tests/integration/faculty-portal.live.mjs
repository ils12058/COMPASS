// Requires tests.faculty_portal_server and the matching local Next build, never a live account.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { createBrowserHarness } from "../support/browser-harness.mjs";

const sessions = JSON.parse(await readFile(process.env.COMPASS_FAC3_FIXTURE_MANIFEST ?? "/tmp/compass-fac3-session.json", "utf8"));
const { check, finish, shown, artifacts, baseURL } = await createBrowserHarness("faculty-portal-live");
const root = "/portal/faculty/referrals";
const api = "/api/v1/faculty/referrals";
const requests = [];
let firstId;
let loseResponse = false;
let lost = false;
const attempts = [];

async function handler({ pathname, method, request, route }) {
  requests.push({ pathname, method });
  if (pathname === api && method === "POST" && loseResponse) {
    attempts.push({ key: request.headers()["idempotency-key"], body: request.postData() });
    if (!lost) {
      const response = await route.fetch();
      assert.equal(response.status(), 201, "The actual backend committed before transport loss");
      lost = true;
      await route.abort("failed");
      return true;
    }
  }
  await route.continue();
  return true;
}
const options = (cookie, extra = {}) => ({
  handler, ...extra,
  beforeNavigate: async ({ context }) => {
    await context.addCookies([{ name: "compass_session", value: cookie, url: baseURL, httpOnly: true, sameSite: "Lax" }]);
  },
});
async function prepare(page) {
  await shown(page.getByLabel("Student institutional ID", { exact: true }));
  await page.getByLabel("Student institutional ID").fill("FAC2-STUDENT");
  await page.getByRole("button", { name: "Confirm Student", exact: true }).click();
  await shown(page.getByText("Synthetic student", { exact: true }));
  await page.getByLabel("Course/Year/Block").fill("CCMS Student referred by CAS Faculty");
  await page.getByLabel("Referral reason").fill("Synthetic confidential cross-College reason");
  await page.getByRole("button", { name: "Review referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Review referral", exact: true }));
}

await check("real-approved-cross-college-submit-and-own-detail", root + "/new", options(sessions.faculty_cookie), async page => {
  await prepare(page);
  await page.getByRole("button", { name: "Submit referral", exact: true }).click();
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
  const link = page.getByRole("link", { name: "View referral details", exact: true });
  firstId = (await link.getAttribute("href")).split("/").at(-1);
  await page.screenshot({ path: join(artifacts, "real-canonical-submission.png"), fullPage: true });
  await link.click();
  await shown(page.getByRole("heading", { name: "Referral details", exact: true }));
  await shown(page.getByText("Synthetic student", { exact: true }));
  assert.equal(await page.getByText("Synthetic confidential cross-College reason", { exact: true }).count(), 0);
  assert.equal(requests.some(r => r.pathname.startsWith("/api/v1/referrals")), false);
});
await check("real-committed-response-loss-replays-identical-request", root + "/new", options(sessions.faculty_cookie, { viewport: { width: 390, height: 1000 } }), async page => {
  loseResponse = true;
  await prepare(page);
  await page.getByRole("button", { name: "Submit referral", exact: true }).click();
  await shown(page.getByRole("button", { name: "Retry same submission", exact: true }));
  assert.equal(attempts.length, 1, "No automatic replay after a committed response was lost");
  const replay = page.waitForResponse(response => response.request().method() === "POST" && new URL(response.url()).pathname === api);
  await page.getByRole("button", { name: "Retry same submission", exact: true }).click();
  assert.equal((await replay).status(), 200, "The actual backend confirms canonical replay");
  await shown(page.getByRole("heading", { name: "Referral submitted", exact: true }));
  assert.equal(attempts.length, 2);
  assert.ok(attempts[0].key === attempts[1].key && attempts[0].body === attempts[1].body, "Exact original key and body are replayed deliberately");
  loseResponse = false;
  await page.screenshot({ path: join(artifacts, "real-replay-phone.png"), fullPage: true });
});
await check("real-own-list-shows-canonical-records-only", root, options(sessions.faculty_cookie), async page => {
  await shown(page.getByRole("heading", { name: "Submitted referrals", exact: true }));
  await shown(page.getByRole("link", { name: /^View referral REF-/ }).first());
  await page.screenshot({ path: join(artifacts, "real-own-list.png"), fullPage: true });
});
await check("real-foreign-owner-retains-safe-404", `${root}/${firstId}`, options(sessions.other_faculty_cookie), async page => {
  await shown(page.getByText("This referral is not available. Return to My Referrals.", { exact: true }));
  assert.equal(await page.getByText("Synthetic student", { exact: true }).count(), 0);
});
const beforeOtherRole = requests.length;
await check("real-other-role-does-not-mount-faculty-query", root + "/new", options(sessions.student_cookie), async page => {
  await shown(page.getByRole("heading", { name: "Workspace unavailable", exact: true }));
  assert.equal(await page.getByLabel("Student institutional ID").count(), 0);
  assert.equal(requests.slice(beforeOtherRole).some(request => request.pathname.startsWith(api)), false);
});
await finish();
