import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import type { CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";

export function counselingErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

const counselingErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Counseling action.",
  counseling_resource_not_found: "This counseling record is unavailable to this account.",
  counseling_invalid_request: "The Counseling request was not valid. Review the information and try again.",
  counseling_invalid_time: "The recorded start and end times are not valid. Review the actual interaction times.",
  counseling_appointment_already_used: "A Counseling Encounter has already been recorded for this Appointment. Refresh the candidates and your encounter list.",
  counseling_appointment_invalid: "This Appointment is no longer eligible for this Counseling action. Refresh the candidates and try again.",
  counseling_finalized_routine_conflict: "This correction cannot be saved because the encounter is used by a finalized Routine Interview and the new details would no longer match it.",
  counseling_feedback_chronology_conflict: "This completion time cannot be saved because Feedback for this encounter was already made available before the corrected end time.",
  counseling_feedback_provenance_conflict: "This correction cannot be saved because the encounter's Feedback record is inconsistent. The record needs administrative review.",
  counseling_service_not_configured: "Counseling cannot be recorded until the service is set up.",
  counseling_not_permitted: "You cannot complete this counseling action with this account.",
  counseling_context_not_found: "This counseling view is no longer available.",
  current_academic_year_not_configured: "Counseling cannot be recorded until the current academic year is set up.",
  shared_summary_not_found: "No Shared Summary has been drafted yet.",
  shared_summary_already_published: "This Shared Summary has already been published and is locked from ordinary editing.",
  shared_summary_empty: "Add content before publishing this Shared Summary.",
};

export function counselingErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code && counselingErrors[code]) return counselingErrors[code];
  return fallback;
}

export function expiredContextEncounterMessage(hasEncounter: boolean): string | null {
  return hasEncounter
    ? "The recorded encounter remains available from My counseling encounters."
    : null;
}

export function formatCounselingDateTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  return formatInstitutionalDateTime(value);
}

export function counselingEntryModeLabel(mode: CounselingEntryMode | string): string {
  switch (mode) {
    case "APPOINTMENT": return "Appointment";
    case "WALK_IN": return "Walk-in";
    case "CALLED_IN": return "Called-in";
    case "REFERRED": return "Referred";
    default: return "Unavailable";
  }
}

export function counselingDeliveryModeLabel(mode: DeliveryMode | string): string {
  switch (mode) {
    case "IN_PERSON": return "In person";
    case "ONLINE": return "Online";
    default: return "Unavailable";
  }
}

export function CounselingPageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-heading text-3xl font-bold text-ink">{title}</h1>
        {description ? <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {action}
    </header>
  );
}
export function CounselingUnavailable({
  title = "Counseling unavailable",
  children = "Counseling is unavailable to this account.",
}: {
  title?: string;
  children?: ReactNode;
}) {
  return <WorkspaceUnavailable title={title}>{children}</WorkspaceUnavailable>;
}

export function CounselingListSkeleton({ label }: { label: string }) {
  return (
    <LoadingRegion label={label} className="space-y-2 py-3">
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
      <Skeleton className="h-14 w-full" />
    </LoadingRegion>
  );
}

export function CounselingWorkspaceSkeleton() {
  return (
    <LoadingRegion label="Loading Counseling context…">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="mt-5 h-32 w-full" />
      <Skeleton className="mt-5 h-72 w-full" />
    </LoadingRegion>
  );
}

export function SharedSummaryDetailSkeleton() {
  return (
    <LoadingRegion label="Loading published Shared Summary…">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="mt-4 h-32 w-full" />
    </LoadingRegion>
  );
}

export function EncounterDetailSkeleton() {
  return (
    <LoadingRegion label="Loading assigned Counseling Encounter…">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="mt-4 h-28 w-full" />
      <Skeleton className="mt-5 h-48 w-full" />
    </LoadingRegion>
  );
}

export function CounselingQueryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="border-y border-danger/30 py-5">
      <p className="text-sm leading-6 text-danger">{message}</p>
      {onRetry ? <Button className="mt-3" variant="secondary" onClick={onRetry}>Retry</Button> : null}
    </div>
  );
}
