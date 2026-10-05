import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { FormRevisionFilter, revisionFilterLabel } from "../src/features/institutional-forms/form-revision-filter.tsx";

const old = { id: "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", official_code: "CNSC-OP-GTA-01F9", official_revision: "0" };
const current = { ...old, id: "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb" };

function render(props) {
  return renderToStaticMarkup(createElement(FormRevisionFilter, { id: "revision", selectedId: old.id, ...props }));
}

test("a selected historical UUID is still submitted when its metadata is unavailable", () => {
  const html = render({ defaultValue: old.id });
  assert.match(html, /name="form_revision_id"/);
  assert.match(html, new RegExp(`value="${old.id}" selected="">Selected revision`));
  assert.match(html, /<label[^>]*for="revision"/);
  assert.doesNotMatch(html, /<select[^>]*\sdisabled(?:[= >])/);
  assert.doesNotMatch(html, new RegExp(`>${old.id}<`));
});

test("metadata arrival resolves the selected identity without discarding its UUID", () => {
  const html = render({ options: [old], defaultValue: old.id });
  assert.match(html, new RegExp(`value="${old.id}" selected="">CNSC-OP-GTA-01F9 · Rev. 0`));
  assert.doesNotMatch(html, /Selected revision/);
});

test("same-looking revision metadata keeps distinct stored UUID choices", () => {
  const html = render({ options: [old, current], value: current.id });
  assert.equal((html.match(/CNSC-OP-GTA-01F9 · Rev. 0/g) ?? []).length, 2);
  assert.match(html, new RegExp(`value="${current.id}" selected=""`));
  assert.match(html, new RegExp(`value="${old.id}"`));
});

test("null identity values produce honest labels without inventing official metadata", () => {
  assert.equal(revisionFilterLabel({ ...old, official_code: null, official_revision: null }), "Form Revision");
  assert.equal(revisionFilterLabel({ ...old, official_code: " ", official_revision: "2" }), "Rev. 2");
  assert.equal(revisionFilterLabel({ ...old, official_revision: null }), old.official_code);
  assert.equal(revisionFilterLabel({ ...old, official_code: " CODE ", official_revision: " 0 " }), "CODE · Rev. 0");
});

test("All revisions uses an empty value and never invents a no-revision choice", () => {
  const html = render({ selectedId: "", value: "", options: [old] });
  assert.match(html, /value="" selected="">All revisions/);
  assert.doesNotMatch(html, /Selected revision|No revision|Not assigned|Pending revision/);
});
