import assert from "node:assert/strict";
import { test } from "node:test";

import { browserTestRuntimeEnabled, isLoopbackHostname } from "../src/lib/browser-test-runtime.ts";
import { DailyCallSession } from "../src/features/ecounseling/call/daily-call-session.ts";
import { installFakeDaily } from "./support/fake-daily.mjs";

async function withRuntime({ mode, flag, hostname }, check) {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousMode = process.env.NODE_ENV;
  const previousFlag = process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE;
  try {
    process.env.NODE_ENV = mode;
    if (flag === undefined) delete process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE;
    else process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE = flag;
    if (hostname === undefined) delete globalThis.window;
    else globalThis.window = { location: { hostname } };
    await check();
  } finally {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else delete globalThis.window;
    if (previousMode === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = previousMode;
    if (previousFlag === undefined) delete process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE;
    else process.env.NEXT_PUBLIC_COMPASS_UI_TEST_MODE = previousFlag;
  }
}

test("browser provider seams require a local page and development or the exact explicit build flag", async () => {
  for (const [mode, flag, hostname, expected] of [
    ["production", undefined, "localhost", false],
    ["production", "0", "127.0.0.1", false],
    ["production", "true", "127.0.0.1", false],
    ["production", "1", "127.0.0.1", true],
    ["production", "1", "[::1]", true],
    ["production", "1", "staging.compass.example", false],
    ["production", "1", "localhost.example", false],
    ["development", undefined, "localhost", true],
    ["development", undefined, "staging.compass.example", false],
    ["production", "1", undefined, false],
  ]) {
    await withRuntime({ mode, flag, hostname }, () => {
      assert.equal(browserTestRuntimeEnabled(), expected, `${mode}/${flag}/${hostname}`);
    });
  }
  for (const hostname of ["localhost", "127.0.0.1", "127.255.0.2", "[::1]", "::1"]) assert.equal(isLoopbackHostname(hostname), true);
  for (const hostname of ["128.0.0.1", "127.0.0.999", "127.0.0.1.example", "localhost.example", ""]) assert.equal(isLoopbackHostname(hostname), false);
});

test("a flagged production build joins through the local fake Daily factory", async () => {
  await withRuntime({ mode: "production", flag: "1", hostname: "127.0.0.1" }, async () => {
    const daily = installFakeDaily(window);
    const session = new DailyCallSession({ supportsSpeakerSelection: () => false });
    try {
      await session.join({
        fetchCredential: async () => ({ roomUrl: "https://example.daily.co/synthetic-room", token: "synthetic", expiresAt: new Date(Date.now() + 60_000).toISOString() }),
        describeCredentialError: () => "Unavailable",
      });
      assert.equal(session.getSnapshot().phase, "joined");
      assert.equal(daily.count("createCallObject"), 1);
      assert.equal(daily.count("join"), 1);
    } finally {
      await session.leave();
    }
  });
});
