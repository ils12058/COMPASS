import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ContextHelp, HelpSections } from "../src/components/ui/context-help.tsx";
import { IconAction, actionIcons } from "../src/components/ui/icon-action.tsx";
import { PageHeader } from "../src/components/ui/page-header.tsx";
import { CounselingContextPanel } from "../src/features/counseling/counseling-workspace.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { CounselorMediaControls } from "../src/features/ecounseling/counselor-media-controls.tsx";
import { SessionStage } from "../src/features/ecounseling/session-stage.tsx";
import { StudentConsentPanel } from "../src/features/ecounseling/student-consent-panel.tsx";
import { ecounselingHelpSections } from "../src/features/ecounseling/session-help.tsx";
import { institutionalFormsHelpSections } from "../src/features/institution-configuration/forms-help.tsx";
import { responsibilitiesHelpSections } from "../src/features/organization/responsibilities/responsibilities-help.tsx";
import { serviceHelpSections } from "../src/features/services/service-help.tsx";
import { platformHelpSections } from "../src/features/platform/platform-help.tsx";
import { retentionHelpSections } from "../src/features/privacy-governance/retention/retention-help.tsx";
import { getECounselingListAssignedConsentsQueryKey, getECounselingListMyConsentsQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { appointmentId, workspace, consents, user, appointment } from "./support/ui-hierarchy-fixtures.mjs";

const render = (element, seed = () => {}) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(h(QueryClientProvider, { client }, element));
  client.clear();
  return html;
};
const help = (sections) => renderToStaticMarkup(h(HelpSections, { sections }));

test("page Help is a named keyboard/tap button, not a hover-only explanation", () => {
  const html = renderToStaticMarkup(h(PageHeader, { title: "Session", help: h(ContextHelp, { title: "About session", sections: [{ heading: "Permissions", content: "Explanation" }] }) }));
  assert.match(html, /<button[^>]*type="button"[^>]*aria-label="Help: About session"/);
  assert.match(html, /aria-haspopup="dialog"/);
  assert.match(html, /min-h-11/);
  assert.doesNotMatch(html, /Explanation/);
});

test("Help groups are named headings and can contain real links", () => {
  const html = help([{ heading: "Permissions", content: h("a", { href: "/portal/account/privacy" }, "Privacy Notices") }]);
  assert.match(html, /<h3[^>]*>Permissions<\/h3>/);
  assert.match(html, /<a href="\/portal\/account\/privacy">Privacy Notices<\/a>/);
});

test("compact actions have independent names, touch labels and conventional low-risk icons", () => {
  const html = renderToStaticMarkup(h(IconAction, { action: "refresh", label: "Refresh Call Slip" }));
  assert.match(html, /aria-label="Refresh Call Slip"/);
  assert.match(html, /min-h-11 min-w-11/);
  assert.match(html, /pointer:coarse/);
  assert.match(html, /<svg[^>]*aria-hidden="true"/);
  for (const unsafe of ["delete", "issue", "publish", "record", "withdraw", "disable"]) assert.equal(unsafe in actionIcons, false);
});

test("E-Counseling Help holds separate media and encounter concepts", () => {
  const html = help(ecounselingHelpSections);
  for (const heading of ["Media consent", "Recording", "Transcription", "Transcript storage", "Encounter records"]) assert.ok(ecounselingHelpSections.some((section) => section.heading === heading));
  assert.match(html, /separately/);
  assert.match(html, /approval alone does not start recording/);
  assert.match(html, /requires separate student consent/);
});

test("Service Help explains coverage, saved appointments and separate video settings", () => {
  const html = help(serviceHelpSections);
  assert.match(html, /All active Counselors/);
  assert.match(html, /existing Appointments keep their saved settings/);
  assert.match(html, /separate video-service settings/);
});

test("Institutional Form Help distinguishes Current, software support and approval", () => {
  const html = help(institutionalFormsHelpSections);
  assert.match(html, /Current means the revision selected for new records/);
  assert.match(html, /does not grant institutional approval/);
  assert.match(html, /CNSC\/GTA/);
});

