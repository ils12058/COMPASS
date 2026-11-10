import {
  Award,
  BellRing,
  BookOpen,
  Building2,
  CalendarClock,
  CalendarRange,
  ChartColumn,
  ClipboardList,
  Clock3,
  DoorOpen,
  FileText,
  Forward,
  GraduationCap,
  HeartHandshake,
  ListChecks,
  LayoutDashboard,
  Megaphone,
  MessageCircle,
  MessageCircleHeart,
  MessageSquareText,
  MessagesSquare,
  ScrollText,
  ServerCog,
  ShieldCheck,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

import { getAssessmentRecordsAccess } from "@/features/assessment-records/assessment-records-access";
import { canManageAnnouncements } from "@/features/announcements/announcements-access";
import { hasAvailabilityWorkspace } from "@/features/availability/availability-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { followupAccess } from "@/features/guidance-followups/followups-access";
import { getGuidanceMessagesAccess } from "@/features/guidance-messages/guidance-messages-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { canAttemptReports } from "@/features/reports/reports-access";
import { canViewOwnAcademicRecord } from "@/features/student-academics/student-academics-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { hasPrivacyGovernanceWorkspace } from "@/features/privacy-governance/privacy-governance-access";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { canManageResources } from "@/features/resources/resources-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { hasGroupSessionsWorkspace } from "@/features/group-sessions/group-sessions-access";
import { hasServicesWorkspace } from "@/features/services/services-access";
import {
  canEnterOrganization,
  canViewAcademicYears,
  canViewInstitutionalForms,
  hasInstitutionWorkspace,
} from "@/features/institution-configuration/institution-access";
import type { FacultyReferralAvailability, UserSummary } from "@/lib/api/generated/model";
import { facultyReferralAccess, facultyReferralsPath, facultySubmitPath, facultySubmissionAvailable } from "@/features/faculty-referrals/access";
import { hasStudentActions } from "@/features/student-actions/student-actions-access";
import { hasWorkQueue } from "@/features/work-queue/work-queue-access";
import { hasGuidanceOperations } from "@/features/guidance-operations/guidance-operations-access";

export type PortalWorkspaceLink = {
  href: string;
  label: string;
  icon: LucideIcon;
  // Platform Operations opens on its Health page but owns everything under /portal/platform.
  section?: string;
};

export type PortalWorkspaceGroup = { label: string; links: PortalWorkspaceLink[] };

type CandidateLink = PortalWorkspaceLink & { visible: boolean };

// The shared access-filtered registry for the dock, command palette and public quick access.
// Daily navigation orders this result; its role preferences never grant or remove a workspace.
export function portalWorkspaceGroups(user: UserSummary, facultyAvailability?: FacultyReferralAvailability): PortalWorkspaceGroup[] {
  if (user.role === "FACULTY") {
    const access = facultyReferralAccess(user);
    const links: PortalWorkspaceLink[] = [];
    if (access.submit && facultySubmissionAvailable(facultyAvailability)) links.push({ href: facultySubmitPath, label: "Submit Referral", icon: Forward });
    if (access.read && facultyAvailability?.can_view_submissions) links.push({ href: facultyReferralsPath, label: "My Referrals", icon: FileText });
    // Guidance Office inquiries only: the workspace gate decides, and templates stay staff-only.
    const messages: PortalWorkspaceLink[] = getGuidanceMessagesAccess(user).hasWorkspace
      ? [{ href: "/portal/messages", label: "Messages", icon: MessageCircle }]
      : [];
    const groups: PortalWorkspaceGroup[] = [];
    if (links.length) groups.push({ label: "Referrals", links });
    if (messages.length) groups.push({ label: "Communication", links: messages });
    return groups;
  }
  const canManageAccounts = user.capabilities.includes("accounts.manage");
  const hasOrganization = canEnterOrganization(user);
  const hasAcademicYears = canViewAcademicYears(user);
  const hasInstitutionalForms = canViewInstitutionalForms(user);
  const hasInstitution = hasInstitutionWorkspace(user);
  const hasServices = hasServicesWorkspace(user);
  const hasAvailability = hasAvailabilityWorkspace(user);
  const hasAppointments = getAppointmentAccess(user).hasWorkspace;
  const hasReminders = getAppointmentAccess(user).canManage || getGraduateTracerAccess(user).canViewOperational;
  const hasGroupSessions = hasGroupSessionsWorkspace(user);
  // Students with their own Messages, and Guidance staff with Messages for their workload. No other
  // role or designation (IT Admin, Institutional Officer, Head, DPO) adds it.
  const hasMessages = getGuidanceMessagesAccess(user).hasWorkspace;
  const hasAssessmentRecords = getAssessmentRecordsAccess(user).canView;
  const hasInventory = getInventoryAccess(user).hasWorkspace;
  const hasRoutineInterviews = getRoutineInterviewAccess(user).hasWorkspace;
  const hasCounseling = getCounselingAccess(user).hasWorkspace;
  const hasReferrals = getReferralAccess(user).hasWorkspace;
  const hasCallSlips = getCallSlipAccess(user).hasWorkspace;
  // Students who can submit Feedback reach the same entry page as the reviewing staff.
  const hasFeedback = getFeedbackAccess(user).canOpenFeedback;
  const hasGoodMoral = getGoodMoralAccess(user).hasWorkspace;
  const exitInterviews = getExitInterviewAccess(user);
  const hasExitInterviews = exitInterviews.hasWorkspace;
  // Label by the account's resolved actions, never its role: reviewers and Students see their
  // Exit Interviews; access management without review authority is named for what it manages.
  const exitInterviewsLabel =
    exitInterviews.canManageOpportunities &&
    !exitInterviews.canViewOperational &&
    !exitInterviews.hasStudentWorkspace
      ? "Exit Interview access"
      : "Exit Interviews";
  const hasGraduateTracer = getGraduateTracerAccess(user).hasWorkspace;
  const hasMyAcademicRecord = canViewOwnAcademicRecord(user);
  const hasPlatformOperations = user.capabilities.includes(
    "platform_operations.view",
  );
  const hasReports = canAttemptReports(user);
  const hasAnnouncements = canManageAnnouncements(user);
  const hasResources = canManageResources(user);
  const hasPrivacyGovernance = hasPrivacyGovernanceWorkspace(user);

  // Daily work comes first; institution setup and administration sit at the end.
  const groups: { label: string; links: CandidateLink[] }[] = [
    {
      label: "Daily work",
      links: [
        { href: "/portal/actions", label: "My actions", icon: ClipboardList, visible: hasStudentActions(user) },
        { href: "/portal/follow-ups", label: "Follow-Ups", icon: ListChecks, visible: followupAccess(user).view },
        { href: "/portal/work", label: "My work", icon: ClipboardList, visible: hasWorkQueue(user) },
        { href: "/portal/operations", label: "Guidance operations", icon: ListChecks, visible: hasGuidanceOperations(user) },
      ],
    },
    {
      label: "Scheduling",
      links: [
        { href: "/portal/appointments", label: "Appointments", icon: CalendarClock, visible: hasAppointments },
        { href: "/portal/reminders", label: "Reminders", icon: BellRing, visible: hasReminders },
        { href: "/portal/group-sessions", label: "Group Sessions", icon: UsersRound, visible: hasGroupSessions },
        { href: "/portal/availability", label: "Availability", icon: Clock3, visible: hasAvailability },
        { href: "/portal/services", label: "Services", icon: HeartHandshake, visible: hasServices },
      ],
    },
    {
      label: "Communication",
      links: [{ href: "/portal/messages", label: "Messages", icon: MessageCircle, visible: hasMessages }],
    },
    {
      label: "Records",
      links: [
        { href: "/portal/assessment-records", label: "Assessment Records", icon: ClipboardList, visible: hasAssessmentRecords },
        { href: "/portal/routine-interviews", label: "Routine Interviews", icon: MessagesSquare, visible: hasRoutineInterviews },
        { href: "/portal/counseling", label: "Counseling", icon: MessageCircleHeart, visible: hasCounseling },
        { href: "/portal/referrals", label: "Referrals", icon: Forward, visible: hasReferrals },
        { href: "/portal/call-slips", label: "Call Slips", icon: ScrollText, visible: hasCallSlips },
        { href: "/portal/inventory", label: "Individual Inventory", icon: ClipboardList, visible: hasInventory },
        { href: "/portal/academic-record", label: "Academic Record", icon: GraduationCap, visible: hasMyAcademicRecord },
      ],
    },
    {
      label: "Requests and surveys",
      links: [
        { href: "/portal/good-moral", label: "Good Moral", icon: Award, visible: hasGoodMoral },
        { href: "/portal/exit-interviews", label: exitInterviewsLabel, icon: DoorOpen, visible: hasExitInterviews },
        { href: "/portal/graduate-tracer", label: "Graduate Tracer", icon: GraduationCap, visible: hasGraduateTracer },
        { href: "/portal/feedback", label: "Feedback", icon: MessageSquareText, visible: hasFeedback },
      ],
    },
    {
      label: "Content",
      links: [
        { href: "/portal/announcements", label: "Announcements", icon: Megaphone, visible: hasAnnouncements },
        { href: "/portal/resources", label: "Resources", icon: BookOpen, visible: hasResources },
      ],
    },
    {
      label: "Reports",
      links: [{ href: "/portal/reports", label: "Reports", icon: ChartColumn, visible: hasReports }],
    },
    {
      label: "Institution",
      links: [
        { href: "/portal/organization", label: "Organization", icon: Building2, visible: hasInstitution && hasOrganization },
        { href: "/portal/academic-years", label: "Academic Years", icon: CalendarRange, visible: hasInstitution && hasAcademicYears },
        { href: "/portal/institutional-forms", label: "Institutional Forms", icon: FileText, visible: hasInstitution && hasInstitutionalForms },
      ],
    },
    {
      label: "Identity & Access",
      links: [
        { href: "/portal/accounts", label: "Accounts", icon: UsersRound, visible: canManageAccounts },
      ],
    },
    {
      label: "Privacy",
      links: [
        { href: "/portal/privacy", label: "Privacy Governance", icon: ShieldCheck, visible: hasPrivacyGovernance },
      ],
    },
    {
      label: "Platform",
      links: [
        {
          href: "/portal/platform/health",
          label: "Platform Operations",
          icon: ServerCog,
          visible: hasPlatformOperations,
          section: "/portal/platform",
        },
      ],
    },
  ];
  return groups
    .map((group) => ({
      label: group.label,
      links: group.links
        .filter((link) => link.visible)
        .map((link) => ({ href: link.href, label: link.label, icon: link.icon, section: link.section })),
    }))
    .filter((group) => group.links.length > 0);
}

export const portalHomeLink: PortalWorkspaceLink = { href: "/portal", label: "Home", icon: LayoutDashboard };

// Formal page names remain unchanged. The short menu labels also appear in destination search,
// which retains each registry label as an alias.
export function portalNavigationLabel(link: PortalWorkspaceLink): string {
  const labels: Readonly<Record<string, string>> = {
    "/portal/group-sessions": "Group sessions",
    "/portal/routine-interviews": "Routine interviews",
    "/portal/call-slips": "Call slips",
    "/portal/inventory": "Inventory",
    "/portal/academic-record": "Academic record",
    "/portal/follow-ups": "Follow-ups",
    "/portal/operations": "Office workload",
    "/portal/assessment-records": "Assessment records",
    "/portal/academic-years": "Academic years",
    "/portal/institutional-forms": "Institutional forms",
    "/portal/platform/health": "Platform",
    "/portal/privacy": "Privacy governance",
  };
  if (link.href === "/portal/exit-interviews" && link.label === "Exit Interviews") return "Exit interviews";
  return labels[link.href] ?? link.label;
}

// Approved F2 ordering preferences, not allowlists. Keep additional effective grants and new
// registry destinations at the end of the secondary list in their original registry order.
const navigationOrder = {
  "Student": {
    daily: ["actions", "appointments", "messages", "inventory", "good-moral"],
    more: ["group-sessions", "routine-interviews", "counseling", "call-slips", "academic-record", "exit-interviews", "feedback"],
  },
  "Alumni": {
    daily: ["actions", "graduate-tracer", "good-moral", "messages"],
    more: ["appointments", "group-sessions", "routine-interviews", "counseling", "call-slips", "inventory", "academic-record", "exit-interviews", "feedback"],
  },
  "Faculty": {
    daily: ["faculty/referrals/new", "faculty/referrals", "messages"],
    more: [],
  },
  "Head": {
    daily: ["work", "operations", "appointments", "messages", "counseling", "reports"],
    more: ["follow-ups", "reminders", "group-sessions", "availability", "services", "assessment-records", "routine-interviews", "referrals", "call-slips", "inventory", "good-moral", "exit-interviews", "graduate-tracer", "feedback", "announcements", "resources", "organization", "academic-years", "institutional-forms"],
  },
  "Counselor": {
    daily: ["work", "appointments", "messages", "counseling", "routine-interviews", "follow-ups"],
    more: ["operations", "reminders", "group-sessions", "availability", "referrals", "call-slips", "inventory", "good-moral", "announcements", "resources", "reports", "organization", "academic-years", "institutional-forms"],
  },
  "GOA": {
    daily: ["work", "appointments", "messages", "good-moral", "call-slips", "referrals"],
    more: ["follow-ups", "operations", "reminders", "group-sessions", "counseling", "exit-interviews", "announcements", "resources", "organization", "academic-years", "institutional-forms"],
  },
  "IT Admin": {
    daily: ["accounts", "platform/health", "organization"],
    more: ["availability", "services"],
  },
  "DPO": {
    daily: ["privacy"],
    more: [],
  },
} as const;

export function portalNavigationGroups(user: UserSummary, facultyAvailability?: FacultyReferralAvailability) {
  const links = portalWorkspaceGroups(user, facultyAvailability).flatMap((group) => group.links);
  const profile = user.role === "STUDENT" ? (user.student_lifecycle_status === "GRADUATED" ? "Alumni" : "Student")
    : user.role === "COUNSELOR" ? (user.designations.includes("HEAD_GUIDANCE_COUNSELOR") ? "Head" : "Counselor")
      : user.role === "GUIDANCE_OFFICE_ASSISTANT" ? "GOA"
        : user.role === "IT_ADMIN" ? "IT Admin"
          : user.role === "FACULTY" ? "Faculty" : "DPO";
  const order = navigationOrder[profile];
  const remaining = new Map(links.map((link) => [link.href, { ...link, label: portalNavigationLabel(link) }]));
  const take = (slugs: readonly string[]) => slugs.flatMap((slug) => {
    const href = `/portal/${slug}`;
    const link = remaining.get(href);
    if (!link) return [];
    remaining.delete(href);
    return [link];
  });
  const daily = [portalHomeLink, ...take(order.daily)];
  const secondary = { label: user.role === "IT_ADMIN" ? "Administration" : "More", links: [...take(order.more), ...remaining.values()] };
  return { daily, secondary };
}
