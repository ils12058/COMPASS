import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement, isValidElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { Dialog, DialogContent } from "../src/components/ui/dialog.tsx";
import { StepUpDialog } from "../src/features/account/security/security-shared.tsx";
import { stepUpNotice, stepUpRequirement } from "../src/features/account/security/step-up.ts";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { isMutationAuthorityError } from "../src/features/freshness/query-freshness.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";

const refusal = (code, status = 403) =>
  new CompassApiError({ status, body: { error: { code, message: code } }, headers: {}, method: "POST", url: "/api/v1/x" });

test("the backend's step-up codes map to verify or set up, and nothing else opens step-up", () => {
  assert.equal(stepUpRequirement(refusal("recent_mfa_required")), "verify");
  assert.equal(stepUpRequirement(refusal("mfa_setup_required")), "setup");
  assert.equal(stepUpRequirement(refusal("permission_denied")), null);
  assert.equal(stepUpRequirement(new TypeError("offline")), null);
  assert.match(stepUpNotice("setup"), /Set one up in Security/);
  assert.doesNotMatch(stepUpNotice("setup"), /code/i);
});

test("a step-up refusal is about the request, so it does not recheck the session's access", () => {
  assert.equal(isMutationAuthorityError(refusal("recent_mfa_required")), false);
  assert.equal(isMutationAuthorityError(refusal("mfa_setup_required")), false);
  assert.equal(isMutationAuthorityError(refusal("csrf_failed")), false);
  assert.equal(isMutationAuthorityError(refusal("permission_denied")), true);
});

// Renders a closed-over dialog component's content without a browser (see dialog.test.mjs).
function dialogHtml(element) {
  const client = new QueryClient();
  let tree;
  function Expand() {
    tree = element.type(element.props);
    if (isValidElement(tree) && typeof tree.type === "function" && tree.type !== Dialog) {
      tree = tree.type(tree.props);
    }
    return null;
  }
  renderToStaticMarkup(createElement(QueryClientProvider, { client }, createElement(Expand)));
  const content = [tree.props.children].flat().find((child) => child?.type === DialogContent);
  let portal;
  function Probe() {
    portal = DialogContent.render(content.props, null);
    return null;
  }
  renderToStaticMarkup(createElement(Probe));
  const rendered = [portal.props.children].flat().at(-1);
  return renderToStaticMarkup(
    createElement(
      QueryClientProvider,
      { client },
      createElement(UnsavedChangesProvider, null, createElement(Dialog, { open: true }, rendered)),
    ),
  );
}

test("without an authenticator, step-up points to setup and never asks for a code", () => {
  const html = dialogHtml(createElement(StepUpDialog, { open: true, onOpenChange() {}, requirement: "setup" }));

  assert.match(html, /Set up an authenticator/);
  assert.match(html, /href="\/portal\/account\/security\/authenticator"/);
  assert.doesNotMatch(html, /Authenticator code/);
  assert.doesNotMatch(html, /<input/);
});

test("with an authenticator, step-up asks for the current code", () => {
  const html = dialogHtml(createElement(StepUpDialog, { open: true, onOpenChange() {} }));

  assert.match(html, /Enter the current code from your authenticator app\./);
  assert.match(html, /Authenticator code/);
});

// Only screens whose backend action keeps a step-up boundary handle step-up. Routine work
// (Appointments, Availability, Good Moral issuance, email retry) and Referral and Call Slip
// actions, whose backend never required it, must not open authenticator prompts.
const featuresRoot = fileURLToPath(new URL("../src/features/", import.meta.url));
function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? sourceFiles(full) : /\.tsx?$/.test(name) ? [full] : [];
  });
}

test("step-up handling stays on the features whose actions keep it", () => {
  const allowed = [
    "account/",
    "accounts/",
    // Sign-in sends an account whose role requires an authenticator to set one up.
    "auth/",
    "freshness/query-freshness.ts",
    "institution-configuration/",
    "organization/",
    "platform/platform-actions.tsx",
    "privacy-governance/privacy-governance-shared.tsx",
    "services/",
  ];
  const offenders = sourceFiles(featuresRoot)
    .map((file) => path.relative(featuresRoot, file))
    .filter((file) => /StepUpDialog|recent_mfa_required|mfa_setup_required|stepUpRequirement/.test(readFileSync(path.join(featuresRoot, file), "utf8")))
    .filter((file) => !allowed.some((prefix) => file.startsWith(prefix)));
  assert.deepEqual(offenders, []);
});
