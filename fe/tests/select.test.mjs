import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement, createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Select } from "../src/components/ui/select.tsx";

const options = [
  ["", "Any"],
  ["a", "First"],
  ["b", "Second"],
];

function render(props) {
  return renderToStaticMarkup(
    createElement(
      Select,
      props,
      ...options.map(([value, label]) => createElement("option", { key: value, value }, label)),
    ),
  );
}

test("Select renders a native select and forwards its native props", () => {
  const html = render({
    id: "status",
    name: "status",
    required: true,
    disabled: true,
    defaultValue: "b",
    "aria-describedby": "status-hint",
  });

  assert.match(html, /^<select\b/);
  assert.match(html, /\bid="status"/);
  assert.match(html, /\bname="status"/);
  assert.match(html, /\brequired=""/);
  assert.match(html, /\bdisabled=""/);
  assert.match(html, /\baria-describedby="status-hint"/);
  assert.match(html, /<option value="b" selected="">Second<\/option>/);
});

test("Select exposes aria-invalid only when the control is invalid", () => {
  assert.match(render({ id: "category", "aria-invalid": true }), /\baria-invalid="true"/);
  assert.doesNotMatch(render({ id: "category" }), /aria-invalid/);
});

test("Select passes its ref to the native select element", () => {
  const ref = createRef();
  const element = Select.render({ id: "category" }, ref);

  assert.equal(element.type, "select");
  assert.equal(element.props.ref, ref);
});
