// Synthetic-only responsive and visual checks for the P2A record detail refinements.
import assert from "node:assert/strict";

import { createBrowserHarness } from "./support/browser-harness.mjs";
import { assessmentWorld, content, recordId } from "./support/assessment-records-fixtures.mjs";
import { appointment, service, slip, user } from "./support/ui-hierarchy-fixtures.mjs";

const { check, shown, hidden, noHorizontalOverflow, screenshot, finish } = await createBrowserHarness("ux-p2a");
const expectRails = process.env.COMPASS_UX_P2A_EXPECT_RAILS !== "0";
async function capture(page, name) {
  await page.addStyleTag({ content: "nextjs-portal { display: none !important; }" });
  await screenshot(page, name);
}
const routineId = "routine-p2a-synthetic";
const widths = [320, 375, 768, 1024, 1440];

const counselorCapabilities = [
  "call_slips.view",
  "call_slips.manage",
  "referrals.view",
  "services.catalog.view",
  "services.manage",
  "appointments.view_assigned",
  "appointments.manage",
  "counseling.view_assigned",
  "routine_interviews.view_assigned",
  "routine_interviews.manage_assigned",
];
const studentCapabilities = [
  "call_slips.view_self",
  "routine_interviews.view_self",
  "routine_interviews.manage_self",
];

function session(role, capabilities) {
  const account = { ...user(role), capabilities };
  return { user: account, session: { id: `p2a-${role.toLowerCase()}-session`, expires_at: "2099-10-07T00:00:00Z", is_current: true } };
}

const p2aSlip = {
  ...slip,
  student_institutional_id: "P2A-STUDENT-001",
  recorded_by: appointment.provider,
  updated_at: "2026-10-07T01:00:00Z",
  void_reason: "",
  referral: { id: "referral-p2a-synthetic", reference_code: "REF-P2A-0007" },
};

function callSlipHandler(role) {
  const studentFacing = role === "STUDENT";
  const base = studentFacing ? "/api/v1/call-slips/me" : "/api/v1/call-slips";
  const capabilities = studentFacing ? studentCapabilities : counselorCapabilities;
  return async ({ pathname, reply, route }) => {
    if (pathname === "/api/v1/auth/session") {
      await reply(session(role, capabilities));
      return true;
    }
    if (pathname === `${base}/${slip.id}`) {
      await reply(p2aSlip);
      return true;
    }
    if (pathname === `${base}/${slip.id}/pdf`) {
      await route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n% Synthetic Call Slip\n%%EOF" });
      return true;
    }
    return false;
  };
}

const p2aService = {
  ...service,
  id: "service-p2a-synthetic",
  code: "GCO-FLEX-GROUP",
  name: "Student Guidance and Counseling",
  description: "Individual appointments, scheduled appointment slots, and group sessions offered by the Guidance and Counseling Office.",
  is_system_required: false,
  booking_pathways: ["FLEXIBLE_APPOINTMENT", "FIXED_DATE_SLOT", "GROUP_SESSION"],
};

const serviceHandler = async ({ pathname, reply }) => {
  if (pathname === "/api/v1/auth/session") {
    await reply(session("COUNSELOR", ["services.catalog.view", "services.manage", "appointments.manage"]));
    return true;
  }
  if (pathname === `/api/v1/services/${p2aService.id}`) {
    await reply(p2aService);
    return true;
  }
  if (pathname === `/api/v1/services/${p2aService.id}/slots`) {
    await reply([]);
    return true;
  }
  if (pathname === `/api/v1/services/${p2aService.id}/operational-provider-candidates`) {
    await reply({ items: [], page: 1, page_size: 50, has_next: false });
    return true;
  }
  if (pathname === "/api/v1/group-sessions") {
    await reply([]);
    return true;
  }
  if (pathname === "/api/v1/group-sessions/metrics") {
    await reply({ total_sessions: 0, published_sessions: 0, completed_sessions: 0, total_registrations: 0, capacity_utilization_percent: 0, attendance_rate_percent: 0, absent_count: 0, attended_count: 0, cancelled_registrations: 0, cancelled_sessions: 0, total_capacity: 0 });
    return true;
  }
  if (pathname === "/api/v1/group-sessions/facilitator-candidates") {
    await reply([]);
    return true;
  }
  return false;
};

