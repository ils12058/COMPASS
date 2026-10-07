import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { LoadingRegion } from "@/components/ui/loading-region";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import type {
  DeliveryMode,
  RoutineAcademicYearSummary,
  RoutineAppointmentSummary,
  RoutineEncounterSummary,
  RoutineEntryMode,
  RoutineEvaluationStatus,
  RoutineFormRevisionSummary,
  RoutineIntakeStatus,
  RoutineInventoryContext,
  RoutinePersonSummary,
} from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { RoutineInterviewOrdering } from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE,
} from "@/lib/institutional-time";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import { Panel } from "@/components/ui/panel";

export function formatRoutineDateTime(value: string): string {
  return formatInstitutionalDateTime(value);
}

export function formatRoutineDateTimeRange(start: string, end: string): string {
  const endDate = new Date(end);
  if (Number.isNaN(endDate.getTime())) {
    return formatRoutineDateTime(start) + " – " + end;
  }
  return (
    formatRoutineDateTime(start) +
    " – " +
    new Intl.DateTimeFormat("en-PH", {
      timeZone: INSTITUTION_TIME_ZONE,
      hour: "numeric",
      minute: "2-digit",
    }).format(endDate)
  );
}

export function routineEntryModeLabel(mode: RoutineEntryMode): string {
  switch (mode) {
    case "APPOINTMENT":
      return "Appointment";
    case "WALK_IN":
      return "Walk-in";
    case "CALLED_IN":
      return "Called-in";
    case "REFERRED":
      return "Referred";
  }
}

// The Academic Year configured when the Routine Interview began, if any.
export function routineAcademicYearLabel(academicYear: RoutineAcademicYearSummary | null): string {
  return academicYear?.label ?? "Not recorded";
}

// Course and major from the bound Inventory, only while it is submitted (ADR-088).
export function routineProgramLabel(context: RoutineInventoryContext | null): string | null {
  if (!context?.available || !context.course) return null;
  const major = context.major?.trim();
  return major ? `${context.course} · ${major}` : context.course;
}

// Shown only when the Routine Interview has no submitted Inventory context to display.
export function routineInventoryNote(context: RoutineInventoryContext | null): string | null {
  if (!context) return "Not available at initiation";
  if (!context.available) return "Being corrected";
  return null;
}

export function routineDeliveryModeLabel(mode: DeliveryMode): string {
  return mode === "ONLINE" ? "Online" : "In person";
}

const routineIntakeStatusLabels: Record<RoutineIntakeStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
};

const routineEvaluationStatusLabels: Record<RoutineEvaluationStatus, string> = {
  DRAFT: "Draft",
  FINALIZED: "Finalized",
};

// Submitted intakes awaiting evaluation default to the oldest waiting, so newer submissions never
// bury older unfinished work; finalized evaluations default to the most recent (ADR-090).
export const routineOrderingOptions: readonly SortOption<RoutineInterviewOrdering>[] = [
  { value: RoutineInterviewOrdering.OLDEST_WAITING, label: "Oldest waiting first" },
  { value: RoutineInterviewOrdering.NEWEST_SUBMITTED, label: "Newest submitted first" },
  { value: RoutineInterviewOrdering.RECENTLY_FINALIZED, label: "Recently finalized first" },
  { value: RoutineInterviewOrdering.NEWEST_CREATED, label: "Newest created first" },
  { value: RoutineInterviewOrdering.STUDENT_ASC, label: "Student A–Z" },
  { value: RoutineInterviewOrdering.STUDENT_DESC, label: "Student Z–A" },
];

export function routineIntakeStatusLabel(status: RoutineIntakeStatus): string {
  return routineIntakeStatusLabels[status];
}

export function routineEvaluationStatusLabel(status: RoutineEvaluationStatus): string {
  return routineEvaluationStatusLabels[status];
}

export function routineErrorCode(error: unknown): string | undefined {
  return error instanceof CompassApiError
    ? readApiErrorCode(error.body)
    : undefined;
}

