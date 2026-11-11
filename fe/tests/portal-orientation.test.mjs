import assert from "node:assert/strict";
import { test } from "node:test";
import { GUIDE_STORAGE_KEY, GUIDE_VERSION, parseGuidePreference, saveGuidePreference, readGuidePreference } from "../src/features/portal/orientation/guide-preference.ts";
import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";

test("guide state accepts only the current version and known UI statuses", () => {
  for (const raw of [null, "{", "null", "[]", "true", '{"version":0,"status":"completed"}', '{"version":2,"status":"completed"}', '{"version":1,"status":"other"}']) {
    assert.equal(parseGuidePreference(raw), "new");
  }
  for (const status of ["completed", "dismissed"]) assert.equal(parseGuidePreference(JSON.stringify({ version: GUIDE_VERSION, status })), status);
});

test("saved preferences contain only a version and a non-sensitive UI status", () => {
  let entry;
  const previous = globalThis.window;
  globalThis.window = { localStorage: { setItem: (key, value) => { entry = { key, value }; }, getItem: () => entry.value } };
  try {
    saveGuidePreference("completed");
    assert.deepEqual(entry, { key: GUIDE_STORAGE_KEY, value: '{"version":1,"status":"completed"}' });
    assert.equal(readGuidePreference(), "completed");
  } finally { globalThis.window = previous; }
});

test("blocked storage never prevents launch or completion", () => {
  const previous = globalThis.window;
  globalThis.window = { get localStorage() { throw new Error("Storage unavailable"); } };
  try {
    assert.equal(readGuidePreference(), "new");
    assert.doesNotThrow(() => saveGuidePreference("completed"));
  } finally { globalThis.window = previous; }
});

test("orientation browser coverage runs in both CI engines", () => {
  assertBrowserSuiteInCI("portal-orientation.browser.mjs");
});
