"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import {
  AvailabilityModeScope,
  type WeeklyWindowResponse,
} from "@/lib/api/generated/model";
import {
  CompassApiError,
  readApiErrorCode,
  readApiErrorMessage,
} from "@/lib/api/errors";

export type StepUpHooks = {
  onStepUpRequired?: () => void;
  onStepUpVerified?: () => void;
};

const knownErrors: Record<string, string> = {
  availability_resource_not_found:
    "The requested Availability record is no longer available.",
  invalid_availability_request:
    "The Availability request contains a value that is not accepted.",
  availability_not_applicable:
    "Availability cannot be configured for the selected provider or Service.",
  availability_conflict:
    "The Availability change conflicts with the current configuration.",
  permission_denied:
    "You do not have permission to use this Availability action.",
  recent_mfa_required: "Recent authenticator verification is required.",
};

export const availabilitySelectClass =
  "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

export function canUseSelfAvailability(user: {
  role: string;
  capabilities: string[];
}): boolean {
  return (
    user.role === "COUNSELOR" &&
    user.capabilities.includes("availability.view")
  );
}

export function canManageAvailability(user: {
  capabilities: string[];
}): boolean {
  return user.capabilities.includes("availability.manage");
}

export function hasAvailabilityWorkspace(user: {
  role: string;
  capabilities: string[];
}): boolean {
  return canUseSelfAvailability(user) || canManageAvailability(user);
}

export function availabilityErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  const backendMessage = readApiErrorMessage(error.body);

  if (
    code === "availability_resource_not_found" ||
    code === "invalid_availability_request" ||
    code === "availability_not_applicable" ||
    code === "availability_conflict"
  ) {
    return backendMessage ?? knownErrors[code] ?? fallback;
  }

  return (code && knownErrors[code]) || backendMessage || fallback;
}

export function useAvailabilityAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [afterStepUp, setAfterStepUp] = useState<(() => void) | null>(null);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: StepUpHooks & { administrative?: boolean },
  ): Promise<T | undefined> {
    setError(null);
    setNotice(null);

    try {
      return await operation();
    } catch (caught) {
      const code =
        caught instanceof CompassApiError
          ? readApiErrorCode(caught.body)
          : undefined;

      if (code === "recent_mfa_required" && options?.administrative) {
        options.onStepUpRequired?.();
        setAfterStepUp(() => options.onStepUpVerified ?? null);
        setNotice("Verify your authenticator, then submit the action again.");
        setStepUpOpen(true);
      } else {
        setError(availabilityErrorMessage(caught, fallback));
      }

      return undefined;
    }
  }

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      onOpenChange={setStepUpOpen}
      onVerified={() => {
        setNotice("Verification complete. Submit the action again to continue.");
        const resume = afterStepUp;
        setAfterStepUp(null);
        resume?.();
      }}
    />
  );

  return {
    error,
    notice,
    setError,
    setNotice,
    run,
    stepUpDialog,
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
        ? "Your current access does not include Availability administration."
        : "Your current access does not include this Availability workspace."}
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
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={
        "inline-flex min-h-10 items-center border-b-2 px-1 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
        (current
          ? "border-brand text-brand"
          : "border-transparent text-muted hover:text-ink")
      }
    >
      {children}
    </Link>
  );
}

export function AvailabilityNavigation() {
  const { user } = usePortalSession();
  const self = canUseSelfAvailability(user);
  const manage = canManageAvailability(user);

  return (
    <div className="mb-8 border-b border-border">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {self ? (
          <NavLink href="/portal/availability/me">My availability</NavLink>
        ) : null}
        {manage ? (
          <>
            <NavLink href="/portal/availability/office">Office</NavLink>
            <NavLink href="/portal/availability/providers">Counselors</NavLink>
          </>
        ) : null}
      </div>
    </div>
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
  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 className="font-heading text-3xl font-bold text-ink sm:text-4xl">
          {title}
        </h1>
        {action}
      </div>
      {description ? (
        <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
          {description}
        </p>
      ) : null}
    </div>
  );
}

export function AvailabilityStatusBadge({
  active,
  legacy = false,
}: {
  active: boolean;
  legacy?: boolean;
}) {
  const label = legacy ? "Legacy Availability" : active ? "Active" : "Inactive";

  return (
    <span
      className={
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold " +
        (legacy
          ? "border-warning/30 bg-warning/10 text-warning"
          : active
            ? "border-success/30 bg-success/10 text-success"
            : "border-border bg-surface-muted text-muted")
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
    <div role="alert" className="border-y border-border py-6">
      <p className="text-sm text-danger">
        {availabilityErrorMessage(error, fallback)}
      </p>
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export function AvailabilitySectionSkeleton({
  label = "Loading Availability…",
}: {
  label?: string;
}) {
  return (
    <div className="mt-5 space-y-3" aria-busy="true">
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-4/5" />
      <p className="sr-only">{label}</p>
    </div>
  );
}

export function modeScopeLabel(scope: AvailabilityModeScope): string {
  if (scope === AvailabilityModeScope.IN_PERSON) return "In person";
  if (scope === AvailabilityModeScope.ONLINE) return "Online";
  return "All delivery modes";
}

export function weeklyWindowLabel(window: WeeklyWindowResponse): string {
  return (
    window.start_time.slice(0, 5) +
    " – " +
    window.end_time.slice(0, 5) +
    " · " +
    modeScopeLabel(window.mode_scope)
  );
}

export function ActionFeedback({
  error,
  notice,
}: {
  error: string | null;
  notice: string | null;
}) {
  return (
    <>
      {error ? (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-4 text-sm text-success">
          {notice}
        </p>
      ) : null}
    </>
  );
}