const routineErrors: Record<string, string> = {
  permission_denied: "You do not have permission to use this Routine Interview action.",
  current_academic_year_not_configured:
    "The current Academic Year is not configured, so a new Routine Interview cannot be started yet.",
  current_student_required:
    "Only a current Student can start or update a Routine Interview.",
  routine_interview_not_found:
    "This Routine Interview is unavailable to this account.",
  routine_interview_not_permitted:
    "This Routine Interview is unavailable to this account.",
  routine_interview_appointment_invalid:
    "This Appointment no longer has a Routine Interview to complete, for example because it was cancelled.",
  routine_interview_closed_by_appointment:
    "This Routine Interview is historical and no longer accepts Intake or Evaluation changes because its Appointment ended without a completed interaction.",
  routine_interview_intake_already_submitted:
    "The Student Intake has already been submitted and is now read-only.",
  routine_interview_intake_required:
    "The Student must submit the Intake before the Counselor Evaluation can be finalized.",
  routine_interview_evaluation_finalized:
    "The Counselor Evaluation has already been finalized and is read-only.",
  routine_interview_encounter_required:
    "A matching completed Counseling Encounter is required before finalization.",
  routine_interview_encounter_mismatch:
    "That Counseling Encounter does not match this Routine Interview. The available encounters have been reloaded.",
  routine_interview_encounter_conflict:
    "A different Counseling Encounter is already linked to this Routine Interview. The latest details are now shown.",
  routine_interview_form_revision_unsupported:
    "The configured Routine Interview form revision is not supported for new records.",
  idempotency_key_conflict:
    "This create attempt no longer matches its original Student, visit type, and delivery mode. Review the choices and submit again.",
  routine_interview_invalid:
    "The Routine Interview request was not valid. Review the information and try again.",
};

export function routineErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (!(error instanceof CompassApiError)) return fallback;
  const code = readApiErrorCode(error.body);
  if (code && routineErrors[code]) return routineErrors[code];
  return fallback;
}

export function RoutinePageHeading({
  title,
  description,
  action,
  back,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  // A "Back to …" text link, styled with pageBackLinkClass.
  back?: ReactNode;
}) {
  return <PageHeader title={title} description={description} back={back} actions={action} />;
}

export function RoutineStatus({
  children,
  complete = false,
}: {
  children: ReactNode;
  complete?: boolean;
}) {
  return (
    <span
      className={
        "inline-flex min-h-6 items-center rounded-full border px-2.5 text-xs font-semibold " +
        (complete
          ? "border-success/30 bg-success/10 text-success"
          : "border-warning/30 bg-warning/10 text-warning")
      }
    >
      {children}
    </span>
  );
}

function MetadataItem({
  label,
  value,
}: {
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm text-ink">{value}</dd>
    </div>
  );
}

function formRevisionLabel(
  revision: RoutineFormRevisionSummary | null,
): string | null {
  if (!revision) return null;
  if (revision.official_code && revision.official_revision) {
    return revision.official_code + " · " + revision.official_revision;
  }
  return revision.official_code ?? revision.official_revision;
}

