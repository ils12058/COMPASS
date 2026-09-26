import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";
import type { CounselingEntryMode, DeliveryMode } from "@/lib/api/generated/model";

export function counselingErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

const counselingErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Counseling action.",
  counseling_resource_not_found: "This Counseling record is not available within your current access.",
  counseling_invalid_request: "The Counseling request was not valid. Review the information and try again.",
  counseling_invalid_time: "The recorded start and end times are not valid. Review the actual interaction times.",
  counseling_appointment_already_used: "A Counseling Encounter has already been recorded for this Appointment. Refresh the candidates and your encounter list.",
  counseling_appointment_invalid: "This Appointment is no longer eligible for this Counseling action. Refresh the candidates and try again.",
  counseling_service_not_configured: "Counseling cannot be recorded because the Counseling Service is not configured.",
  counseling_not_permitted: "This Counseling action is not available within your current access.",
  counseling_context_not_found: "This temporary Counseling Context is no longer available.",
  current_academic_year_not_configured: "The current Academic Year is not configured for this Counseling workflow.",
  shared_summary_not_found: "No Shared Summary has been drafted yet.",
  shared_summary_already_published: "This Shared Summary has already been published and is locked from ordinary editing.",
  shared_summary_empty: "Add content before publishing this Shared Summary.",
};

export function counselingErrorMessage(error: unknown, fallback: string): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code && counselingErrors[code]) return counselingErrors[code];
  return readApiErrorMessage(error.body) ?? fallback;
}

export function formatCounselingDateTime(value: string | null | undefined): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
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
  children = "Your current access does not include this Counseling workspace.",
}: {
  title?: string;
  children?: ReactNode;
}) {
  return <WorkspaceUnavailable title={title}>{children}</WorkspaceUnavailable>;
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

export function CounselingPagination({
  page,
  hasNext,
  onPageChange,
}: {
  page: number;
  hasNext: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav aria-label="Counseling results pages" className="flex items-center justify-between border-t border-border py-4">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onPageChange(Math.max(1, page - 1))}>Previous</Button>
      <span className="text-sm text-muted">Page {page}</span>
      <Button variant="secondary" disabled={!hasNext} onClick={() => onPageChange(page + 1)}>Next</Button>
    </nav>
  );
}
