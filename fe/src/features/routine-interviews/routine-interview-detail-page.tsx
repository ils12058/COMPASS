"use client";

import { NotebookPen } from "lucide-react";
import { PageActionLink } from "@/components/ui/page-action";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
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
  RoutineInterviewDetailSkeleton,
  RoutinePageHeading,
  RoutineQueryError,
  RoutineUnavailable,
  formatRoutineDateTime,
  routineErrorMessage,
} from "@/features/routine-interviews/routine-interviews-shared";
import { userDisplayName } from "@/features/portal/components/portal-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { RoutineWorkflowState } from "@/lib/api/generated/model";
import {
  useRoutineInterviewsGetAssigned,
  useRoutineInterviewsGetMine,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

function routineWorkflowMessage(state: RoutineWorkflowState): string | null {
  if (state === RoutineWorkflowState.CLOSED_APPOINTMENT_CANCELLED) {
    return "This Routine Interview is no longer active because the Appointment was cancelled.";
  }
  if (state === RoutineWorkflowState.CLOSED_APPOINTMENT_NO_SHOW) {
    return "This Routine Interview is no longer active because the Appointment was marked as no-show.";
  }
  return null;
}

function RoutineLifecycleNotice({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <Notice role="status" className="mb-5">
      {message} The record remains available as historical context.
    </Notice>
  );
}

function RoutineBackLink() {
  return (
    <GuardedPortalLink href="/portal/routine-interviews" className={pageBackLinkClass}>
      Back to Routine Interviews
    </GuardedPortalLink>
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
    return <StudentRoutineDetail routineInterviewId={routineInterviewId} studentName={userDisplayName(user)} canManage={access.canManageSelf} />;
  }
  if (access.isCounselor && access.canViewAssigned) {
    return <CounselorRoutineDetail routineInterviewId={routineInterviewId} canManage={access.canManageAssigned} />;
  }
  return <RoutineUnavailable message="This Routine Interview is unavailable to this account." />;
}

function StudentRoutineDetail({
  routineInterviewId,
  studentName,
  canManage,
}: {
  routineInterviewId: string;
  studentName: string;
  canManage: boolean;
}) {
  const query = useRoutineInterviewsGetMine(routineInterviewId, {
    query: { retry: false },
  });
  const detail = query.data?.data;
  const workflowMessage = detail ? routineWorkflowMessage(detail.workflow_state) : null;
  const actionable = detail?.workflow_state === RoutineWorkflowState.ACTIVE;

  if (query.isPending) {
    return <RoutineInterviewDetailSkeleton />;
  }
  if (query.isError || !detail) {
    return (
      <div>
        <RoutinePageHeading title="Routine Interview" back={<RoutineBackLink />} />
        <RoutineQueryError message={routineErrorMessage(query.error, "This Routine Interview could not be loaded for this account.")} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interview"
        back={<RoutineBackLink />}
      />
      <RoutineContextSummary
        personName={detail.inventory_context?.full_name ?? studentName}
        academicYear={detail.academic_year}
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
        studentFacing
      />
      <RoutineLifecycleNotice message={workflowMessage} />
      {canManage && actionable && detail.intake_status === "DRAFT" ? (
        <RoutineStudentIntakeEditor
          key={detail.id}
          routineInterviewId={detail.id}
          initialIntake={detail.intake}
        />
      ) : (
        <Panel aria-labelledby="routine-student-intake-heading">
          <PanelHeader
            title="Student Intake"
            titleId="routine-student-intake-heading"
            description={detail.intake_status === "SUBMITTED"
              ? "Submitted responses are read-only."
              : !actionable
                ? "This draft is preserved for history and is now read-only."
                : "You can view your draft, but your current Student status does not allow Intake changes."}
          />
          <div className="px-4 sm:px-5">
            <RoutineStudentIntakeReadOnly intake={detail.intake} />
          </div>
        </Panel>
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
  const workflowMessage = detail ? routineWorkflowMessage(detail.workflow_state) : null;
  const actionable = detail?.workflow_state === RoutineWorkflowState.ACTIVE;

  if (query.isPending) {
    return <RoutineInterviewDetailSkeleton />;
  }
  if (query.isError || !detail) {
    return (
      <div>
        <RoutinePageHeading title="Routine Interview" back={<RoutineBackLink />} />
        <RoutineQueryError message={routineErrorMessage(query.error, "This Routine Interview could not be loaded for this account.")} onRetry={() => void query.refetch()} />
      </div>
    );
  }

  // COMPASS decides whether the time-bounded Counseling Context is open to this Counselor.
  const workspaceHref = actionable && detail.counseling_context_available
    ? detail.appointment
      ? `/portal/counseling/workspace/appointment/${detail.appointment.id}`
      : `/portal/counseling/workspace/routine-interview/${detail.id}`
    : null;

  return (
    <div>
      <RoutinePageHeading
        title="Routine Interview"
        back={<RoutineBackLink />}
        action={workspaceHref ? <PageActionLink as={GuardedPortalLink} href={workspaceHref} icon={NotebookPen} variant="secondary" label="Open Counseling workspace" /> : undefined}
      />
      <RoutineContextSummary
        personName={detail.inventory_context?.full_name ?? detail.student.display_name}
        academicYear={detail.academic_year}
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
      <RoutineLifecycleNotice message={workflowMessage} />

      <div className="space-y-5">
      <Panel aria-labelledby="routine-student-intake-heading">
        <PanelHeader
          title="Student Intake"
          titleId="routine-student-intake-heading"
          description={detail.intake_status === "DRAFT"
            ? "Student-authored responses are protected until submission."
            : "Student-authored responses are read-only for Counselors."}
        />
        {detail.intake_status === "DRAFT" || detail.intake === null ? (
          <PanelMessage role="status">
            Student Intake is still a draft. The Student’s answers become available after they submit their Intake.
          </PanelMessage>
        ) : (
          <div className="px-4 sm:px-5">
            <RoutineStudentIntakeReadOnly intake={detail.intake} />
          </div>
        )}
      </Panel>

      {detail.intake_status !== "SUBMITTED" ? (
        <Panel aria-labelledby="routine-evaluation-unavailable">
          <PanelHeader title="Counselor Evaluation" titleId="routine-evaluation-unavailable" />
          <PanelMessage>
            Counselor Evaluation becomes available after the Student submits the Intake.
          </PanelMessage>
        </Panel>
      ) : detail.evaluation_status === "FINALIZED" ? (
        <Panel aria-labelledby="routine-evaluation-heading">
          <PanelHeader
            title="Counselor Evaluation"
            titleId="routine-evaluation-heading"
            description={`Finalized${detail.evaluation_finalized_at ? ` ${formatRoutineDateTime(detail.evaluation_finalized_at)}` : ""}. Read-only.`}
          />
          <div className="px-4 sm:px-5">
            <RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} />
          </div>
        </Panel>
      ) : canManage ? (
        <RoutineCounselorEvaluationWorkspace
          key={detail.id}
          routineInterviewId={detail.id}
          entryMode={detail.entry_mode}
          linkedEncounter={detail.counseling_encounter}
          workspaceHref={workspaceHref}
          initialEvaluation={detail.evaluation}
          evaluationFinalized={false}
        />
      ) : (
        <Panel aria-labelledby="routine-evaluation-heading">
          <PanelHeader
            title="Counselor Evaluation"
            titleId="routine-evaluation-heading"
            description={actionable
              ? "Draft evaluation · Read-only for this account."
              : "Draft evaluation · Preserved for history and read-only because the Appointment is no longer active."}
          />
          <div className="px-4 sm:px-5">
            <RoutineCounselorEvaluationReadOnly evaluation={detail.evaluation} />
          </div>
        </Panel>
      )}
      </div>
    </div>
  );
}
