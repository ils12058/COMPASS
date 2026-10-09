"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { MoreHorizontal } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader, PanelMessage, PanelSection, RecordSummary } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
import {
  appointmentSlotFreshness,
  isSlotTakenError,
  slotIsOffered,
  SLOT_JUST_TAKEN,
  SLOT_NO_LONGER_AVAILABLE,
  SLOTS_NOT_RECHECKED,
  useSlotSelection,
} from "@/features/appointments/appointment-slot-freshness";
import { canShowLastKnownData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import {
  AppointmentDetailSkeleton,
  AppointmentStatusBadge,
  AppointmentsLocalNavigation,
  AppointmentsPageHeading,
  AppointmentsUnavailable,
  appointmentErrorCode,
  appointmentErrorMessage,
  deliveryModeLabel,
  formatAppointmentDateTime,
  formatAppointmentTime,
} from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { getECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { GuidanceContextualMessages, GuidanceMessagesTrigger } from "@/features/guidance-messages/guidance-contextual-messages";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";
import { formatInstitutionalDateTime, institutionalDateInputValue } from "@/lib/institutional-time";
import { isCounselingService } from "@/features/counseling/canonical-counseling-service";
import {
  AppointmentActionBlocker,
  AppointmentActionConsequenceCode,
  AppointmentStatus,
  DeliveryMode,
  type AppointmentActionsResponse,
  type BookableSlotResponse,
} from "@/lib/api/generated/model";
import {
  getAppointmentsGetHistoryQueryKey,
  getAppointmentsGetQueryKey,
  getAppointmentsListBookableSlotsQueryKey,
  getAppointmentsListManagedQueryKey,
  getAppointmentsListMyQueryKey,
  getAppointmentsListRescheduleSlotsQueryKey,
  useAppointmentsCancel,
  useAppointmentsComplete,
  useAppointmentsGet,
  useAppointmentsGetHistory,
  useAppointmentsListReassignmentCandidates,
  useAppointmentsListRescheduleSlots,
  useAppointmentsMarkNoShow,
  useAppointmentsReassign,
  useAppointmentsReschedule,
} from "@/lib/api/generated/appointments/appointments";
import {
  getECounselingGetAssignedWorkspaceQueryKey,
  getECounselingGetMyWorkspaceQueryKey,
} from "@/lib/api/generated/e-counseling/e-counseling";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsGetMineQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListMineQueryKey,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

type ConfirmAction = "cancel" | "complete" | "no-show";
type ActionError = { scope: "confirm" | "reschedule" | "reassign"; message: string };

function occurredAt(value: string): string {
  return formatInstitutionalDateTime(value);
}

function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    CREATED: "Appointment created",
    RESCHEDULED: "Appointment rescheduled",
    REASSIGNED: "Counselor reassigned",
    CANCELLED: "Appointment cancelled",
    COMPLETED: "Appointment completed",
    NO_SHOW: "Marked no-show",
  };
  return labels[eventType] ?? "Appointment updated";
}

function eventContext(entry: {
  event_type: string;
  previous_starts_at: string | null;
  previous_ends_at: string | null;
  new_starts_at: string | null;
  new_ends_at: string | null;
  previous_provider: { display_name: string; id: string } | null;
  new_provider: { display_name: string; id: string } | null;
}): string | null {
  if (entry.event_type === "RESCHEDULED") {
    const previous = entry.previous_starts_at
      ? entry.previous_ends_at
        ? formatAppointmentDateTime(entry.previous_starts_at, entry.previous_ends_at)
        : occurredAt(entry.previous_starts_at)
      : null;
    const next = entry.new_starts_at
      ? entry.new_ends_at
        ? formatAppointmentDateTime(entry.new_starts_at, entry.new_ends_at)
        : occurredAt(entry.new_starts_at)
      : null;
    return previous && next ? `${previous} → ${next}` : next ?? previous;
  }
  if (entry.event_type === "REASSIGNED") {
    const previous = entry.previous_provider?.display_name;
    const next = entry.new_provider?.display_name;
    return previous && next ? `${previous} → ${next}` : next ?? previous ?? null;
  }
  return null;
}

const actionNames: Record<keyof AppointmentActionsResponse, string> = {
  cancel: "Cancel",
  reschedule: "Reschedule",
  reassign: "Reassign counselor",
  complete: "Complete",
  mark_no_show: "Mark no-show",
};

