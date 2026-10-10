"use client";

import {
  Award,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  DoorOpen,
  GraduationCap,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { LoadingRegion } from "@/components/ui/loading-region";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getExitInterviewAccess } from "@/features/exit-interviews/exit-interviews-access";
import { getGoodMoralAccess } from "@/features/good-moral/good-moral-access";
import { getGraduateTracerAccess } from "@/features/graduate-tracer/graduate-tracer-access";
import { getInventoryAccess } from "@/features/inventory/inventory-access";
import { portalWorkspaceGroups } from "@/features/portal/components/portal-workspaces";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { RoleCode, type UserSummary } from "@/lib/api/generated/model";

type Service = {
  href: string;
  label: string;
  // Who the service is for, from the same rules the portal uses.
  audience: string;
  icon: LucideIcon;
  available: (user: UserSummary) => boolean;
};

// Student services that already exist in COMPASS, named as the portal names them. Signed-out
// readers see all of them, each behind sign-in; a signed-in reader sees the ones their account
// can open.
const services: Service[] = [
  {
    href: "/portal/appointments/book",
    label: "Book appointment",
    audience: "Current students",
    icon: CalendarClock,
    available: (user) => getAppointmentAccess(user).canBook,
  },
  {
    href: "/portal/inventory",
    label: "Individual Inventory",
    audience: "Students",
    icon: ClipboardList,
    available: (user) => getInventoryAccess(user).canViewSelf,
  },
  {
    href: "/portal/good-moral/request",
    label: "Request Good Moral Certificate",
    audience: "Current students and graduates",
    icon: Award,
    available: (user) => {
      const access = getGoodMoralAccess(user);
      const lifecycle = user.student_lifecycle_status;
      return access.isStudent && access.canRequestSelf && (lifecycle === "CURRENT" || lifecycle === "GRADUATED");
    },
  },
  {
    href: "/portal/exit-interviews",
    label: "Exit Interview",
    audience: "Current students",
    icon: DoorOpen,
    available: (user) => getExitInterviewAccess(user).hasStudentWorkspace,
  },
  {
    href: "/portal/graduate-tracer",
    label: "Graduate Tracer Survey",
    audience: "Graduates",
    icon: GraduationCap,
    available: (user) => getGraduateTracerAccess(user).hasStudentWorkspace,
  },
];

// Staff see the workspaces they can open, daily casework first, named as the portal sidebar names
// them. Workspaces not listed here are still reachable from the portal itself.
const staffPriority = [
  "/portal/appointments",
  "/portal/routine-interviews",
  "/portal/counseling",
  "/portal/referrals",
  "/portal/call-slips",
  "/portal/good-moral",
  "/portal/inventory",
  "/portal/exit-interviews",
  "/portal/graduate-tracer",
  "/portal/feedback",
  "/portal/availability",
  "/portal/announcements",
  "/portal/resources",
  "/portal/reports",
  "/portal/accounts",
  "/portal/platform/health",
  "/portal/privacy",
  "/portal/services",
  "/portal/organization",
  "/portal/academic-years",
  "/portal/institutional-forms",
];
const STAFF_SHORTCUT_LIMIT = 5;

type Shortcut = { href: string; label: string; detail?: string; icon: LucideIcon };

function shortcutsFor(user: UserSummary | null): Shortcut[] {
  if (!user) {
    return services.map((service) => ({ href: service.href, label: service.label, detail: service.audience, icon: service.icon }));
  }
  if (user.role === RoleCode.STUDENT) {
    return services
      .filter((service) => service.available(user))
      .map((service) => ({ href: service.href, label: service.label, icon: service.icon }));
  }
  const workspaces = portalWorkspaceGroups(user).flatMap((group) => group.links);
  return staffPriority
    .map((href) => workspaces.find((link) => link.href === href))
    .filter((link): link is NonNullable<typeof link> => Boolean(link))
    .slice(0, STAFF_SHORTCUT_LIMIT)
    .map((link) => ({ href: link.href, label: link.label, icon: link.icon }));
}

const rowClass =
  "group flex min-h-14 items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:px-5";

function ServiceRow({ href, label, detail, icon: Icon }: { href: string; label: string; detail?: string; icon: LucideIcon }) {
  return (
    <li>
      <Link href={href} className={rowClass}>
        <Icon size={18} aria-hidden="true" className="shrink-0 text-brand" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold text-ink group-hover:text-brand group-hover:underline">{label}</span>
          {detail ? <span className="block text-xs leading-5 text-muted">{detail}</span> : null}
        </span>
        <ChevronRight size={16} aria-hidden="true" className="shrink-0 text-muted" />
      </Link>
    </li>
  );
}

// Entry points beside the landing's announcements. Signed-out readers see the student services,
// each behind sign-in. A signed-in Student sees the services their account can open; staff see
// their own workspaces. The site header and hero already offer "Open COMPASS", so this panel does
// not repeat it, and an account with no shortcuts gets no panel at all.
export function QuickAccess({ className }: { className?: string }) {
  const session = useAuthGetSession({ query: { retry: false, staleTime: 60_000 } });
  const signedIn = session.isSuccess && session.data.data.authenticated;
  const user = signedIn ? session.data.data.user : null;
  const shortcuts = shortcutsFor(user);

  if (!session.isPending && shortcuts.length === 0) return null;

  return (
    <Panel as="aside" aria-labelledby="quick-access-heading" className={className} data-quick-access="">
      <PanelHeader title="Quick access" titleId="quick-access-heading" />
      {session.isPending ? (
        <LoadingRegion label="Loading quick access…" className="space-y-4 px-4 py-4 sm:px-5">
          {[0, 1, 2].map((row) => (
            <Skeleton key={row} className="h-9 w-full" />
          ))}
        </LoadingRegion>
      ) : (
        <>
          <ul className="divide-y divide-border">
            {shortcuts.map((shortcut) => (
              <ServiceRow
                key={shortcut.href}
                href={shortcut.href}
                label={shortcut.label}
                detail={shortcut.detail}
                icon={shortcut.icon}
              />
            ))}
          </ul>
          {user ? null : (
            <p className="rounded-b-sm border-t border-brand-line bg-brand-wash px-4 py-3 text-xs leading-5 text-muted sm:px-5">
              Sign in with your University of Camarines Norte COMPASS account to use these services.
            </p>
          )}
        </>
      )}
    </Panel>
  );
}
