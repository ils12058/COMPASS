import assert from "node:assert/strict";
import { test } from "node:test";

const environmentKeys = [
  "COMPASS_API_BASE_URL", "COMPASS_SITE_URL", "COMPASS_CSP_STORAGE_ORIGINS",
  "NEXT_PUBLIC_REALTIME_URL", "NEXT_PUBLIC_COMPASS_UI_TEST_MODE",
];
let configNumber = 0;

async function loadConfig(environment = {}) {
  const previous = Object.fromEntries(environmentKeys.map((key) => [key, process.env[key]]));
  try {
    for (const key of environmentKeys) {
      if (environment[key] === undefined) delete process.env[key];
      else process.env[key] = environment[key];
    }
    return (await import(`../next.config.ts?security-headers=${configNumber++}`)).default;
  } finally {
    for (const key of environmentKeys) {
      if (previous[key] === undefined) delete process.env[key];
      else process.env[key] = previous[key];
    }
  }
}

const headerValues = (rule) => Object.fromEntries(rule.headers.map(({ key, value }) => [key, value]));
const directives = (policy) => Object.fromEntries(policy.split(";").map((directive) => {
  const [name, ...sources] = directive.trim().split(/\s+/);
  return [name, sources];
}));

test("every route receives the simple headers and canonical-origin CORS override", async () => {
  const config = await loadConfig({ COMPASS_SITE_URL: "https://staging.compass-gco.com/" });
  const rules = await config.headers();
  const allRoutes = rules.find((rule) => rule.source === "/:path*");
  assert.ok(allRoutes);
  const headers = headerValues(allRoutes);
  assert.equal(headers["X-Content-Type-Options"], "nosniff");
  assert.equal(headers["X-Frame-Options"], "DENY");
  assert.equal(headers["Referrer-Policy"], "strict-origin-when-cross-origin");
  assert.equal(headers["Permissions-Policy"], "camera=(self), microphone=(self), display-capture=(self), geolocation=(), payment=(), usb=()");
  assert.equal(headers["Access-Control-Allow-Origin"], "https://staging.compass-gco.com");
  assert.equal(headers["Strict-Transport-Security"], undefined, "Hosting retains its HSTS policy");
  assert.equal(headers["Content-Security-Policy"], undefined, "The full frontend CSP remains report-only");
  assert.ok(headers["Content-Security-Policy-Report-Only"]);
});

test("CSP contains the required directives and the inventoried provider, storage, and realtime origins", async () => {
  const config = await loadConfig({
    COMPASS_API_BASE_URL: "https://api.example.test/",
    NEXT_PUBLIC_REALTIME_URL: "wss://realtime.example.test/api/realtime/v1/socket",
    COMPASS_CSP_STORAGE_ORIGINS: " https://photos.example.test/, https://recordings.example.test,https://photos.example.test ",
  });
  const policy = headerValues((await config.headers())[0])["Content-Security-Policy-Report-Only"];
  const sources = directives(policy);
  assert.deepEqual(Object.keys(sources), [
    "default-src", "script-src", "style-src", "img-src", "font-src", "connect-src", "media-src",
    "frame-src", "worker-src", "manifest-src", "frame-ancestors", "base-uri", "form-action",
    "object-src", "upgrade-insecure-requests",
  ]);
  assert.deepEqual(sources["default-src"], ["'self'"]);
  assert.deepEqual(sources["frame-ancestors"], ["'none'"]);
  assert.deepEqual(sources["base-uri"], ["'self'"]);
  assert.deepEqual(sources["form-action"], ["'self'"]);
  assert.deepEqual(sources["object-src"], ["'none'"]);
  assert.deepEqual(sources["font-src"], ["'self'"], "next/font serves the built fonts locally");
  assert.deepEqual(sources["worker-src"], ["'self'", "blob:"]);
  assert.deepEqual(sources["manifest-src"], ["'self'"]);
  assert.ok(sources["script-src"].includes("'unsafe-inline'"));
  assert.deepEqual(sources["style-src"], ["'self'", "'unsafe-inline'"]);
  for (const name of ["script-src", "connect-src", "frame-src"]) {
    assert.ok(sources[name].includes("https://challenges.cloudflare.com"), name);
    assert.ok(sources[name].includes("https://*.daily.co"), name);
  }
  assert.ok(sources["script-src"].includes("https://c.daily.co"));
  assert.ok(sources["connect-src"].includes("wss://*.daily.co"));
  assert.ok(sources["connect-src"].includes("wss://realtime.example.test"));
  assert.ok(sources["connect-src"].includes("blob:"), "PDF preview reads use local Blob URLs");
  for (const name of ["img-src", "connect-src", "media-src"]) {
    for (const origin of ["https://photos.example.test", "https://recordings.example.test"]) {
      assert.equal(sources[name].filter((source) => source === origin).length, 1, `${name}: ${origin}`);
    }
  }
  assert.ok(sources["img-src"].includes("data:"));
  for (const name of ["img-src", "media-src", "frame-src"]) assert.ok(sources[name].includes("blob:"));
  assert.deepEqual(sources["upgrade-insecure-requests"], []);
  assert.ok(!policy.includes("unsafe-eval"));
  assert.ok(!policy.includes("api.example.test"), "HTTP API calls use the same-origin rewrite");
  assert.ok(!policy.includes("socket"), "Realtime contributes its origin without a path or ticket");
  assert.ok(!sources["connect-src"].includes("wss:"));
  assert.ok(!sources["img-src"].includes("https:"));
  assert.deepEqual(await config.rewrites(), [{ source: "/api/v1/:path*", destination: "https://api.example.test/api/v1/:path*" }]);
});