const evaluation = {
  academic_adjustment_rating: null,
  physical_adjustment_rating: null,
  social_adjustment_rating: null,
  spiritual_adjustment_rating: null,
  financial_adjustment_rating: null,
  emotional_adjustment_rating: null,
  other_adjustment: "",
  special_concern: "",
  recommendations: "Synthetic evaluation for visual review.",
};
const intake = {
  coping_with_college_challenges: "Synthetic Student response for visual review.",
  coping_remarks: "",
  college_experience: "",
  reason_for_choosing_institution: "",
  difficulties_encountered: "",
  stress_anxiety_causes: "",
  stress_anxiety_management: "",
  family_description: "",
  concerns: [],
  other_concern_specification: "",
  concerns_explanation: "",
  college_adjustment_and_peer_group: "",
  academic_goals: "",
  career_goals: "",
};
const routineBase = {
  id: routineId,
  academic_year: { id: "academic-year-p2a", label: "2026–2027", is_current: true },
  appointment: { id: "appointment-p2a", reference_code: "APT-P2A-0007", starts_at: "2026-10-08T02:00:00Z", ends_at: "2026-10-08T03:00:00Z" },
  counseling_encounter: null,
  created_at: "2026-10-07T00:00:00Z",
  delivery_mode: "IN_PERSON",
  entry_mode: "APPOINTMENT",
  form_revision: { official_code: "RI-01", official_revision: "1" },
  inventory_context: null,
  workflow_state: "ACTIVE",
  intake_submitted_at: "2026-10-07T00:30:00Z",
};

function routineOptions(role) {
  const isStudent = role === "STUDENT";
  const capabilities = isStudent ? studentCapabilities : counselorCapabilities;
  const counselorDetail = {
    ...routineBase,
    counseling_context_available: true,
    evaluation,
    evaluation_finalized_at: null,
    evaluation_status: "DRAFT",
    intake,
    intake_status: "SUBMITTED",
    student: { id: "student-p2a-synthetic", display_name: "Maria Santos", institutional_id: "P2A-STUDENT-001" },
  };
  const studentDetail = {
    ...routineBase,
    counselor: { id: "counselor-p2a-synthetic", display_name: "Ana Reyes" },
    intake,
    intake_status: "DRAFT",
    intake_submitted_at: null,
  };
  const overrides = isStudent
    ? { [`/api/v1/routine-interviews/me/${routineId}`]: studentDetail }
    : {
        [`/api/v1/routine-interviews/${routineId}`]: counselorDetail,
        [`/api/v1/routine-interviews/${routineId}/encounter-candidates`]: { items: [], page: 1, page_size: 20, has_next: false },
      };
  return {
    role,
    overrides: {
      "/api/v1/auth/session": ({ reply }) => reply(session(role, capabilities)),
      ...overrides,
    },
  };
}

async function assertActionPlacement(page, name, labels, width) {
  if (!expectRails) return;
  const rail = page.getByRole("group", { name, exact: true });
  await shown(rail);
  assert.equal(await page.locator("[data-page-header-actions]").count(), 0, "detail actions are not duplicated in the heading");
  const expectedDirection = width >= 1024 ? "column" : "row";
  assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), expectedDirection);
  for (const [kind, label] of labels) {
    const action = rail.getByRole(kind, { name: label, exact: true });
    await shown(action);
    const surface = action.locator("[data-page-action-surface]");
    const box = await surface.boundingBox();
    assert.ok(box && Math.abs(box.width - 48) < 1 && Math.abs(box.height - 48) < 1, `${label} has a 48px square action surface`);
    await shown(action.locator("[data-page-action-label]"));
  }
}

await check("P2A Call Slip detail keeps authorized commands clear across widths", `/portal/call-slips/${slip.id}`, { handler: callSlipHandler("COUNSELOR") }, async (page) => {
  await shown(page.getByRole("heading", { name: "Call Slip / Interview Permit", exact: true }));
  await shown(page.getByRole("heading", { name: "Operational actions", exact: true }));
  await shown(page.getByRole("link", { name: expectRails ? "Open Referral REF-P2A-0007" : "Open linked Referral REF-P2A-0007", exact: true }));
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await assertActionPlacement(page, "Call Slip page actions", [["button", "Download Call Slip"], ["link", "Open Referral REF-P2A-0007"]], width);
    if (expectRails && width === 1440) {
      assert.equal(await page.getByRole("link", { name: "Open Referral REF-P2A-0007", exact: true }).getAttribute("href"), "/portal/referrals/referral-p2a-synthetic");
    }
    await noHorizontalOverflow(page);
    if (width === 1440) await capture(page, "call-slip-counselor-expanded");
    if (width === 1024) await capture(page, "call-slip-narrow-desktop");
    if (width === 320) await capture(page, "call-slip-counselor-mobile");
  }
  const collapse = page.getByRole("button", { name: "Collapse navigation", exact: true });
  await collapse.click();
  await page.waitForTimeout(250);
  await capture(page, "call-slip-counselor-collapsed");
});

