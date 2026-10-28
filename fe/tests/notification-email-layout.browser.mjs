// Local reuse of committed synthetic previews. No SMTP or external-client claims.
import assert from "node:assert/strict";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { chromium, webkit } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
assert.ok(["chromium", "webkit"].includes(engine));
const out = join(process.env.COMPASS_UI_ARTIFACTS ?? join(tmpdir(), "compass-notif04-email"), "notification-email-layout");
await mkdir(out, { recursive: true });
const browser = await (engine === "webkit" ? webkit : chromium).launch();
const context = await browser.newContext();
await context.route("**/*", route => route.abort());
const results = [];
try {
  for (const slice of ["notif-02", "notif-03"]) {
    const directory = join(root, "docs", slice, "previews");
    for (const file of (await readdir(directory)).filter(name => name.endsWith(".html")).sort()) {
      const html = await readFile(join(directory, file), "utf8");
      const plain = await readFile(join(directory, file.replace(/\.html$/, ".txt")), "utf8");
      assert.ok(plain.trim());
      for (const width of [390, 680]) {
        const page = await context.newPage();
        await page.setViewportSize({ width, height: 900 });
        await page.setContent(html);
        assert.equal(await page.locator("script,iframe,object,embed,img,link[rel=stylesheet]").count(), 0);
        const urls = await page.locator("a[href]").evaluateAll(nodes => nodes.map(node => node.getAttribute("href")));
        for (const href of urls) {
          const url = new URL(href);
          assert.equal(url.origin, "https://portal.example");
          assert.ok(url.pathname.startsWith("/portal/"));
          assert.ok(plain.includes(href), "Matching plain-text action");
        }
        const bounds = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, client: document.documentElement.clientWidth }));
        assert.ok(bounds.scroll <= bounds.client + 1, `${slice}/${file} overflows at ${width}`);
        if ((file === "scheduled-student.html" && width === 680) || (file === "good-moral-issued.html" && width === 390) || (file === "long-labels.html" && width === 390)) {
          await page.screenshot({ path: join(out, `${slice}-${file}-${width}.png`), fullPage: true });
        }
        results.push({ slice, file, width, passed: true, links: urls.length });
        await page.close();
      }
    }
  }
} finally {
  await browser.close();
  await writeFile(join(out, "results.json"), JSON.stringify({ engine, reusedSyntheticPreviews: true, results }, null, 2) + "\n");
}
console.log(`PASS ${results.length} ${engine} email layouts; no overflow, active/remote resources or unsafe links`);
