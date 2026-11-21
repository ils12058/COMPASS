// Actual production response headers and PWA behavior, on a loopback server only. Provider and
// backend compatibility are covered by the affected synthetic workflow suites separately.
import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { chromium, webkit } from "playwright";

const baseURL = process.env.COMPASS_UI_BASE_URL ?? "http://localhost:3107";
const engine = process.env.COMPASS_UI_BROWSER ?? "chromium";
assert.ok(["localhost", "127.0.0.1", "[::1]"].includes(new URL(baseURL).hostname));
assert.ok(["chromium", "webkit"].includes(engine));
const artifacts = join(process.env.COMPASS_UI_ARTIFACTS ?? tmpdir(), "security-headers");
await mkdir(artifacts, { recursive: true });
const browser = await (engine === "webkit" ? webkit : chromium).launch({ headless: true });
const results = [];
const cspConsole = [];
let context;

async function check(name, run) {
  try {
    await run();
    results.push({ name, passed: true });
    console.log(`PASS ${name}`);
  } catch (error) {
    results.push({ name, passed: false, error: error.message });
    console.error(`FAIL ${name}: ${error.message}`);
    process.exitCode = 1;
  }
}

try {
  context = await browser.newContext({ serviceWorkers: "allow" });
  context.setDefaultTimeout(12_000);
  await context.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return !["http:", "https:"].includes(url.protocol) || ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
      ? route.continue() : route.abort("blockedbyclient");
  });

  for (const path of [
    "/", "/login", "/portal/messages", "/portal/e-counseling/synthetic-session", "/resources",
    "/brand/compass-mark.svg", "/manifest.webmanifest", "/offline.html", "/sw.js",
  ]) {
    await check(`production response headers: ${path}`, async () => {
      const response = await context.request.get(`${baseURL}${path}`);
      assert.equal(response.status(), 200);
      const headers = response.headers();
      assert.equal(headers["x-content-type-options"], "nosniff");
      assert.equal(headers["x-frame-options"], "DENY");
      assert.equal(headers["referrer-policy"], "strict-origin-when-cross-origin");
      assert.ok(headers["permissions-policy"].includes("camera=(self)"));
      assert.ok(headers["permissions-policy"].includes("microphone=(self)"));
      assert.ok(headers["permissions-policy"].includes("display-capture=(self)"));
      assert.notEqual(headers["access-control-allow-origin"], "*");
      assert.match(headers["content-security-policy-report-only"], /frame-ancestors 'none'/);
      assert.ok(!headers["content-security-policy-report-only"].includes("unsafe-eval"));
      if (path === "/sw.js") {
        assert.equal(headers["content-security-policy"], "default-src 'self'; script-src 'self'");
        assert.equal(headers["cache-control"], "no-cache, no-store, must-revalidate");
      } else {
        assert.equal(headers["content-security-policy"], undefined);
      }
    });
  }

  const page = await context.newPage();
  page.on("console", (message) => {
    if (/content.security.policy/i.test(message.text())) cspConsole.push(message.text());
  });
  await page.goto(`${baseURL}/offline.html`);

  await check("permissions allow in-page calling and deny unused browser devices", async () => {
    const features = await page.evaluate(() => {
      const policy = document.featurePolicy;
      return policy ? Object.fromEntries(["camera", "microphone", "display-capture", "geolocation", "payment", "usb"]
        .map((name) => [name, policy.allowsFeature(name)])) : null;
    });
    // WebKit has no document.featurePolicy inspection API; its response header is checked above.
    if (features) assert.deepEqual(features, {
      camera: true, microphone: true, "display-capture": true,
      geolocation: false, payment: false, usb: false,
    });
  });

  await check("service worker installs and caches only the public offline fallback", async () => {
    const scope = await page.evaluate(async () => {
      await navigator.serviceWorker.register("/sw.js");
      return (await navigator.serviceWorker.ready).scope;
    });
    assert.equal(scope, `${baseURL}/`);
    await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
    const paths = await page.evaluate(async () => (await (await caches.open("compass-offline-v1")).keys())
      .map((request) => new URL(request.url).pathname));
    assert.deepEqual(paths, ["/offline.html"]);
  });

  await check("PWA offline navigation still reaches the public reconnect page", async () => {
    // WebKit's context.setOffline() rejects the navigation before dispatching the worker's fetch
    // event. Drop a real loopback connection instead, using the exact worker/shell bytes and
    // headers from Next. This exercises the public fallback on both engines without that seam.
    const resources = new Map();
    for (const path of ["/offline.html", "/sw.js"]) {
      const response = await context.request.get(`${baseURL}${path}`);
      const headers = response.headers();
      for (const name of ["content-encoding", "content-length", "transfer-encoding", "connection"]) delete headers[name];
      resources.set(path, { headers, body: await response.body() });
    }
    const outage = createServer((request, response) => {
      const resource = resources.get(request.url);
      if (!resource) {
        request.socket.destroy();
        return;
      }
      response.writeHead(200, resource.headers);
      response.end(resource.body);
    });
    await new Promise((resolve) => outage.listen(0, "127.0.0.1", resolve));
    const localURL = `http://127.0.0.1:${outage.address().port}`;
    try {
      await page.goto(`${localURL}/offline.html`);
      await page.evaluate(async () => {
        await navigator.serviceWorker.register("/sw.js");
        await navigator.serviceWorker.ready;
      });
      await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
      await page.evaluate(() => { window.__BEFORE_OFFLINE_NAVIGATION__ = true; });
      await page.goto(`${localURL}/login`, { waitUntil: "domcontentloaded" });
      await page.getByRole("heading", { name: "You’re offline." }).waitFor();
      assert.equal(new URL(page.url()).pathname, "/login");
      assert.equal(await page.evaluate(() => window.__BEFORE_OFFLINE_NAVIGATION__ === true), false,
        "The worker returned a fresh fallback document instead of leaving the old page visible");
    } finally {
      const closed = new Promise((resolve) => outage.close(resolve));
      outage.closeAllConnections();
      await closed;
    }
  });

  await check("CSP has no resource violations or invalid-source diagnostics", async () => {
    assert.deepEqual(cspConsole.filter((message) => /violat|refused|invalid source|could not be parsed/i.test(message)), []);
  });

  await check("a different web origin cannot read the HTML response through wildcard CORS", async () => {
    const foreignContext = await browser.newContext({ serviceWorkers: "block" });
    try {
      const foreignPage = await foreignContext.newPage();
      await foreignContext.route("http://localhost:3199/security-headers-cors", (route) => route.fulfill({ contentType: "text/html", body: "<!doctype html><title>Synthetic origin</title>" }));
      await foreignPage.goto("http://localhost:3199/security-headers-cors");
      const outcome = await foreignPage.evaluate(async (url) => {
        try {
          await fetch(url, { mode: "cors" });
          return "readable";
        } catch (error) {
          return error.name;
        }
      }, `${baseURL}/login`);
      assert.equal(outcome, "TypeError");
    } finally {
      await foreignContext.close();
    }
  });
} finally {
  await context?.close();
  await browser.close();
  await writeFile(join(artifacts, "results.json"), `${JSON.stringify({ baseURL, engine, results, cspConsole }, null, 2)}\n`);
  console.log(`${results.filter((result) => result.passed).length}/${results.length} browser checks passed; artifacts: ${artifacts}`);
}