await check("P2A Student Call Slip keeps the PDF action near the mobile heading", `/portal/call-slips/${slip.id}`, { handler: callSlipHandler("STUDENT"), device: "phone" }, async (page) => {
  await shown(page.getByText("Show this Call Slip to your instructor and report to Guidance Office.", { exact: true }));
  await hidden(page.getByRole("heading", { name: "Operational actions", exact: true }));
  const download = page.getByRole("button", { name: "Download Call Slip", exact: true });
  await shown(download);
  if (expectRails) {
    const rail = page.getByRole("group", { name: "Call Slip page actions", exact: true });
    await shown(rail);
    assert.equal(await rail.evaluate((element) => getComputedStyle(element).flexDirection), "row");
    const actionBox = await rail.boundingBox();
    const summaryBox = await page.locator("#student-call-slip-summary").boundingBox();
    assert.ok(actionBox && summaryBox && actionBox.y < summaryBox.y, "Mobile actions precede the record summary");
  }
  for (const width of [320, 375, 390, 768]) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await noHorizontalOverflow(page);
  }
  await capture(page, "call-slip-student-mobile");
});

await check("P2A Service detail preserves distinct booking pathways and management access", `/portal/services/${p2aService.id}`, { handler: serviceHandler }, async (page) => {
  await shown(page.getByRole("heading", { level: 1, name: p2aService.name, exact: true }));
  for (const label of ["Flexible individual appointments", "Fixed-date appointment slots", "Group sessions and events"]) await shown(page.getByText(label, { exact: true }).first());
  await shown(page.getByRole("button", { name: "Disable Service", exact: true }));
  await shown(page.getByRole("heading", { name: "Fixed-date appointment slots", exact: true }));
  await shown(page.getByRole("heading", { name: "Group Sessions & Events", exact: true }));
  await shown(page.getByText("No fixed-date appointment slots published yet.", { exact: true }));
  await shown(page.getByText("No group sessions match this view.", { exact: true }));
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await assertActionPlacement(page, "Service page actions", [["link", "Edit Service"]], width);
    if (expectRails && width === 1440) assert.equal(await page.getByRole("link", { name: "Edit Service", exact: true }).getAttribute("href"), "/portal/services/service-p2a-synthetic/edit");
    await noHorizontalOverflow(page);
    if (width === 1440) await capture(page, "service-detail-desktop");
    if (width === 1024) await capture(page, "service-detail-narrow-desktop");
  }
});

await check("P2A Assessment Record keeps confidential content and edit access scoped", `/portal/assessment-records/${recordId}`, assessmentWorld().options(), async (page) => {
  await shown(page.getByRole("heading", { name: "Assessment Record", exact: true }));
  await shown(page.getByText(content.score, { exact: true }));
  await shown(page.getByText("Confidential institutional record. Score and interpretation are recorded as supplied by the Guidance Office.", { exact: true }));
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await assertActionPlacement(page, "Assessment Record page actions", [["link", "Edit assessment record"]], width);
    if (expectRails && width === 1440) assert.equal(await page.getByRole("link", { name: "Edit assessment record", exact: true }).getAttribute("href"), `/portal/assessment-records/${recordId}/edit`);
    await noHorizontalOverflow(page);
    if (width === 1440) await capture(page, "assessment-record-desktop");
  }
});

await check("P2A Counselor Routine Interview distinguishes context from Student and Counselor work", `/portal/routine-interviews/${routineId}`, routineOptions("COUNSELOR"), async (page) => {
  await shown(page.getByRole("heading", { name: "Routine Interview", exact: true }));
  await shown(page.getByRole("link", { name: "Open Counseling workspace", exact: true }));
  await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
  await shown(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await assertActionPlacement(page, "Routine Interview page actions", [["link", "Open Counseling workspace"]], width);
    if (expectRails && width === 1440) assert.equal(await page.getByRole("link", { name: "Open Counseling workspace", exact: true }).getAttribute("href"), "/portal/counseling/workspace/appointment/appointment-p2a");
    await noHorizontalOverflow(page);
    if (width === 1440) await capture(page, "routine-interview-counselor-desktop");
  }
});

await check("P2A Student Routine Interview keeps Intake work in its existing form flow", `/portal/routine-interviews/${routineId}`, routineOptions("STUDENT"), async (page) => {
  await shown(page.getByRole("heading", { name: "Routine Interview", exact: true }));
  await shown(page.getByRole("heading", { name: "Student Intake", exact: true }));
  await shown(page.getByRole("button", { name: "Save progress", exact: true }));
  await hidden(page.getByRole("heading", { name: "Counselor Evaluation", exact: true }));
  await hidden(page.getByRole("link", { name: "Open Counseling workspace", exact: true }));
  await hidden(page.getByRole("group", { name: "Routine Interview page actions", exact: true }));
  for (const width of [320, 375, 390, 768]) {
    await page.setViewportSize({ width, height: width < 400 ? 820 : 900 });
    await noHorizontalOverflow(page);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await capture(page, "routine-interview-student-mobile");
});

await finish();
