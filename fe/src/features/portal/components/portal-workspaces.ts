import {
  Award,
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
  Megaphone,
  MessageCircleHeart,
  MessageSquareText,
  MessagesSquare,
  ScrollText,
  ServerCog,
  ShieldCheck,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

import { canManageAnnouncements } from "@/features/announcements/announcements-access";
import { hasAvailabilityWorkspace } from "@/features/availability/availability-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import { getFeedbackAccess } from "@/features/feedback/feedback-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { canAttemptReports } from "@/features/reports/reports-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { hasPrivacyGovernanceWorkspace } from "@/features/privacy-governance/privacy-governance-access";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { canManageResources } from "@/features/resources/resources-access";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import { hasServicesWorkspace } from "@/features/services/services-access";
import {
  canManageOrganization,
  canViewAcademicYears,
  canViewInstitutionalForms,
  hasInstitutionWorkspace,
} from "@/features/institution-configuration/institution-access";
import type { UserSummary } from "@/lib/api/generated/model";

export type PortalWorkspaceLink = {
  href: string;
  label: string;
  icon: LucideIcon;
  // Platform Operations opens on its Health page but owns everything under /portal/platform.
  section?: string;
};

export type PortalWorkspaceGroup = { label: string; links: PortalWorkspaceLink[] };

type CandidateLink = PortalWorkspaceLink & { visible: boolean };

// The portal workspaces an account can open, grouped as the portal sidebar shows them. The sidebar
// and the public landing's quick access both read this list, so they never offer different places.
export function portalWorkspaceGroups(user: UserSummary): PortalWorkspaceGroup[] {
  const canManageAccounts = user.capabilities.includes("accounts.manage");
  const hasOrganization = canManageOrganization(user);
  const hasAcademicYears = canViewAcademicYears(user);
  const hasInstitutionalForms = canViewInstitutionalForms(user);
  const hasInstitution = hasInstitutionWorkspace(user);
  const hasServices = hasServicesWorkspace(user);
  const hasAvailability = hasAvailabilityWorkspace(user);
  const hasAppointments = getAppointmentAccess(user).hasWorkspace;
  const hasInventory = getInventoryAccess(user).hasWorkspace;
  const hasRoutineInterviews = getRoutineInterviewAccess(user).hasWorkspace;
  const hasCounseling = getCounselingAccess(user).hasWorkspace;
  const hasReferrals = getReferralAccess(user).hasWorkspace;
  const hasCallSlips = getCallSlipAccess(user).hasWorkspace;
  // Students who can submit Feedback reach the same entry page as the reviewing staff.
  const hasFeedback = getFeedbackAccess(user).canOpenFeedback;
  const hasGoodMoral = getGoodMoralAccess(user).hasWorkspace;
  const hasExitInterviews = getExitInterviewAccess(user).hasWorkspace;
  const hasGraduateTracer = getGraduateTracerAccess(user).hasWorkspace;
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
      label: "Scheduling",
      links: [
        { href: "/portal/appointments", label: "Appointments", icon: CalendarClock, visible: hasAppointments },
        { href: "/portal/availability", label: "Availability", icon: Clock3, visible: hasAvailability },
        { href: "/portal/services", label: "Services", icon: HeartHandshake, visible: hasServices },
      ],
    },
    {
      label: "Records",
      links: [
        { href: "/portal/routine-interviews", label: "Routine Interviews", icon: MessagesSquare, visible: hasRoutineInterviews },
        { href: "/portal/counseling", label: "Counseling", icon: MessageCircleHeart, visible: hasCounseling },
        { href: "/portal/referrals", label: "Referrals", icon: Forward, visible: hasReferrals },
        { href: "/portal/call-slips", label: "Call Slips", icon: ScrollText, visible: hasCallSlips },
        { href: "/portal/inventory", label: "Individual Inventory", icon: ClipboardList, visible: hasInventory },
      ],
    },
    {
      label: "Requests and surveys",
      links: [
        { href: "/portal/good-moral", label: "Good Moral", icon: Award, visible: hasGoodMoral },
        { href: "/portal/exit-interviews", label: user.role === "GUIDANCE_SERVICES_STAFF" ? "Exit Interview opportunities" : "Exit Interviews", icon: DoorOpen, visible: hasExitInterviews },
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
