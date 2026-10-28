import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
const h = await createBrowserHarness("simplify-3b-public-pages");
const phase = process.env.COMPASS_3B_PHASE ?? "after";
for (const width of [320, 390, 768, 1440]) {
  const reads = [];
  const handler = async ({ pathname, url, reply }) => {
    if (pathname !== "/api/v1/privacy/public-notices") return false;
    const page = Number(url.searchParams.get("page") ?? 1);
    reads.push(page);
    const notice = { revision_id: "synthetic-notice", title: "Example privacy notice", effective_on: "2026-01-01", summary: "Synthetic example.", body: "Synthetic notice text." };
    await reply({ items: page === 1 ? [notice] : [], page, page_size: 10, has_next: page === 1 });
    return true;
  };
  await h.check(`${phase}-${width}`, "/privacy", { handler, viewport: { width, height: 900 } }, async page => {
    await h.shown(page.getByRole("heading", { name: "Example privacy notice" }));
    const nav = page.getByRole("navigation", { name: "Pagination" });
    await h.shown(nav.getByRole("link", { name: "Next", exact: true }));
    await h.screenshot(page, `${phase}-${width}`);
    await nav.getByRole("link", { name: "Next", exact: true }).click();
    await h.shown(page.getByText("No privacy notices on this page."));
    assert.ok(reads.includes(2));
    if (phase === "before") {
      assert.equal(await page.getByRole("link", { name: "Previous", exact: true }).count(), 0, "Baseline leaves an empty later page without a return link");
      return;
    }
    await h.shown(page.getByRole("link", { name: "Previous", exact: true }));
    assert.equal(await page.getByRole("link", { name: "Previous", exact: true }).getAttribute("href"), "/privacy?page=1");
    await page.addStyleTag({ content: "html { font-size: 200%; }" });
    const bounds = await page.getByRole("navigation", { name: "Pagination" }).evaluate(element => {
      const nav = element.getBoundingClientRect();
      return [...element.querySelectorAll("a, div")].map(child => child.getBoundingClientRect()).every(rect => rect.left >= nav.left - 1 && rect.right <= nav.right + 1);
    });
    assert.ok(bounds, "Pager controls fit their navigation region at enlarged text");
  });
}
await h.finish();
