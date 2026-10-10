import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CanonicalPagination } from "../src/features/portal/components/canonical-pagination.tsx";

function render(props) {
  return renderToStaticMarkup(
    createElement(CanonicalPagination, { label: "Accounts pagination", onPageChange() {}, ...props }),
  );
}

function isDisabled(html, name) {
  const button = html.match(new RegExp(`<button\\b([^>]*)>${name}</button>`));
  assert.ok(button, `${name} is rendered`);
  return /\bdisabled=""/.test(button[1]);
}

// The component is a plain function, so calling it reaches the Previous and Next handlers.
function controls(props) {
  const nav = CanonicalPagination({ label: "Accounts pagination", ...props });
  const buttons = [nav.props.children].flat().filter((child) => child?.props?.onClick);
  return Object.fromEntries(buttons.map((button) => [button.props.children, button.props]));
}

test("a single page of results renders no pager", () => {
  assert.equal(render({ page: 1, hasNext: false }), "");
});

test("the first page can only move forward", () => {
  const html = render({ page: 1, hasNext: true });

  assert.match(html, /<nav aria-label="Accounts pagination"/);
  assert.match(html, />Page 1</);
  assert.equal(isDisabled(html, "Previous"), true);
  assert.equal(isDisabled(html, "Next"), false);
});

test("an empty later page keeps a way back", () => {
  const html = render({ page: 3, hasNext: false });

  assert.equal(isDisabled(html, "Previous"), false);
  assert.equal(isDisabled(html, "Next"), true);
});

test("Previous and Next ask for the adjacent pages", () => {
  const requested = [];
  const { Previous, Next } = controls({ page: 4, hasNext: true, onPageChange: (page) => requested.push(page) });

  Previous.onClick();
  Next.onClick();

  assert.deepEqual(requested, [3, 5]);
});

test("disabled holds both directions while a page is loading", () => {
  const html = render({ page: 2, hasNext: true, disabled: true });

  assert.equal(isDisabled(html, "Previous"), true);
  assert.equal(isDisabled(html, "Next"), true);
});

test("the page position is announced politely when it changes", () => {
  assert.match(render({ page: 2, hasNext: true }), /<span aria-live="polite"[^>]*>Page 2<\/span>/);
});
