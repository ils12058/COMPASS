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

// The text of a JSX prop such as `actions={…}`, read to its matching brace.
function propValues(source, name) {
  const values = [];
  for (const match of source.matchAll(new RegExp(`\\s${name}=\\{`, "g"))) {
    let depth = 0;
    for (let i = match.index + match[0].length - 1; i < source.length; i += 1) {
      if (source[i] === "{") depth += 1;
      else if (source[i] === "}" && --depth === 0) {
        values.push(source.slice(match.index, i + 1));
        break;
      }
    }
  }
  return values;
}

// Each page header's opening tag — PageHeader or a feature wrapper such as CounselingPageHeading —
// with its props, read to the closing `>` outside any braces.
function pageHeaders(source) {
  const headers = [];
  for (const match of source.matchAll(/<(PageHeader|[A-Z]\w*(?:PageHeading|Heading|PageHeader))\b/g)) {
    let depth = 0;
    for (let i = match.index; i < source.length; i += 1) {
      if (source[i] === "{") depth += 1;
      else if (source[i] === "}") depth -= 1;
      else if (source[i] === ">" && depth === 0) {
        headers.push(source.slice(match.index, i + 1));
        break;
      }
    }
  }
  return headers;
}

test("Back stays a text link above the title, never a button among the page's commands", () => {
  let headers = 0;
  for (const file of sources(featuresRoot)) {
    const source = readFileSync(file, "utf8");
    const where = path.relative(featuresRoot, file);
    for (const header of pageHeaders(source)) {
      headers += 1;
      for (const value of [...propValues(header, "action"), ...propValues(header, "actions")]) {
        assert.doesNotMatch(value, />\s*(Back to|Return to)\b|<RoutineBackLink/, `${where} puts Back in the header's back slot`);
      }
      for (const value of propValues(header, "back")) {
        assert.doesNotMatch(value, /buttonVariants|secondaryLinkClass|rounded-md border/, `${where} styles Back as a text link`);
      }
    }
  }
  assert.ok(headers > 50, "the scan reads the portal's page headers");
});

test("Notifications and Retention use page commands for their header commands", () => {
  const read = (file) => readFileSync(new URL(`../src/features/${file}`, import.meta.url), "utf8");
  const notifications = read("notifications/notification-center/notification-center.tsx");
  assert.match(notifications, /actions=\{hasUnread \? \(\s*<PageAction\s+icon=\{CheckCheck\}/);
  assert.match(notifications, /label=\{markingAll \? "Marking as read…" : "Mark all read"\}/);
  assert.match(notifications, /disabled=\{markingAll\}/);

  const retention = read("privacy-governance/retention/retention-page.tsx");
  assert.match(retention, /action=\{\s*<PageActionLink\s+href="\/portal\/privacy\/retention\/rules"/);
  assert.doesNotMatch(retention, /secondaryLinkClass/);
});
