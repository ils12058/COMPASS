"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import { ListSearchField } from "@/components/ui/floating-list-tools";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import {
  stepUpNotice,
  stepUpRequirement,
  type StepUpRequirement,
} from "@/features/account/security/step-up";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { hasServicesWorkspace } from "@/features/services/services-access";
import {
  CompassApiError,
  readApiErrorCode,
} from "@/lib/api/errors";
import {
  DeliveryMode,
  ServiceActivationBlocker,
  ServiceOrdering,
  ServiceProviderCoverage,
} from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";

// The Service Catalog is reference data and reads by code A–Z (ADR-090). Active and booking state
// stay filters.
export const serviceOrderingOptions: readonly SortOption<ServiceOrdering>[] = [
  { value: ServiceOrdering.CODE_ASC, label: "Code A–Z" },
  { value: ServiceOrdering.CODE_DESC, label: "Code Z–A" },
  { value: ServiceOrdering.NAME_ASC, label: "Name A–Z" },
  { value: ServiceOrdering.NAME_DESC, label: "Name Z–A" },
];
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";

const knownErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Services action.",
  service_not_found: "The requested Service is no longer available.",
  service_catalog_conflict:
    "The Service configuration conflicts with the current Service Catalog rules.",
  invalid_service_catalog_request:
    "The Service request contains a value that is not accepted by the Service Catalog.",
  canonical_service_reserved:
    "The COUNSELING code is reserved for the Counseling Service that COMPASS provides. Use a different Service code.",
  canonical_service_required:
    "Counseling is required by COMPASS and must stay active.",
  service_scheduling_consequence_review_required:
    "Review the scheduling consequences before saving this Service change.",
};

export type ServiceSchedulingConsequenceDetails = {
  existingAppointmentDependencyDetected: boolean;
  providerDependencyDetected: boolean;
  counselingOnlineEnabled: boolean;
};

export function serviceDeliveryLabel(modes: DeliveryMode[]): string {
  const labels = [
    modes.includes(DeliveryMode.IN_PERSON) ? "In person" : null,
    modes.includes(DeliveryMode.ONLINE) ? "Online" : null,
  ].filter(Boolean);
  return labels.length ? labels.join(", ") : "Not configured";
}

export function serviceBookingLabel(enabled: boolean): string {
  return enabled ? "Available" : "Not available";
}

export const serviceCoverageLabels: Record<ServiceProviderCoverage, string> = {
  [ServiceProviderCoverage.ALL_COUNSELORS]: "All active Counselors",
  [ServiceProviderCoverage.SELECTED_COUNSELORS]: "Selected Counselors",
};

// Why an inactive Service cannot be enabled yet, as the backend reports it.
export const activationBlockerLabels: Record<ServiceActivationBlocker, string> = {
  [ServiceActivationBlocker.DELIVERY_MODE_MISSING]: "No delivery mode is selected.",
  [ServiceActivationBlocker.APPOINTMENT_DURATION_MISSING]:
    "Appointment booking is available but has no default Appointment duration.",
  [ServiceActivationBlocker.SELECTED_COUNSELORS_MISSING]:
    "Coverage is limited to selected Counselors, but no active Counselor is selected.",
};

// What the reviewed change itself does, known only to the editor that built it.
export type ServiceConsequenceChange = {
  counselingOnlineRemoved: boolean;
  bookingTurnedOff: boolean;
};

// What a reviewed Service change means for Appointments that are already scheduled.
export function ServiceConsequenceSummary({
  details,
  change,
}: {
  details: ServiceSchedulingConsequenceDetails | null;
  change?: ServiceConsequenceChange;
}) {
  if (!details) {
    return (
      <p>
        One or more scheduling consequences require review. Existing Appointments are not
        changed by this Service update.
      </p>
    );
  }
  const onlineRemoved = Boolean(change?.counselingOnlineRemoved);
  return (
    <>
      {details.existingAppointmentDependencyDetected && onlineRemoved ? (
        <>
          <p>
            New Online Counseling work will no longer be available. Existing Online Counseling
            appointments remain scheduled and keep their saved Online delivery mode; they are not
            changed to in person.
          </p>
          <p>
            While Online counseling is off, those appointments cannot be rescheduled or
            reassigned.
          </p>
        </>
      ) : null}
      {details.existingAppointmentDependencyDetected &&
      (!onlineRemoved || change?.bookingTurnedOff) ? (
        <p>
          Some upcoming Appointments use a setting this change removes. They stay scheduled and
          can still take place as booked, but rescheduling or reassigning them follows the new
          settings.
        </p>
      ) : null}
      {details.providerDependencyDetected ? (
        <p>
          Some upcoming Appointments are with a Counselor who would no longer provide this
          Service. Those Appointments stay with that Counselor and can still take place; the
          Counselor will not receive new Appointments for this Service.
        </p>
      ) : null}
      {details.counselingOnlineEnabled ? (
        <p>
          Enabling Online counseling allows new Online Counseling appointments to be scheduled
          where Counselor Availability and booking requirements permit. Scheduled Online
          Counseling appointments use E-Counseling. This change does not confirm that the
          video-session provider is configured or available.
        </p>
      ) : null}
    </>
  );
}

export function servicesErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

