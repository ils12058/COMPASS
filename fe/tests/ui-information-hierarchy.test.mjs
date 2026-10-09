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
import { CaptureIndicators } from "../src/features/ecounseling/call/capture-indicators.tsx";
import { CounselorMediaStrip, GovernedCaptureControls, useCounselorMedia } from "../src/features/ecounseling/counselor-media.tsx";
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
  for (const heading of ["Media consent", "Recording", "Transcription", "Transcript storage", "Encounter records", "Call and devices"]) assert.ok(ecounselingHelpSections.some((section) => section.heading === heading));
  assert.match(html, /separately/);
  assert.match(html, /approval alone doesn’t start recording/);
  assert.match(html, /requires separate student consent/);
  // Leaving the call is not stopping capture, and that is said where people look for call help.
  assert.match(html, /doesn’t stop recording or transcription/);
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
  assert.match(html, /Guidance Services Staff handle/);
  assert.match(html, /unique active Head when no valid Counselor is assigned/);
  assert.match(html, /Staff do not inherit Head oversight authority/);
});

test("operator Help retains diagnostic limitations and approval semantics", () => {
  assert.match(help(platformHelpSections), /does not establish worker, scheduler, Daily.co, or Turnstile/);
  assert.match(help(retentionHelpSections), /Eligibility alone never authorizes disposition/);
});

test("active recording and transcription are visible on the call without opening Help and without relying on color", () => {
  const html = renderToStaticMarkup(h(CaptureIndicators, { media: workspace("ACTIVE").media }));
  assert.match(html, /aria-live="polite"/);
  assert.match(html, />Recording<\/li>|Recording<\/li>/);
  assert.match(html, /Transcription on/);
  assert.equal(renderToStaticMarkup(h(CaptureIndicators, { media: workspace("NOT_STARTED").media })).includes("<li"), false, "Consent alone never shows as activity");
});

function CounselorMediaProbe(props) {
  const media = useCounselorMedia(props);
  return h("div", null, h(GovernedCaptureControls, { media }), h(CounselorMediaStrip, { media }));
}

test("governed media controls keep specific blockers and failed states visible and fail closed", () => {
  const data = workspace("ERROR");
  data.provider_readiness.daily_enabled = false;
  const html = render(h(CounselorMediaProbe, { appointmentId, access: { canManageMediaAssigned: true }, workspace: data, inCall: true, sessionStateCurrent: true }), (client) => {
    client.setQueryData(getECounselingListAssignedConsentsQueryKey(appointmentId), { data: { items: consents("DENIED") }, status: 200, headers: {} });
  });
  assert.match(html, /Needs attention/);
  assert.match(html, /Recording permission declined/);
  assert.doesNotMatch(html, /aria-label="Start recording"/, "A capture needing attention offers no start");
  assert.match(html, /<button type="button" disabled=""(?:(?!<\/button>).)*>Record<\/span>/);
});

test("starting capture fails closed when the latest session state couldn’t be confirmed, while stop stays available", () => {
  const ready = workspace("NOT_STARTED");
  const stale = render(h(CounselorMediaProbe, { appointmentId, access: { canManageMediaAssigned: true }, workspace: ready, inCall: true, sessionStateCurrent: false }), (client) => {
    client.setQueryData(getECounselingListAssignedConsentsQueryKey(appointmentId), { data: { items: consents("APPROVED") }, status: 200, headers: {} });
  });
  assert.match(stale, /<button[^>]*aria-label="Start recording"[^>]*disabled=""/);
  assert.match(stale, /Session status couldn’t be refreshed/);
  const active = render(h(CounselorMediaProbe, { appointmentId, access: { canManageMediaAssigned: true }, workspace: workspace("ACTIVE"), inCall: true, sessionStateCurrent: false }), (client) => {
    client.setQueryData(getECounselingListAssignedConsentsQueryKey(appointmentId), { data: { items: consents("APPROVED") }, status: 200, headers: {} });
  });
  assert.match(active, /<button(?![^>]*disabled="")[^>]*aria-label="Stop recording"/);
});

test("Student decisions keep each scope's meaning and Counseling access visible without opening Help", () => {
  const html = render(h(StudentConsentPanel, { appointmentId, access: { canConsentSelf: true }, media: workspace().media }), (client) => {
    client.setQueryData(getECounselingListMyConsentsQueryKey(appointmentId), { data: { items: consents("PENDING") }, status: 200, headers: {} });
  });
  assert.match(html, /audio and video from this Counseling session to be recorded/);
  assert.match(html, /speech from this session to be processed as text/);
  assert.match(html, /don’t affect your access to Counseling/);
  assert.match(html, />Allow</);
  assert.match(html, /aria-label="Allow audio\/video recording"/);
  assert.match(html, /aria-label="Allow session transcription"/);
  assert.match(html, />Decline</);
  assert.match(html, /<details/);
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
  assert.match(html, /won’t be requested again/);
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