test("the existing service worker policy and uncached update rule still override the general rule", async () => {
  const rules = await (await loadConfig()).headers();
  const workerIndex = rules.findIndex((rule) => rule.source === "/sw.js");
  assert.ok(workerIndex > rules.findIndex((rule) => rule.source === "/:path*"));
  assert.deepEqual(headerValues(rules[workerIndex]), {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Content-Security-Policy": "default-src 'self'; script-src 'self'",
    "X-Content-Type-Options": "nosniff",
  });
});

test("account-recovery route retains its private referrer and no-store policy", async () => {
  const rules = await (await loadConfig()).headers();
  const recoveryIndex = rules.findIndex((rule) => rule.source === "/account-recovery");
  assert.ok(recoveryIndex > rules.findIndex((rule) => rule.source === "/:path*"));
  assert.deepEqual(headerValues(rules[recoveryIndex]), {
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
  });
});

test("only the dedicated local browser build allows the existing loopback realtime fixtures", async () => {
  const ordinary = headerValues((await (await loadConfig()).headers())[0])["Content-Security-Policy-Report-Only"];
  assert.ok(!ordinary.includes("ws:"));
  const config = await loadConfig({ NEXT_PUBLIC_COMPASS_UI_TEST_MODE: "1" });
  const policy = headerValues((await config.headers())[0])["Content-Security-Policy-Report-Only"];
  const sources = directives(policy)["connect-src"];
  assert.ok(sources.includes("ws://localhost:*"));
  assert.ok(sources.includes("ws://127.0.0.1:*"));
  assert.ok(!sources.includes("ws:"));
  assert.ok(!policy.includes("unsafe-eval"));
});

for (const value of [
  "https://photos.example.test/path", "https://photos.example.test?signature=synthetic",
  "https://photos.example.test#fragment", "https://user:synthetic@photos.example.test",
  "https://*.example.test", "https://photos.example.test; script-src *",
  "http://photos.example.test", "data:image/png", "not-an-origin",
]) {
  test(`storage allowlist rejects non-origin input: ${value}`, async () => {
    await assert.rejects(loadConfig({ COMPASS_CSP_STORAGE_ORIGINS: value }), /COMPASS_CSP_STORAGE_ORIGINS/);
  });
}

test("site and realtime configuration cannot inject arbitrary policy directives", async () => {
  await assert.rejects(loadConfig({ COMPASS_SITE_URL: "https://compass.example.test;anything" }), /COMPASS_SITE_URL/);
  await assert.rejects(loadConfig({ NEXT_PUBLIC_REALTIME_URL: "https://realtime.example.test/api/realtime/v1/socket" }), /NEXT_PUBLIC_REALTIME_URL/);
  await assert.rejects(loadConfig({ NEXT_PUBLIC_REALTIME_URL: "wss://realtime.example.test/api/realtime/v1/socket?ticket=synthetic" }), /NEXT_PUBLIC_REALTIME_URL/);
});
