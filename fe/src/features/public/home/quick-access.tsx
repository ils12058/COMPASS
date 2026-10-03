"use client";

import {
  Award,
  CalendarClock,
  ChevronRight,
  ClipboardList,
  DoorOpen,
  GraduationCap,
  LayoutDashboard,
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
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import type { UserSummary } from "@/lib/api/generated/model";

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

export function QuickAccess({ className }: { className?: string }) {
  const session = useAuthGetSession({ query: { retry: false, staleTime: 60_000 } });
  const signedIn = session.isSuccess && session.data.data.authenticated;
  const user = signedIn ? session.data.data.user : null;
  const shown = user ? services.filter((service) => service.available(user)) : services;

  return (
    <Panel as="aside" aria-labelledby="quick-access-heading" className={className}>
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
            {shown.map((service) => (
              <ServiceRow
                key={service.href}
                href={service.href}
                label={service.label}
                detail={user ? undefined : service.audience}
                icon={service.icon}
              />
            ))}
            {user ? (
              <ServiceRow href="/portal" label="Open COMPASS" icon={LayoutDashboard} />
            ) : null}
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