test("Responsibilities Help includes safe fallback, confidential access and GSS inheritance", () => {
  const html = help(responsibilitiesHelpSections);
  assert.match(html, /exactly one active Head Guidance Counselor/);
  assert.match(html, /does not automatically grant blanket access/);
  assert.match(html, /Guidance Services Staff inherit/);
});

test("operator Help retains diagnostic limitations and approval semantics", () => {
  assert.match(help(platformHelpSections), /does not establish worker, scheduler, Daily.co, or Turnstile/);
  assert.match(help(retentionHelpSections), /Eligibility alone never authorizes disposition/);
});

test("active recording and transcription are visible without opening Help and without relying on color", () => {
  const data = workspace("ACTIVE");
  const html = renderToStaticMarkup(h(SessionStage, {
    readiness: data.provider_readiness, media: data.media, canJoin: true, inCall: false,
    join: { showDailyFrame: false, joining: false, joinError: null, requestJoin() {} },
  }));
  assert.match(html, /<dt[^>]*>Recording<\/dt>/);
  assert.match(html, /<dt[^>]*>Transcription<\/dt>/);
  assert.equal((html.match(/Active<\/span>/g) ?? []).length, 2);
  assert.match(html, /aria-live="polite"/);
});

test("media controls keep specific blockers and failed states visible", () => {
  const data = workspace("ERROR");
  data.provider_readiness.daily_enabled = false;
  const html = render(h(CounselorMediaControls, { appointmentId, access: { canManageMediaAssigned: true }, workspace: data }), (client) => {
    client.setQueryData(getECounselingListAssignedConsentsQueryKey(appointmentId), { data: { items: consents("DENIED") }, status: 200, headers: {} });
  });
  assert.match(html, /Video sessions are off/);
  assert.match(html, /Needs attention/);
  assert.match(html, /Declined/);
  assert.doesNotMatch(html, />Start recording</);
});

test("Student decisions retain all scope meanings and Counseling access without opening Help", () => {
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media: workspace().media }), (client) => {
    client.setQueryData(getECounselingListMyConsentsQueryKey(appointmentId), { data: { items: consents("PENDING") }, status: 200, headers: {} });
  });
  assert.match(html, /audio and video from this Counseling session to be recorded/);
  assert.match(html, /speech from this session to be processed as text/);
  assert.match(html, /stored by the video service/);
  assert.match(html, /does not affect your ability to receive Counseling/);
  assert.match(html, />Allow</);
  assert.match(html, /aria-label="Allow audio\/video recording"/);
  assert.match(html, /aria-label="Allow session transcription"/);
  assert.match(html, />Decline</);
});

test("withdrawn and denied permissions remain visible and cannot be re-requested", () => {
  const rows = consents("DENIED");
  rows[0] = { ...rows[0], decision: "APPROVED", withdrawn_at: "2026-10-07T00:02:00Z", effective: false };
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media: workspace().media }), (client) => {
    client.setQueryData(getECounselingListMyConsentsQueryKey(appointmentId), { data: { items: rows }, status: 200, headers: {} });
  });
  assert.match(html, /Withdrawn/);
  assert.match(html, /Declined/);
  assert.doesNotMatch(html, />Allow</);
  assert.match(html, /will not be requested again/);
});

test("embedded Counseling retains the access deadline; a standalone Interaction panel owns its repeated facts", () => {
  const overview = {
    source_type: "APPOINTMENT", source_id: appointmentId, entry_mode: "APPOINTMENT", delivery_mode: "ONLINE",
    valid_until: "2099-01-01T00:00:00Z", student: { ...appointment.student, year_level: 4 },
    available_sections: ["OVERVIEW"], matching_encounter: null, routine_interview: null,
  };
  const panel = (showInteractionFacts) => render(h(PortalSessionProvider, { value: { user: user() } },
    h(CounselingContextPanel, { overview, anchorType: "APPOINTMENT", anchorId: appointmentId,
      access: { canViewAssigned: true }, ...(showInteractionFacts === undefined ? {} : { showInteractionFacts }) })));
  assert.match(panel(), /<dt[^>]*>Available until<\/dt>/);
  assert.match(panel(), /<dt[^>]*>Origin<\/dt>/);
  assert.doesNotMatch(panel(false), /<dt[^>]*>Available until<\/dt>/);
  assert.match(panel(false), /Maria Santos/);
});
