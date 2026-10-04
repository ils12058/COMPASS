import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { Plus, Upload } from "lucide-react";
import { createElement, createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { PageAction, PageActionGroup, PageActionLink } from "../src/components/ui/page-action.tsx";

const render = (element) => renderToStaticMarkup(withNextRouter(element));
const visibleText = (html) => html.replace(/<span class="sr-only">[^<]*<\/span>/g, "").replace(/<[^>]+>/g, "");
const accessibleText = (html) => html.replace(/<span aria-hidden="true"[\s\S]*?<\/svg><\/span>/g, "").replace(/<[^>]+>/g, "");

test("a navigating page command is a real link with its label visible and its name complete", () => {
  const html = render(createElement(PageActionLink, { href: "/portal/accounts/new", icon: Plus, label: "Create", labelDetail: "account" }));

  assert.match(html, /^<a [^>]*href="\/portal\/accounts\/new"/);
  assert.doesNotMatch(html, /<button|role="button"|tabindex="-1"/);
  assert.equal(visibleText(html), "Create");
  assert.equal(accessibleText(html), "Create account");
  // The square icon surface is decoration; the words carry the meaning.
  assert.match(html, /<span aria-hidden="true" data-page-action-surface="primary"/);
});

test("a page command that acts is a real button, keyboard-operable, and can be disabled", () => {
  const enabled = render(createElement(PageAction, { icon: Upload, label: "Import", labelDetail: "CSV", variant: "secondary" }));
  assert.match(enabled, /^<button type="button"/);
  assert.doesNotMatch(enabled, /disabled=""|tabindex="-1"/);
  assert.match(enabled, /data-page-action-surface="secondary"/);
  assert.equal(accessibleText(enabled), "Import CSV");

  const disabled = render(createElement(PageAction, { icon: Upload, label: "Import", disabled: true }));
  assert.match(disabled, /<button type="button" disabled=""/);

  const toggle = render(createElement(PageAction, { icon: Plus, label: "Record", "aria-expanded": false }));
  assert.match(toggle, /aria-expanded="false"/);
});

test("a page command forwards its ref so it can open a dialog as its trigger", () => {
  const ref = createRef();
  const element = PageAction.render({ icon: Plus, label: "Add", labelDetail: "Academic Year" }, ref);
  assert.equal(element.type, "button");
  assert.equal(element.ref ?? element.props.ref, ref);
});

test("primary and secondary commands differ only in their surface treatment", () => {
  const primary = render(createElement(PageAction, { icon: Plus, label: "Create" }));
  const secondary = render(createElement(PageAction, { icon: Plus, label: "Create", variant: "secondary" }));
  assert.match(primary, /bg-brand text-on-brand/);
  assert.match(secondary, /bg-surface-raised text-brand/);
  assert.equal(visibleText(primary), visibleText(secondary));
});

test("commands wrap as a group instead of scrolling sideways", () => {
  const html = render(createElement(PageActionGroup, null, createElement(PageAction, { icon: Plus, label: "Create" })));
  assert.match(html, /^<div class="flex flex-wrap/);
  assert.doesNotMatch(html, /overflow-x/);
});

const featuresRoot = fileURLToPath(new URL("../src/features/", import.meta.url));
function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? sources(full) : full.endsWith(".tsx") ? [full] : [];
  });
}

test("page commands stay few per page and out of activity pages and panel headers", () => {
  const users = sources(featuresRoot)
    .map((file) => ({ file, source: readFileSync(file, "utf8") }))
    .filter(({ source }) => /<PageAction(Link)?\b/.test(source));
  assert.ok(users.length >= 10, "major page commands use PageAction");
  for (const { file, source } of users) {
    const count = source.match(/<PageAction(Link)?\b/g).length;
    assert.ok(count <= 3, `${path.relative(featuresRoot, file)} has at most three page commands`);
    assert.doesNotMatch(source, /<PanelHeader[^>]*actions=\{\s*<PageAction/, `${file} keeps panel actions as ordinary buttons`);
  }
  for (const { file } of users) {
    assert.doesNotMatch(path.relative(featuresRoot, file), /activity/, "Activity pages are not redesigned here");
  }
});
