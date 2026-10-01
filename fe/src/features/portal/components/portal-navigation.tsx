"use client";

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
  LayoutDashboard,
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
import Image from "next/image";
import { usePathname } from "next/navigation";

import { canManageAnnouncements } from "@/features/announcements/announcements-access";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
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
import { usePortalSession } from "@/features/portal/components/portal-session";
import { cn } from "@/lib/utils/cn";

type NavLink = {
  href: string;
  label: string;
  icon: LucideIcon;
  visible: boolean;
  // Platform Operations opens on its Health page but owns everything under /portal/platform.
  section?: string;
};

type NavGroup = { label: string; links: NavLink[] };

function NavItem({
  link,
  current,
  onNavigate,
}: {
  link: NavLink;
  current: boolean;
  onNavigate?: () => void;
}) {
  const Icon = link.icon;

  return (
    <GuardedPortalLink
      href={link.href}
      onNavigate={onNavigate}
      aria-current={current ? "page" : undefined}
      className={cn(
        "relative flex min-h-10 items-center gap-3 rounded-md px-3 text-sm text-on-brand/85 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand",
        current
          ? "bg-on-brand/15 font-semibold text-on-brand before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-on-brand"
          : "font-medium hover:bg-on-brand/10 hover:text-on-brand",
      )}
    >
      <Icon size={18} aria-hidden="true" className="shrink-0" />
      <span className="min-w-0">{link.label}</span>
    </GuardedPortalLink>
  );
}

export function PortalNavigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = usePortalSession();
  const pathname = usePathname();
  const isWithin = (href: string) =>
    pathname === href || pathname.startsWith(href + "/");
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
  const hasFeedback = getFeedbackAccess(user).hasOperationalWorkspace;
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

  const groups: NavGroup[] = [
    {
      label: "Identity & Access",
      links: [
        { href: "/portal/accounts", label: "Accounts", icon: UsersRound, visible: canManageAccounts },
      ],
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
      label: "Scheduling",
      links: [
        { href: "/portal/services", label: "Services", icon: HeartHandshake, visible: hasServices },
        { href: "/portal/appointments", label: "Appointments", icon: CalendarClock, visible: hasAppointments },
        { href: "/portal/availability", label: "Availability", icon: Clock3, visible: hasAvailability },
      ],
    },
    {
      label: "Records",
      links: [
        { href: "/portal/inventory", label: "Individual Inventory", icon: ClipboardList, visible: hasInventory },
        { href: "/portal/routine-interviews", label: "Routine Interviews", icon: MessagesSquare, visible: hasRoutineInterviews },
        { href: "/portal/counseling", label: "Counseling", icon: MessageCircleHeart, visible: hasCounseling },
        { href: "/portal/referrals", label: "Referrals", icon: Forward, visible: hasReferrals },
        { href: "/portal/call-slips", label: "Call Slips", icon: ScrollText, visible: hasCallSlips },
      ],
    },
    {
      label: "Requests and surveys",
      links: [
        { href: "/portal/good-moral", label: "Good Moral", icon: Award, visible: hasGoodMoral },
        { href: "/portal/exit-interviews", label: "Exit Interviews", icon: DoorOpen, visible: hasExitInterviews },
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
  const visibleGroups = groups
    .map((group) => ({ ...group, links: group.links.filter((link) => link.visible) }))
    .filter((group) => group.links.length > 0);

  return (
    <div className="flex h-full min-h-full flex-col overflow-y-auto bg-brand-strong text-on-brand">
      <GuardedPortalLink
        href="/portal"
        onNavigate={onNavigate}
        className="flex min-h-18 shrink-0 items-center gap-3 border-b border-on-brand/15 px-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-on-brand"
        aria-label="COMPASS Portal Overview"
      >
        <Image
          src="/brand/compass-mark.svg"
          width={36}
          height={36}
          alt=""
          aria-hidden="true"
        />
        <span className="font-heading text-lg font-bold tracking-[0.08em]">
          COMPASS
        </span>
      </GuardedPortalLink>
      <nav aria-label="Portal navigation" className="p-3">
        <NavItem
          link={{ href: "/portal", label: "Overview", icon: LayoutDashboard, visible: true }}
          current={pathname === "/portal"}
          onNavigate={onNavigate}
        />
        {visibleGroups.map((group) => (
          <div key={group.label} className="mt-3 border-t border-on-brand/10 pt-3">
            {/* A label only earns its place when it groups more than one destination. */}
            {group.links.length > 1 ? (
              <p className="px-3 pb-1.5 text-xs font-semibold uppercase tracking-wider text-on-brand/60">
                {group.label}
              </p>
            ) : null}
            <div className="space-y-0.5">
              {group.links.map((link) => (
                <NavItem
                  key={link.href}
                  link={link}
                  current={isWithin(link.section ?? link.href)}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>
    </div>
  );
}
