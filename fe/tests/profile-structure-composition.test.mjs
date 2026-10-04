import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { withNextRouter } from "./support/next-router.mjs";
import { ProfilePage } from "../src/features/account/profile/profile-page.tsx";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { OrganizationStructurePage } from "../src/features/organization/structure/organization-structure-page.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import {
  getOrganizationListCampusesQueryKey,
  getOrganizationListCollegesQueryKey,
  getOrganizationListProgramsQueryKey,
} from "../src/lib/api/generated/organization/organization.ts";
import { getProfileGetMyProfileQueryKey } from "../src/lib/api/generated/profile/profile.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const user = { id: "u1", first_name: "Ana", last_name: "Cruz", email: "ana.cruz@example.edu", role: "STUDENT", capabilities: [] };

function render(component, records, pathname = "/portal") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  for (const [key, data] of records) client.setQueryData(key, ok(data));
  return renderToStaticMarkup(withNextRouter(createElement(QueryClientProvider, { client },
    createElement(PortalSessionProvider, { value: { user } },
      createElement(UnsavedChangesProvider, null, component))), { pathname }));
}

// --- Profile -------------------------------------------------------------------------------------

const profile = {
  user_id: "u1", first_name: "Ana", middle_name: "", last_name: "Cruz", suffix: "", full_name: "Ana Cruz",
  email: "ana.cruz@example.edu", institutional_id: "2023-0001", role: "STUDENT",
  date_of_birth: "2004-05-01", civil_status: "Single", contact_number: "0917 000 0000",
  current_address: "Daet", permanent_address: "Daet", profile_photo_url: null, profile_photo_updated_at: null,
};

test("Profile puts the read-only identity beside one form of editable details", () => {
  const html = render(createElement(ProfilePage), [[getProfileGetMyProfileQueryKey(), profile]], "/portal/account/profile");

  assert.match(html, /@container\/profile/);
  assert.match(html, /@\[48rem\]\/profile:grid-cols-\[minmax\(14rem,18rem\)_minmax\(0,1fr\)\]/);
  // Identity is text, not inputs: name, institutional ID, role, and sign-in email, with photo actions.
  const identity = html.slice(0, html.indexOf("<form"));
  for (const fact of ["Ana Cruz", "2023-0001", "Student", "ana.cruz@example.edu", "Change photo"]) {
    assert.match(identity, new RegExp(fact));
  }
  assert.doesNotMatch(identity, /<input(?![^>]*type="file")/);
  // Exactly the fields the update contract accepts, in one form, with one Save.
  assert.equal((html.match(/<form/g) ?? []).length, 1);
  const fields = [...html.matchAll(/<input[^>]*id="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(fields.sort(), ["civil-status", "contact-number", "current-address", "date-of-birth", "permanent-address"]);
  assert.match(html, /<button type="submit"[^>]*disabled=""[^>]*>Save changes<\/button>/);
  // Success is no longer a permanent green line in the form.
  assert.doesNotMatch(html, /Profile changes saved/);
  assert.match(html, /data-action-status=""/);
});

test("Profile confirms a save transiently and keeps a failure, and the typed values, in the form", () => {
  const source = readFileSync(new URL("../src/features/account/profile/profile-page.tsx", import.meta.url), "utf8");
  const save = source.slice(source.indexOf("async function save("), source.indexOf("return (", source.indexOf("async function save(")));
  assert.ok(save.indexOf("onAttempt()") < save.indexOf("update.mutateAsync"), "an earlier confirmation is cleared first");
  assert.ok(save.indexOf('onSaved("Profile changes saved.")') > save.indexOf("setSaved(next)"), "confirmed only after the response");
  assert.match(save, /catch \(caught\) \{\s*setError\(accountErrorMessage\(caught/);
  assert.doesNotMatch(save.slice(save.indexOf("catch")), /setValues/);
  assert.match(source, /useUnsavedChangesGuard\(\{\s*dirty,/);
  // Photo changes confirm the same way; a photo error stays beside the photo.
  assert.match(source, /onSaved\("Profile photo updated\."\)/);
  assert.match(source, /onSaved\("Profile photo removed\."\)/);
  assert.match(source, /\{error \? <p role="alert" className="mt-3 text-sm text-danger">\{error\}<\/p> : null\}/);
});

// --- Organization Structure ----------------------------------------------------------------------

const campus = (id, name, active = true) => ({ id, code: id.toUpperCase(), name, is_active: active });
const college = (id, campusId, name, active = true) => ({ id, code: id.toUpperCase(), name, is_active: active, campus: { id: campusId, code: campusId.toUpperCase(), name: "" } });
const program = (id, collegeId, name, active = true) => ({ id, code: id.toUpperCase(), name, is_active: active, college: { id: collegeId, code: collegeId.toUpperCase(), name: "" } });

function structure({ campuses, colleges, programs }) {
  return render(createElement(OrganizationStructurePage), [
    [getOrganizationListCampusesQueryKey({}), { items: campuses }],
    [getOrganizationListCollegesQueryKey({}), { items: colleges }],
    [getOrganizationListProgramsQueryKey({}), { items: programs }],
  ], "/portal/organization");
}

test("Structure reads as a hierarchy: each Campus, its Colleges, and each College's Programs", () => {
  const html = structure({
    campuses: [campus("main", "Main Campus"), campus("north", "North Campus")],
    colleges: [college("ccms", "main", "College of Computing"), college("cba", "main", "College of Business", false)],
    programs: [program("bsis", "ccms", "BS Information Systems"), program("bsit", "ccms", "BS Information Technology"), program("bsba", "cba", "BS Business Administration", false)],
  });

  assert.match(html, /<section aria-labelledby="organization-structure-heading" class="max-w-4xl">/);
  assert.match(html, /id="campus-main"[^>]*>Main Campus</);
  const computing = html.slice(html.indexOf('id="college-ccms"'), html.indexOf('id="college-cba"'));
  assert.match(computing, /aria-label="Programs in College of Computing"/);
  assert.match(computing, /BS Information Systems[\s\S]*BS Information Technology/);
  assert.doesNotMatch(computing, /BS Business Administration/);
  const business = html.slice(html.indexOf('id="college-cba"'));
  assert.match(business, /BS Business Administration[\s\S]*Inactive/);
  // A Campus without Colleges still says so.
  assert.match(html.slice(html.indexOf('id="campus-north"')), /No colleges are recorded for this campus\./);
  // Programs are indented beneath their College, not boxed inside it.
  assert.doesNotMatch(html, /rounded-sm border border-border/);
  // Read-only: nothing to type into or press.
  assert.doesNotMatch(html, /<input|<select|<textarea|<button/);
});

test("a College without Programs says so, and only the Structure page is bounded", () => {
  const html = structure({ campuses: [campus("main", "Main Campus")], colleges: [college("ccms", "main", "College of Computing")], programs: [] });
  assert.match(html, /No programs are recorded\./);
  const layout = readFileSync(new URL("../src/app/(portal)/portal/organization/layout.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(layout, /max-w|pageSheetWidth/);
});
