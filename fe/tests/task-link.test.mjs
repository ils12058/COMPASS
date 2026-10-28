import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { withNextRouter } from "./support/next-router.mjs";
import { TaskLink } from "../src/components/ui/task-link.tsx";

test("task navigation has one link, a named action and its distinguishing context", () => {
  const html = renderToStaticMarkup(withNextRouter(createElement(TaskLink, {
    href: "/portal/follow-ups/example", actionLabel: "Open follow-up",
    title: "Review Guidance follow-up", subject: "Synthetic Student",
    detail: "Due today", priority: "Time sensitive",
  })));
  assert.equal((html.match(/<a /g) ?? []).length, 1);
  assert.doesNotMatch(html, /<button|role="button"/);
  assert.match(html, /aria-label="Open follow-up"/);
  const context = html.match(/aria-describedby="([^"]+)"/)?.[1];
  assert.ok(context && html.includes(`id="${context}"`));
  for (const text of ["Review Guidance follow-up", "Synthetic Student", "Due today", "Time sensitive"]) assert.ok(html.includes(text));
});
