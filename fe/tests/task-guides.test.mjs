import assert from "node:assert/strict";
import { test } from "node:test";
import { taskGuides, guideOnPage, taskGuideSteps } from "../src/features/portal/orientation/task-guide-definitions.ts";
import { taskGuideAccess } from "../src/features/portal/orientation/task-guide-access.ts";
import { readTaskPreference, saveTaskPreference, parseGuidePreference } from "../src/features/portal/orientation/guide-preference.ts";
import { user } from "./support/ui-hierarchy-fixtures.mjs";
import { homeCapabilities } from "./support/ux15-home-fixtures.mjs";
import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";

test("exactly eleven implemented guides with safe entry pages, short named steps, and fallbacks", () => {
  assert.equal(taskGuides.length, 11);
  assert.equal(new Set(taskGuides.map(guide => guide.id)).size, 11);
  for (const guide of taskGuides) {
    assert.ok(guideOnPage(guide, guide.entry));
    assert.match(guide.entry, /^\/portal\/[a-z/-]+$/);
    assert.ok(!guide.entry.includes("?"));
    assert.ok(guide.steps.length >= 3 && guide.steps.length <= 5);
    assert.equal(guide.version, 1);
    for (const step of guide.steps) {
      assert.ok(step.title && step.description && step.fallback && step.targets.length);
      assert.doesNotMatch(step.description + step.fallback, /anonymous|counseling is complete|always cancel/i);
    }
    assert.equal(guideOnPage(guide, "/portal/work"), false);
    assert.equal(guideOnPage(guide, "/portal/appointments/manage"), false);
    assert.equal(guideOnPage(guide, "/portal/feedback/csm/responses"), false);
  }
});

test("discovery follows owning access helpers, including lifecycle and Faculty dependencies", () => {
  const current = { ...user("STUDENT"), capabilities: [...homeCapabilities, "feedback.submit_csm"], exit_interview_workspace_available: true };
  const access = taskGuideAccess(current);
  assert.equal(Object.values(access).filter(Boolean).length, 8);
  assert.equal(access["graduate-tracer"], false);
  assert.equal(taskGuideAccess({ ...current, student_lifecycle_status: "GRADUATED" })["graduate-tracer"], true);
  assert.equal(taskGuideAccess({ ...current, exit_interview_workspace_available: false })["exit-interview"], false);
  const faculty = { ...current, role: "FACULTY", capabilities: ["referrals.submit_self"] };
  assert.equal(taskGuideAccess(faculty)["faculty-submit"], false);
  assert.equal(taskGuideAccess({ ...faculty, capabilities: ["referrals.view_submitted_self"] })["faculty-submit"], false);
  assert.equal(taskGuideAccess({ ...faculty, capabilities: ["referrals.view_submitted_self", "referrals.submit_self"] })["faculty-submit"], true);
  const officer = taskGuideAccess({ ...current, role: "INSTITUTIONAL_OFFICER" });
  assert.equal(Object.values(officer).some(Boolean), false);
});

test("every guide resolves visible source-owned targets and finishable missing-target explanations", () => {
  const previous = globalThis.getComputedStyle;
  globalThis.getComputedStyle = element => ({ visibility: element.hidden ? "hidden" : "visible" });
  try {
    for (const guide of taskGuides) {
      const anchor = { dataset: { guideLaunch: guide.id }, getClientRects: () => [1] };
      const hidden = { hidden: true, getClientRects: () => [1] };
      const shown = { dataset: {}, getClientRects: () => [1], querySelector: () => null };
      const root = { querySelectorAll: selector => selector === "[data-guide-launch]" ? [anchor] : [hidden, shown] };
      const actual = taskGuideSteps(root, guide);
      assert.equal(actual.length, guide.steps.length);
      actual.forEach((step, i) => { assert.equal(step.target, shown); assert.equal(step.description, guide.steps[i].description); });
      root.querySelectorAll = selector => selector === "[data-guide-launch]" ? [anchor] : [];
      const fallback = taskGuideSteps(root, guide);
      fallback.forEach((step, i) => { assert.equal(step.target, anchor); assert.equal(step.highlight, false); assert.equal(step.description, guide.steps[i].fallback); });
      root.querySelectorAll = () => [];
      assert.deepEqual(taskGuideSteps(root, guide), []);
    }
  } finally { globalThis.getComputedStyle = previous; }
});

test("guide completion is independent, versioned, and contains no record or account data", () => {
  const previous = globalThis.window;
  const entries = new Map([["compass.portal-orientation", '{"version":1,"status":"completed"}']]);
  globalThis.window = { localStorage: { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, value) } };
  try {
    for (const guide of taskGuides) assert.equal(readTaskPreference(guide.id, guide.version), "new");
    saveTaskPreference(taskGuides[0].id, 1, "completed");
    assert.equal(readTaskPreference(taskGuides[0].id, 1), "completed");
    assert.equal(readTaskPreference(taskGuides[1].id, 1), "new");
    assert.equal(readTaskPreference(taskGuides[0].id, 2), "new");
    assert.deepEqual([...entries.values()].map(JSON.parse), [{ version: 1, status: "completed" }, { version: 1, status: "completed" }]);
    for (const raw of ["{", "[]", "null", '{"version":0,"status":"completed"}', '{"version":1,"status":"unknown"}']) assert.equal(parseGuidePreference(raw), "new");
    globalThis.window = { get localStorage() { throw new Error("Blocked"); } };
    for (const guide of taskGuides) { assert.equal(readTaskPreference(guide.id, 1), "new"); assert.doesNotThrow(() => saveTaskPreference(guide.id, 1, "completed")); }
  } finally { globalThis.window = previous; }
});

test("task guides run in both CI browser engines", () => assertBrowserSuiteInCI("task-guides.browser.mjs"));