// NOT_PERMITTED and NOT_SCHEDULED are not explained here: the actor's access and the
// status badge already say why nothing can be changed.
const blockerExplanations: Partial<Record<AppointmentActionBlocker, string>> = {
  [AppointmentActionBlocker.ALREADY_STARTED]: "The appointment has already started.",
  [AppointmentActionBlocker.NOT_STARTED]: "Available once the appointment starts.",
  [AppointmentActionBlocker.NOT_ENDED]: "Available once the appointment ends.",
  [AppointmentActionBlocker.CUTOFF_PASSED]: "The deadline to change this appointment has passed.",
  [AppointmentActionBlocker.CURRENT_STUDENT_REQUIRED]: "Only a current student can reschedule an appointment.",
  [AppointmentActionBlocker.ECOUNSELING_ROOM_LINKED]: "An E-Counseling room is already linked to this Appointment.",
  [AppointmentActionBlocker.ECOUNSELING_ACCESS_STARTED]: "This Appointment can no longer be cancelled because its online counseling access period has begun.",
  [AppointmentActionBlocker.ECOUNSELING_ACCESS_OPEN]: "Wait until the online counseling access or rejoin period has ended.",
  [AppointmentActionBlocker.ROUTINE_INTERVIEW_LINKED]: "A Routine Interview is already linked to this Appointment.",
  [AppointmentActionBlocker.COUNSELING_ENCOUNTER_LINKED]: "A Counseling encounter is already linked to this Appointment.",
};

function unavailableActions(actions: AppointmentActionsResponse): { action: string; reason: string }[] {
  return (Object.keys(actionNames) as (keyof AppointmentActionsResponse)[]).flatMap((name) => {
    const { allowed, blocker } = actions[name];
    const reason = !allowed && blocker ? blockerExplanations[blocker] : undefined;
    return reason ? [{ action: actionNames[name], reason }] : [];
  });
}

