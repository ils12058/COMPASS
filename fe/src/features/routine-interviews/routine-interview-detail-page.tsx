"use client";

import Link from "next/link";

import { Skeleton } from "@/components/ui/skeleton";
import {
  RoutineStudentIntakeEditor,
  RoutineStudentIntakeReadOnly,
} from "@/features/routine-interviews/routine-student-intake";
import {
  RoutineCounselorEvaluationReadOnly,
  RoutineCounselorEvaluationWorkspace,
} from "@/features/routine-interviews/routine-counselor-evaluation";
import { getRoutineInterviewAccess } from "@/features/routine-interviews/routine-interviews-access";
import {
  RoutineContextSummary,
  RoutinePageHeading,
  RoutineQueryError,
  RoutineUnavailable,
  formatRoutineDateTime,
  routineErrorMessage,
} from "@/features/routine-interviews/routine-interviews-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  useRoutineInterviewsGetAssigned,
  useRoutineInterviewsGetMine,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

function RoutineBackLink() {
  return (
    <Link href="/portal/routine-interviews" className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
      Back to Routine Interviews
    </Link>
  );
}

export function RoutineInterviewDetailPage({
  routineInterviewId,
}: {
  routineInterviewId: string;
}) {
  const { user } = usePortalSession();
  const access = getRoutineInterviewAccess(user);

  if (access.isStudent && access.canViewSelf) {
    return <StudentRoutineDetail routineInterviewId={routineInterviewId} canManage={access.canManageSelf} />;
  }
  if (access.isCounselor && (access.canViewAssigned || access.canManageAssigned)) {
    return <CounselorRoutineDetail routineInterviewId={routineInterviewId} canManage={access.canManageAssigned} />;
  }
  return <RoutineUnavailable message="This Routine Interview is not available within your current access." />;
}

