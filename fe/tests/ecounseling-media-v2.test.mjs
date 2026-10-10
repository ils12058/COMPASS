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
import { dispositionConsequence, dispositionActionLabel } from "../src/features/privacy-governance/retention/retention-shared.tsx";
import { getECounselingListMyConsentsQueryKey, getECounselingListAssignedConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { appointmentId, workspace, consents, user } from "./support/ui-hierarchy-fixtures.mjs";

function render(element, key, rows) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  if (key) client.setQueryData(key, { data: { items: rows }, status: 200, headers: {} });
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, element));
  client.clear();
  return html;
}
const v2Rows = (decision) => ["SESSION_MEDIA_CAPTURE", "TRANSCRIPT_STORAGE"].map((scope, index) => ({ ...consents(decision)[0], id: `v2-${index}`, scope }));

test("V2 student has two compact decisions, longer meaning under Details, and no automatic capture", () => {
  const media = { ...workspace().media, media_policy_version: 2 };
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media }), getECounselingListMyConsentsQueryKey(appointmentId), v2Rows("PENDING"));
  assert.equal((html.match(/aria-label="Allow /g) ?? []).length, 2);
  assert.match(html, /Recording &amp; live transcription/);
  assert.match(html, /Recording creates a saved audio\/video file\./);
  assert.match(html, /Allows a transcript file to be saved\./);
  // The fuller explanation is present, collapsed under Details.
  assert.equal((html.match(/<details/g) ?? []).length, 2);
  assert.match(html, /<details[^>]*>(?:(?!<\/details>).)*Approval doesn’t start either operation/);
  assert.match(html, /<details[^>]*>(?:(?!<\/details>).)*separately allowed/);
  assert.doesNotMatch(html, /Allow audio\/video recording|Allow session transcription/);
  assert.doesNotMatch(html, /Media policy|v2|V2/);
});

function CounselorMediaProbe(props) {
  const media = useCounselorMedia(props);
  return h("div", null, h(GovernedCaptureControls, { media }), h(CounselorMediaStrip, { media }));
}

test("V2 has one media permission while recording and transcription controls stay independent", () => {
  const data = workspace("ACTIVE"); data.media.media_policy_version = 2;
  const html = render(h(CounselorMediaProbe, { appointmentId, workspace: data, access: { canManageMediaAssigned: true, canAccessMediaAssigned: true }, inCall: true, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), v2Rows("APPROVED"));
  assert.match(html, /aria-label="Stop recording"/);
  assert.match(html, /aria-label="Stop transcription"/);
  assert.match(html, /Media permission approved/);
  assert.match(html, /Transcript storage approved/);
  assert.doesNotMatch(html, /Recording permission|Transcription permission/);
});

test("a V2 media permission that was never requested offers one request; V1 keeps three distinct permissions", () => {
  const v2 = workspace(); v2.media.media_policy_version = 2;
  const requestable = render(h(CounselorMediaProbe, { appointmentId, workspace: v2, access: { canManageMediaAssigned: true }, inCall: false, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), []);
  assert.match(requestable, /Media permission not requested/);
  assert.match(requestable, /aria-label="Request media permission"/);
  assert.doesNotMatch(requestable, /Transcript storage/, "Storage is requested only after media permission");
  const v1 = render(h(CounselorMediaProbe, { appointmentId, workspace: workspace(), access: { canManageMediaAssigned: true }, inCall: false, sessionStateCurrent: true }), getECounselingListAssignedConsentsQueryKey(appointmentId), consents("PENDING"));
  for (const subject of ["Recording permission · Waiting for Student", "Transcription permission · Waiting for Student", "Transcript storage not requested"]) assert.match(v1, new RegExp(subject));
});

for (const state of ["PENDING", "PROCESSING", "FAILED", "DISPOSED"]) test(`artifact ${state} has a truthful outcome without a download action`, () => {
  const value = { artifact_status: state, artifact_available: false, artifact_disposed_at: null };
  assert.equal(renderToStaticMarkup(h(MediaArtifactDownload, { appointmentId, kind: "RECORDING", state: value, canAccess: true })), "");
  assert.match(artifactOutcome("RECORDING", value).text, state === "DISPOSED" ? /Deleted under an approved retention rule/ : state === "FAILED" ? /isn't available/ : /Preparing file…/);
});

test("stored files require the dedicated capability and never embed a URL", () => {
  const props = { appointmentId, kind: "TRANSCRIPTION", state: { artifact_status: "STORED", artifact_available: true, artifact_disposed_at: null } };
  const html = renderToStaticMarkup(h(MediaArtifactDownload, { ...props, canAccess: true }));
  assert.match(html, /aria-label="Download transcript"/);
  assert.doesNotMatch(html, /href=|https?:\/\/(?!www\.w3\.org\/)/);
  assert.equal(renderToStaticMarkup(h(MediaArtifactDownload, { ...props, canAccess: false })), "");
  assert.equal(getECounselingAccess(user()).canAccessMediaAssigned, true);
  assert.equal(getECounselingAccess(user("STUDENT")).canAccessMediaAssigned, false);
  assert.equal(getECounselingAccess({ ...user(), capabilities: ["ecounseling.access_media_assigned"] }).canAccessMediaAssigned, false);
});

test("session files describe the outcome, not the storage setting", () => {
  const stopped = workspace(); stopped.media.media_policy_version = 2;
  stopped.media.recording = { ...stopped.media.recording, capture_status: "READY", artifact_status: "STORED", artifact_available: true };
  stopped.media.transcription = { ...stopped.media.transcription, capture_status: "STOPPED", storage_enabled: false };
  assert.deepEqual(sessionFileRows(stopped.media).map((row) => [row.label, row.outcome.text]), [["Recording", "Ready"], ["Transcript", "No transcript saved."]]);
  const saved = workspace(); saved.media.media_policy_version = 2;
  saved.media.transcription = { ...saved.media.transcription, capture_status: "READY", artifact_status: "STORED", artifact_available: true, storage_enabled: false };
  assert.deepEqual(sessionFileRows(saved.media).map((row) => [row.label, row.outcome.short]), [["Transcript", "saved"]], "A saved file is described by the file, whatever the last storage setting");
  const v1 = workspace("READY");
  assert.deepEqual(sessionFileRows(v1.media).map((row) => row.outcome.text), ["Recording completed.", "Transcription completed. The transcript was stored by the video service."]);
  assert.deepEqual(sessionFileRows(workspace().media), [], "Nothing captured, nothing listed");
});

test("V2 disposition names both copies and the limits on downloaded copies", () => {
  assert.match(dispositionConsequence({ category: "ECOUNSELING_RECORDING", contract_version: 2 }), /COMPASS media file and any remaining provider copy/);
  assert.match(dispositionConsequence({ category: "ECOUNSELING_RECORDING", contract_version: 2 }), /downloaded copies cannot be recalled/);
  assert.match(dispositionActionLabel("DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE"), /provider artifact/);
  assert.match(dispositionActionLabel("DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE"), /COMPASS media/);
});
