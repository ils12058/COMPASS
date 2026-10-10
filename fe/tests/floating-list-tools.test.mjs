import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { FilterField } from "../src/components/ui/filter-toolbar.tsx";
import {
  FloatingListTools,
  ListSearchField,
  ListToolField,
} from "../src/components/ui/floating-list-tools.tsx";

function statusFilter() {
  return createElement(
    FilterField,
    { label: "Status", htmlFor: "status-filter" },
    createElement("select", { id: "status-filter", name: "status" }, createElement("option", { value: "" }, "All")),
  );
}

function searchField() {
  return createElement(ListSearchField, { id: "records-search", name: "search", label: "Search records" });
}

function renderInForm(props, children) {
  return renderToStaticMarkup(
    createElement(
      "form",
      { role: "search", "aria-label": "Records" },
      createElement(FloatingListTools, props, children),
    ),
  );
}

test("filters stay inside the list's form in a dialog the Filters button controls", () => {
  const html = renderInForm({ submits: true, filterCount: 2, filters: statusFilter() }, searchField());

  // The dialog and its fields are rendered inside the form, so folded filters still submit.
  assert.match(html, /^<form[^>]*>.*<dialog[^>]*>.*name="status".*<\/dialog>.*<\/form>$/s);
  assert.match(html, /data-floating-list-tools=""/);

  const trigger = html.match(/<button[^>]*aria-haspopup="dialog"[^>]*>(.*?)<\/button>/s);
  assert.ok(trigger, "the bar has a Filters button");
  assert.match(trigger[0], /aria-expanded="false"/);
  const controls = trigger[0].match(/aria-controls="([^"]+)"/)[1];
  assert.match(html, new RegExp(`<dialog[^>]*id="${controls.replace(/[:]/g, "\\:")}"`));
  assert.match(trigger[1], /Filters/);
  assert.match(trigger[1], /<span class="sr-only">, 2 in use<\/span>/);

  // The dialog is named by its heading and can be closed by a named button.
  const labelledBy = html.match(/<dialog[^>]*aria-labelledby="([^"]+)"/)[1];
  assert.match(html, new RegExp(`<h2 id="${labelledBy.replace(/[:]/g, "\\:")}"[^>]*>Filters</h2>`));
  assert.match(html, /aria-label="Close filters"/);
});

test("explicit filters submit from the bar and from the panel", () => {
  const html = renderInForm(
    { submits: true, filters: statusFilter(), clear: createElement("a", { href: "/records" }, "Clear filters") },
    searchField(),
  );

  const submits = [...html.matchAll(/<button type="submit"[^>]*>([^<]*)<\/button>/g)].map((match) => match[1]);
  assert.deepEqual(submits, ["Search", "Apply filters"]);
  // With a panel, Clear filters lives in the panel rather than in the bar.
  assert.match(html, /<dialog[^>]*>.*Clear filters.*<\/dialog>/s);
});

test("filters that apply on change close with Show results and need no submit", () => {
  const html = renderInForm({ filters: statusFilter() }, searchField());

  assert.doesNotMatch(html, /type="submit"/);
  assert.match(html, /<button type="button"[^>]*>Show results<\/button>/);
});

test("the search field has a label tied to it and searches", () => {
  const html = renderToStaticMarkup(searchField());

  assert.match(html, /<label[^>]*for="records-search"[^>]*>Search records<\/label>/);
  assert.match(html, /<input[^>]*type="search"[^>]*id="records-search"|<input[^>]*id="records-search"[^>]*type="search"/);
});

test("a lone choice can stand in the bar with a visible label", () => {
  const html = renderToStaticMarkup(
    createElement(
      FloatingListTools,
      { label: "Delivery filters", compact: true },
      createElement(
        ListToolField,
        { label: "Status", htmlFor: "delivery-status" },
        createElement("select", { id: "delivery-status" }, createElement("option", { value: "ALL" }, "All statuses")),
      ),
    ),
  );

  assert.match(html, /role="group" aria-label="Delivery filters"/);
  assert.match(html, /<label[^>]*for="delivery-status"[^>]*>Status<\/label>/);
  assert.doesNotMatch(html, /<dialog/);
  assert.doesNotMatch(html, /aria-haspopup/);
});