function StudentRoutineDetail({
  routineInterviewId,
  canManage,
}: {
  routineInterviewId: string;
  canManage: boolean;
}) {
  const query = useRoutineInterviewsGetMine(routineInterviewId, {
    query: { retry: false },
  });
  const detail = query.data?.data;

  if (query.isPending) {
    return <div aria-busy="true"><Skeleton className="h-9 w-1/2" /><Skeleton className="mt-5 h-28 w-full" /><Skeleton className="mt-8 h-96 w-full" /><p className="sr-only">Loading Routine Interview…</p></div>;
  }
  if (query.isError || !detail) {
    return (
      <div>
        <RoutinePageHeading title="Routine Interview" action={<RoutineBackLink />} />
        <RoutineQueryError message={routineErrorMessage(query.error, "This Routine Interview could not be loaded or is not available within your current access.")} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interview"
        description="Your Routine Interview details and Student Intake."
        action={<RoutineBackLink />}
      />
      <RoutineContextSummary
        personName={detail.inventory_context.full_name}
        inventoryContext={detail.inventory_context}
        counselor={detail.counselor}
        appointment={detail.appointment}
        encounter={detail.counseling_encounter}
        entryMode={detail.entry_mode}
        deliveryMode={detail.delivery_mode}
        intakeStatus={detail.intake_status}
        intakeSubmittedAt={detail.intake_submitted_at}
        createdAt={detail.created_at}
        formRevision={detail.form_revision}
      />
      {canManage && detail.intake_status === "DRAFT" ? (
        <RoutineStudentIntakeEditor
          key={detail.id}
          routineInterviewId={detail.id}
          initialIntake={detail.intake}
        />
      ) : (
        <section aria-labelledby="routine-student-intake-heading">
          <header className="border-b border-border pb-4">
            <h2 id="routine-student-intake-heading" className="font-heading text-2xl font-semibold text-ink">Student Intake</h2>
            <p className="mt-2 text-sm leading-6 text-muted">
              {detail.intake_status === "SUBMITTED"
                ? "Submitted responses are read-only."
                : "You can view your draft, but your current Student status does not allow Intake changes."}
            </p>
          </header>
          <RoutineStudentIntakeReadOnly intake={detail.intake} />
        </section>
      )}
    </div>
  );
}

function CounselorRoutineDetail({
  routineInterviewId,
  canManage,
}: {
  routineInterviewId: string;
  canManage: boolean;
}) {
  const query = useRoutineInterviewsGetAssigned(routineInterviewId, {
    query: { retry: false },
  });
  const detail = query.data?.data;

  if (query.isPending) {
    return <div aria-busy="true"><Skeleton className="h-9 w-1/2" /><Skeleton className="mt-5 h-28 w-full" /><Skeleton className="mt-8 h-96 w-full" /><p className="sr-only">Loading Routine Interview…</p></div>;
  }
  if (query.isError || !detail) {
    return (
      <div>
        <RoutinePageHeading title="Routine Interview" action={<RoutineBackLink />} />
        <RoutineQueryError message={routineErrorMessage(query.error, "This Routine Interview could not be loaded or is not available within your current access.")} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  // COMPASS decides whether the time-bounded Counseling Context is open to this Counselor.
  const workspaceHref = detail.counseling_context_available
    ? detail.appointment
      ? `/portal/counseling/workspace/appointment/${detail.appointment.id}`
      : `/portal/counseling/workspace/routine-interview/${detail.id}`
    : null;

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interview"
        description="Review the Student-authored Intake separately from the Counselor Evaluation."
        action={<div className="flex flex-wrap gap-2">{workspaceHref ? <Link href={workspaceHref} className="inline-flex min-h-10 items-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Open Counseling workspace</Link> : null}<RoutineBackLink /></div>}
      />
      <RoutineContextSummary
        personName={detail.inventory_context.full_name}
        inventoryContext={detail.inventory_context}
        appointment={detail.appointment}
        encounter={detail.counseling_encounter}
        entryMode={detail.entry_mode}
        deliveryMode={detail.delivery_mode}
        intakeStatus={detail.intake_status}
        intakeSubmittedAt={detail.intake_submitted_at}
        evaluationStatus={detail.evaluation_status}
        evaluationFinalizedAt={detail.evaluation_finalized_at}
        createdAt={detail.created_at}
        formRevision={detail.form_revision}
      />

      <section aria-labelledby="routine-student-intake-heading">
        <header className="border-b border-border pb-4">
          <h2 id="routine-student-intake-heading" className="font-heading text-2xl font-semibold text-ink">Student Intake</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {detail.intake_status === "DRAFT"
              ? "Student-authored responses are protected until submission."
              : "Student-authored responses are read-only for Counselors."}
          </p>
        </header>
        {detail.intake_status === "DRAFT" || detail.intake === null ? (
          <p role="status" className="border-b border-border py-5 text-sm text-muted">
            Student Intake is still a draft. The Student’s answers become available after they submit their Intake.
          </p>
        ) : (
          <RoutineStudentIntakeReadOnly intake={detail.intake} />
        )}
      </section>

      {detail.intake_status !== "SUBMITTED" ? (
        <section aria-labelledby="routine-evaluation-unavailable" className="mt-10 border-t-2 border-border pt-6">
          <h2 id="routine-evaluation-unavailable" className="font-heading text-2xl font-semibold text-ink">Counselor Evaluation</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Counselor Evaluation becomes available after the Student submits the Intake.
          </p>
        </section>
      ) : detail.evaluation_status === "FINALIZED" ? (
        <section aria-labelledby="routine-evaluation-heading" className="mt-10 border-t-2 border-brand pt-6">
          <header className="border-b border-border pb-4">
            <h2 id="routine-evaluation-heading" className="font-heading text-2xl font-semibold text-ink">Counselor Evaluation</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Finalized{detail.evaluation_finalized_at ? ` ${formatRoutineDateTime(detail.evaluation_finalized_at)}` : ""}. Read-only.</p>
          </header>
          <RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} />
        </section>
      ) : canManage ? (
        <RoutineCounselorEvaluationWorkspace
          key={detail.id}
          routineInterviewId={detail.id}
          entryMode={detail.entry_mode}
          initialEvaluation={detail.evaluation}
          evaluationFinalized={false}
        />
      ) : (
        <section aria-labelledby="routine-evaluation-heading" className="mt-10 border-t-2 border-brand pt-6">
          <header className="border-b border-border pb-4">
            <h2 id="routine-evaluation-heading" className="font-heading text-2xl font-semibold text-ink">Counselor Evaluation</h2>
            <p className="mt-2 text-sm leading-6 text-muted">Draft evaluation · Read-only in your current access.</p>
          </header>
          <RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} />
        </section>
      )}
    </div>
  );
}
