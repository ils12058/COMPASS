import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentConsentPanel } from "../src/features/ecounseling/student-consent-panel.tsx";
import { CounselorMediaStrip, GovernedCaptureControls, useCounselorMedia } from "../src/features/ecounseling/counselor-media.tsx";
import { MediaArtifactDownload, artifactOutcome } from "../src/features/ecounseling/media-artifact-download.tsx";
import { sessionFileRows } from "../src/features/ecounseling/session-files.tsx";
import { getECounselingAccess } from "../src/features/ecounseling/ecounseling-access.ts";
import { readFileSync } from "node:fs";
import { ecounselingHelpSections } from "../src/features/ecounseling/session-help.tsx";
import { getECounselingListMyConsentsQueryKey, getECounselingListAssignedConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { appointmentId, workspace, consents, user } from "./support/ui-hierarchy-fixtures.mjs";

// EC-RC-1/2: E-Counseling is recording-only. One recording permission, one Record control, one
// kind of session file, and no transcription wording anywhere.

function render(element, key, rows) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (key) client.setQueryData(key, { data: { items: rows }, status: 200, headers: {} });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, element));
  client.clear();
  return html;
}

test("a Student has one compact recording decision, longer meaning under Details, and no automatic capture", () => {
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media: workspace().media }), getECounselingListMyConsentsQueryKey(appointmentId), consents("PENDING"));
  assert.equal((html.match(/aria-label="Allow /g) ?? []).length, 1);
  assert.match(html, /aria-label="Allow audio\/video recording"/);
  assert.match(html, /Recording is optional and creates a saved audio\/video file\./);
  assert.equal((html.match(/<details/g) ?? []).length, 1);
  assert.match(html, /<details[^>]*>(?:(?!<\/details>).)*Allowing doesn’t start it/);
  assert.doesNotMatch(html, /transcri|caption|Media policy|v2|V2/i);
});

function CounselorMediaProbe(props) {
  const media = useCounselorMedia(props);
  return h("div", null, h(GovernedCaptureControls, { media }), h(CounselorMediaStrip, { media }));
}

test("the Counselor has one recording permission and one Record control", () => {
  const html = render(h(CounselorMediaProbe, { appointmentId, workspace: workspace("ACTIVE"), access: { canManageMediaAssigned: true, canAccessMediaAssigned: true }, inCall: true, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), consents("APPROVED"));
  assert.match(html, /aria-label="Stop recording"/);
  assert.match(html, /Recording permission · Approved/);
  assert.doesNotMatch(html, /transcri|Transcript storage|Media permission/i);
});

test("a recording permission that was never requested offers exactly one request", () => {
  const html = render(h(CounselorMediaProbe, { appointmentId, workspace: workspace(), access: { canManageMediaAssigned: true }, inCall: false, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), []);
  assert.match(html, /Recording permission · Not requested/);
  assert.equal((html.match(/aria-label="Request /g) ?? []).length, 1);
  assert.match(html, /aria-label="Request recording permission"/);
});

test("an old approved consent list cannot authorize Start against a withdrawn workspace projection", () => {
  const data = workspace();
  data.media.recording.consent_status = "WITHDRAWN";
  const html = render(h(CounselorMediaProbe, { appointmentId, workspace: data, access: { canManageMediaAssigned: true }, inCall: true, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), consents("APPROVED"));
  assert.match(html, /<button[^>]*aria-label="Start recording"[^>]*disabled=""/);
  assert.match(html, /Recording permission · Withdrawn/);
  assert.doesNotMatch(html, /Recording permission · Approved/);
});

for (const state of ["PENDING", "PROCESSING", "FAILED", "DISPOSED"]) test(`artifact ${state} has a truthful outcome without a download action`, () => {
  const value = { artifact_status: state, artifact_available: false, artifact_disposed_at: null };
  assert.equal(render(h(MediaArtifactDownload, { appointmentId, kind: "RECORDING", state: value, canAccess: true })), "");
  assert.match(artifactOutcome("RECORDING", value).text, state === "DISPOSED" ? /Deleted under an approved retention rule/ : state === "FAILED" ? /isn't available/ : /Preparing file…/);
});

test("stored recordings require the dedicated capability and never embed a URL", () => {
  const props = { appointmentId, kind: "RECORDING", state: { artifact_status: "STORED", artifact_available: true, artifact_disposed_at: null } };
  const html = render(h(MediaArtifactDownload, { ...props, canAccess: true }));
  assert.match(html, /aria-label="Download recording"/);
  assert.doesNotMatch(html, /href=|https?:\/\/(?!www\.w3\.org\/)/);
  assert.equal(render(h(MediaArtifactDownload, { ...props, canAccess: false })), "");
  assert.equal(getECounselingAccess(user()).canAccessMediaAssigned, true);
  assert.equal(getECounselingAccess(user("STUDENT")).canAccessMediaAssigned, false);
  assert.equal(getECounselingAccess({ ...user(), capabilities: ["ecounseling.access_media_assigned"] }).canAccessMediaAssigned, false);
});

test("session files list only the recording, described by its outcome", () => {
  const ready = workspace();
  ready.media.recording = { ...ready.media.recording, capture_status: "READY", artifact_status: "STORED", artifact_available: true };
  assert.deepEqual(sessionFileRows(ready.media).map((row) => [row.kind, row.label, row.outcome.text]), [["RECORDING", "Recording", "Ready"]]);
  assert.deepEqual(sessionFileRows(workspace().media), [], "Nothing captured, nothing listed");
});

test("withdrawal copy keeps recordings without promising deletion or in-app disposition", () => {
  const help = ecounselingHelpSections.map((section) => section.content).join(" ");
  assert.match(help, /Withdrawing permission doesn’t delete what was already recorded/);
  assert.match(help, /subject to the University’s records and privacy requirements/);
  assert.match(help, /Downloaded copies can’t be recalled/);
  const panel = readFileSync(new URL("../src/features/ecounseling/student-consent-panel.tsx", import.meta.url), "utf8");
  assert.match(panel, /Withdrawing doesn’t delete files already created\. They remain subject to the University’s records and privacy requirements, and copies already downloaded can’t be recalled\./);
  for (const text of [help, panel]) {
    assert.doesNotMatch(text, /retention rules|holds|deleted right away|after \d+ days|approved disposal|immediately deleted/i);
  }
});

test("no E-Counseling source offers transcription", () => {
  for (const file of ["session-help.tsx", "student-consent-panel.tsx", "counselor-media.tsx", "session-files.tsx", "use-capture-stop.ts", "runtime/global-call-dock.tsx", "call/capture-indicators.tsx"]) {
    const source = readFileSync(new URL(`../src/features/ecounseling/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source.replace(/^\s*\/\/.*$/gm, ""), /transcri|TRANSCRIPT|WEBVTT|\.vtt\b/, file);
  }
});