export function serviceSchedulingConsequenceDetails(
  error: unknown,
): ServiceSchedulingConsequenceDetails | null {
  if (!(error instanceof CompassApiError)) return null;
  if (
    readApiErrorCode(error.body) !==
    "service_scheduling_consequence_review_required"
  ) {
    return null;
  }
  if (!error.body || typeof error.body !== "object" || !("error" in error.body)) {
    return null;
  }
  const envelopeError = error.body.error;
  if (!envelopeError || typeof envelopeError !== "object") return null;
  const details = "details" in envelopeError ? envelopeError.details : null;
  if (!details || typeof details !== "object") return null;
  const existing =
    "existing_appointment_dependency_detected" in details
      ? details.existing_appointment_dependency_detected
      : undefined;
  const provider =
    "provider_dependency_detected" in details
      ? details.provider_dependency_detected
      : undefined;
  const counselingOnline =
    "counseling_online_enabled" in details
      ? details.counseling_online_enabled
      : undefined;
  if (
    typeof existing !== "boolean" ||
    typeof provider !== "boolean" ||
    typeof counselingOnline !== "boolean"
  ) {
    return null;
  }
  return {
    existingAppointmentDependencyDetected: existing,
    providerDependencyDetected: provider,
    counselingOnlineEnabled: counselingOnline,
  };
}

export function servicesErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  return (code && knownErrors[code]) || fallback;
}

export function ServicesGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return hasServicesWorkspace(user) ? (
    children
  ) : (
    <WorkspaceUnavailable title="Services unavailable">
      Service management is unavailable to this account.
    </WorkspaceUnavailable>
  );
}

export function useServicesAction() {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUp, setStepUp] = useState<StepUpRequirement>("verify");
  const [afterStepUp, setAfterStepUp] = useState<(() => void) | null>(null);

  async function run<T>(
    operation: () => Promise<T>,
    fallback: string,
    options?: {
      onStepUpRequired?: () => void;
      onStepUpVerified?: () => void;
      onError?: (error: unknown, code: string | undefined) => boolean;
    },
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
      const requirement = stepUpRequirement(caught);
      if (requirement) {
        setStepUp(requirement);
        options?.onStepUpRequired?.();
        setAfterStepUp(() => options?.onStepUpVerified ?? null);
        setNotice(stepUpNotice(requirement));
        setStepUpOpen(true);
      } else if (!options?.onError?.(caught, code)) {
        setError(servicesErrorMessage(caught, fallback));
      }
      return undefined;
    }
  }

  const messages = (
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

  const stepUpDialog = (
    <StepUpDialog
      open={stepUpOpen}
      requirement={stepUp}
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
    messages,
    stepUpDialog,
  };
}

export function ServicesPageHeading({
  title,
  description,
  action,
  help,
  backHref,
  backLabel,
  children,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  help?: ReactNode;
  backHref?: string;
  backLabel?: string;
  // Facts that belong under the title, such as the Service code and status.
  children?: ReactNode;
}) {
  return (
    <PageHeader
      title={title}
      description={description}
      actions={action} help={help}
      back={backHref ? (
        <GuardedPortalLink href={backHref} className={pageBackLinkClass}>
          ← {backLabel ?? "Services"}
        </GuardedPortalLink>
      ) : undefined}
    >
      {children}
    </PageHeader>
  );
}

export function ServicesStatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={
        "inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold " +
        (active
          ? "border-success/30 bg-success/10 text-success"
          : "border-border bg-surface-muted text-muted")
      }
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function ServicesSystemRequiredBadge() {
  return (
    <span className="inline-flex rounded-full border border-info/30 bg-info/10 px-2 py-0.5 text-xs font-semibold text-info">
      System-required
    </span>
  );
}

export function ServicesSearchField() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = (searchParams.get("search") ?? "").slice(0, 160);
  const [value, setValue] = useState(current);

  useEffect(() => {
    if (value === current) return;
    const timer = window.setTimeout(() => {
      const next = new URLSearchParams(searchParams.toString());
      const trimmed = value.trim();
      if (trimmed) next.set("search", trimmed);
      else next.delete("search");
      next.delete("page");
      const query = next.toString();
      router.replace(query ? pathname + "?" + query : pathname, {
        scroll: false,
      });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [current, pathname, router, searchParams, value]);

  return (
    <ListSearchField
      id="services-search"
      label="Search Services"
      maxLength={160}
      placeholder="Search by Service name or code"
      value={value}
      onChange={(event) => setValue(event.target.value)}
    />
  );
}

export function ServicesQueryError({
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
      {servicesErrorMessage(error, fallback)}
    </Notice>
  );
}

export function ServicesListSkeleton({ framed = true }: { framed?: boolean }) {
  return <RowsSkeleton label="Loading Services…" rows={5} framed={framed} />;
}

export function ServicesDetailSkeleton() {
  return (
    <LoadingRegion label="Loading Service…" className="space-y-7">
      <Skeleton className="h-12 w-72 max-w-full" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-36 w-full" />
    </LoadingRegion>
  );
}

export function replaceServicesQueryParam(
  pathname: string,
  searchParams: URLSearchParams,
  key: string,
  value: string,
  resetPage = true,
): string {
  const next = new URLSearchParams(searchParams.toString());
  if (value) next.set(key, value);
  else next.delete(key);
  if (resetPage) next.delete("page");
  const query = next.toString();
  return query ? pathname + "?" + query : pathname;
}
