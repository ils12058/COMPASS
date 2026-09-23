import Link from "next/link";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type {
  DeliveryMode,
  RoutineAppointmentSummary,
  RoutineEncounterSummary,
  RoutineEntryMode,
  RoutineEvaluationStatus,
  RoutineFormRevisionSummary,
  RoutineIntakeStatus,
  RoutineInventoryContext,
  RoutinePersonSummary,
} from "@/lib/api/generated/model";
import { CompassApiError, readApiErrorCode, readApiErrorMessage } from "@/lib/api/errors";

export function formatRoutineDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatRoutineDateTimeRange(start: string, end: string): string {
  return formatRoutineDateTime(start) + " – " + new Intl.DateTimeFormat("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(end));
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

export function routineDeliveryModeLabel(mode: DeliveryMode): string {
  return mode === "ONLINE" ? "Online" : "In person";
}

export function routineIntakeStatusLabel(status: RoutineIntakeStatus): string {
  return status === "SUBMITTED" ? "Submitted" : "Draft";
}

export function routineEvaluationStatusLabel(
  status: RoutineEvaluationStatus,
): string {
  return status === "FINALIZED" ? "Finalized" : "Draft";
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
    "This Routine Interview is not available in your current access.",
  routine_interview_not_permitted:
    "This Routine Interview is not available in your current access.",
  routine_interview_inventory_required:
    "A submitted Individual Inventory for the current Academic Year is required before starting an Appointment-backed Routine Interview.",
  routine_interview_appointment_invalid:
    "This Appointment is no longer eligible for a Routine Interview. Refresh the candidates and try again.",
  routine_interview_intake_already_submitted:
    "The Student Intake has already been submitted and is now read-only.",
  routine_interview_intake_required:
    "The Student must submit the Intake before the Counselor Evaluation can be finalized.",
  routine_interview_evaluation_finalized:
    "The Counselor Evaluation has already been finalized and is read-only.",
  routine_interview_encounter_required:
    "A matching completed Counseling Encounter is required before finalization.",
  routine_interview_encounter_mismatch:
    "That Counseling Encounter no longer matches this Routine Interview. Refresh the available encounters and choose again.",
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
  return readApiErrorMessage(error.body) ?? fallback;
}

export function RoutinePageHeading({
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
        {description ? (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </header>
  );
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
    <div className="min-w-0 py-3 sm:py-2">
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
}: {
  personName: string;
  inventoryContext: RoutineInventoryContext;
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
}) {
  const revision = formRevisionLabel(formRevision);
  const major = inventoryContext.major.trim();

  return (
    <section
      aria-label="Routine Interview context"
      className="mb-8 border-y border-border"
    >
      <dl className="grid gap-x-7 divide-y divide-border sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-3">
        <MetadataItem label="Student" value={personName} />
        <MetadataItem label="Academic Year" value={inventoryContext.academic_year.label} />
        <MetadataItem
          label="Course and major"
          value={major ? inventoryContext.course + " · " + major : inventoryContext.course}
        />
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
            label="Counseling Encounter"
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
        <MetadataItem label="Routine created" value={formatRoutineDateTime(createdAt)} />
        {revision ? <MetadataItem label="Form revision" value={revision} /> : null}
      </dl>
    </section>
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
    <section role="alert" className="border-y border-danger/30 py-6">
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

export function RoutineUnavailable({
  message = "Your current access does not include a Routine Interview workspace.",
}: {
  message?: string;
}) {
  return (
    <section className="max-w-xl border-y border-border py-8">
      <h1 className="font-heading text-3xl font-bold text-ink">
        Routine Interviews unavailable
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">{message}</p>
      <Link
        href="/portal"
        className="mt-5 inline-block min-h-10 text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Return to Home
      </Link>
    </section>
  );
}

export function RoutinePagination({
  page,
  hasNext,
  label,
  onPrevious,
  onNext,
}: {
  page: number;
  hasNext: boolean;
  label: string;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav
      aria-label={label}
      className="flex items-center justify-between gap-3 border-t border-border py-4"
    >
      <p className="text-sm text-muted">Page {page}</p>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={onPrevious}>
          Previous
        </Button>
        <Button variant="secondary" disabled={!hasNext} onClick={onNext}>
          Next
        </Button>
      </div>
    </nav>
  );
}
