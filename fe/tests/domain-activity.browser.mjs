// Synthetic API projection fixtures; backend tests own authorization and source validation.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";

const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness(`domain-activity-${engine}`);
const item = (type, title, description, index) => ({
  id: `domain-event-${index}`, type, title, description,
  occurred_at: new Date(Date.UTC(2026, 9, 16, 2, 0) - index * 60000).toISOString(),
});
const account = item("auth.login", "Signed in to COMPASS", "You signed in to your account.", 30);
const domain = [
  item("inventory.resubmitted", "Individual Inventory resubmitted", "You resubmitted your Individual Inventory.", 0),
  item("inventory.reopened", "Individual Inventory returned for correction", "Your Individual Inventory was returned for correction.", 1),
  item("inventory.submitted", "Individual Inventory submitted", "You submitted your Individual Inventory.", 2),
];
for (const width of [320, 1440]) {
  await check(`mixed-history-pagination-keyboard-${width}`, "/portal/account/activity", {
    role: "STUDENT", viewport: { width, height: 1000 }, timezoneId: "America/New_York",
    overrides: {
      "/api/v1/me/activity": ({ url, reply }) => {
        const page = Number(url.searchParams.get("page"));
        return reply({ items: page === 1 ? [...domain, ...Array.from({ length: 17 }, (_, index) => item("appointment.cancelled", "Appointment cancelled", "Your appointment was cancelled.", index + 3))] : [account], page, page_size: 20, has_next: page === 1 });
      },
      "/api/v1/me/security-activity": { items: [account], page: 1, page_size: 20, has_next: false },
    },
  }, async (page, { requests }) => {
    await shown(page.getByText(domain[1].description, { exact: true }));
    const list = page.getByLabel("My activity").locator("ol");
    assert.equal(await list.locator("li").count(), 20);
    assert.equal(await list.locator("li").first().locator("p").first().textContent(), domain[0].title);
    assert.match(await list.locator("time").first().textContent(), /10:00/); // Asia/Manila, independent of browser zone.
    await hidden(page.getByText("New session created", { exact: true }));
    await page.getByRole("button", { name: "Next", exact: true }).focus();
    await page.keyboard.press("Enter");
    await shown(page.getByText(account.title, { exact: true }));
    assert.equal(await page.getByRole("button", { name: "Next", exact: true }).isDisabled(), true);
    await page.getByRole("button", { name: "Previous", exact: true }).click();
    await shown(page.getByText(domain[0].title, { exact: true }));
    await noHorizontalOverflow(page);
    await screenshot(page, `mixed-${width}`);
    await page.getByRole("button", { name: "Security activity", exact: true }).click();
    await shown(page.getByText(account.title, { exact: true }));
    await hidden(page.getByText(domain[0].title, { exact: true }));
    assert.equal(requests.filter((request) => request.method !== "GET").length, 0);
    assert.ok(requests.some((request) => request.pathname === "/api/v1/me/activity" && request.search.includes("page=2")));
  });
}

for (const [perspective, role, event] of [
  ["counselor", "COUNSELOR", item("inventory.reopened", "Individual Inventory returned for correction", "You returned an Individual Inventory for correction.", 0)],
  ["head", "COUNSELOR", item("exit_interview.reopened", "Exit Interview returned for correction", "You returned an Exit Interview for correction.", 0)],
  ["gss", "GUIDANCE_SERVICES_STAFF", item("good_moral.prepared", "Good Moral certificate prepared", "You prepared a Good Moral certificate.", 0)],
  ["it", "IT_ADMIN", account],
  ["dpo", "INSTITUTIONAL_OFFICER", account],
]) {
  await check(`${perspective}-safe-projection`, "/portal/account/activity", {
    role, overrides: { "/api/v1/me/activity": { items: [event], page: 1, page_size: 20, has_next: false } },
  }, async (page) => {
    await shown(page.getByText(event.description, { exact: true }));
    await hidden(page.getByRole("button", { name: "Next", exact: true }));
    await noHorizontalOverflow(page);
  });
}

await check("empty-history", "/portal/account/activity", {
  role: "STUDENT", mobile: true,
  overrides: { "/api/v1/me/activity": { items: [], page: 1, page_size: 20, has_next: false } },
}, async (page) => {
  await shown(page.getByText("No activity is available yet.", { exact: true }));
  await hidden(page.getByText("No account activity is available yet.", { exact: true }));
  await noHorizontalOverflow(page);
});

let recovered = false;
await check("backend-unavailable-retry", "/portal/account/activity", {
  role: "STUDENT",
  overrides: { "/api/v1/me/activity": async ({ reply }) => {
    if (!recovered) return reply({ error: { code: "synthetic_unavailable", message: "SECRET DIAGNOSTIC" } }, 503);
    return reply({ items: domain, page: 1, page_size: 20, has_next: false });
  } },
}, async (page) => {
  await shown(page.getByRole("alert").filter({ hasText: "My activity could not be loaded." }));
  await hidden(page.getByText("No activity is available yet.", { exact: true }));
  await hidden(page.getByText("SECRET DIAGNOSTIC", { exact: true }));
  recovered = true;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await shown(page.getByText(domain[0].title, { exact: true }));
});

let releaseLoading;
const loading = new Promise((resolve) => { releaseLoading = resolve; });
await check("loading-is-not-empty", "/portal/account/activity", {
  role: "STUDENT",
  overrides: { "/api/v1/me/activity": async ({ reply }) => {
    await loading;
    return reply({ items: domain, page: 1, page_size: 20, has_next: false });
  } },
}, async (page) => {
  await shown(page.getByRole("status").filter({ hasText: "Loading activity…" }));
  await hidden(page.getByText("No activity is available yet.", { exact: true }));
  releaseLoading();
  await shown(page.getByText(domain[0].title, { exact: true }));
});
releaseLoading();
await finish();
