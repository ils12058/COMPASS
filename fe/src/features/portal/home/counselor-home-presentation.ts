import { CalendarClock, type LucideIcon } from "lucide-react";
import { canManageAvailability } from "@/features/availability/availability-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { portalWorkspaceGroups } from "@/features/portal/components/portal-workspaces";
import { DesignationCode, type UserSummary } from "@/lib/api/generated/model";

export type CounselorHomeDestination = {
  href: string;
  label: string;
  description: string;
};

const COUNSELOR_DESTINATIONS: CounselorHomeDestination[] = [
  {
    href: "/portal/routine-interviews",
    label: "Routine Interviews",
    description: "Continue authorized intake and evaluation work.",
  },
  {
    href: "/portal/follow-ups",
    label: "Follow-Ups",
    description: "Review assigned Guidance follow-up work.",
  },
  {
    href: "/portal/counseling",
    label: "Counseling",
    description: "Open assigned Counseling records.",
  },
  {
    href: "/portal/messages",
    label: "Messages",
    description: "Continue authorized Guidance conversations.",
  },
  {
    href: "/portal/assessment-records",
    label: "Assessment Records",
    description: "Open records available to you.",
  },
  {
    href: "/portal/operations",
    label: "Guidance operations",
    description: "Open your authorized operational workspaces.",
  },
  {
    href: "/portal/referrals",
    label: "Referrals",
    description: "Continue authorized Referral work.",
  },
  {
    href: "/portal/call-slips",
    label: "Call Slips",
    description: "Open Call Slips available to you.",
  },
  {
    href: "/portal/good-moral",
    label: "Good Moral",
    description: "Continue authorized preparation or issuance.",
  },
];

const HEAD_OVERSIGHT_DESTINATIONS: CounselorHomeDestination[] = [
  {
    href: "/portal/reports",
    label: "Reports",
    description: "Open the reports available to you.",
  },
  {
    href: "/portal/organization",
    label: "Organization",
    description: "Open authorized organization responsibilities.",
  },
  {
    href: "/portal/availability",
    label: "Availability",
    description: "Manage the schedules available to you.",
  },
  {
    href: "/portal/services",
    label: "Services",
    description: "Open authorized service configuration.",
  },
];

function visibleWorkspaceHrefs(user: UserSummary): Set<string> {
  return new Set(portalWorkspaceGroups(user).flatMap((group) => group.links.map((link) => link.href)));
}

export function isHeadGuidanceCounselor(user: UserSummary): boolean {
  return user.role === "COUNSELOR" && user.designations.includes(DesignationCode.HEAD_GUIDANCE_COUNSELOR);
}

export function getCounselorHomeDestinations(user: UserSummary) {
  if (user.role !== "COUNSELOR") return [];
  const visible = visibleWorkspaceHrefs(user);
  return withIcons(user, COUNSELOR_DESTINATIONS.filter((destination) => visible.has(destination.href)).slice(0, 4));
}

export function getHeadGuidanceHomeDestinations(user: UserSummary) {
  if (!isHeadGuidanceCounselor(user)) return [];

  const visible = visibleWorkspaceHrefs(user);
  return withIcons(user, HEAD_OVERSIGHT_DESTINATIONS.filter((destination) => {
    if (destination.href === "/portal/availability" && !canManageAvailability(user)) return false;
    return visible.has(destination.href);
  }).concat(
    getAppointmentAccess(user).canManage && visible.has("/portal/appointments")
      ? [{
          href: "/portal/appointments/manage",
          label: "Manage appointments",
          description: "Open the Appointments you are authorized to manage.",
        }]
      : [],
  ).slice(0, 5));
}

function withIcons(user: UserSummary, destinations: CounselorHomeDestination[]): (CounselorHomeDestination & { icon: LucideIcon })[] {
  const icons = new Map(portalWorkspaceGroups(user).flatMap((group) => group.links).map((link) => [link.href, link.icon]));
  return destinations.map((destination) => ({ ...destination, icon: icons.get(destination.href) ?? CalendarClock }));
}
