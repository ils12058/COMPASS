import { featureWorld } from "./simplify-2c-feature-fixtures.mjs";
import { inventoryFixture } from "./inventory-guide-fixture.mjs";
import { tracerFixture } from "./ux15-tracer-fixtures.mjs";
import { exitFixture } from "./ux15-exit-fixtures.mjs";
import { user, appointment } from "./ui-hierarchy-fixtures.mjs";
import { sessionFor } from "./guidance-messages-fixtures.mjs";

export const empty = { items: [], page: 1, page_size: 20, has_next: false };
export const referralId = "f3000000-0000-4000-8000-000000000001";
export const exitId = "e3000000-0000-4000-8000-000000000001";
export const opportunityId = "bb111111-1111-4111-8111-111111111111";
export const opportunity = { id: opportunityId, service_kind: "COUNSELING", service_label: "Synthetic service", service_completed_at: "2026-10-14T00:00:00Z", customer_feedback_submitted: false, csm_submitted: false, can_submit_customer_feedback: true, can_submit_csm: true };
export const faculty = { ...user("STUDENT"), role: "FACULTY", student_lifecycle_status: null, designations: [], capabilities: ["referrals.view_submitted_self", "referrals.submit_self"], faculty_affiliation: { active: true, college_name: "Synthetic College", campus_name: "Main Campus", resource_version: 1 } };
export const referral = { id: referralId, reference_code: "REF-SYNTHETIC-01", submitted_at: "2026-11-01T01:30:00Z", state: "RECEIVED_BY_GCO", received_at: "2026-11-02T01:30:00Z", closed_at: null, student: { display_name: "Synthetic Student" } };

export function guideWorld(id, mode = "available") {
  const name = ({ "book-appointment": "booking", "individual-inventory": "inventory", "exit-interview": "exit", "graduate-tracer": "tracer", "send-message": "messages" })[id] ?? "good-moral";
  const world = featureWorld(name, mode === "ineligible" ? "blocked" : "intro");
  world.account.capabilities.push("feedback.submit_customer_feedback", "feedback.submit_csm");
  const domain = id === "individual-inventory" && mode !== "empty" ? inventoryFixture({ submitted: mode === "completed" })
    : id === "graduate-tracer" && mode !== "empty" ? tracerFixture({ submitted: mode === "completed" })
    : id === "exit-interview" && mode === "form" ? exitFixture() : null;
  if (id.startsWith("faculty-")) world.account = structuredClone(faculty);
  if (mode === "read-only") world.account.capabilities = world.account.capabilities.filter(capability => !capability.includes("manage_self"));
  const parent = world.handler;
  const handler = async args => {
    const { pathname, method = "GET", reply } = args;
    if (pathname === "/api/v1/auth/session") { await reply(sessionFor(world.account)); return true; }
    // No preview or guide test may perform a consequential write.
    if (method !== "GET") { await reply({ error: { code: "synthetic_write_blocked" } }, 405); return true; }
    if (domain && await domain.handler({ ...args, pathname: pathname.replace(exitId, "exit-1b") })) return true;
    if (pathname === "/api/v1/faculty/referrals/availability") { await reply({ can_confirm_student: mode !== "ineligible", can_submit_referral: mode !== "ineligible", can_view_submissions: true, valid_until: "2099-01-01T00:00:00Z" }); return true; }
    if (pathname === "/api/v1/faculty/referrals") { await reply({ ...empty, items: mode === "empty" ? [] : [referral] }); return true; }
    if (pathname === `/api/v1/faculty/referrals/${referralId}`) { await reply(referral); return true; }
    if (pathname === "/api/v1/good-moral/me") { await reply(empty); return true; }
    if (pathname === "/api/v1/feedback/opportunities") { await reply(mode === "empty" ? [] : [{ ...opportunity, ...(mode === "completed" ? { customer_feedback_submitted: true, csm_submitted: true, can_submit_customer_feedback: false, can_submit_csm: false } : {}) }]); return true; }
    if (pathname === `/api/v1/feedback/opportunities/${opportunityId}`) { await reply(opportunity); return true; }
    if (pathname === "/api/v1/appointments/me") { await reply({ ...empty, items: mode === "empty" ? [] : [appointment] }); return true; }
    if (mode === "empty" && pathname === "/api/v1/appointments/booking/services") { await reply(empty); return true; }
    if (mode === "empty" && pathname === "/api/v1/student-actions") { await reply(empty); return true; }
    return parent(args);
  };
  return { world, options: { handler }, handler };
}
