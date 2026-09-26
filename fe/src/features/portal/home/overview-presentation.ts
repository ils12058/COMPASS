import {
  getAppointmentAccess,
} from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { canManageOrganization, canViewAcademicYears, canViewInstitutionalForms } from "@/features/institution-configuration/institution-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { hasPrivacyGovernanceWorkspace } from "@/features/privacy-governance/privacy-governance-access";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { canAttemptReports } from "@/features/reports/reports-access";
import { hasServicesWorkspace } from "@/features/services/services-access";
import { designationLabels, isDesignationCode } from "@/features/accounts/presentation";
import { userRoleLabel } from "@/features/portal/components/portal-presentation";
import { DesignationCode, type OverviewSummaryResponse, type UserSummary } from "@/lib/api/generated/model";

export type OverviewMetric = {
  label: string;
  value: number;
  href?: string;
};

export type OverviewQuickAccessLink = {
  label: string;
  href: string;
};

function addMetric(
  metrics: OverviewMetric[],
  label: string,
  value: number | null | undefined,
  href?: string,
) {
  if (value !== null && value !== undefined) metrics.push({ label, value, href });
}

function appointmentHref(user: UserSummary): string | undefined {
  const access = getAppointmentAccess(user);
  if (access.canViewSelf) return "/portal/appointments/my";
  if (access.canManage) return "/portal/appointments/manage";
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
  const canViewEmailDeliveries = user.capabilities.includes("platform_operations.view");

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
      callSlipAccess.hasWorkspace ? "/portal/call-slips" : undefined,
    );
  }

  if (summary.guidance) {
    addMetric(
      metrics,
      "Your upcoming appointments",
      summary.guidance.upcoming_self_appointments_count,
      getAppointmentAccess(user).canViewSelf ? "/portal/appointments/my" : undefined,
    );
    addMetric(
      metrics,
      "Upcoming managed appointments",
      summary.guidance.upcoming_managed_appointments_count,
      getAppointmentAccess(user).canManage ? "/portal/appointments/manage" : undefined,
    );
    addMetric(
      metrics,
      "Routine evaluations pending",
      summary.guidance.routine_evaluation_pending_count,
      routineAccess.hasWorkspace ? "/portal/routine-interviews" : undefined,
    );
    addMetric(
      metrics,
      "Good Moral requests",
      summary.guidance.good_moral_requested_count,
      goodMoralAccess.hasWorkspace ? "/portal/good-moral" : undefined,
    );
    addMetric(
      metrics,
      "Active Call Slips",
      summary.guidance.active_call_slip_count,
      callSlipAccess.hasWorkspace ? "/portal/call-slips" : undefined,
    );
  }

  if (summary.platform) {
    const emailHref = canViewEmailDeliveries
      ? "/portal/platform/email-delivery"
      : undefined;
    addMetric(metrics, "Pending email deliveries", summary.platform.email_pending_count, emailHref);
    addMetric(metrics, "Due pending deliveries", summary.platform.email_due_pending_count, emailHref);
    addMetric(metrics, "Failed email deliveries", summary.platform.email_failed_count, emailHref);
    addMetric(metrics, "Email deliveries sent today", summary.platform.email_sent_today_count, emailHref);
  }

  if (summary.privacy) {
    // Active incidents have no single backend status filter, so that metric
    // opens the unfiltered incident list.
    const hasPrivacy = hasPrivacyGovernanceWorkspace(user);
    addMetric(
      metrics,
      "Open privacy reviews",
      summary.privacy.open_review_count,
      hasPrivacy ? "/portal/privacy/reviews?status=OPEN" : undefined,
    );
    addMetric(
      metrics,
      "Active privacy incidents",
      summary.privacy.active_incident_count,
      hasPrivacy ? "/portal/privacy/incidents" : undefined,
    );
  }

  return metrics;
}

