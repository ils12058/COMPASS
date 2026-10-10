import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { mock, test } from "node:test";
import { fileURLToPath } from "node:url";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  ACTION_STATUS_DURATION_MS,
  ActionStatus,
  createDismissTimer,
  nextActionStatus,
} from "../src/components/ui/action-status.tsx";

const render = (status) => renderToStaticMarkup(createElement(ActionStatus, { status, onDismiss() {} }));

test("the status region is always present, so a confirmation is announced when it appears", () => {
  const empty = render(null);
  assert.match(empty, /<p role="status"[^>]*><\/p>/);
  assert.doesNotMatch(empty, /Dismiss message/);

  const shown = render({ id: 1, text: "Weekly schedule saved." });
  assert.match(shown, /<p role="status"[^>]*><span>Weekly schedule saved\.<\/span><\/p>/);
  assert.match(shown, /<button type="button" aria-label="Dismiss message"/);
});

test("a confirmation never takes focus", () => {
  const html = render({ id: 1, text: "Profile changes saved." });
  assert.doesNotMatch(html, /autofocus|tabindex="-?\d"/i);
  const source = readFileSync(new URL("../src/components/ui/action-status.tsx", import.meta.url), "utf8");
  // Focus moves only back to where it came from, after the reader dismisses the message.
  assert.equal((source.match(/\.focus\(\)/g) ?? []).length, 1);
  assert.match(source, /origin\?\.isConnected\) origin\.focus\(\)/);
});

test("one message per surface: a newer confirmation replaces the last instead of stacking", () => {
  const first = nextActionStatus(null, "Unavailability added.");
  const second = nextActionStatus(first, "Weekly schedule saved.");
  assert.deepEqual(first, { id: 1, text: "Unavailability added." });
  assert.deepEqual(second, { id: 2, text: "Weekly schedule saved." });
  // The same text again is a new message, so it is announced again.
  assert.notEqual(nextActionStatus(second, "Weekly schedule saved.").id, second.id);
});

test("it leaves after a readable interval, and pausing gives the reader the full time again", () => {
  assert.ok(ACTION_STATUS_DURATION_MS >= 4000 && ACTION_STATUS_DURATION_MS <= 6000);
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    let dismissed = 0;
    const timer = createDismissTimer(() => {
      dismissed += 1;
    });
    timer.start();
    mock.timers.tick(ACTION_STATUS_DURATION_MS - 1);
    assert.equal(dismissed, 0);
    // The pointer or focus arrives: the clock stops.
    timer.clear();
    mock.timers.tick(ACTION_STATUS_DURATION_MS * 3);
    assert.equal(dismissed, 0);
    // It leaves: the reader gets the whole interval again, then it goes once.
    timer.start();
    mock.timers.tick(ACTION_STATUS_DURATION_MS - 1);
    assert.equal(dismissed, 0);
    mock.timers.tick(1);
    assert.equal(dismissed, 1);
    assert.equal(timer.running, false);
    mock.timers.tick(ACTION_STATUS_DURATION_MS * 2);
    assert.equal(dismissed, 1);
  } finally {
    mock.timers.reset();
  }
});

test("its entrance respects reduced motion and it clears the floating list tools", () => {
  const css = readFileSync(new URL("../src/styles/globals.css", import.meta.url), "utf8");
  assert.match(css, /@keyframes action-status-in/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation-duration: 0\.01ms !important/);
  assert.match(css, /html\[data-a11y-motion="reduce"\][\s\S]*animation-duration: 0\.01ms !important/);
  assert.match(css, /:root:has\(\[data-floating-list-tools\]\) \{\s*--action-status-offset: var\(--list-tools-clearance\);/);
  // Below dialogs (z-50) and above the floating list tools (z-30).
  assert.match(render(null), /fixed[^"]*z-40/);
});

const featuresRoot = fileURLToPath(new URL("../src/features/", import.meta.url));
function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? sources(full) : full.endsWith(".tsx") ? [full] : [];
  });
}

test("transient status confirms routine success only; failures stay in context", () => {
  const messages = [];
  for (const file of sources(featuresRoot)) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/\.show\("([^"]+)"\)/g)) messages.push(match[1]);
    for (const match of source.matchAll(/onSaved\("([^"]+)"\)/g)) messages.push(match[1]);
  }
  assert.ok(messages.length >= 6, "routine saves announce through ActionStatus");
  for (const message of messages) {
    assert.doesNotMatch(message, /could not|failed|error|unable|try again|unconfirmed/i, message);
  }
});
