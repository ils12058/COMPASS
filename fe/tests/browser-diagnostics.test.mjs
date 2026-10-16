import assert from "node:assert/strict";
import test from "node:test";
import { diagnosticAssertion, diagnosticError, diagnosticURL, documentReadiness } from "./support/browser-diagnostics.mjs";

test("failure diagnostics omit credentials, queries, provider paths and assertion value dumps", () => {
  assert.equal(diagnosticURL("http://username:secret@localhost:3107/portal/messages?token=secret#private"), "http://localhost:3107/portal/messages");
  assert.equal(diagnosticURL("https://media.example/signed-secret-path?token=secret"), "https://media.example/[external]");
  const error = new Error("private payload secret");
  error.stack = "Error: private payload secret\n at http://localhost:3107/_next/static/chunk.js:12:3?token=secret";
  const summary = diagnosticError(error);
  assert.equal(summary.name, "Error");
  assert.deepEqual(summary.sources, ["http://localhost:3107/_next/static/chunk.js:12:3"]);
  assert.equal(summary.fingerprint, diagnosticError(error.stack).fingerprint);
  assert.doesNotMatch(JSON.stringify(summary), /private|secret|token/);
  assert.equal(diagnosticAssertion({ message: "Expected values to be equal:\n+ secret payload" }), "Expected values to be equal:");
});

test("a wedged page cannot block diagnostics and cleanup indefinitely", async () => {
  assert.equal(await documentReadiness({ evaluate: () => new Promise(() => {}) }, 5), "unavailable");
  assert.equal(await documentReadiness({ evaluate: async () => "complete" }), "complete");
  assert.equal(await documentReadiness({ evaluate: async () => { throw new Error("closed"); } }), "unavailable");
});
