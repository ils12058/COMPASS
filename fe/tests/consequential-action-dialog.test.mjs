import assert from "node:assert/strict";
import { test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { AlertDialog, AlertDialogContent } from "../src/components/ui/alert-dialog.tsx";
import { ConsequentialActionDialog } from "../src/components/ui/consequential-action-dialog.tsx";

const baseProps = {
  open: true,
  title: "Disable Ana Cruz's account?",
  confirmLabel: "Disable account",
  pendingLabel: "Disabling…",
  pending: false,
  error: null,
  variant: "danger",
  children: createElement("p", null, "They will no longer be able to sign in."),
};

// The confirmation portals into the page, which needs a browser, so the content it would portal
// is rendered on its own inside the same AlertDialog root.
function confirmation(props = {}) {
  const changes = [];
  const root = ConsequentialActionDialog({
    ...baseProps,
    onOpenChange: (open) => changes.push(open),
    onConfirm() {},
    ...props,
  });
  const contentProps = root.props.children.props;
  let portal;
  function Probe() {
    portal = AlertDialogContent.render(contentProps, null);
    return null;
  }
  renderToStaticMarkup(createElement(Probe));
  const content = [portal.props.children].flat().at(-1);
  return {
    html: renderToStaticMarkup(createElement(AlertDialog, { open: true }, content)),
    content: contentProps,
    requestOpenChange: root.props.onOpenChange,
    changes,
  };
}

function button(html, label) {
  const match = html.match(new RegExp(`<button\\b([^>]*)>${label}</button>`));
  assert.ok(match, `${label} is rendered`);
  return { disabled: /\bdisabled=""/.test(match[1]), classes: match[1].match(/class="([^"]*)"/)[1].split(" ") };
}

function escapeKey() {
  return {
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
}

test("an idle confirmation offers both Cancel and the named action", () => {
  const { html } = confirmation();

  assert.match(html, /role="alertdialog"/);
  assert.match(html, /Disable Ana Cruz&#x27;s account\?/);
  assert.equal(button(html, "Cancel").disabled, false);
  assert.equal(button(html, "Disable account").disabled, false);
  assert.match(html, /aria-busy="false"/);
});

test("confirmDisabled holds the action but still allows Cancel", () => {
  const { html } = confirmation({ confirmDisabled: true });

  assert.equal(button(html, "Cancel").disabled, false);
  assert.equal(button(html, "Disable account").disabled, true);
});

test("while pending, both buttons are disabled and the pending label replaces the action", () => {
  const { html } = confirmation({ pending: true });

  assert.equal(button(html, "Cancel").disabled, true);
  assert.equal(button(html, "Disabling…").disabled, true);
  assert.doesNotMatch(html, />Disable account</);
  assert.match(html, /aria-busy="true"/);
});

test("while pending, the dialog ignores requests to close and Escape", () => {
  const { content, requestOpenChange, changes } = confirmation({ pending: true });
  const escape = escapeKey();

  requestOpenChange(false);
  content.onEscapeKeyDown(escape);

  assert.deepEqual(changes, []);
  assert.equal(escape.defaultPrevented, true);
});

test("an idle confirmation closes on Cancel or Escape", () => {
  const { content, requestOpenChange, changes } = confirmation();
  const escape = escapeKey();

  requestOpenChange(false);
  content.onEscapeKeyDown(escape);

  assert.deepEqual(changes, [false]);
  assert.equal(escape.defaultPrevented, false);
});

test("a failed request stays inline in the dialog with the action available again", () => {
  const { html } = confirmation({ error: "The account could not be disabled." });

  assert.match(html, /<p role="alert"[^>]*>The account could not be disabled\.<\/p>/);
  assert.equal(button(html, "Disable account").disabled, false);
});

test("the danger variant reaches the action button", () => {
  const danger = button(confirmation().html, "Disable account").classes;
  const primary = button(
    confirmation({ variant: "primary", confirmLabel: "Enable account" }).html,
    "Enable account",
  ).classes;

  assert.ok(danger.includes("bg-danger"));
  assert.ok(!danger.includes("bg-brand"));
  assert.ok(primary.includes("bg-brand"));
});

test("a confirmation has no corner close button", () => {
  assert.doesNotMatch(confirmation().html, /aria-label="Close/);
});
