import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { PanelMessage } from "../src/components/ui/panel.tsx";

const render = (props, text = "No counseling encounters are assigned to you yet.") =>
  renderToStaticMarkup(createElement(PanelMessage, props, text));

test("a short empty message is compact, so a sparse collection stays shallow", () => {
  const html = render({});
  assert.match(html, /data-density="compact"/);
  assert.match(html, /py-3\.5/);
  assert.doesNotMatch(html, /py-6/);
});

test("a failure or a message with a next step keeps room for its action", () => {
  const retry = createElement("button", { type: "button" }, "Retry");
  for (const props of [{ tone: "danger", role: "alert" }, { action: retry }]) {
    const html = render(props, "Counseling encounters could not be loaded.");
    assert.match(html, /data-density="regular"/);
    assert.match(html, /py-6/);
  }
  // The action keeps its full target size.
  assert.match(render({ tone: "danger", action: retry }), /<div class="mt-3 flex flex-wrap gap-3"><button/);
});

test("density can be set deliberately", () => {
  assert.match(render({ density: "regular" }), /data-density="regular"/);
  assert.match(render({ tone: "danger", density: "compact" }), /data-density="compact"/);
});
