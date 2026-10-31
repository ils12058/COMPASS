import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { facultyPortalPathAvailable } from "../src/features/portal/components/faculty-access.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { FacultyHome } from "../src/features/portal/home/faculty-home.tsx";
import { roleLabels, compatibleDesignation } from "../src/features/accounts/presentation.ts";

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
  for (const route of ["/portal/referrals", "/portal/referrals/new", "/portal/appointments/book", "/portal/counseling/encounters/private", "/portal/accounts", "/portal/accounting", "/portal/platform/health"]) {
    assert.equal(facultyPortalPathAvailable(route), false, route);
  }
  for (const route of ["/portal", "/portal/account/profile", "/portal/account/security/authenticator", "/portal/notifications"]) {
    assert.equal(facultyPortalPathAvailable(route), true);
  }
  assert.equal(roleLabels.FACULTY, "Faculty");
  assert.equal(compatibleDesignation("FACULTY"), null);
});

test("Faculty holding Home states unavailable Referrals and missing affiliation honestly", () => {
  const html = renderToStaticMarkup(createElement(FacultyHome, { user: faculty }));
  assert.match(html, /Digital Student Referrals are not available yet/);
  assert.match(html, /Not assigned/);
  assert.match(html, /Contact the account administrator/);
  assert.doesNotMatch(html, /Book appointment|Record referral|href=.*referrals/);
  const assigned = renderToStaticMarkup(createElement(FacultyHome, { user: { ...faculty, faculty_affiliation: { college_name: "Faculty College", campus_name: "Main Campus", active: true } } }));
  assert.match(assigned, /Main Campus · Faculty College/);
  assert.doesNotMatch(assigned, /Contact the account administrator/);
});
