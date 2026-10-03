import {
  getAppointmentAccess,
} from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { designationLabels, isDesignationCode } from "@/features/accounts/presentation";
import { userRoleLabel } from "@/features/portal/components/portal-presentation";
import { DesignationCode, type OverviewSummaryResponse, type UserSummary } from "@/lib/api/generated/model";

export type OverviewMetric = {
  label: string;
  value: number;
  href?: string;
};

function addMetric(
  metrics: OverviewMetric[],
  label: string,
  value: number | null | undefined,
  href?: string,
) {
  if (value !== null && value !== undefined) metrics.push({ label, value, href });
}

// The Overview counts Scheduled Appointments that have not started; these links open that
// same population rather than every Scheduled Appointment.
const MY_UPCOMING_APPOINTMENTS = "/portal/appointments/my?status=UPCOMING";
const MANAGED_UPCOMING_APPOINTMENTS = "/portal/appointments/manage?status=UPCOMING";
// Submitted intake with an evaluation that is not finalized, as counted on the Overview.
export const PENDING_ROUTINE_EVALUATIONS = "/portal/routine-interviews?intake_status=SUBMITTED&evaluation_status=DRAFT";
export const REQUESTED_GOOD_MORAL = "/portal/good-moral?status=REQUESTED";

function appointmentHref(user: UserSummary): string | undefined {
  const access = getAppointmentAccess(user);
  if (access.canViewSelf) return MY_UPCOMING_APPOINTMENTS;
  if (access.canManage) return MANAGED_UPCOMING_APPOINTMENTS;
  return undefined;
}

export function getOverviewMetrics(
  summary: OverviewSummaryResponse,
  user: UserSummary,
): OverviewMetric[] {
  const metrics: OverviewMetric[] = [];
  const appointments = appointmentHref(user);
  const routineAccess = getRoutineInterviewAccess(user);
  const goodMoralAccess = getGoodMoralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);

  if (summary.student) {
    addMetric(
      metrics,
      "Upcoming appointments",
      summary.student.upcoming_appointments_count,
      appointments,
    );
    addMetric(
      metrics,
      "Routine Interview drafts",
      summary.student.routine_intake_draft_count,
      routineAccess.hasWorkspace ? "/portal/routine-interviews" : undefined,
    );
    addMetric(
      metrics,
      "Good Moral requests",
      summary.student.good_moral_requested_count,
      goodMoralAccess.hasWorkspace ? "/portal/good-moral" : undefined,
    );
    addMetric(
      metrics,
      "Active Call Slips",
      summary.student.active_call_slip_count,
      callSlipAccess.hasWorkspace ? "/portal/call-slips?state=ACTIVE" : undefined,
    );
  }

  if (summary.guidance) {
    addMetric(
      metrics,
      "Your upcoming appointments",
      summary.guidance.upcoming_self_appointments_count,
      getAppointmentAccess(user).canViewSelf ? MY_UPCOMING_APPOINTMENTS : undefined,
    );
    addMetric(
      metrics,
      "Upcoming managed appointments",
      summary.guidance.upcoming_managed_appointments_count,
      getAppointmentAccess(user).canManage ? MANAGED_UPCOMING_APPOINTMENTS : undefined,
    );
    addMetric(
      metrics,
      "Routine evaluations pending",
      summary.guidance.routine_evaluation_pending_count,
      routineAccess.hasWorkspace ? PENDING_ROUTINE_EVALUATIONS : undefined,
    );
    addMetric(
      metrics,
      "Good Moral requests",
      summary.guidance.good_moral_requested_count,
      goodMoralAccess.hasWorkspace ? REQUESTED_GOOD_MORAL : undefined,
    );
    addMetric(
      metrics,
      "Active Call Slips",
      summary.guidance.active_call_slip_count,
      callSlipAccess.hasWorkspace ? "/portal/call-slips?state=ACTIVE" : undefined,
    );
  }

  return metrics;
}

export type EmailDeliveryStatus = {
  failed: number;
  pending: number;
  duePending: number;
  sentToday: number;
  href?: string;
};

// Platform email counts read better as one status line than as four separate tiles.
export function getEmailDeliveryStatus(
  summary: OverviewSummaryResponse,
  user: UserSummary,
): EmailDeliveryStatus | null {
  if (!summary.platform) return null;
  return {
    failed: summary.platform.email_failed_count ?? 0,
    pending: summary.platform.email_pending_count ?? 0,
    duePending: summary.platform.email_due_pending_count ?? 0,
    sentToday: summary.platform.email_sent_today_count ?? 0,
    href: user.capabilities.includes("platform_operations.view")
      ? "/portal/platform/email-delivery"
      : undefined,
  };
}

export type OverviewPrimaryAction = { label: string; href: string };

// The one task worth a button above the fold. Everything else is already in the sidebar.
export function getOverviewPrimaryAction(user: UserSummary): OverviewPrimaryAction | null {
  return getAppointmentAccess(user).canBook
    ? { label: "Book appointment", href: "/portal/appointments/book" }
    : null;
}

export function getOverviewGreeting(user: UserSummary): string | null {
  const firstName = user.first_name.trim();
  if (firstName) return "Welcome, " + firstName + ".";
  const fullName = [user.first_name, user.last_name].map((part) => part.trim()).filter(Boolean).join(" ");
  return fullName ? "Welcome, " + fullName + "." : null;
}

export function getOverviewRoleContext(user: UserSummary): string | null {
  const designation = user.designations
    .filter(isDesignationCode)
    .find((code) =>
      (code === DesignationCode.HEAD_GUIDANCE_COUNSELOR && user.role === "COUNSELOR") ||
      (code === DesignationCode.DPO && user.role === "INSTITUTIONAL_OFFICER"),
    );
  return designation ? userRoleLabel(user.role) + " · " + designationLabels[designation] : null;
}
