import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Dialog, DialogContent, DialogTitle } from "../src/components/ui/dialog.tsx";

// DialogContent portals into the page, which needs a browser. Rendering it inside a component
// lets its hooks run, and the content element it would portal can then be rendered on its own.
function dialogContent(props = {}) {
  let portal;
  function Probe() {
    portal = DialogContent.render(
      { children: createElement(DialogTitle, null, "Edit link"), ...props },
      null,
    );
    return null;
  }
  renderToStaticMarkup(createElement(Probe));
  const content = [portal.props.children].flat().at(-1);
  return {
    props: content.props,
    html: renderToStaticMarkup(createElement(Dialog, { open: true }, content)),
  };
}

function closeButton(html) {
  return html.match(/<button\b[^>]*aria-label="([^"]*)"[^>]*>/);
}

function dismissal() {
  return {
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
}

test("the close button is named Close dialog by default", () => {
  const button = closeButton(dialogContent().html);

  assert.ok(button, "a close button is rendered");
  assert.equal(button[1], "Close dialog");
  assert.match(button[0], /\btype="button"/);
});

test("a dialog can give its close button a contextual name", () => {
  assert.equal(closeButton(dialogContent({ closeLabel: "Close navigation" }).html)[1], "Close navigation");
});

test("the close button keeps the 44px interaction size", () => {
  const classes = closeButton(dialogContent().html)[0].match(/class="([^"]*)"/)[1].split(" ");

  assert.ok(classes.includes("min-h-11"));
  assert.ok(classes.includes("min-w-11"));
  assert.ok(classes.includes("focus-visible:ring-2"));
});

test("a dialog that cannot be dismissed shows no close button", () => {
  const { html } = dialogContent({ dismissible: false });

  assert.match(html, /role="dialog"/);
  assert.equal(closeButton(html), null);
});

test("Escape and outside clicks close a dismissible dialog", () => {
  const seen = [];
  const { props } = dialogContent({
    onEscapeKeyDown: () => seen.push("escape"),
    onInteractOutside: () => seen.push("outside"),
  });
  const escape = dismissal();
  const outside = dismissal();

  props.onEscapeKeyDown(escape);
  props.onInteractOutside(outside);

  assert.equal(escape.defaultPrevented, false);
  assert.equal(outside.defaultPrevented, false);
  assert.deepEqual(seen, ["escape", "outside"]);
});

test("Escape and outside clicks leave a non-dismissible dialog open", () => {
  const seen = [];
  const { props } = dialogContent({
    dismissible: false,
    onEscapeKeyDown: () => seen.push("escape"),
    onInteractOutside: () => seen.push("outside"),
  });
  const escape = dismissal();
  const outside = dismissal();

  props.onEscapeKeyDown(escape);
  props.onInteractOutside(outside);

  assert.equal(escape.defaultPrevented, true);
  assert.equal(outside.defaultPrevented, true);
  assert.deepEqual(seen, ["escape", "outside"], "the consumer's own handlers still run");
});

// Focus return reads the page's focused element, so these tests stand in a minimal document.
class FakeElement {
  isConnected = true;
  focusCount = 0;

  constructor(dialog = null) {
    this.dialog = dialog;
  }

  closest() {
    return this.dialog;
  }

  focus() {
    this.focusCount += 1;
    globalThis.document.activeElement = this;
  }
}

function openWithFocusOn(opener, props) {
  const body = {};
  globalThis.HTMLElement = FakeElement;
  globalThis.document = { body, activeElement: opener };
  const dialog = dialogContent(props).props;
  dialog.onOpenAutoFocus(dismissal());
  return {
    dialog,
    // Closing removes the focused dialog content, and the browser falls back to the body.
    loseFocusToBody() {
      globalThis.document.activeElement = body;
    },
  };
}

function closing(container) {
  return Object.assign(dismissal(), { target: container });
}

afterEach(() => {
  delete globalThis.document;
  delete globalThis.HTMLElement;
});

test("closing returns focus to the control that opened the dialog", () => {
  const opener = new FakeElement();
  const { dialog, loseFocusToBody } = openWithFocusOn(opener);

  loseFocusToBody();
  dialog.onCloseAutoFocus(dismissal());

  assert.equal(opener.focusCount, 1);
});

test("a dialog that places focus itself keeps that focus", () => {
  const opener = new FakeElement();
  const { dialog, loseFocusToBody } = openWithFocusOn(opener, {
    onCloseAutoFocus: (event) => event.preventDefault(),
  });

  loseFocusToBody();
  dialog.onCloseAutoFocus(dismissal());

  assert.equal(opener.focusCount, 0);
});

test("focus that already moved on, such as into the next dialog, is left there", () => {
  const opener = new FakeElement();
  const { dialog } = openWithFocusOn(opener);
  const nextDialogButton = new FakeElement();

  globalThis.document.activeElement = nextDialogButton;
  dialog.onCloseAutoFocus(dismissal());

  assert.equal(opener.focusCount, 0);
  assert.equal(globalThis.document.activeElement, nextDialogButton);
});

test("the review step of a two-step flow returns focus to the control that started the flow", () => {
  const opener = new FakeElement();
  const { dialog: selection, loseFocusToBody } = openWithFocusOn(opener);

  // The selection dialog closes as the review opens, before the review has anything to return to.
  loseFocusToBody();
  const review = dialogContent().props;
  review.onOpenAutoFocus(dismissal());
  const reviewContainer = {};
  globalThis.document.activeElement = new FakeElement(reviewContainer);
  selection.onCloseAutoFocus(closing({}));
  assert.equal(opener.focusCount, 0, "the review keeps focus while it is open");

  loseFocusToBody();
  review.onCloseAutoFocus(closing(reviewContainer));

  assert.equal(opener.focusCount, 1);
});

test("an opener that left the page is not focused", () => {
  const opener = new FakeElement();
  const { dialog, loseFocusToBody } = openWithFocusOn(opener);

  opener.isConnected = false;
  loseFocusToBody();
  dialog.onCloseAutoFocus(dismissal());

  assert.equal(opener.focusCount, 0);
});
