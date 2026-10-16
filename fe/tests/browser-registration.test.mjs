import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { browserSuites, runSuites, shardSuites } from "./run-browser-regressions.mjs";

test("browser discovery includes future and nested suites without a script edit", () => {
  const directory = mkdtempSync(join(tmpdir(), "compass-browser-discovery-"));
  try {
    mkdirSync(join(directory, "nested"));
    for (const name of ["new.browser.mjs", "nested/other.browser.mjs", "helper.mjs"]) {
      writeFileSync(join(directory, name), "");
    }
    assert.deepEqual(browserSuites(directory), ["nested/other.browser.mjs", "new.browser.mjs"]);
  } finally {
    rmSync(directory, { recursive: true });
  }
});

test("all current browser suites run exactly once across the four CI shards", () => {
  const suites = browserSuites();
  const planned = [1, 2, 3, 4].flatMap((index) => shardSuites(suites, `${index}/4`));
  assert.ok(suites.length > 0);
  assert.deepEqual(planned.sort(), suites);
  assert.equal(new Set(planned).size, suites.length);
  for (const invalid of ["0/4", "5/4", "1/0", "bad", `1/${suites.length + 1}`]) {
    assert.throws(() => shardSuites(suites, invalid));
  }
});

test("a failing or interrupted suite cannot hide later failures or produce green", () => {
  const seen = [];
  const run = (command, args, options) => {
    seen.push({ command, args, options });
    return seen.length === 1 ? { status: 1 } : { status: null, signal: "SIGTERM" };
  };
  assert.equal(runSuites(["first.browser.mjs", "second.browser.mjs"], "webkit", {
    run, env: { COMPASS_UI_ARTIFACTS: "/tmp/evidence" },
  }), 1);
  assert.equal(seen.length, 2);
  assert.equal(seen[1].options.env.COMPASS_UI_BROWSER, "webkit");
  assert.equal(seen[1].options.env.COMPASS_UI_ARTIFACTS, "/tmp/evidence/webkit");
  assert.equal(runSuites(["passing.browser.mjs"], "chromium", { run: () => ({ status: 0 }) }), 0);
  assert.throws(() => runSuites([], "chromium"));
  assert.throws(() => runSuites(["example.browser.mjs"], "unknown"));
});
