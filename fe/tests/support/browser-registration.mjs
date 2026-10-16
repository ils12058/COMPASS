import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { browserSuites, shardSuites } from "../run-browser-regressions.mjs";

// Preserve feature-specific CI assertions when shell chains are replaced with discovery.
export function assertBrowserSuiteInCI(suite) {
  const pkg = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8"));
  assert.equal(pkg.scripts["test:ui:regressions"], "node tests/run-browser-regressions.mjs");
  const suites = browserSuites();
  assert.ok(suites.includes(suite), `${suite} must be discovered`);
  const selected = [1, 2, 3, 4].flatMap((index) => shardSuites(suites, `${index}/4`));
  assert.equal(selected.filter((name) => name === suite).length, 1, `${suite} must run once per engine`);
  const workflow = readFileSync(new URL("../../../.github/workflows/frontend-targeted.yml", import.meta.url), "utf8");
  assert.match(workflow, /browser: \[chromium, webkit\]/);
  assert.match(workflow, /shard: \[1, 2, 3, 4\]/);
  assert.match(workflow, /pnpm test:ui:regressions --browser "\$\{\{ matrix.browser \}\}" --shard "\$\{\{ matrix.shard \}\}\/4"/);
  return workflow;
}
