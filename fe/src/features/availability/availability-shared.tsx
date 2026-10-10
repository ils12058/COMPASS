"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ActiveStatusBadge } from "@/components/ui/active-status-badge";
import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  AvailabilityModeScope,
  type CapabilityCode,
  type RoleCode,
} from "@/lib/api/generated/model";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE,
} from "@/lib/institutional-time";
import {
  CompassApiError,
  readApiErrorCode,
} from "@/lib/api/errors";
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";

const knownErrors: Record<string, string> = {
  availability_resource_not_found:
    "This availability record is unavailable.",
  invalid_availability_request:
    "Some schedule details need attention. Review them and try again.",
  availability_not_applicable:
    "Availability cannot be set for the selected Counselor or Service.",
  availability_conflict:
    "The schedule is unavailable right now. Try again or contact the institutional administrator.",
  permission_denied:
    "You can't perform this availability action.",
};

export function canUseSelfAvailability(user: {
  role: RoleCode;
  capabilities: readonly CapabilityCode[];
}): boolean {
  return (
    user.role === "COUNSELOR" &&
    user.capabilities.includes("availability.view")
  );
}

export function canManageAvailability(user: {
  capabilities: readonly CapabilityCode[];
}): boolean {
  return user.capabilities.includes("availability.manage");
}

export function hasAvailabilityWorkspace(user: {
  role: RoleCode;
  capabilities: readonly CapabilityCode[];
}): boolean {
  return canUseSelfAvailability(user) || canManageAvailability(user);
}

export function availabilityErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || fallback;
}

// Availability changes are routine scheduling work and need no step-up; the capability and the
// backend's scheduling checks decide them. A failure stays beside the work it concerns; success is
// announced by the page (ActionStatus) or shown in the confirming dialog.
export function useAvailabilityAction() {
  const [error, setError] = useState<string | null>(null);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
  ): Promise<T | undefined> {
    setError(null);

    try {
      return await operation();
    } catch (caught) {
      setError(availabilityErrorMessage(caught, fallback));
      return undefined;
    }
  }

  return {
    error,
    setError,
    resetError: () => setError(null),
    run,
  };
}

function AvailabilityUnavailable({
  management = false,
}: {
  management?: boolean;
}) {
  return (
    <WorkspaceUnavailable title="Availability unavailable">
      {management
        ? "You don’t have access to manage availability."
        : "You don’t have access to availability."}
    </WorkspaceUnavailable>
  );
}

export function AvailabilityGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return hasAvailabilityWorkspace(user) ? (
    children
  ) : (
    <AvailabilityUnavailable />
  );
}

export function AvailabilityRouteUnavailable({
  management = false,
}: {
  management?: boolean;
}) {
  return <AvailabilityUnavailable management={management} />;
}

function NavLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const current = pathname === href;

  return (
    <GuardedPortalLink
      href={href}
      aria-current={current ? "page" : undefined}
      className={workspaceTabClass(current)}
    >
      {children}
    </GuardedPortalLink>
  );
}

export function AvailabilityNavigation() {
  const { user } = usePortalSession();
  const self = canUseSelfAvailability(user);
  const manage = canManageAvailability(user);

  return (
    <WorkspaceTabs label="Availability navigation">
      {self ? (
        <NavLink href="/portal/availability/me">My availability</NavLink>
      ) : null}
      {manage ? (
        <>
          <NavLink href="/portal/availability/office">Office</NavLink>
          <NavLink href="/portal/availability/providers">Counselors</NavLink>
        </>
      ) : null}
    </WorkspaceTabs>
  );
}

export function AvailabilityIndex() {
  const { user } = usePortalSession();
  const router = useRouter();
  const destination = canUseSelfAvailability(user)
    ? "/portal/availability/me"
    : canManageAvailability(user)
      ? "/portal/availability/office"
      : "/portal";

  useEffect(() => {
    router.replace(destination);
  }, [destination, router]);

  return (
    <div className="max-w-xl" aria-busy="true">
      <Skeleton className="h-10 w-64 max-w-full" />
      <Skeleton className="mt-5 h-20 w-full" />
      <p className="sr-only">Opening Availability…</p>
    </div>
  );
}

export function AvailabilityPageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return <PageHeader title={title} description={description} actions={action} />;
}

export function AvailabilityStatusBadge({
  active,
  legacy = false,
}: {
  active: boolean;
  legacy?: boolean;
}) {
  if (!legacy) return <ActiveStatusBadge active={active} />;
  const label = "Legacy Availability";

  return (
    <span
      className={
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold " +
        "border-warning/30 bg-warning/10 text-warning"
      }
    >
      {label}
    </span>
  );
}

export function AvailabilityQueryError({
  error,
  fallback,
  onRetry,
}: {
  error: unknown;
  fallback: string;
  onRetry: () => void;
}) {
  return (
    <Notice
      tone="danger"
      role="alert"
      action={<Button variant="secondary" onClick={onRetry}>Retry</Button>}
    >
      {availabilityErrorMessage(error, fallback)}
    </Notice>
  );
}

export function AvailabilitySectionSkeleton({
  label = "Loading availability…",
}: {
  label?: string;
}) {
  return (
    <LoadingRegion label={label} className="mt-5 space-y-3">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-4/5" />
    </LoadingRegion>
  );
}

export function modeScopeLabel(scope: AvailabilityModeScope): string {
  if (scope === AvailabilityModeScope.IN_PERSON) return "In person";
  if (scope === AvailabilityModeScope.ONLINE) return "Online";
  return "All delivery modes";
}

// One dated period in the institution's time zone, shortened when it starts and ends on the same
// day: "Mon, Oct 12, 2026 · 8:00 AM – 12:00 PM" or "Oct 20, 2026, 8:00 AM – Oct 21, 2026, 5:00 PM".
export function formatUnavailabilityRange(startsAt: string, endsAt: string): string {
  const start = new Date(startsAt);
  const end = new Date(endsAt);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return formatInstitutionalDateTime(startsAt) + " – " + formatInstitutionalDateTime(endsAt);
  }
  const zone = { timeZone: INSTITUTION_TIME_ZONE } as const;
  const day = new Intl.DateTimeFormat("en-US", { ...zone, year: "numeric", month: "short", day: "numeric" });
  const weekday = new Intl.DateTimeFormat("en-US", { ...zone, weekday: "short" });
  const time = new Intl.DateTimeFormat("en-US", { ...zone, hour: "numeric", minute: "2-digit" });
  if (day.format(start) === day.format(end)) {
    return `${weekday.format(start)}, ${day.format(start)} · ${time.format(start)} – ${time.format(end)}`;
  }
  return `${day.format(start)}, ${time.format(start)} – ${day.format(end)}, ${time.format(end)}`;
}
