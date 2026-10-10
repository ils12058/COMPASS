import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement, isValidElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Dialog, DialogContent, DialogTitle } from "../src/components/ui/dialog.tsx";
import { PortalShell } from "../src/features/portal/components/portal-shell.tsx";

// Rendering inside a component lets hooks run while capturing the element a component returns.
function capture(render) {
  let element;
  function Probe() {
    element = render();
    return null;
  }
  renderToStaticMarkup(createElement(Probe));
  return element;
}

function findElement(node, matches) {
  if (!isValidElement(node)) return null;
  if (matches(node)) return node;
  for (const child of [node.props.children].flat()) {
    const found = findElement(child, matches);
    if (found) return found;
  }
  return null;
}

test("the mobile portal navigation names its close button Close navigation", () => {
  const shell = capture(() => PortalShell({ children: null }));
  const drawer = findElement(shell, (element) => element.type === DialogContent);
  assert.ok(drawer, "the shell renders the navigation drawer");

  // The drawer's own navigation needs the portal session, so only its title is rendered here.
  const portal = capture(() =>
    DialogContent.render(
      { ...drawer.props, children: createElement(DialogTitle, { className: "sr-only" }, "Portal navigation") },
      null,
    ),
  );
  const content = [portal.props.children].flat().at(-1);
  const html = renderToStaticMarkup(createElement(Dialog, { open: true }, content));
  const close = html.match(/<button\b[^>]*aria-label="([^"]*)"[^>]*>/);

  assert.ok(close, "the drawer has a close button");
  assert.equal(close[1], "Close navigation");
  const classes = close[0].match(/class="([^"]*)"/)[1].split(" ");
  assert.ok(classes.includes("min-h-11") && classes.includes("min-w-11"));
});
