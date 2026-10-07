import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StudentConsentPanel } from "../src/features/ecounseling/student-consent-panel.tsx";
import { CounselorMediaControls } from "../src/features/ecounseling/counselor-media-controls.tsx";
import { MediaArtifactDownload } from "../src/features/ecounseling/media-artifact-download.tsx";
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

test("V2 student has two decisions with separate transcript persistence and no automatic capture", () => {
  const media = { ...workspace().media, media_policy_version: 2 };
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media }), getECounselingListMyConsentsQueryKey(appointmentId), v2Rows("PENDING"));
  assert.equal((html.match(/aria-label="Allow /g) ?? []).length, 2);
  assert.match(html, /Recording &amp; live transcription/);
  assert.match(html, /Approval alone does not start/);
  assert.match(html, /separately allow transcript storage/);
  assert.doesNotMatch(html, /Allow audio\/video recording|Allow session transcription/);
});

test("V2 has one media request while capture controls remain independent", () => {
  const data = workspace("ACTIVE"); data.media.media_policy_version = 2;
  const html = render(h(CounselorMediaControls, { appointmentId, workspace: data, access: { canManageMediaAssigned: true, canAccessMediaAssigned: true } }), getECounselingListAssignedConsentsQueryKey(appointmentId), v2Rows("APPROVED"));
  assert.match(html, /Stop recording/); assert.match(html, /Stop transcription/);
  assert.doesNotMatch(html, /Request recording consent|Request transcription consent/);
});

for (const state of ["PENDING", "PROCESSING", "FAILED", "DISPOSED"]) test(`artifact ${state} has truthful availability without a download action`, () => {
  const html = renderToStaticMarkup(h(MediaArtifactDownload, { appointmentId, kind: "RECORDING", state: { artifact_status: state, artifact_available: false, artifact_disposed_at: null }, canAccess: true }));
  assert.doesNotMatch(html, /<button/);
  assert.match(html, state === "DISPOSED" ? /Deleted under an approved retention rule/ : state === "FAILED" ? /isn&#x27;t available/ : /Preparing recording/);
});

test("stored files require the dedicated capability and never embed a URL", () => {
  const props = { appointmentId, kind: "TRANSCRIPTION", state: { artifact_status: "STORED", artifact_available: true, artifact_disposed_at: null } };
  assert.match(renderToStaticMarkup(h(MediaArtifactDownload, { ...props, canAccess: true })), /Download transcript/);
  assert.equal(renderToStaticMarkup(h(MediaArtifactDownload, { ...props, canAccess: false })), "");
  assert.equal(getECounselingAccess(user()).canAccessMediaAssigned, true);
  assert.equal(getECounselingAccess(user("STUDENT")).canAccessMediaAssigned, false);
  assert.equal(getECounselingAccess({ ...user(), capabilities: ["ecounseling.access_media_assigned"] }).canAccessMediaAssigned, false);
});

test("V2 disposition names both copies and the limits on downloaded copies", () => {
  assert.match(dispositionConsequence({ category: "ECOUNSELING_RECORDING", contract_version: 2 }), /COMPASS media file and any remaining provider copy/);
  assert.match(dispositionConsequence({ category: "ECOUNSELING_RECORDING", contract_version: 2 }), /downloaded copies cannot be recalled/);
  assert.match(dispositionActionLabel("DELETE_PROVIDER_ARTIFACT_KEEP_EVIDENCE"), /provider artifact/);
  assert.match(dispositionActionLabel("DELETE_MEDIA_ARTIFACT_KEEP_EVIDENCE"), /COMPASS media/);
});
