// Run every browser suite, with a named log group and isolated evidence per engine/suite.
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function browserSuites(directory = join(frontend, "tests")) {
  return readdirSync(directory, { recursive: true })
    .filter((name) => name.endsWith(".browser.mjs"))
    .sort();
}

export function shardSuites(suites, shard = "1/1") {
  const match = /^(\d+)\/(\d+)$/.exec(shard);
  if (!match) throw new Error("Use --shard INDEX/TOTAL (one-based).");
  const [, index, total] = match.map(Number);
  if (index < 1 || total < 1 || index > total || total > suites.length) {
    throw new Error("Shard must select a nonempty part of the browser inventory.");
  }
  return suites.filter((_, position) => position % total === index - 1);
}

export function runSuites(suites, engine, { run = spawnSync, env = process.env } = {}) {
  if (!["chromium", "webkit"].includes(engine)) throw new Error(`Unsupported browser: ${engine}`);
  if (!suites.length) throw new Error("No browser suites selected.");
  const failed = [];
  const artifacts = join(env.COMPASS_UI_ARTIFACTS ?? join(tmpdir(), "compass-browser-regressions"), engine);
  for (const suite of suites) {
    console.log(`::group::${engine}: ${suite}`);
    const result = run(process.execPath, [join("tests", suite)], {
      cwd: frontend,
      env: { ...env, COMPASS_UI_BROWSER: engine, COMPASS_UI_ARTIFACTS: artifacts },
      stdio: "inherit",
      timeout: 10 * 60 * 1000,
    });
    if (result.error || result.status !== 0) {
      failed.push(suite);
      console.error(`FAIL ${engine}: ${suite} (${result.error?.message ?? result.signal ?? result.status})`);
    } else {
      console.log(`PASS ${engine}: ${suite}`);
    }
    console.log("::endgroup::");
  }
  console.log(`${engine}: ${suites.length - failed.length}/${suites.length} suites passed.`);
  if (failed.length) console.error(`Failed suites:\n${failed.join("\n")}`);
  return failed.length ? 1 : 0;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { values } = parseArgs({ options: {
    browser: { type: "string" },
    shard: { type: "string", default: "1/1" },
    suite: { type: "string" },
    list: { type: "boolean", default: false },
  } });
  let suites = browserSuites();
  if (values.suite) {
    if (!suites.includes(values.suite)) throw new Error(`Unknown suite: ${values.suite}`);
    suites = [values.suite];
  }
  suites = shardSuites(suites, values.shard);
  if (values.list) {
    console.log(suites.map((suite) => relative(frontend, join(frontend, "tests", suite))).join("\n"));
  } else {
    const engines = values.browser ? [values.browser] : ["chromium", "webkit"];
    let status = 0;
    for (const engine of engines) status |= runSuites(suites, engine);
    process.exitCode = status;
  }
}
