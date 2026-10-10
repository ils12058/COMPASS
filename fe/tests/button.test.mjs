import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Button, buttonVariants } from "../src/components/ui/button.tsx";

function classes(value) {
  return value.split(/\s+/).filter(Boolean);
}

test("Button is a real button that defaults to type=button", () => {
  assert.match(renderToStaticMarkup(createElement(Button, null, "Save")), /^<button\b[^>]*\btype="button"/);
  assert.match(
    renderToStaticMarkup(createElement(Button, { type: "submit" }, "Save changes")),
    /^<button\b[^>]*\btype="submit"/,
  );
});

test("the danger variant keeps its danger colour on hover", () => {
  const danger = classes(buttonVariants({ variant: "danger" }));
  const hover = danger.filter((name) => name.startsWith("hover:"));
  const fills = danger.filter((name) => /(^|:)(bg|border)-/.test(name));

  assert.ok(hover.length > 0);
  assert.ok(hover.every((name) => name.includes("danger")), hover.join(" "));
  assert.ok(fills.every((name) => !name.includes("brand")), fills.join(" "));
});

test("a link can take a button variant and replace one of its defaults", () => {
  const link = classes(buttonVariants({ variant: "secondary", className: "mt-6 min-h-11 w-full" }));

  assert.ok(link.includes("mt-6"));
  assert.ok(link.includes("min-h-11"));
  assert.ok(!link.includes("min-h-10"), "the merged className replaces the conflicting default");
});