function ActionConfirmation({
  action,
  busy,
  selfCancellation,
  referenceCode,
  error,
  routineInterviewWillClose,
  onClose,
  onConfirm,
}: {
  action: ConfirmAction | null;
  busy: boolean;
  selfCancellation: boolean;
  referenceCode: string;
  error: string | null;
  routineInterviewWillClose: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const content: Record<ConfirmAction, { title: string; description: string; confirm: string; pending: string; variant: "danger" | "primary" }> = {
    cancel: {
      title: `Cancel Appointment ${referenceCode}?`,
      description: selfCancellation
        ? "This scheduled appointment will be cancelled. You can still view it in your appointment history."
        : "This scheduled appointment will be cancelled. You can still view its record afterward.",
      confirm: "Cancel appointment",
      pending: "Cancelling…",
      variant: "danger",
    },
    complete: {
      title: `Complete Appointment ${referenceCode}?`,
      description: "This appointment will be marked completed and will no longer be scheduled.",
      confirm: "Complete appointment",
      pending: "Completing…",
      variant: "primary",
    },
    "no-show": {
      title: `Mark Appointment ${referenceCode} as no-show?`,
      description: "This appointment will be marked no-show and will no longer be scheduled.",
      confirm: "Mark no-show",
      pending: "Marking no-show…",
      variant: "danger",
    },
  };
  if (!action) return null;
  const selected = content[action];

  return (
    <ConsequentialActionDialog
      open
      title={selected.title}
      confirmLabel={selected.confirm}
      pendingLabel={selected.pending}
      pending={busy}
      error={error}
      variant={selected.variant}
      cancelLabel={action === "cancel" ? "Keep appointment" : "Back to appointment"}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      onConfirm={onConfirm}
    >
      <p>{selected.description}</p>
      {routineInterviewWillClose ? (
        <p>
          The linked Routine Interview will remain in COMPASS for record history, but no further intake or evaluation changes can be made.
        </p>
      ) : null}
    </ConsequentialActionDialog>
  );
}

function DetailContent({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  const ecounselingAccess = getECounselingAccess(user);
  const queryClient = useQueryClient();
  const appointmentQuery = useAppointmentsGet(appointmentId, { query: { retry: false } });
  const historyQuery = useAppointmentsGetHistory(appointmentId, {
    query: { enabled: appointmentQuery.isSuccess, retry: false },
  });
  const cancel = useAppointmentsCancel();
  const reschedule = useAppointmentsReschedule();
  const reassign = useAppointmentsReassign();
  const complete = useAppointmentsComplete();
  const noShow = useAppointmentsMarkNoShow();

  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  // Covers the whole confirmation, including the refresh after the request succeeds.
  const [confirming, setConfirming] = useState(false);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [reassignmentReason, setReassignmentReason] = useState("");
  const [reassigning, setReassigning] = useState(false);
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [reassignmentOpen, setReassignmentOpen] = useState(false);
  const [error, setError] = useState<ActionError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Set when an action found the Appointment changed and the page reloaded it.
  const [updatedNotice, setUpdatedNotice] = useState<string | null>(null);

  const appointment = appointmentQuery.data?.data;
  // A failed reload keeps the last confirmed details on screen, but actions wait for a fresh copy.
  const detailsUnconfirmed = appointmentQuery.isError && appointment !== undefined;
  // COMPASS projects availability for this actor with server time and linked records.
  // Every mutation still revalidates, so conflicts reload the Appointment below.
  const actions = detailsUnconfirmed ? undefined : appointment?.actions;
  const canCancel = actions?.cancel.allowed === true;
  const canReschedule = actions?.reschedule.allowed === true;
  const canReassign = actions?.reassign.allowed === true;
  const canComplete = actions?.complete.allowed === true;
  const canMarkNoShow = actions?.mark_no_show.allowed === true;
  const unavailable = actions ? unavailableActions(actions) : [];
  // A confirmation is only offered while its action is still allowed for the latest details.
  const confirmationAllowed =
    (confirmAction === "cancel" && canCancel) ||
    (confirmAction === "complete" && canComplete) ||
    (confirmAction === "no-show" && canMarkNoShow);

  const rescheduleSlots = useAppointmentsListRescheduleSlots(
    appointmentId,
    { date: rescheduleDate || "1970-01-01" },
    {
      query: {
        enabled: Boolean(appointment && canReschedule && rescheduleOpen && rescheduleDate),
        retry: false,
        ...appointmentSlotFreshness,
      },
    },
  );
  const rescheduleSlotItems = rescheduleSlots.data?.data.items ?? [];
  const rescheduleChoice = useSlotSelection(rescheduleSlots.data?.data.items, rescheduleSlots.dataUpdatedAt);
  const selectedRescheduleSlot = rescheduleSlotItems.find(
    (slot) => slot.starts_at === rescheduleChoice.selected,
  );
  const rescheduleSlotsUnconfirmed = rescheduleSlots.isError && rescheduleSlots.data !== undefined;

  const candidates = useAppointmentsListReassignmentCandidates(appointmentId, {
    query: {
      enabled: Boolean(appointment && canReassign && reassignmentOpen),
      retry: false,
    },
  });
  const candidateItems = (candidates.data?.data.items ?? []).filter(
    (candidate) => candidate.id !== appointment?.provider.id,
  );
  const selectedCandidate = candidateItems.find(
    (candidate) => candidate.id === selectedProviderId,
  );

  const pending =
    cancel.isPending ||
    rescheduling ||
    reschedule.isPending ||
    reassign.isPending ||
    reassigning ||
    complete.isPending ||
    noShow.isPending ||
    confirming;

  async function refreshAppointmentQueries(includeSchedulingSlots = false) {
    const invalidations = [
      queryClient.invalidateQueries({ queryKey: getAppointmentsGetQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getAppointmentsGetHistoryQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getAppointmentsListMyQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getAppointmentsListManagedQueryKey() }),
    ];
    if (includeSchedulingSlots) {
      invalidations.push(
        queryClient.invalidateQueries({ queryKey: getAppointmentsListBookableSlotsQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getAppointmentsListRescheduleSlotsQueryKey(appointmentId) }),
      );
    }
    await Promise.all(invalidations);
  }

  async function refreshDependentWorkflowQueries(routineInterviewId?: string) {
    const invalidations = [
      queryClient.invalidateQueries({
        queryKey: getECounselingGetMyWorkspaceQueryKey(appointmentId),
      }),
      queryClient.invalidateQueries({
        queryKey: getECounselingGetAssignedWorkspaceQueryKey(appointmentId),
      }),
    ];
    if (routineInterviewId) {
      invalidations.push(
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        }),
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId),
        }),
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsListMineQueryKey(),
        }),
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsListAssignedQueryKey(),
        }),
      );
    }
    await Promise.all(invalidations);
  }

  async function handleMutationError(
    caught: unknown,
    fallback: string,
    scope: ActionError["scope"],
  ) {
    if (scope === "reassign" && isSlotTakenError(caught)) {
      // The chosen Counselor is no longer free at this time; the reason stays as typed.
      setSelectedProviderId("");
      setError({ scope, message: "The selected Counselor is no longer available at this time. Choose another Counselor." });
      void candidates.refetch();
      return;
    }
    if (caught instanceof CompassApiError && caught.status === 409) {
      // The Appointment changed after this page loaded. Close the stale confirmation, reload the
      // Appointment so its actions are recalculated, and let the person review them again; the
      // action is never resubmitted automatically.
      setConfirmAction(null);
      setError(null);
      await refreshAppointmentQueries();
      const reloaded = queryClient.getQueryState(getAppointmentsGetQueryKey(appointmentId))?.status !== "error";
      const reason = appointmentErrorMessage(caught, "This appointment was updated before your action completed.");
      setUpdatedNotice(reloaded ? `${reason} The latest details are now shown.` : reason);
      return;
    }
    setError({ scope, message: appointmentErrorMessage(caught, fallback) });
  }

  async function confirmMutation() {
    if (!appointment || !confirmAction) return;
    const routineConsequence =
      confirmAction === "cancel"
        ? actions?.cancel.consequences.find(
            (item) => item.code === AppointmentActionConsequenceCode.ROUTINE_INTERVIEW_WILL_CLOSE,
          )
        : confirmAction === "no-show"
          ? actions?.mark_no_show.consequences.find(
              (item) => item.code === AppointmentActionConsequenceCode.ROUTINE_INTERVIEW_WILL_CLOSE,
            )
          : undefined;
    setError(null);
    setNotice(null);
    setUpdatedNotice(null);
    setConfirming(true);
    try {
      if (confirmAction === "cancel") {
        await cancel.mutateAsync({ appointmentId });
        await Promise.all([
          refreshAppointmentQueries(true),
          refreshDependentWorkflowQueries(routineConsequence?.routine_interview_id),
        ]);
        setNotice("Appointment cancelled.");
      } else if (confirmAction === "complete") {
        await complete.mutateAsync({ appointmentId });
        await Promise.all([
          refreshAppointmentQueries(),
          refreshDependentWorkflowQueries(),
        ]);
        setNotice("Appointment completed.");
      } else {
        await noShow.mutateAsync({ appointmentId });
        await Promise.all([
          refreshAppointmentQueries(),
          refreshDependentWorkflowQueries(routineConsequence?.routine_interview_id),
        ]);
        setNotice("Appointment marked no-show.");
      }
      setConfirmAction(null);
    } catch (caught) {
      await handleMutationError(caught, "The Appointment could not be updated.", "confirm");
    } finally {
      setConfirming(false);
    }
  }

  async function submitReschedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRescheduleSlot) return;
    const startsAt = selectedRescheduleSlot.starts_at;
    setError(null);
    setNotice(null);
    setUpdatedNotice(null);
    setRescheduling(true);
    try {
      // Advisory recheck before submitting; the server still decides.
      const recheck = await rescheduleSlots.refetch();
      if (recheck.isError) {
        setError({ scope: "reschedule", message: SLOTS_NOT_RECHECKED });
        return;
      }
      if (!slotIsOffered(recheck.data?.data.items, startsAt)) {
        rescheduleChoice.drop();
        return;
      }
      await reschedule.mutateAsync({
        appointmentId,
        data: {
          starts_at: startsAt,
          ...(rescheduleReason.trim() ? { reason: rescheduleReason.trim() } : {}),
        },
      });
      await refreshAppointmentQueries(true);
      setRescheduleOpen(false);
      rescheduleChoice.clear();
      setRescheduleReason("");
      setNotice("Appointment rescheduled.");
    } catch (caught) {
      if (isSlotTakenError(caught)) {
        // The reason stays as typed; only the time needs choosing again.
        rescheduleChoice.clear();
        setError({ scope: "reschedule", message: SLOT_JUST_TAKEN });
        void rescheduleSlots.refetch();
        return;
      }
      await handleMutationError(caught, "The Appointment could not be rescheduled.", "reschedule");
    } finally {
      setRescheduling(false);
    }
  }

  async function submitReassignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProviderId || !reassignmentReason.trim() || reassigning) return;
    setError(null);
    setNotice(null);
    setUpdatedNotice(null);
    setReassigning(true);
    try {
      await reassign.mutateAsync({
        appointmentId,
        data: {
          provider_id: selectedProviderId,
          reason: reassignmentReason.trim(),
        },
      });
      await refreshAppointmentQueries(true);
      setReassignmentOpen(false);
      setSelectedProviderId("");
      setReassignmentReason("");
      setNotice("Counselor reassigned.");
    } catch (caught) {
      await handleMutationError(caught, "The Counselor could not be reassigned.", "reassign");
    } finally {
      setReassigning(false);
    }
  }

  if (!access.hasWorkspace) return <AppointmentsUnavailable />;
  if (appointmentQuery.isPending) {
    return <AppointmentDetailSkeleton />;
  }
  if ((appointmentQuery.isError && !canShowLastKnownData(appointmentQuery)) || !appointment) {
    const notFound = appointmentErrorCode(appointmentQuery.error) === "appointment_not_found";
    return (
      <section>
        <AppointmentsLocalNavigation />
        <Notice
          role="alert"
          className="max-w-2xl px-5 py-6 sm:px-6"
          title={
            <h1 className="font-heading text-2xl font-bold text-ink">
              {notFound ? "Appointment not available" : "Appointment could not be loaded"}
            </h1>
          }
          action={<Button variant="secondary" onClick={() => void appointmentQuery.refetch()}>Retry</Button>}
        >
          {notFound
            ? "This appointment is unavailable to this account."
            : appointmentErrorMessage(appointmentQuery.error, "Appointment details could not be loaded.")}
        </Notice>
      </section>
    );
  }

  const historyItems = historyQuery.data?.data.items ?? [];
  const confirmationRoutineConsequence =
    confirmAction === "cancel"
      ? actions?.cancel.consequences.find(
          (item) => item.code === AppointmentActionConsequenceCode.ROUTINE_INTERVIEW_WILL_CLOSE,
        )
      : confirmAction === "no-show"
        ? actions?.mark_no_show.consequences.find(
            (item) => item.code === AppointmentActionConsequenceCode.ROUTINE_INTERVIEW_WILL_CLOSE,
          )
        : undefined;

  const showCounselingLink = appointment.counseling_context_available;
  const showEcounselingLink =
    appointment.status === AppointmentStatus.SCHEDULED &&
    isCounselingService(appointment.service) &&
    appointment.delivery_mode === DeliveryMode.ONLINE &&
    ((ecounselingAccess.isStudent && ecounselingAccess.canViewSelf && appointment.student.id === user.id) ||
      (ecounselingAccess.isCounselor && ecounselingAccess.canViewAssigned && appointment.provider.id === user.id));

  // Messages opens the Appointment's one Counseling thread beside this page (ADR-103). Only
  // canonical Counseling Appointments ask; the backend decides whether it is offered.
  const counseling = isCounselingService(appointment.service);
  const counterpartName = appointment.student.id === user.id ? appointment.provider.display_name : appointment.student.display_name;

  return (
    <GuidanceContextualMessages appointmentId={appointment.id} counterpartName={counterpartName} enabled={counseling}>
    <section aria-labelledby="appointment-detail-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="appointment-detail-heading"
        title="Appointment"
        action={
          <>
            {showCounselingLink ? (
              <Link href={`/portal/counseling/workspace/appointment/${appointment.id}`} className={buttonVariants({ variant: "secondary" })}>
                Open Counseling workspace
              </Link>
            ) : null}
            {showEcounselingLink ? (
              <Link href={`/portal/e-counseling/${appointment.id}`} className={buttonVariants({ variant: "secondary" })}>
                Open E-Counseling
              </Link>
            ) : null}
            {counseling ? <GuidanceMessagesTrigger /> : null}
          </>
        }
      />

      {notice ? <Notice role="status" tone="success" className="mb-4">{notice}</Notice> : null}
      {updatedNotice ? <Notice role="status" tone="info" className="mb-4">{updatedNotice}</Notice> : null}
      {detailsUnconfirmed ? (
        <RefreshFailureNotice
          message="The latest appointment details could not be loaded. Showing the last confirmed details; actions are unavailable until they load."
          onRetry={() => void appointmentQuery.refetch()}
          retrying={appointmentQuery.isFetching}
        />
      ) : null}

      <div className="space-y-5">
      <Panel aria-labelledby="appointment-reference-heading">
        <RecordSummary
          label="Appointment"
          title={<span className="break-all font-mono text-lg">{appointment.reference_code}</span>}
          titleId="appointment-reference-heading"
          status={<AppointmentStatusBadge status={appointment.status} />}
          facts={[
            { label: "Service", value: appointment.service.name },
            ...(!access.isStudent
              ? [{
                  label: "Student",
                  value: (
                    <>
                      <span className="block break-words">{appointment.student.display_name}</span>
                      {appointment.student.institutional_id ? <span className="mt-0.5 block break-all text-xs text-muted">{appointment.student.institutional_id}</span> : null}
                    </>
                  ),
                }]
              : []),
            { label: "Counselor", value: appointment.provider.display_name },
            { label: "Date and time", value: formatAppointmentDateTime(appointment.starts_at, appointment.ends_at) },
          ]}
        />
        <PanelSection title="Details" titleId="appointment-details-heading">
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
            <div><dt className="text-xs font-semibold text-muted">Delivery</dt><dd className="mt-1 text-sm text-ink">{deliveryModeLabel(appointment.delivery_mode)}</dd></div>
            {appointment.cancellation_cutoff_minutes !== null ? (
              <div><dt className="text-xs font-semibold text-muted">Student change deadline</dt><dd className="mt-1 text-sm text-ink">Students must cancel or reschedule at least {appointment.cancellation_cutoff_minutes} minutes before the appointment starts.</dd></div>
            ) : null}
            <div><dt className="text-xs font-semibold text-muted">Created</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.created_at)}</dd></div>
            {appointment.cancelled_at ? <div><dt className="text-xs font-semibold text-muted">Cancelled</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.cancelled_at)}</dd></div> : null}
            {appointment.completed_at ? <div><dt className="text-xs font-semibold text-muted">Completed</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.completed_at)}</dd></div> : null}
            {appointment.no_show_at ? <div><dt className="text-xs font-semibold text-muted">Marked no-show</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.no_show_at)}</dd></div> : null}
          </dl>
        </PanelSection>
      </Panel>

      {(canCancel || canReschedule || canReassign || canComplete || canMarkNoShow || unavailable.length > 0) ? (
        <Panel aria-labelledby="appointment-actions-heading">
          <PanelHeader title="Actions" titleId="appointment-actions-heading" />
          <PanelBody className="*:first:mt-0">
          {canCancel || canReschedule || canReassign || canComplete || canMarkNoShow ? (
            // The usual outcome leads; cancelling, the destructive one, comes last.
            <div className="mt-4 flex flex-wrap gap-2">
              {canComplete ? <Button disabled={pending} onClick={() => { setError(null); setConfirmAction("complete"); }}>Complete appointment</Button> : null}
              {canReschedule ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); rescheduleChoice.clear(); setNotice(null); setReassignmentOpen(false); setRescheduleOpen(true); }}>Reschedule</Button> : null}
              {canReassign ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); setNotice(null); setRescheduleOpen(false); setReassignmentOpen(true); }}>Reassign</Button> : null}
              {canMarkNoShow ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild><Button variant="secondary" disabled={pending}><MoreHorizontal aria-hidden="true" size={18} />More actions</Button></DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => { setError(null); setConfirmAction("no-show"); }}>Mark no-show</DropdownMenuItem>
                    {canCancel ? <DropdownMenuItem className="text-danger" onSelect={() => { setError(null); setConfirmAction("cancel"); }}>Cancel appointment</DropdownMenuItem> : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : canCancel ? <Button variant="danger" disabled={pending} onClick={() => { setError(null); setConfirmAction("cancel"); }}>Cancel appointment</Button> : null}
            </div>
          ) : null}
          {error && ((error.scope === "reschedule" && !canReschedule) || (error.scope === "reassign" && !canReassign)) ? (
            <p role="alert" className="mt-4 text-sm text-danger">{error.message}</p>
          ) : null}
          {unavailable.length > 0 ? (
            <div className="mt-4 max-w-3xl">
              <h3 className="text-sm font-semibold text-ink">Not available right now</h3>
              <ul className="mt-2 space-y-1 text-sm text-muted">
                {unavailable.map((item) => (
                  <li key={item.action}><span className="font-semibold text-ink">{item.action}:</span> {item.reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
          </PanelBody>

          {canReschedule ? (
            <Dialog open={rescheduleOpen} onOpenChange={setRescheduleOpen}>
            <DialogContent className="max-w-2xl" dismissible={!rescheduling}>
            <DialogTitle>Reschedule appointment</DialogTitle>
            <DialogDescription>Choose a new time and review it before saving.</DialogDescription>
            <form onSubmit={submitReschedule} className="mt-5">
              <div className="grid gap-2 sm:max-w-xs">
                <Label htmlFor="reschedule-date">New date</Label>
                <Input
                  id="reschedule-date"
                  type="date"
                  min={institutionalDateInputValue()}
                  value={rescheduleDate}
                  disabled={rescheduling}
                  onChange={(event) => {
                    setRescheduleDate(event.target.value);
                    rescheduleChoice.clear();
                    setError(null);
                  }}
                />
              </div>
              {rescheduleDate ? (
                <div className="mt-4">
                  {rescheduleChoice.lost ? (
                    <p role="status" className="mb-3 text-sm text-warning">{SLOT_NO_LONGER_AVAILABLE}</p>
                  ) : null}
                  {rescheduleSlots.isPending ? (
                    <LoadingRegion label="Loading replacement times…" className="flex flex-wrap gap-2"><Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" /></LoadingRegion>
                  ) : rescheduleSlots.isError && !rescheduleSlotsUnconfirmed ? (
                    <div role="alert"><p className="text-sm text-danger">Replacement times could not be loaded.</p><Button className="mt-2" variant="secondary" onClick={() => void rescheduleSlots.refetch()}>Retry</Button></div>
                  ) : rescheduleSlotItems.length === 0 ? (
                    <p role="status" className="text-sm text-muted">No times are available. Choose another date.</p>
                  ) : (
                    <>
                      {rescheduleSlotsUnconfirmed ? (
                        <Notice
                          role="status"
                          tone="warning"
                          className="mb-3"
                          action={<Button variant="secondary" disabled={rescheduleSlots.isFetching} onClick={() => void rescheduleSlots.refetch()}>{rescheduleSlots.isFetching ? "Retrying…" : "Retry"}</Button>}
                        >
                          {SLOTS_NOT_RECHECKED}
                        </Notice>
                      ) : null}
                      <p className="mb-3 text-sm font-semibold text-ink">Available times · {rescheduleSlots.data?.data.timezone}</p>
                      <div role="group" aria-label="Available replacement times" className="flex flex-wrap gap-2">
                        {rescheduleSlotItems.map((slot: BookableSlotResponse) => (
                          <button
                            key={slot.starts_at}
                            type="button"
                            disabled={rescheduling}
                            aria-pressed={rescheduleChoice.selected === slot.starts_at}
                            onClick={() => { rescheduleChoice.select(slot.starts_at); setError(null); }}
                            className={
                              "min-h-11 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                              (rescheduleChoice.selected === slot.starts_at ? "border-brand bg-brand text-on-brand" : "border-border-strong bg-surface-raised text-ink hover:bg-surface-subtle")
                            }
                          >
                            {formatAppointmentTime(slot.starts_at, rescheduleSlots.data?.data.timezone)}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              ) : null}
              <div className="mt-4 grid gap-2">
                <Label htmlFor="reschedule-reason">Reason (optional)</Label>
                <Textarea id="reschedule-reason" disabled={rescheduling} className="min-h-24" value={rescheduleReason} onChange={(event) => setRescheduleReason(event.target.value)} />
              </div>
              {selectedRescheduleSlot ? (
                <section aria-labelledby="reschedule-review-heading" className="mt-5 rounded-sm bg-surface-subtle px-4 py-3.5">
                  <h4 id="reschedule-review-heading" className="font-semibold text-ink">Review reschedule</h4>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div><dt className="text-xs text-muted">Current time</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd></div>
                    <div><dt className="text-xs text-muted">New time</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(selectedRescheduleSlot.starts_at, selectedRescheduleSlot.ends_at, rescheduleSlots.data?.data.timezone)}</dd></div>
                  </dl>
                  {rescheduleReason.trim() ? <p className="mt-3 text-sm text-muted">Reason: {rescheduleReason.trim()}</p> : null}
                </section>
              ) : null}
              {error?.scope === "reschedule" ? <p role="alert" className="mt-4 text-sm text-danger">{error.message}</p> : null}
              <Button className="mt-4" type="submit" disabled={!selectedRescheduleSlot || rescheduling || rescheduleSlotsUnconfirmed} aria-busy={rescheduling}>
                {rescheduling ? "Rescheduling…" : "Reschedule appointment"}
              </Button>
              <Button className="ml-2" variant="secondary" disabled={rescheduling} onClick={() => setRescheduleOpen(false)}>Cancel</Button>
            </form>
            </DialogContent>
            </Dialog>
          ) : null}

          {canReassign ? (
            <Dialog open={reassignmentOpen} onOpenChange={setReassignmentOpen}>
            <DialogContent className="max-w-2xl" dismissible={!pending}>
            <DialogTitle>Reassign counselor</DialogTitle>
            <DialogDescription>Choose a counselor and review the change before saving.</DialogDescription>
            <form onSubmit={submitReassignment} className="mt-5">
              <p className="text-sm text-muted"><span className="font-semibold text-ink">Current counselor:</span> {appointment.provider.display_name}</p>
              {candidates.isPending ? (
                <LoadingRegion label="Loading reassignment candidates…" className="mt-4">
                  <Skeleton className="h-10 w-full max-w-xl" />
                </LoadingRegion>
              ) : candidates.isError ? (
                <div role="alert" className="mt-4"><p className="text-sm text-danger">Reassignment candidates could not be loaded.</p><Button className="mt-2" variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button></div>
              ) : candidateItems.length === 0 ? (
                <p className="mt-4 text-sm text-muted">No other Counselors are available at this time.</p>
              ) : (
                <div className="mt-4 grid gap-2 sm:max-w-xl">
                  <Label htmlFor="reassignment-counselor">New counselor</Label>
                  <Select id="reassignment-counselor" disabled={reassigning} value={selectedProviderId} onChange={(event) => setSelectedProviderId(event.target.value)}>
                    <option value="">Choose a Counselor</option>
                    {candidateItems.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.display_name}</option>)}
                  </Select>
                </div>
              )}
              <div className="mt-4 grid max-w-3xl gap-2">
                <Label htmlFor="reassignment-reason">Reason</Label>
                <Textarea id="reassignment-reason" required disabled={reassigning} className="min-h-24" value={reassignmentReason} onChange={(event) => setReassignmentReason(event.target.value)} />
              </div>
              {selectedCandidate && reassignmentReason.trim() ? (
                <div className="mt-4 rounded-sm bg-surface-subtle px-4 py-3.5">
                  <h4 className="font-semibold text-ink">Review reassignment</h4>
                  <p className="mt-2 text-sm text-ink">{appointment.provider.display_name} <span aria-hidden="true">→</span> {selectedCandidate.display_name}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-muted">Reason: {reassignmentReason.trim()}</p>
                </div>
              ) : null}
              {error?.scope === "reassign" ? <p role="alert" className="mt-4 text-sm text-danger">{error.message}</p> : null}
              <Button className="mt-4" type="submit" disabled={!selectedProviderId || !reassignmentReason.trim() || reassigning || candidates.isPending} aria-busy={reassigning}>
                {reassigning ? "Reassigning…" : "Reassign counselor"}
              </Button>
              <Button className="ml-2" variant="secondary" disabled={pending} onClick={() => setReassignmentOpen(false)}>Cancel</Button>
            </form>
            </DialogContent>
            </Dialog>
          ) : null}
        </Panel>
      ) : null}

      <Panel aria-labelledby="appointment-history-heading">
        <PanelHeader title="Appointment history" titleId="appointment-history-heading" />
        {historyQuery.isPending ? (
          <RowsSkeleton label="Loading Appointment history…" rows={2} />
        ) : historyQuery.isError ? (
          <PanelMessage
            role="alert"
            tone="danger"
            action={<Button variant="secondary" onClick={() => void historyQuery.refetch()}>Retry history</Button>}
          >
            Appointment history could not be loaded.
          </PanelMessage>
        ) : historyItems.length === 0 ? (
          <PanelMessage>No appointment history yet.</PanelMessage>
        ) : (
          <ol className="divide-y divide-border">
            {historyItems.map((entry, index) => (
              <li key={`${entry.event_type}-${entry.occurred_at}-${index}`} className="px-4 py-3.5 sm:px-5">
                <article>
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
                    <h3 className="font-semibold text-ink">{eventLabel(entry.event_type)}</h3>
                    <time dateTime={entry.occurred_at} className="text-xs text-muted">{occurredAt(entry.occurred_at)}</time>
                  </div>
                  {entry.actor ? <p className="mt-1 text-sm text-muted">{entry.actor.display_name}</p> : null}
                  {eventContext(entry) ? <p className="mt-1 text-sm text-ink">{eventContext(entry)}</p> : null}
                  {entry.reason.trim() ? <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-muted">{entry.reason}</p> : null}
                </article>
              </li>
            ))}
          </ol>
        )}
      </Panel>
      </div>

      <ActionConfirmation
        action={confirmationAllowed || pending ? confirmAction : null}
        busy={pending}
        selfCancellation={access.isStudent}
        referenceCode={appointment.reference_code}
        error={error?.scope === "confirm" ? error.message : null}
        routineInterviewWillClose={Boolean(confirmationRoutineConsequence)}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => void confirmMutation()}
      />
    </section>
    </GuidanceContextualMessages>
  );
}

export function AppointmentDetailPage({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.hasWorkspace) return <AppointmentsUnavailable />;
  return <DetailContent appointmentId={appointmentId} />;
}
