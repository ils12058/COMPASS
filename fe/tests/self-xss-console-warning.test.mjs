import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

import { DeveloperConsoleSafetyWarning } from "../src/features/security/self-xss-console-warning.tsx";

const source = readFileSync(new URL("../src/features/security/self-xss-console-warning.tsx", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});

// Run the actual component's mount effect in a fresh page realm, without adding a DOM dependency
// or changing React's own environment. Real server rendering is checked separately below.
function page(nodeEnv = "production", globals = {}) {
  const calls = [];
  const effects = [];
  const browserConsole = Object.freeze({
    log: (...args) => calls.push(args),
    warn() {},
    error() {},
  });
  const context = {
    exports: {}, console: browserConsole, process: { env: { NODE_ENV: nodeEnv } },
    require(name) {
      assert.equal(name, "react");
      return { useEffect: (effect, dependencies) => {
        assert.equal(dependencies.length, 0);
        effects.push(effect);
      } };
    },
    ...globals,
  };
  vm.runInNewContext(outputText, context);
  return {
    calls, context,
    render: (props) => context.exports.DeveloperConsoleSafetyWarning(props),
    flush: () => { for (const effect of effects.splice(0)) effect(); },
  };
}

test("the component renders no DOM and emits nothing during server rendering", () => {
  assert.equal(renderToStaticMarkup(createElement(DeveloperConsoleSafetyWarning)), "");
  const browser = page();
  assert.equal(browser.render(), null);
  assert.equal(browser.calls.length, 0, "output waits for the client mount effect");
});

test("production emits one styled safety message with the essential meaning and attribution", () => {
  const browser = page();
  browser.render();
  browser.flush();
  assert.equal(browser.calls.length, 1);
  const [text, headingStyle, bodyStyle] = browser.calls[0];
  assert.match(text, /^%cSTOP!%c/);
  assert.match(text, /Do not paste or run code here if someone told you/);
  assert.match(text, /can act with the permissions of your signed-in COMPASS session/);
  assert.match(text, /may expose data available to your account/);
  assert.match(text, /COMPASS will never ask you to paste code into Developer Tools/);
  assert.match(text, /University of Camarines Norte\nGuidance and Counseling Office\nCOMPASS/);
  assert.match(text, /Hello, developer/);
  assert.match(headingStyle, /font-size: 40px/);
  assert.match(headingStyle, /font-weight: 800/);
  assert.match(bodyStyle, /font-weight: normal/);
});

test("development, test, and an unset environment stay quiet", () => {
  for (const env of ["development", "test"]) {
    const browser = page(env);
    browser.render();
    browser.flush();
    assert.equal(browser.calls.length, 0, env);
  }
  const unset = page("production", { process: { env: {} } });
  unset.render();
  unset.flush();
  assert.equal(unset.calls.length, 0);
});

test("effect replays and component remounts stay quiet until a new page load", () => {
  const browser = page();
  for (let mount = 0; mount < 4; mount += 1) {
    browser.render();
    browser.flush();
  }
  assert.equal(browser.calls.length, 1);
  const nextPage = page();
  nextPage.render();
  nextPage.flush();
  assert.equal(nextPage.calls.length, 1, "a fresh page gets its own warning");
});

test("the message is static and never reads user, session, page, or storage data", () => {
  let reads = 0;
  const privateData = new Proxy({}, { get() { reads += 1; throw new Error("Private data must not be read"); } });
  const browser = page("production", {
    window: privateData, document: privateData, navigator: privateData,
    localStorage: privateData, sessionStorage: privateData,
  });
  browser.render({ user: "PRIVATE-USER", email: "private@example.test", session: "PRIVATE-SESSION", token: "PRIVATE-TOKEN" });
  browser.flush();
  assert.equal(reads, 0);
  assert.equal(browser.calls.length, 1);
  assert.ok(browser.calls[0].every((argument) => typeof argument === "string"));
  assert.doesNotMatch(browser.calls[0].join(" "), /PRIVATE-|private@example|https?:\/\//);
});

test("console methods retain their identity and ordinary diagnostics remain usable", () => {
  const browser = page();
  const original = { ...browser.context.console };
  browser.render();
  browser.flush();
  for (const method of ["log", "warn", "error"]) {
    assert.equal(browser.context.console[method], original[method]);
  }
  browser.context.console.log("ordinary diagnostic");
  assert.equal(browser.calls[1][0], "ordinary diagnostic");
});

test("keyboard, context-menu, and paste events remain unblocked", () => {
  const window = new EventTarget();
  const document = new EventTarget();
  const browser = page("production", { window, document });
  browser.render();
  browser.flush();
  for (const target of [window, document]) {
    for (const type of ["keydown", "contextmenu", "paste"]) {
      const event = Object.assign(new Event(type, { cancelable: true }), { key: "F12" });
      assert.equal(target.dispatchEvent(event), true);
      assert.equal(event.defaultPrevented, false);
    }
  }
});

test("unexpected console failures never escape or trigger repeated attempts", () => {
  let attempts = 0;
  const browser = page("production", { console: { log() { attempts += 1; throw new Error("Console unavailable"); } } });
  browser.render();
  assert.doesNotThrow(() => browser.flush());
  browser.render();
  assert.doesNotThrow(() => browser.flush());
  assert.equal(attempts, 1);
  const missingConsole = page("production", { console: undefined });
  missingConsole.render();
  assert.doesNotThrow(() => missingConsole.flush());
});

test("the shared root providers mount the warning once alongside the service worker", () => {
  const providers = readFileSync(new URL("../src/app/providers.tsx", import.meta.url), "utf8");
  assert.equal(providers.match(/<DeveloperConsoleSafetyWarning\b/g)?.length, 1);
  assert.match(providers, /<ServiceWorkerRegistration\s*\/>\s*<DeveloperConsoleSafetyWarning\s*\/>\s*\{children\}/);
});
