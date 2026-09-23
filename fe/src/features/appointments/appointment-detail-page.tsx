"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { StepUpDialog } from "@/features/account/security/security-shared";
import {
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
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  AppointmentStatus,
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

type ConfirmAction = "cancel" | "complete" | "no-show";
type StepUpAction = "cancel" | "reschedule" | "reassign";

const controlClass = "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function occurredAt(value: string): string {
  return new Date(value).toLocaleString("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  });
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

function ActionConfirmation({
  action,
  busy,
  selfCancellation,
  onClose,
  onConfirm,
}: {
  action: ConfirmAction | null;
  busy: boolean;
  selfCancellation: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const content: Record<ConfirmAction, { title: string; description: string; confirm: string; pending: string; variant: "danger" | "primary" }> = {
    cancel: {
      title: "Cancel this Appointment?",
      description: selfCancellation
        ? "This will cancel the scheduled Appointment. The saved self-service cutoff and Appointment lifecycle rules still apply."
        : "This will administratively cancel the scheduled Appointment in your authorized scope. Recent authenticator verification may be required.",
      confirm: "Cancel appointment",
      pending: "Cancelling…",
      variant: "danger",
    },
    complete: {
      title: "Complete this Appointment?",
      description: "This will mark the scheduled Appointment as completed. The backend will verify its lifecycle and timing.",
      confirm: "Complete appointment",
      pending: "Completing…",
      variant: "primary",
    },
    "no-show": {
      title: "Mark this Appointment no-show?",
      description: "This will mark the scheduled Appointment as no-show. The backend will verify its end time and related records.",
      confirm: "Mark no-show",
      pending: "Updating…",
      variant: "danger",
    },
  };
  const selected = action ? content[action] : null;

  return (
    <Dialog
      open={action !== null}
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      {selected ? (
        <DialogContent
          onEscapeKeyDown={(event) => { if (busy) event.preventDefault(); }}
          onPointerDownOutside={(event) => { if (busy) event.preventDefault(); }}
        >
          <DialogTitle>{selected.title}</DialogTitle>
          <DialogDescription>{selected.description}</DialogDescription>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" disabled={busy} onClick={onClose}>Keep Appointment</Button>
            <Button variant={selected.variant} disabled={busy} onClick={onConfirm} aria-busy={busy}>
              {busy ? selected.pending : selected.confirm}
            </Button>
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}

function DetailContent({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
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
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUpAction, setStepUpAction] = useState<StepUpAction | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduleSlotStart, setRescheduleSlotStart] = useState("");
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [reassignmentReason, setReassignmentReason] = useState("");
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [reassignmentOpen, setReassignmentOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const appointment = appointmentQuery.data?.data;
  const isScheduled = appointment?.status === AppointmentStatus.SCHEDULED;
  const adminActor = access.canManage && !access.isStudent;
  const canCancelSelf = access.isStudent && access.canManageSelf && isScheduled;
  const canRescheduleSelf = access.isStudent && access.canRescheduleSelf && isScheduled;
  const canAdminister = adminActor && isScheduled;
  const canCancel = canCancelSelf || canAdminister;
  const canReschedule = canRescheduleSelf || canAdminister;

  const rescheduleSlots = useAppointmentsListRescheduleSlots(
    appointmentId,
    { date: rescheduleDate || "1970-01-01" },
    {
      query: {
        enabled: Boolean(appointment && canReschedule && rescheduleOpen && rescheduleDate && isScheduled),
        retry: false,
      },
    },
  );
  const rescheduleSlotItems = rescheduleSlots.data?.data.items ?? [];
  const selectedRescheduleSlot = rescheduleSlotItems.find(
    (slot) => slot.starts_at === rescheduleSlotStart,
  );

  const candidates = useAppointmentsListReassignmentCandidates(appointmentId, {
    query: {
      enabled: Boolean(appointment && canAdminister && reassignmentOpen),
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
    reschedule.isPending ||
    reassign.isPending ||
    complete.isPending ||
    noShow.isPending;

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

  function handleMutationError(caught: unknown, fallback: string, stepUpFor?: StepUpAction) {
    if (
      stepUpFor &&
      appointmentErrorCode(caught) === "recent_mfa_required" &&
      adminActor
    ) {
      setError(null);
      setConfirmAction(null);
      setStepUpAction(stepUpFor);
      setStepUpOpen(true);
      return;
    }
    setError(appointmentErrorMessage(caught, fallback));
  }

  async function confirmMutation() {
    if (!appointment || !confirmAction) return;
    setError(null);
    setNotice(null);
    try {
      if (confirmAction === "cancel") {
        await cancel.mutateAsync({ appointmentId });
        await refreshAppointmentQueries(true);
        setNotice("Appointment cancelled.");
      } else if (confirmAction === "complete") {
        await complete.mutateAsync({ appointmentId });
        await refreshAppointmentQueries();
        setNotice("Appointment completed.");
      } else {
        await noShow.mutateAsync({ appointmentId });
        await refreshAppointmentQueries();
        setNotice("Appointment marked no-show.");
      }
      setConfirmAction(null);
    } catch (caught) {
      handleMutationError(
        caught,
        "The Appointment could not be updated.",
        confirmAction === "cancel" && adminActor ? "cancel" : undefined,
      );
    }
  }

  async function submitReschedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedRescheduleSlot) return;
    setError(null);
    setNotice(null);
    try {
      await reschedule.mutateAsync({
        appointmentId,
        data: {
          starts_at: selectedRescheduleSlot.starts_at,
          ...(rescheduleReason.trim() ? { reason: rescheduleReason.trim() } : {}),
        },
      });
      await refreshAppointmentQueries(true);
      setRescheduleOpen(false);
      setRescheduleSlotStart("");
      setRescheduleReason("");
      setNotice("Appointment rescheduled.");
    } catch (caught) {
      const code = appointmentErrorCode(caught);
      if (code === "appointment_time_unavailable" || code === "appointment_time_conflict") {
        setRescheduleSlotStart("");
        setError("The selected time is no longer available. Available times have been refreshed; choose another time.");
        void rescheduleSlots.refetch();
        return;
      }
      handleMutationError(
        caught,
        "The Appointment could not be rescheduled.",
        adminActor ? "reschedule" : undefined,
      );
    }
  }

  async function submitReassignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProviderId || !reassignmentReason.trim()) return;
    setError(null);
    setNotice(null);
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
      handleMutationError(
        caught,
        "The Counselor could not be reassigned.",
        "reassign",
      );
    }
  }

  function onStepUpVerified() {
    if (stepUpAction === "cancel") {
      setNotice("Verification complete. Review and confirm cancellation again.");
      setConfirmAction("cancel");
    } else if (stepUpAction === "reschedule") {
      setNotice("Verification complete. Review the selected time and submit the reschedule again.");
    } else if (stepUpAction === "reassign") {
      setNotice("Verification complete. Review the selected Counselor and reason, then submit again.");
    }
    setStepUpAction(null);
  }

  if (!access.hasWorkspace) return <AppointmentsUnavailable />;
  if (appointmentQuery.isPending) {
    return (
      <section aria-busy="true" aria-label="Loading Appointment details">
        <AppointmentsLocalNavigation />
        <Skeleton className="h-9 w-2/5" />
        <Skeleton className="mt-5 h-24 w-full" />
        <Skeleton className="mt-5 h-48 w-full" />
      </section>
    );
  }
  if (appointmentQuery.isError || !appointment) {
    const notFound = appointmentErrorCode(appointmentQuery.error) === "appointment_not_found";
    return (
      <section>
        <AppointmentsLocalNavigation />
        <div role="alert" className="max-w-2xl border-y border-border py-7">
          <h1 className="font-heading text-3xl font-bold text-ink">
            {notFound ? "Appointment not available" : "Appointment could not be loaded"}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            {notFound
              ? "This Appointment is not available within your current access."
              : appointmentErrorMessage(appointmentQuery.error, "Appointment details could not be loaded.")}
          </p>
          <Button className="mt-4" variant="secondary" onClick={() => void appointmentQuery.refetch()}>Retry</Button>
        </div>
      </section>
    );
  }

  const historyItems = historyQuery.data?.data.items ?? [];

  return (
    <section aria-labelledby="appointment-detail-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="appointment-detail-heading"
        title="Appointment details"
        description={appointment.reference_code}
      />

      {notice ? <p role="status" className="mb-4 text-sm text-success">{notice}</p> : null}
      {error ? <p role="alert" className="mb-4 text-sm text-danger">{error}</p> : null}

      <div className="flex flex-wrap items-center gap-3 border-y border-border py-4">
        <span className="break-all font-mono text-sm font-semibold text-ink">{appointment.reference_code}</span>
        <AppointmentStatusBadge status={appointment.status} />
      </div>

      <dl className="grid gap-x-8 gap-y-5 border-b border-border py-6 sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-xs font-semibold text-muted">Service</dt><dd className="mt-1 text-sm text-ink">{appointment.service.name}<span className="ml-2 font-mono text-xs text-muted">{appointment.service.code}</span></dd></div>
        {!access.isStudent ? (
          <div><dt className="text-xs font-semibold text-muted">Student</dt><dd className="mt-1 break-words text-sm text-ink">{appointment.student.display_name}</dd>{appointment.student.institutional_id ? <dd className="mt-1 break-all text-xs text-muted">{appointment.student.institutional_id}</dd> : null}</div>
        ) : null}
        <div><dt className="text-xs font-semibold text-muted">Counselor</dt><dd className="mt-1 text-sm text-ink">{appointment.provider.display_name}</dd></div>
        <div><dt className="text-xs font-semibold text-muted">Date and time</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd></div>
        <div><dt className="text-xs font-semibold text-muted">Delivery</dt><dd className="mt-1 text-sm text-ink">{deliveryModeLabel(appointment.delivery_mode)}</dd></div>
        {appointment.cancellation_cutoff_minutes !== null ? (
          <div><dt className="text-xs font-semibold text-muted">Saved self-service cutoff</dt><dd className="mt-1 text-sm text-ink">Changes are subject to the {appointment.cancellation_cutoff_minutes}-minute cutoff saved with this Appointment.</dd></div>
        ) : null}
        <div><dt className="text-xs font-semibold text-muted">Created</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.created_at)}</dd></div>
        {appointment.cancelled_at ? <div><dt className="text-xs font-semibold text-muted">Cancelled</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.cancelled_at)}</dd></div> : null}
        {appointment.completed_at ? <div><dt className="text-xs font-semibold text-muted">Completed</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.completed_at)}</dd></div> : null}
        {appointment.no_show_at ? <div><dt className="text-xs font-semibold text-muted">Marked no-show</dt><dd className="mt-1 text-sm text-ink">{occurredAt(appointment.no_show_at)}</dd></div> : null}
      </dl>

      {(canCancel || canReschedule || canAdminister) ? (
        <section aria-labelledby="appointment-actions-heading" className="border-b border-border py-6">
          <h2 id="appointment-actions-heading" className="font-heading text-xl font-semibold text-ink">Appointment actions</h2>
          {canRescheduleSelf && appointment.cancellation_cutoff_minutes !== null ? (
            <p className="mt-2 max-w-3xl text-sm text-muted">Self-service rescheduling is subject to the cutoff saved with this Appointment. The backend confirms whether a change is still allowed.</p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            {canCancel ? <Button variant="danger" disabled={pending} onClick={() => { setError(null); setConfirmAction("cancel"); }}>Cancel appointment</Button> : null}
            {canReschedule ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); setRescheduleSlotStart(""); setNotice(null); setRescheduleOpen((open) => !open); }}>{rescheduleOpen ? "Close reschedule" : "Reschedule appointment"}</Button> : null}
            {canAdminister ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); setNotice(null); setReassignmentOpen((open) => !open); }}>{reassignmentOpen ? "Close reassignment" : "Reassign counselor"}</Button> : null}
            {canAdminister ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); setConfirmAction("complete"); }}>Complete appointment</Button> : null}
            {canAdminister ? <Button variant="secondary" disabled={pending} onClick={() => { setError(null); setConfirmAction("no-show"); }}>Mark no-show</Button> : null}
          </div>

          {canReschedule && rescheduleOpen ? (
            <form onSubmit={submitReschedule} className="mt-6 max-w-3xl border-t border-border pt-5">
              <h3 className="font-heading text-lg font-semibold text-ink">Reschedule appointment</h3>
              <p className="mt-1 text-sm text-muted">Choose a date to load replacement times from the Appointment service.</p>
              <div className="mt-4 grid gap-2 sm:max-w-xs">
                <Label htmlFor="reschedule-date">New date</Label>
                <Input
                  id="reschedule-date"
                  type="date"
                  value={rescheduleDate}
                  disabled={reschedule.isPending}
                  onChange={(event) => {
                    setRescheduleDate(event.target.value);
                    setRescheduleSlotStart("");
                    setError(null);
                  }}
                />
              </div>
              {rescheduleDate ? (
                <div className="mt-4" aria-live="polite">
                  {rescheduleSlots.isPending ? (
                    <div aria-busy="true" aria-label="Loading replacement times" className="flex flex-wrap gap-2"><Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" /></div>
                  ) : rescheduleSlots.isError ? (
                    <div role="alert"><p className="text-sm text-danger">Replacement times could not be loaded.</p><Button className="mt-2" variant="secondary" onClick={() => void rescheduleSlots.refetch()}>Retry</Button></div>
                  ) : rescheduleSlotItems.length === 0 ? (
                    <p className="text-sm text-muted">No available appointment times were found for this date. Choose another date.</p>
                  ) : (
                    <>
                      <p className="mb-3 text-sm font-semibold text-ink">Available times · {rescheduleSlots.data?.data.timezone}</p>
                      <div role="group" aria-label="Available replacement times" className="flex flex-wrap gap-2">
                        {rescheduleSlotItems.map((slot: BookableSlotResponse) => (
                          <button
                            key={slot.starts_at}
                            type="button"
                            disabled={reschedule.isPending}
                            aria-pressed={rescheduleSlotStart === slot.starts_at}
                            onClick={() => setRescheduleSlotStart(slot.starts_at)}
                            className={
                              "min-h-10 border px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                              (rescheduleSlotStart === slot.starts_at ? "border-brand bg-brand text-on-brand" : "border-border bg-surface-raised text-ink hover:bg-surface-muted")
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
                <textarea id="reschedule-reason" disabled={reschedule.isPending} className={controlClass + " min-h-24 py-2"} value={rescheduleReason} onChange={(event) => setRescheduleReason(event.target.value)} />
              </div>
              {selectedRescheduleSlot ? (
                <section aria-labelledby="reschedule-review-heading" className="mt-5 border-y border-border py-4">
                  <h4 id="reschedule-review-heading" className="font-semibold text-ink">Review reschedule</h4>
                  <dl className="mt-3 grid gap-3 sm:grid-cols-2">
                    <div><dt className="text-xs text-muted">Current time</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(appointment.starts_at, appointment.ends_at)}</dd></div>
                    <div><dt className="text-xs text-muted">New time</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(selectedRescheduleSlot.starts_at, selectedRescheduleSlot.ends_at, rescheduleSlots.data?.data.timezone)}</dd></div>
                  </dl>
                  {rescheduleReason.trim() ? <p className="mt-3 text-sm text-muted">Reason: {rescheduleReason.trim()}</p> : null}
                </section>
              ) : null}
              <Button className="mt-4" type="submit" disabled={!selectedRescheduleSlot || reschedule.isPending} aria-busy={reschedule.isPending}>
                {reschedule.isPending ? "Rescheduling…" : "Reschedule appointment"}
              </Button>
            </form>
          ) : null}

          {canAdminister && reassignmentOpen ? (
            <form onSubmit={submitReassignment} className="mt-6 max-w-3xl border-t border-border pt-5">
              <h3 className="font-heading text-lg font-semibold text-ink">Reassign counselor</h3>
              <p className="mt-3 text-sm text-muted"><span className="font-semibold text-ink">Current counselor:</span> {appointment.provider.display_name}</p>
              {candidates.isPending ? (
                <Skeleton className="mt-4 h-10 w-full max-w-xl" />
              ) : candidates.isError ? (
                <div role="alert" className="mt-4"><p className="text-sm text-danger">Reassignment candidates could not be loaded.</p><Button className="mt-2" variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button></div>
              ) : candidateItems.length === 0 ? (
                <p className="mt-4 text-sm text-muted">No other eligible Counselors are available for reassignment.</p>
              ) : (
                <div className="mt-4 grid gap-2 sm:max-w-xl">
                  <Label htmlFor="reassignment-counselor">New counselor</Label>
                  <select id="reassignment-counselor" disabled={reassign.isPending} className={controlClass} value={selectedProviderId} onChange={(event) => setSelectedProviderId(event.target.value)}>
                    <option value="">Choose a Counselor</option>
                    {candidateItems.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.display_name}</option>)}
                  </select>
                </div>
              )}
              <div className="mt-4 grid max-w-3xl gap-2">
                <Label htmlFor="reassignment-reason">Reason</Label>
                <textarea id="reassignment-reason" required disabled={reassign.isPending} className={controlClass + " min-h-24 py-2"} value={reassignmentReason} onChange={(event) => setReassignmentReason(event.target.value)} />
              </div>
              {selectedCandidate && reassignmentReason.trim() ? (
                <div className="mt-4 border-y border-border py-4">
                  <h4 className="font-semibold text-ink">Review reassignment</h4>
                  <p className="mt-2 text-sm text-ink">{appointment.provider.display_name} <span aria-hidden="true">→</span> {selectedCandidate.display_name}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-muted">Reason: {reassignmentReason.trim()}</p>
                </div>
              ) : null}
              <Button className="mt-4" type="submit" disabled={!selectedProviderId || !reassignmentReason.trim() || reassign.isPending || candidates.isPending} aria-busy={reassign.isPending}>
                {reassign.isPending ? "Reassigning…" : "Reassign counselor"}
              </Button>
            </form>
          ) : null}
        </section>
      ) : null}

      <section aria-labelledby="appointment-history-heading" className="py-6">
        <h2 id="appointment-history-heading" className="font-heading text-xl font-semibold text-ink">Appointment history</h2>
        {historyQuery.isPending ? (
          <div aria-busy="true" aria-label="Loading Appointment history" className="mt-4 space-y-3"><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>
        ) : historyQuery.isError ? (
          <div role="alert" className="mt-4 border-y border-danger/30 py-5">
            <p className="text-sm text-danger">Appointment history could not be loaded.</p>
            <Button className="mt-3" variant="secondary" onClick={() => void historyQuery.refetch()}>Retry history</Button>
          </div>
        ) : historyItems.length === 0 ? (
          <p className="mt-4 border-y border-border py-5 text-sm text-muted">No Appointment history entries are available.</p>
        ) : (
          <ol className="mt-4 divide-y divide-border border-y border-border">
            {historyItems.map((entry, index) => (
              <li key={`${entry.event_type}-${entry.occurred_at}-${index}`} className="py-4">
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
      </section>

      <ActionConfirmation
        action={confirmAction}
        busy={pending}
        selfCancellation={canCancelSelf}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => void confirmMutation()}
      />
      <StepUpDialog
        open={stepUpOpen}
        onOpenChange={(open) => {
          setStepUpOpen(open);
          if (!open) setStepUpAction(null);
        }}
        onVerified={onStepUpVerified}
      />
    </section>
  );
}

export function AppointmentDetailPage({ appointmentId }: { appointmentId: string }) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.hasWorkspace) return <AppointmentsUnavailable />;
  return <DetailContent appointmentId={appointmentId} />;
}
