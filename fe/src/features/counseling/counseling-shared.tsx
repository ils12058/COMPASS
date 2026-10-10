import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  CounselingEncounterOrdering,
  type CounselingContextOverviewResponse,
  type CounselingEntryMode,
  type DeliveryMode,
} from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";

// Encounters are history: the latest actual start comes first (ADR-090). Origin and delivery mode
// stay filters.
export const encounterOrderingOptions: readonly SortOption<CounselingEncounterOrdering>[] = [
  { value: CounselingEncounterOrdering.LATEST_ENCOUNTER, label: "Latest encounter first" },
  { value: CounselingEncounterOrdering.OLDEST_ENCOUNTER, label: "Oldest encounter first" },
  { value: CounselingEncounterOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: CounselingEncounterOrdering.STUDENT_DESC, label: "Student Z–A" },
];
import { PageHeader } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";

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
  counseling_linked_routine_conflict: "This correction cannot be saved because the encounter is linked to a Routine Interview and the new details would no longer match it.",
  counseling_routine_interview_already_linked: "A Counseling Encounter is already linked to this Routine Interview, so another one was not recorded.",
  counseling_routine_interview_mismatch: "This encounter does not match the Routine Interview's Student, visit type, or delivery mode, so it was not recorded.",
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

export type ContextEncounterState = "RECORDED" | "RECORDED_OUTSIDE_ROUTINE" | "NOT_RECORDED";

// In a Routine Interview's own workspace only its linked Encounter counts as recorded there. A
// similar Encounter recorded from My Counseling Encounters is linked only when the Counselor
// chooses it while finalizing the Evaluation.
export function contextEncounterState(
  overview: Pick<CounselingContextOverviewResponse, "source_type" | "matching_encounter">,
): ContextEncounterState {
  const encounter = overview.matching_encounter;
  if (!encounter) return "NOT_RECORDED";
  if (overview.source_type === "ROUTINE_INTERVIEW" && !encounter.routine_interview_linked) {
    return "RECORDED_OUTSIDE_ROUTINE";
  }
  return "RECORDED";
}

export const contextEncounterStateLabels: Record<ContextEncounterState, string> = {
  RECORDED: "Recorded",
  RECORDED_OUTSIDE_ROUTINE: "Recorded outside this Routine Interview",
  NOT_RECORDED: "Not yet recorded",
};

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
  help,
  back,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  help?: ReactNode;
  // A "Back to …" text link, styled with pageBackLinkClass.
  back?: ReactNode;
}) {
  return <PageHeader title={title} description={description} back={back} actions={action} help={help} />;
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

export function CounselingListSkeleton({ label, framed = true }: { label: string; framed?: boolean }) {
  return <RowsSkeleton label={label} framed={framed} />;
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
    <Notice
      tone="danger"
      role="alert"
      action={onRetry ? <Button variant="secondary" onClick={onRetry}>Retry</Button> : undefined}
    >
      {message}
    </Notice>
  );
}
