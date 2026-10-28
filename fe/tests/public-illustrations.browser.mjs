// SIMPLIFY-2B: actual public routes, synthetic API fixtures, delayed image decoding.
import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";

const { check, shown, screenshot, noHorizontalOverflow, finish } =
  await createBrowserHarness("public-illustrations");

const empty = { items: [], page: 1, page_size: 10, has_next: false, ordering: "RECOMMENDED" };
const overrides = {
  "/api/v1/auth/session": ({ reply }) =>
    reply({ error: { code: "unauthenticated", message: "Sign in to continue." } }, 401),
  "/api/v1/public/announcements": empty,
  "/api/v1/public/resources": empty,
};
const routes = [
  { path: "/", name: "landing", asset: "gco-characters", ratio: 2 },
  { path: "/announcements", name: "announcements", asset: "gco-character-point-up", ratio: 1 },
  { path: "/resources", name: "resources", asset: "gco-character-point-right", ratio: 1 },
];
const intersects = (a, b) => a.x < b.x + b.width - 1 && a.x + a.width > b.x + 1 &&
  a.y < b.y + b.height - 1 && a.y + a.height > b.y + 1;

for (const device of ["desktop", "phone", "narrowPhone"]) {
  for (const route of routes) {
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    await check(`${route.name}-${device}`, route.path, {
      device, overrides,
      beforeNavigate: async ({ context, page }) => {
        await page.emulateMedia({ reducedMotion: "reduce" });
        await context.route("**/_next/image?**", async (request) => {
          if (new URL(request.request().url()).searchParams.get("url")?.startsWith("/illustrations/")) {
            await gate;
          }
          await request.continue();
        });
      },
    }, async (page) => {
      try {
        await shown(page.locator("main h1"));
        // WebKit's fonts.ready can wait on layout blocked by the intentional
        // image gate. Wait only for fonts currently loading, with a hard timeout.
        await page.waitForFunction(() => [...document.fonts].every((font) => font.status !== "loading"));
        const image = page.locator(`main img[src*="${route.asset}"]`);
        assert.equal(await image.count(), 1, "Existing public placement renders exactly one character illustration");
        assert.equal(await image.getAttribute("alt"), "", "Nearby content supplies decorative image meaning");
        assert.equal(await image.evaluate((element) => element.tabIndex), -1, "Artwork never receives keyboard focus");
        assert.equal(await page.locator('main img[src*="-3d"]').count(), 0,
          "Feature objects remain staged for the separate Home integration");
        const visible = device === "desktop" || route.name === "landing";
        assert.equal(await image.isVisible(), visible, "Title-band artwork remains hidden on narrow phones");
        const headingBefore = await page.locator("main h1").boundingBox();
        const imageBefore = visible ? await image.boundingBox() : null;
        release();
        if (visible) {
          await page.waitForFunction((element) => element.complete && element.naturalWidth > 0,
            await image.elementHandle());
          assert.ok(await image.evaluate((element) => element.complete && element.naturalWidth > 0),
            "The actual optimized artwork loads");
          const imageAfter = await image.boundingBox();
          const headingAfter = await page.locator("main h1").boundingBox();
          for (const key of ["x", "y", "width", "height"]) {
            assert.ok(Math.abs(imageBefore[key] - imageAfter[key]) <= 1,
              "Image space is reserved before delayed decoding");
            assert.ok(Math.abs(headingBefore[key] - headingAfter[key]) <= 1,
              "Image loading does not move the heading");
          }
          assert.ok(Math.abs(imageAfter.width / imageAfter.height - route.ratio) < 0.01,
            "The approved artwork keeps its aspect ratio");
          for (const control of await page.locator("main h1, main a, main button, main input, main select").all()) {
            if (!await control.isVisible()) continue;
            const box = await control.boundingBox();
            assert.ok(!intersects(imageAfter, box), "Artwork stays clear of headings and controls");
          }
        }
        await shown(page.getByText(route.name === "resources"
          ? "No public resources are available right now."
          : "No public announcements are available right now.", { exact: true }));
        await noHorizontalOverflow(page);
        await screenshot(page, `${route.name}-${device}`);
      } finally { release(); }
    });
  }
}

await check("all-fourteen-production-PNGs-decode", "/", { overrides }, async (page, { context }) => {
  const assets = [
    "gco-character-point-right", "gco-character-point-up", "gco-character-wave", "gco-characters",
    "appointment-calendar-3d", "guidance-messages-3d", "individual-inventory-3d",
    "service-catalog-3d", "counseling-3d", "guidance-followups-3d", "good-moral-3d",
    "exit-interview-3d", "graduate-tracer-3d", "announcements-3d",
  ];
  for (const name of assets) {
    const response = await context.request.get(new URL(`/illustrations/${name}.png`, page.url()).href);
    assert.equal(response.status(), 200, `${name} has a working production path`);
  }
  const decoded = await page.evaluate(async (names) => Promise.all(names.map(async (name) => {
    const image = new Image();
    image.src = `/illustrations/${name}.png`;
    await image.decode();
    return { name, width: image.naturalWidth, height: image.naturalHeight };
  })), assets);
  for (const image of decoded) {
    assert.deepEqual([image.width, image.height],
      image.name === "gco-characters" ? [1024, 512] : [512, 512]);
  }
});

await finish();
