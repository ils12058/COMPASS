import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { facultyPortalPathAvailable } from "../src/features/portal/components/faculty-access.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { FacultyHomeView } from "../src/features/portal/home/faculty-home.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { roleLabels, compatibleDesignations } from "../src/features/accounts/presentation.ts";

const faculty = {
  id: "faculty", role: "FACULTY", first_name: "Synthetic", last_name: "Faculty",
  email: "faculty@synthetic.invalid", capabilities: [], designations: [],
  student_lifecycle_status: null, faculty_affiliation: null,
};

test("Faculty has only own-account destinations, including with a stale authority projection", () => {
  for (const account of [faculty, { ...faculty, capabilities: ["accounts.manage", "referrals.view", "referrals.manage", "platform_operations.view", "appointments.manage_self"] }]) {
    assert.deepEqual(portalWorkspaceGroups(account), []);
    for (const command of portalCommandDestinations(account)) assert.ok(facultyPortalPathAvailable(command.href), command.href);
  }
  for (const route of ["/portal/referrals", "/portal/referrals/new", "/portal/appointments/book", "/portal/counseling/encounters/private", "/portal/accounts", "/portal/accounting", "/portal/platform/health", "/portal/messages/templates"]) {
    assert.equal(facultyPortalPathAvailable(route), false, route);
  }
  for (const route of ["/portal", "/portal/account/profile", "/portal/account/security/authenticator", "/portal/notifications"]) {
    assert.equal(facultyPortalPathAvailable(route), true);
  }
  assert.equal(roleLabels.FACULTY, "Faculty");
  assert.deepEqual(compatibleDesignations("FACULTY"), []);
  assert.deepEqual(compatibleDesignations("COUNSELOR"), ["HEAD_GUIDANCE_COUNSELOR", "GENERAL_GUIDANCE_INTAKE"]);
  assert.deepEqual(compatibleDesignations("GUIDANCE_OFFICE_ASSISTANT"), ["GENERAL_GUIDANCE_INTAKE"]);
});

test("Faculty may reach only their own Guidance Office inquiry paths", () => {
  for (const route of ["/portal/messages", "/portal/messages/new", "/portal/messages/f0000000-0000-4000-8000-000000000001"]) {
    assert.equal(facultyPortalPathAvailable(route), true, route);
  }
  assert.equal(facultyPortalPathAvailable("/portal/messages/faculty-inquiry"), false, "Only a thread id opens");
});

test("Faculty holding Home states unavailable Referrals and missing affiliation honestly", () => {
  const renderHome = (user) => renderToStaticMarkup(createElement(UnsavedChangesProvider, null, createElement(FacultyHomeView, { user }, "Digital Student Referrals are not available yet.")));
  const html = renderHome(faculty);
  assert.match(html, /Digital Student Referrals are not available yet/);
  assert.match(html, /Not assigned/);
  assert.match(html, /Contact the account administrator/);
  assert.doesNotMatch(html, /Book appointment|Record referral|href=.*referrals/);
  const assigned = renderHome({ ...faculty, faculty_affiliation: { college_name: "Faculty College", campus_name: "Main Campus", active: true } });
  assert.match(assigned, /Main Campus · Faculty College/);
  assert.doesNotMatch(assigned, /Contact the account administrator/);
});
