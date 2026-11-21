import assert from "node:assert/strict";
import test from "node:test";

import { getAppointmentAccess } from "../src/features/appointments/appointments-access.ts";
import {
  COUNSELOR_BOOKING_HELP_TEXT,
  COUNSELOR_REQUEST_PENDING_LABEL,
  counselorRelationshipLabel,
  counselorRequestErrorMessage,
  counselorRequestStateLabel,
  isCounselorRequestStaleError,
  studentCollegeLabel,
} from "../src/features/appointments/counselor-request-presentation.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { getHeadGuidanceHomeDestinations } from "../src/features/portal/home/counselor-home-presentation.ts";
import { getOverviewMetrics } from "../src/features/portal/home/overview-presentation.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import {
  CounselorBookingRequestState,
  DesignationCode,
  NotificationTargetType,
  WorkKind,
} from "../src/lib/api/generated/model/index.ts";
import { homeWorld } from "./support/ux15-home-fixtures.mjs";

test("counselor relationship labels distinguish assigned default and Head-approved counselors", () => {
  assert.equal(counselorRelationshipLabel({ is_default: true, is_head_approved: false }), "Assigned to you");
  assert.equal(
    counselorRelationshipLabel({ is_default: false, is_head_approved: true }),
    "Approved by the Head Guidance Counselor",
  );
  assert.equal(counselorRelationshipLabel({ is_default: false, is_head_approved: false }), null);
});

test("request copy and error messages stay plain-language without internal terms", () => {
  assert.match(COUNSELOR_BOOKING_HELP_TEXT, /College's counselor/);
  assert.equal(
    counselorRequestStateLabel(CounselorBookingRequestState.PENDING),
    COUNSELOR_REQUEST_PENDING_LABEL,
  );
  assert.equal(counselorRequestStateLabel(CounselorBookingRequestState.APPROVED), "Approved");
  assert.equal(counselorRequestStateLabel(CounselorBookingRequestState.DECLINED), "Declined");
  assert.equal(
    studentCollegeLabel({ college_name: "College of Computing", campus_name: "Main Campus" }),
    "College of Computing · Main Campus",
  );
  assert.equal(
    studentCollegeLabel({ college_name: null, campus_name: null }),
    "No current College recorded",
  );

  const apiError = (status, code) =>
    new CompassApiError({
      status,
      body: { error: { code } },
      headers: {},
      method: "POST",
      url: "/api/v1/appointments",
    });

  const notPermitted = apiError(403, "appointment_counselor_not_permitted");
  const headUnavailable = apiError(409, "head_guidance_unavailable");
  const stale = apiError(409, "counselor_request_changed");

  assert.match(counselorRequestErrorMessage(notPermitted, "fallback"), /Head Guidance Counselor/);
  assert.match(counselorRequestErrorMessage(headUnavailable, "fallback"), /Guidance Office/);
  assert.equal(isCounselorRequestStaleError(stale), true);
  assert.equal(isCounselorRequestStaleError(headUnavailable), false);
});

test("only the Head Guidance Counselor with appointment management can review counselor requests", () => {
  const head = homeWorld({
    role: "COUNSELOR",
    designations: [DesignationCode.HEAD_GUIDANCE_COUNSELOR],
    capabilities: ["appointments.manage", "appointments.view_self"],
  }).account;
  const counselor = homeWorld({
    role: "COUNSELOR",
    designations: [],
    capabilities: ["appointments.manage", "appointments.view_self"],
  }).account;
  const goa = homeWorld({
    role: "GUIDANCE_OFFICE_ASSISTANT",
    designations: [],
    capabilities: ["appointments.manage"],
  }).account;
  const student = homeWorld({
    role: "STUDENT",
    capabilities: ["appointments.manage_self", "appointments.view_self"],
  }).account;

  assert.equal(getAppointmentAccess(head).canReviewCounselorRequests, true);
  assert.equal(getAppointmentAccess(counselor).canReviewCounselorRequests, false);
  assert.equal(getAppointmentAccess(goa).canReviewCounselorRequests, false);
  assert.equal(getAppointmentAccess(student).canReviewCounselorRequests, false);
});

test("Work Queue, Overview, Head Home, and Notifications route counselor requests cleanly", () => {
  const requestId = "12345678-1234-4234-8234-123456789abc";
  const work = presentWork({
    kind: WorkKind.COUNSELOR_BOOKING_REQUEST,
    source_id: requestId,
    due_at: null,
    waiting_since: "2026-11-20T01:00:00Z",
  });
  assert.equal(work.title, "Review different counselor request");
  assert.equal(work.href, `/portal/appointments/counselor-requests/${requestId}`);
  assert.equal(work.actionLabel, "Review request");

  const head = homeWorld({
    role: "COUNSELOR",
    designations: [DesignationCode.HEAD_GUIDANCE_COUNSELOR],
    capabilities: ["appointments.manage", "appointments.view_self"],
  }).account;
  const metrics = getOverviewMetrics(
    {
      guidance: {
        upcoming_self_appointments_count: 1,
        upcoming_managed_appointments_count: null,
        routine_evaluation_pending_count: 0,
        good_moral_requested_count: null,
        good_moral_ready_count: null,
        active_call_slip_count: 0,
        pending_counselor_requests_count: 2,
      },
    },
    head,
  );
  assert.ok(
    metrics.some(
      (metric) =>
        metric.label === "Different counselor requests" &&
        metric.value === 2 &&
        metric.href === "/portal/appointments/counselor-requests",
    ),
  );

  assert.ok(
    getHeadGuidanceHomeDestinations(head).some(
      (destination) => destination.href === "/portal/appointments/counselor-requests",
    ),
  );

  assert.deepEqual(
    notificationDestination(
      { target_type: NotificationTargetType.COUNSELOR_BOOKING_REQUEST, target_id: requestId },
      head.id,
    ),
    {
      href: `/portal/appointments/counselor-requests/${requestId}`,
      label: "Review counselor request",
    },
  );
  assert.deepEqual(
    notificationDestination(
      { target_type: NotificationTargetType.APPOINTMENT_BOOKING, target_id: requestId },
      "student-1",
    ),
    {
      href: "/portal/appointments/book",
      label: "Open Appointment booking",
    },
  );
});