export function RoutineContextSummary({
  personName,
  academicYear,
  inventoryContext,
  counselor,
  appointment,
  encounter,
  entryMode,
  deliveryMode,
  intakeStatus,
  intakeSubmittedAt,
  evaluationStatus,
  evaluationFinalizedAt,
  createdAt,
  formRevision,
  studentFacing = false,
}: {
  personName: string;
  academicYear: RoutineAcademicYearSummary | null;
  inventoryContext: RoutineInventoryContext | null;
  counselor?: RoutinePersonSummary;
  appointment: RoutineAppointmentSummary | null;
  encounter: RoutineEncounterSummary | null;
  entryMode: RoutineEntryMode;
  deliveryMode: DeliveryMode;
  intakeStatus: RoutineIntakeStatus;
  intakeSubmittedAt: string | null;
  evaluationStatus?: RoutineEvaluationStatus;
  evaluationFinalizedAt?: string | null;
  createdAt: string;
  formRevision: RoutineFormRevisionSummary | null;
  studentFacing?: boolean;
}) {
  const revision = formRevisionLabel(formRevision);
  const program = routineProgramLabel(inventoryContext);
  const inventoryNote = routineInventoryNote(inventoryContext);

  return (
    <Panel aria-label="Routine Interview context" className="mb-5">
      <dl className="grid gap-x-7 gap-y-4 px-4 py-4 sm:grid-cols-2 sm:px-5 lg:grid-cols-3">
        <MetadataItem label="Student" value={personName} />
        <MetadataItem label="Academic Year" value={routineAcademicYearLabel(academicYear)} />
        {program ? <MetadataItem label="Course and major" value={program} /> : null}
        {inventoryNote ? <MetadataItem label="Individual Inventory" value={inventoryNote} /> : null}
        {counselor ? (
          <MetadataItem label="Counselor" value={counselor.display_name} />
        ) : null}
        <MetadataItem label="Nature of visit" value={routineEntryModeLabel(entryMode)} />
        <MetadataItem label="Delivery mode" value={routineDeliveryModeLabel(deliveryMode)} />
        {appointment ? (
          <MetadataItem
            label="Appointment"
            value={
              <span>
                {appointment.reference_code}
                <span className="block text-muted">
                  {formatRoutineDateTimeRange(appointment.starts_at, appointment.ends_at)}
                </span>
              </span>
            }
          />
        ) : null}
        {encounter ? (
          <MetadataItem
            label={studentFacing ? "Counseling session" : "Counseling Encounter"}
            value={
              <span>
                {formatRoutineDateTime(encounter.started_at)}
                <span className="block text-muted">
                  Ended {formatRoutineDateTime(encounter.ended_at)}
                </span>
              </span>
            }
          />
        ) : null}
        <MetadataItem
          label="Student Intake"
          value={
            <span className="inline-flex flex-wrap items-center gap-2">
              <RoutineStatus complete={intakeStatus === "SUBMITTED"}>
                {routineIntakeStatusLabel(intakeStatus)}
              </RoutineStatus>
              {intakeSubmittedAt ? (
                <span className="text-xs text-muted">
                  {formatRoutineDateTime(intakeSubmittedAt)}
                </span>
              ) : null}
            </span>
          }
        />
        {evaluationStatus ? (
          <MetadataItem
            label="Counselor Evaluation"
            value={
              <span className="inline-flex flex-wrap items-center gap-2">
                <RoutineStatus complete={evaluationStatus === "FINALIZED"}>
                  {routineEvaluationStatusLabel(evaluationStatus)}
                </RoutineStatus>
                {evaluationFinalizedAt ? (
                  <span className="text-xs text-muted">
                    {formatRoutineDateTime(evaluationFinalizedAt)}
                  </span>
                ) : null}
              </span>
            }
          />
        ) : null}
        <MetadataItem label="Created" value={formatRoutineDateTime(createdAt)} />
        {revision ? <MetadataItem label="Form revision" value={revision} /> : null}
      </dl>
    </Panel>
  );
}

export function RoutineQueryError({
  title = "Routine Interview could not be loaded.",
  message,
  onRetry,
  children,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  children?: ReactNode;
}) {
  return (
    <section role="alert" className="rounded-sm border border-danger/30 bg-surface-raised px-4 py-5 sm:px-5">
      <h2 className="font-semibold text-ink">{title}</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{message}</p>
      {children}
      {onRetry ? (
        <Button className="mt-4" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </section>
  );
}

// Rows shaped like the queue table. Inside the results panel the panel draws the frame; the route
// fallback has no panel yet, so it draws its own.
// Inside the results panel the panel draws the frame; the route fallback has no panel yet.
export function RoutineInterviewListSkeleton({
  label,
  framed = true,
}: {
  label: string;
  framed?: boolean;
}) {
  return <RowsSkeleton label={label} framed={framed} />;
}

export function RoutineInterviewDetailSkeleton() {
  return (
    <LoadingRegion label="Loading Routine Interview…">
      <Skeleton className="h-9 w-1/2" />
      <Skeleton className="mt-5 h-28 w-full" />
      <Skeleton className="mt-8 h-96 w-full" />
    </LoadingRegion>
  );
}

export function RoutineUnavailable({
  message = "Routine Interviews are unavailable to this account.",
}: {
  message?: string;
}) {
  return (
    <WorkspaceUnavailable title="Routine Interviews unavailable">
      {message}
    </WorkspaceUnavailable>
  );
}
