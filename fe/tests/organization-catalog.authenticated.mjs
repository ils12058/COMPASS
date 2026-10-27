// Opt-in real Next -> Django -> PostgreSQL rehearsal, separate from mocked *.browser.mjs.
// See docs/org-4/authenticated-integration.md. No API response bodies are fabricated.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { chromium } from "playwright";

const base = process.env.COMPASS_UI_BASE_URL;
assert.equal(new URL(base).hostname, "localhost");
assert.equal(process.env.COMPASS_ORG4_DISPOSABLE, "1");
const statePath = process.env.COMPASS_ORG4_STATE;
const state = JSON.parse(await readFile(statePath, "utf8"));
const helper = resolve("../be/tests/catalog_authenticated_rehearsal.py");
const oracle = (action, ...args) => execFileSync(process.env.COMPASS_ORG4_PYTHON,
  [helper, action, statePath, ...args], { encoding: "utf8", timeout: 45_000 }).trim();
const snapshot = () => JSON.parse(oracle("snapshot"));
const browser = await chromium.launch({ headless: true });
const contexts = [];
const results = [];
let page;
const observed = new Set();
const mutationRequests = [];
async function check(name, action) {
  await action();
  results.push({ name, result: "PASS" });
  console.log(`PASS ${name}`);
}
async function login(actor) {
  const context = await browser.newContext({ serviceWorkers: "block", viewport: { width: 1440, height: 1000 } });
  contexts.push(context);
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    return ["localhost", "127.0.0.1"].includes(url.hostname) ? route.continue() : route.abort();
  });
  const p = await context.newPage();
  p.setDefaultTimeout(20_000);
  p.on("response", response => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith("/api/v1/organization/") && response.status() === 200) {
      const m = path.match(/\/(campuses|colleges|programs)(?:\/[^/]+\/(name|active|policy|impact|history))?$/);
      if (m && (m[2] || response.request().method() === "POST")) observed.add(`${m[1]}:${m[2] ?? "create"}`);
    }
  });
  p.on("request", request => {
    if (request.url().includes("/api/v1/organization/") && ["POST", "PUT"].includes(request.method())) {
      mutationRequests.push({ path: new URL(request.url()).pathname, method: request.method() });
    }
  });
  await p.goto(`${base}/login?next=%2Fportal%2Forganization`);
  await p.getByLabel("Email", { exact: true }).fill(state.actors[actor].email);
  await p.getByLabel("Password", { exact: true }).fill(state.password);
  const loginResponse = p.waitForResponse(r => r.url().endsWith("/api/v1/auth/login"));
  await p.getByRole("button", { name: "Sign in", exact: true }).click();
  const body = await (await loginResponse).json();
  if (body.mfa_required) {
    await p.getByLabel("Authenticator code", { exact: true }).fill(oracle("totp", actor));
    await p.getByRole("button", { name: "Verify", exact: true }).click();
  }
  await p.waitForURL("**/portal/organization");
  const cookie = (await context.cookies()).find(c => c.name === "compass_session");
  assert.ok(cookie?.httpOnly && cookie.path === "/api/");
  return p;
}
async function actions(name, action) {
  const summary = page.locator("summary").filter({ hasText: `Actions for ${name}` });
  await summary.waitFor({ state: "visible" });
  assert.equal(await summary.count(), 1);
  if (await summary.locator("..").getAttribute("open") === null) await summary.click();
  await summary.locator("..").getByRole("button", { name: action, exact: true }).click();
}
async function basis() { await page.getByLabel("Institutional basis/reference", { exact: true }).fill("Synthetic ORG-4 engineering rehearsal"); }
async function review() { await page.getByRole("button", { name: "Review change", exact: true }).click(); await page.getByRole("alertdialog").waitFor(); }
async function confirm(label) { await page.getByRole("alertdialog").getByRole("button", { name: label, exact: true }).click(); }
async function saved() { await page.getByText(/The change was saved\. Latest record:/).waitFor(); }
async function done() { await page.getByRole("button", { name: "Done", exact: true }).click(); }
function row(kind, code) { const rows = snapshot().catalog[kind].filter(r => r.code === code); assert.equal(rows.length, 1); return rows[0]; }
function evidence(item, version, actor = "catalog") {
  assert.equal(item.resource_version, version);
  const events = snapshot().events.filter(e => e.target_id === item.id);
  assert.equal(events.length, version);
  const versions = events.map(e => e.metadata.resource_version_after).sort((a, b) => a - b);
  assert.deepEqual(versions, Array.from({ length: version }, (_, i) => i + 1));
  assert.ok(events.some(e => e.actor_user_id === state.actors[actor].id));
}
async function rename(name, newName) {
  await actions(name, "Rename"); await page.getByLabel("New official name").fill(newName); await basis();
  await review(); await confirm(name.includes("Campus") ? "Rename campus" : name.includes("College") ? "Rename college" : "Rename program");
  await saved(); await done();
}
async function status(kind, name, active) {
  await actions(name, active ? "Activate" : "Deactivate"); await basis(); await review();
  await confirm(`${active ? "Activate" : "Deactivate"} ${kind}`); await saved(); await done();
}
async function api(p, path, { method = "GET", data, csrf = true } = {}) {
  return p.evaluate(async ({ path, method, data, csrf }) => {
    const token = csrf ? (await (await fetch("/api/v1/auth/csrf")).json()).csrf_token : null;
    const response = await fetch(`/api/v1${path}`, { method, credentials: "include",
      headers: { "Content-Type": "application/json", ...(token ? { "X-CSRFToken": token } : {}) },
      ...(data ? { body: JSON.stringify(data) } : {}) });
    return { status: response.status, body: await response.json() };
  }, { path, method, data, csrf });
}
try {
  page = await login("catalog");
  await check("01 Actual password/TOTP login, opaque HttpOnly session, Catalog-only workspace", async () => {
    await page.getByRole("heading", { name: "Organization structure", exact: true }).waitFor();
    assert.equal(await page.getByRole("link", { name: "Responsibilities", exact: true }).count(), 0);
    const session = await api(page, "/auth/session");
    assert.ok(session.body.user.capabilities.includes("organization.catalog.manage"));
    assert.ok(!session.body.user.capabilities.includes("organization.manage"));
  });
  for (const [kind, code, name, parent] of [
    ["campus", "E2E_CAMPUS", "E2E Campus", null],
    ["college", "E2E_COLLEGE", "E2E College", "E2E Campus"],
    ["program", "E2E_PROGRAM", "E2E Program", "E2E College"],
  ]) {
    await check(`Create ${kind} through UI and verify PostgreSQL identity/version/Audit`, async () => {
      if (parent) await actions(parent, `Add ${kind}`); else await page.getByRole("button", { name: "Add campus", exact: true }).click();
      await page.getByLabel(/^(Campus|College|Program) code$/).fill(code);
      await page.getByLabel("Official name", { exact: true }).fill(name);
      await page.getByLabel("Initial status").selectOption("active");
      if (kind === "program") {
        await page.getByLabel("Academic classification", { exact: true }).selectOption("BACHELORS");
        await page.getByLabel("Year Level policy", { exact: true }).selectOption("CONFIGURED");
        for (const level of ["1st Year", "3rd Year", "5th Year"]) await page.getByLabel(level, { exact: true }).check();
      }
      await basis(); await review(); await confirm(`Add ${kind}`); await saved(); await done();
      evidence(row(kind, code), 1);
    });
    await check(`Rename ${kind}, preserve UUID/code/parent, inspect restricted paginated history`, async () => {
      const before = row(kind, code);
      await rename(name, `${name} Renamed`);
      const after = row(kind, code);
      assert.equal(after.id, before.id); assert.equal(after.code, before.code);
      assert.equal(after.campus_id, before.campus_id); assert.equal(after.college_id, before.college_id);
      evidence(after, 2);
      await actions(after.name, "Change history"); await page.getByRole("dialog").getByText("Official name changed", { exact: true }).waitFor();
      await page.keyboard.press("Escape");
      const collection = kind === "campus" ? "campuses" : `${kind}s`;
      const history = await api(page, `/organization/${collection}/${after.id}/history?page_size=1`);
      assert.equal(history.status, 200); assert.equal(history.body.has_next, true);
      assert.equal(history.body.items[0].actor_id, state.actors.catalog.id);
      const second = await api(page, `/organization/${collection}/${after.id}/history?page=2&page_size=1`);
      assert.equal(second.body.items.length, 1); assert.equal(second.body.has_next, false);
    });
  }
  await check("Complete noncontiguous policy update, actual persisted levels and no-op Audit silence", async () => {
    await actions("E2E Program Renamed", "Edit academic policy");
    await page.getByLabel("Academic classification", { exact: true }).selectOption("MASTERS");
    await basis(); await review(); await confirm("Save Program policy"); await saved(); await done();
    const p = row("program", "E2E_PROGRAM"); evidence(p, 3); assert.deepEqual(p.applicable_year_levels, [1, 3, 5]);
    const res = await api(page, `/organization/programs/${p.id}/policy`, { method: "PUT", data: {
      expected_resource_version: 3, academic_classification: "MASTERS", year_level_policy_status: "CONFIGURED",
      applicable_year_levels: [1, 3, 5], basis: "Synthetic no-op" } });
    assert.equal(res.status, 200); evidence(row("program", "E2E_PROGRAM"), 3);
  });
  await check("Real CSRF, forged MFA/actor/parent fields and stale-version refusals leave DB unchanged", async () => {
    const p = row("program", "E2E_PROGRAM");
    const path = `/organization/programs/${p.id}/name`;
    const data = { name: "Forged", basis: "Synthetic denial", expected_resource_version: 3 };
    assert.equal((await api(page, path, { method: "PUT", data, csrf: false })).status, 403);
    for (const field of ["mfa_verified", "actor_id", "college_id", "code"]) {
      assert.equal((await api(page, path, { method: "PUT", data: { ...data, [field]: "forged" } })).status, 422);
    }
    assert.equal((await api(page, path, { method: "PUT", data: { ...data, expected_resource_version: 1 } })).body.error.code, "catalog_stale_version");
    evidence(row("program", "E2E_PROGRAM"), 3);
  });
  await check("Actual impact blocker, deliberate Program -> College -> Campus retirement and reverse activation", async () => {
    const k = row("college", "E2E_COLLEGE");
    const impact = await api(page, `/organization/colleges/${k.id}/impact`);
    assert.equal(impact.body.can_deactivate, false); assert.equal(impact.body.counts.active_child_programs, 1);
    const blocked = await api(page, `/organization/colleges/${k.id}/active`, { method: "PUT", data: { is_active: false, expected_resource_version: 2, basis: "Blocked rehearsal" } });
    assert.equal(blocked.body.error.code, "catalog_deactivation_blocked");
    for (const [kind, name, code, version] of [["program", "E2E Program Renamed", "E2E_PROGRAM", 4], ["college", "E2E College Renamed", "E2E_COLLEGE", 3], ["campus", "E2E Campus Renamed", "E2E_CAMPUS", 3]]) {
      await status(kind, name, false); const item = row(kind, code); assert.equal(item.is_active, false); evidence(item, version);
    }
    for (const [kind, name, code, version] of [["campus", "E2E Campus Renamed", "E2E_CAMPUS", 4], ["college", "E2E College Renamed", "E2E_COLLEGE", 4], ["program", "E2E Program Renamed", "E2E_PROGRAM", 5]]) {
      await status(kind, name, true); const item = row(kind, code); assert.equal(item.is_active, true); evidence(item, version);
    }
  });
  await check("MFA expiry, concurrent target change during verification, refresh and deliberate reconfirmation", async () => {
    await actions("E2E Program Renamed", "Rename"); await page.getByLabel("New official name").fill("E2E MFA reviewed"); await basis();
    oracle("expire-mfa"); await review(); await confirm("Rename program");
    await page.getByRole("dialog", { name: "Verify it's you" }).waitFor();
    oracle("competing-rename", "E2E_PROGRAM", "Concurrent during MFA");
    const before = mutationRequests.length;
    await page.getByLabel("Authenticator code", { exact: true }).fill(oracle("totp", "catalog"));
    await page.getByRole("dialog").getByRole("button", { name: "Verify", exact: true }).click();
    await page.getByText(/Authenticator verified\. Review the latest saved values/).waitFor();
    assert.equal(mutationRequests.length, before); assert.equal(row("program", "E2E_PROGRAM").name, "Concurrent during MFA");
    assert.equal(await page.getByLabel("New official name").inputValue(), "E2E MFA reviewed");
    await review(); await confirm("Rename program"); await saved(); await done();
    assert.equal(row("program", "E2E_PROGRAM").name, "E2E MFA reviewed");
  });
  await check("Lost response after real commit reconciles current state and actor history without second mutation", async () => {
    const id = row("program", "E2E_PROGRAM").id;
    await page.route(`**/api/v1/organization/programs/${id}/name`, async route => {
      const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort("connectionreset");
    }, { times: 1 });
    await actions("E2E MFA reviewed", "Rename"); await page.getByLabel("New official name").fill("E2E recovered"); await basis();
    await review(); const before = mutationRequests.length; await confirm("Rename program"); await saved();
    assert.equal(mutationRequests.length, before + 1); assert.equal(row("program", "E2E_PROGRAM").name, "E2E recovered"); await done();
  });
  await check("Submitted encrypted Inventory unchanged after actual historical Program rename/policy/retirement", async () => {
    await page.goto(`${base}/portal/organization`);
    await rename("Historical Program", "Historical Program Renamed");
    await actions("Historical Program Renamed", "Edit academic policy");
    await page.getByLabel("Academic classification", { exact: true }).selectOption("DOCTORAL");
    await basis(); await review(); await confirm("Save Program policy"); await saved(); await done();
    await status("program", "Historical Program Renamed", false);
    assert.equal(snapshot().historical_inventory_unchanged, true);
  });
  for (const actor of ["relationships", "both", "reader", "student"]) {
    await check(`Actual ${actor} session, independent workspace authority and restricted API history`, async () => {
      const p = await login(actor);
      const catalog = actor === "both";
      const relationships = ["relationships", "both"].includes(actor);
      await p.getByRole("heading", { name: actor === "student" ? "Organization unavailable" : "Organization structure", exact: true }).waitFor();
      assert.equal(await p.getByRole("button", { name: "Add campus", exact: true }).count(), catalog ? 1 : 0);
      assert.equal(await p.getByRole("link", { name: "Responsibilities", exact: true }).count(), relationships ? 1 : 0);
      const id = row("program", "E2E_PROGRAM").id;
      assert.equal((await api(p, `/organization/programs/${id}/history`)).status, catalog ? 200 : 403);
      if (!catalog) {
        const before = snapshot().events.length;
        assert.equal((await api(p, `/organization/programs/${id}/name`, { method: "PUT", data: { name: "Denied", basis: "Denial test", expected_resource_version: row("program", "E2E_PROGRAM").resource_version } })).status, 403);
        assert.equal(snapshot().events.length, before);
      }
    });
  }
  await check("All sixteen operation families reached real Django successfully", async () => {
    const expected = ["campuses", "colleges", "programs"].flatMap(collection => ["create", "name", "active", "impact", "history"].map(action => `${collection}:${action}`)).concat("programs:policy");
    assert.deepEqual([...observed].sort(), expected.sort());
  });
} catch (error) {
  console.error(error);
  if (page) await page.screenshot({ path: `${process.env.COMPASS_UI_ARTIFACTS}/authenticated-failure.png`, fullPage: true });
  results.push({ name: "aborted scenario", result: "FAIL", error: String(error) });
  process.exitCode = 1;
} finally {
  await writeFile(`${process.env.COMPASS_UI_ARTIFACTS}/authenticated-results.json`, JSON.stringify({ results, operations: [...observed].sort(), mutationRequests }, null, 2));
  for (const context of contexts) await context.close();
  await browser.close();
}
