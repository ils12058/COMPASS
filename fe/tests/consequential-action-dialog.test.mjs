import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
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

// Completion: the same dialog can carry the confirmed outcome instead of closing on success.
const removal = {
  title: "Remove this unavailability?",
  confirmLabel: "Remove unavailability",
  pendingLabel: "Removing…",
  children: createElement("p", null, "Oct 12 will no longer subtract time from Availability."),
};
const removed = {
  title: "Unavailability removed",
  children: createElement("p", null, "Oct 12 no longer subtracts time from Availability."),
};

test("confirm → pending → failure keeps the dialog open with retry available", () => {
  const pending = confirmation({ ...removal, pending: true });
  assert.equal(button(pending.html, "Removing…").disabled, true);

  const failed = confirmation({ ...removal, error: "Your unavailability could not be removed." });
  assert.match(failed.html, /role="alert"[^>]*>Your unavailability could not be removed\./);
  assert.equal(button(failed.html, "Remove unavailability").disabled, false);
  assert.doesNotMatch(failed.html, /Unavailability removed/);
});

test("confirm → pending → success shows the outcome in place, with no way to act twice", () => {
  const { html, requestOpenChange, changes } = confirmation({ ...removal, completed: removed });

  assert.match(html, /role="alertdialog"/);
  assert.match(html, />Unavailability removed</);
  assert.match(html, /no longer subtracts time from Availability\./);
  assert.doesNotMatch(html, /Remove unavailability|Remove this unavailability\?|>Cancel</);
  assert.equal(button(html, "Done").disabled, false);
  // Done is described by the outcome, so moving focus to it also reads what happened.
  const describedBy = html.match(/<button[^>]*aria-describedby="([^"]+)"[^>]*>Done<\/button>/)[1];
  assert.match(html, new RegExp(`id="${describedBy}"[^>]*><p>Oct 12 no longer subtracts`));
  // Done closes the dialog like any other dismissal.
  requestOpenChange(false);
  assert.deepEqual(changes, [false]);
});

test("the completed state places focus on Done and the opener can redirect focus on close", () => {
  const source = readFileSync(new URL("../src/components/ui/consequential-action-dialog.tsx", import.meta.url), "utf8");
  assert.match(source, /function CompletionDone[\s\S]*useEffect\(\(\) => \{\s*done\.current\?\.focus\(\);/);
  const { content } = confirmation({ ...removal, completed: removed, onCloseAutoFocus() {} });
  assert.equal(typeof content.onCloseAutoFocus, "function");
});