export function getOverviewQuickAccess(user: UserSummary): OverviewQuickAccessLink[] {
  const links = new Map<string, OverviewQuickAccessLink>();
  const add = (key: string, label: string, href: string | null | undefined) => {
    if (href) links.set(key, { label, href });
  };

  const appointmentAccess = getAppointmentAccess(user);
  if (appointmentAccess.canBook) {
    add("appointments", "Book appointment", "/portal/appointments/book");
  } else if (appointmentAccess.canViewSelf) {
    add("appointments", "Appointments", "/portal/appointments/my");
  } else if (appointmentAccess.canManage) {
    add("appointments", "Appointments", "/portal/appointments/manage");
  }

  const routineAccess = getRoutineInterviewAccess(user);
  const inventoryAccess = getInventoryAccess(user);
  const exitAccess = getExitInterviewAccess(user);
  const graduateAccess = getGraduateTracerAccess(user);
  const counselingAccess = getCounselingAccess(user);
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const goodMoralAccess = getGoodMoralAccess(user);
  const feedbackAccess = getFeedbackAccess(user);
  const canViewPlatform = user.capabilities.includes("platform_operations.view");
  const hasPrivacy = hasPrivacyGovernanceWorkspace(user);

  add("privacy", "Privacy Governance", hasPrivacy ? "/portal/privacy" : undefined);
  add("services", "Services", hasServicesWorkspace(user) ? "/portal/services" : undefined);
  add("inventory", "Individual Inventory", inventoryAccess.hasWorkspace ? "/portal/inventory" : undefined);
  add("routine", "Routine Interviews", routineAccess.hasWorkspace ? "/portal/routine-interviews" : undefined);
  add("exit", "Exit Interviews", exitAccess.hasWorkspace ? "/portal/exit-interviews" : undefined);
  add("graduate", "Graduate Tracer", graduateAccess.hasWorkspace ? "/portal/graduate-tracer" : undefined);
  add("counseling", "Counseling", counselingAccess.hasWorkspace ? "/portal/counseling" : undefined);
  add("referrals", "Referrals", referralAccess.hasWorkspace ? "/portal/referrals" : undefined);
  add("call-slips", "Call Slips", callSlipAccess.hasWorkspace ? "/portal/call-slips" : undefined);
  add("good-moral", "Good Moral", goodMoralAccess.hasWorkspace ? "/portal/good-moral" : undefined);
  add("feedback", "Feedback", feedbackAccess.hasWorkspace ? "/portal/feedback" : undefined);
  add("reports", "Reports", canAttemptReports(user) ? "/portal/reports" : undefined);
  add("accounts", "Accounts", user.capabilities.includes("accounts.manage") ? "/portal/accounts" : undefined);
  add(
    "platform",
    "Platform Operations",
    canViewPlatform ? "/portal/platform" : undefined,
  );

  add("organization", "Organization", canManageOrganization(user) ? "/portal/organization" : undefined);
  add("academic-years", "Academic Years", canViewAcademicYears(user) ? "/portal/academic-years" : undefined);
  add("institutional-forms", "Institutional Forms", canViewInstitutionalForms(user) ? "/portal/institutional-forms" : undefined);

  const isHeadGuidance =
    user.role === "COUNSELOR" &&
    user.designations.includes(DesignationCode.HEAD_GUIDANCE_COUNSELOR);
  const priorities =
    user.role === "STUDENT"
      ? ["appointments", "good-moral", "feedback"]
      : user.role === "GUIDANCE_SERVICES_STAFF"
        ? ["appointments", "referrals", "call-slips"]
        : user.role === "COUNSELOR" && isHeadGuidance
          ? ["appointments", "routine", "reports", "call-slips", "exit", "graduate", "organization"]
          : user.role === "COUNSELOR"
            ? ["appointments", "routine", "counseling", "referrals", "call-slips", "reports"]
            : canViewPlatform
              ? ["accounts", "platform", "organization", "academic-years", "institutional-forms"]
              : ["organization", "academic-years", "institutional-forms", "appointments", "platform"];

  // Privacy Governance leads for anyone holding the capability, whatever
  // their role; it is not tied to the DPO designation.
  const selected = (hasPrivacy ? ["privacy", ...priorities] : priorities)
    .map((key) => links.get(key))
    .filter((link): link is OverviewQuickAccessLink => Boolean(link))
    .slice(0, 6);

  if (selected.length > 0) return selected;
  return Array.from(links.values()).slice(0, 6);
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

export type OverviewUpcomingItem = {
  message: string;
  href: string;
  linkLabel: string;
};

export function getOverviewUpcomingItems(
  summary: OverviewSummaryResponse,
  user: UserSummary,
): OverviewUpcomingItem[] {
  const items: OverviewUpcomingItem[] = [];
  const countLabel = (count: number, noun: string) =>
    count + " upcoming " + noun + (count === 1 ? "" : "s");
  const access = getAppointmentAccess(user);

  if (
    summary.student?.upcoming_appointments_count !== null &&
    summary.student?.upcoming_appointments_count !== undefined &&
    summary.student.upcoming_appointments_count > 0 &&
    access.canViewSelf
  ) {
    items.push({
      message: "You have " + countLabel(summary.student.upcoming_appointments_count, "appointment") + ".",
      href: "/portal/appointments/my",
      linkLabel: "View appointments",
    });
  }

  if (user.role === "COUNSELOR" && summary.guidance?.upcoming_self_appointments_count != null &&
      summary.guidance.upcoming_self_appointments_count > 0 && access.canViewSelf) {
    items.push({
      message: "You have " + countLabel(summary.guidance.upcoming_self_appointments_count, "appointment") + ".",
      href: "/portal/appointments/my",
      linkLabel: "View your appointments",
    });
  }

  if (user.role === "GUIDANCE_SERVICES_STAFF" &&
      summary.guidance?.upcoming_managed_appointments_count != null &&
      summary.guidance.upcoming_managed_appointments_count > 0 && access.canManage) {
    const count = summary.guidance.upcoming_managed_appointments_count;
    items.push({
      message:
        countLabel(count, "appointment") +
        (count === 1 ? " is" : " are") +
        " in your managed scope.",
      href: "/portal/appointments/manage",
      linkLabel: "Open managed appointments",
    });
  }

  return items;
}
