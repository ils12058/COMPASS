import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { messagesAccount, sessionFor } from "./support/guidance-messages-fixtures.mjs";
const h = await createBrowserHarness("simplify-3b-public-empty");
for (const audience of ["public", "account"]) for (const kind of ["announcements", "resources"]) {
  const reads = [];
  const handler = async ({ pathname, url, reply }) => {
    if (pathname === "/api/v1/auth/session") { await reply(audience === "public" ? { authenticated: false } : sessionFor(messagesAccount("STUDENT"))); return true; }
    if (![ `/api/v1/public/${kind}`, `/api/v1/${kind}` ].includes(pathname)) return false;
    reads.push({ path: pathname, page: url.searchParams.get("page"), search: url.searchParams.get("search"), ordering: url.searchParams.get("ordering") });
    await reply({ items: [], page: Number(url.searchParams.get("page") ?? 1), page_size: 10, has_next: false, ordering: "TITLE_ASC" });
    return true;
  };
  await h.check(`${audience}-${kind}`, `/${kind}?search=example&ordering=TITLE_ASC&page=2`, { handler, viewport: { width: 390, height: 900 } }, async page => {
    await h.shown(page.getByText(`No ${kind} on this page.`, { exact: true }));
    const previous = page.getByRole("navigation", { name: "Pagination" }).getByRole("link", { name: "Previous", exact: true });
    await h.shown(previous);
    const href = new URL(await previous.getAttribute("href"), "http://localhost");
    assert.equal(href.searchParams.get("page"), "1");
    assert.equal(href.searchParams.get("search"), "example");
    assert.equal(href.searchParams.get("ordering"), "TITLE_ASC");
    await previous.focus();
    await page.keyboard.press("Enter");
    await h.shown(page.getByText(new RegExp(`No (?:public )?${kind} match this search`)));
    assert.ok(reads.some(read => read.page === "1" && read.search === "example" && read.ordering === "TITLE_ASC"));
  });
}
await h.finish();
