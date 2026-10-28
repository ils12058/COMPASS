"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Ban, Calendar, Clock, User as UserIcon } from "lucide-react";

import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import { bookingResultIsUncertain, studentSchedulingScope } from "@/features/appointments/booking-recovery";
import { invalidateStudentScheduling } from "@/features/appointments/student-scheduling-invalidation";
import { getAppointmentsListMyQueryKey } from "@/lib/api/generated/appointments/appointments";
import { appointmentErrorMessage } from "@/features/appointments/appointments-shared";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { PanelSection } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { stepUpRequirement, type StepUpRequirement } from "@/features/account/security/step-up";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  useServicesListSlots,
  useServicesCreateSlot,
  useServicesUpdateSlot,
  useServicesWithdrawSlot,
  useServicesListOperationalProviderCandidates,
  useServicesListBookableSlots,
  useServicesBookSlot,
  getServicesListSlotsQueryKey,
  getServicesListBookableSlotsQueryKey,
} from "@/lib/api/generated/services/services";
import {
  DeliveryMode,
  type ServiceResponse,
  type ServiceSlotResponse,
  type StudentBookableSlotResponse,
} from "@/lib/api/generated/model";

export function ServiceFixedSlotsStaffPanel({ service }: { service: ServiceResponse }) {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [withdrawSlot, setWithdrawSlot] = useState<ServiceSlotResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const [stepUpKind, setStepUpKind] = useState<StepUpRequirement>("verify");

  // Form states
  const [providerId, setProviderId] = useState(
    user.role === "COUNSELOR" ? user.id : ""
  );
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>(
    service.delivery_modes[0] ?? DeliveryMode.IN_PERSON
  );
  const [startDateTime, setStartDateTime] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(
    service.default_appointment_duration_minutes ?? 60
  );
  const [providerSearch, setProviderSearch] = useState("");
  const [providerPage, setProviderPage] = useState(1);

  const slotsQuery = useServicesListSlots(service.id, undefined, {
    query: { retry: false },
  });
  const providersQuery = useServicesListOperationalProviderCandidates(
    service.id,
    {
      ...(providerSearch.trim() ? { search: providerSearch.trim() } : {}),
      page: providerPage,
      page_size: 50,
    },
    { query: { retry: false } },
  );

  const createMutation = useServicesCreateSlot();
  const updateMutation = useServicesUpdateSlot();
  const withdrawMutation = useServicesWithdrawSlot();

  const slots = slotsQuery.data?.data ?? [];
  const providers = providersQuery.data?.data.items ?? [];

  function handleMutationError(err: unknown, fallback: string): boolean {
    const requirement = stepUpRequirement(err);
    if (requirement) {
      setStepUpKind(requirement);
      setStepUpOpen(true);
      setErrorMessage(
        requirement === "verify"
          ? "A recent security check is required. Review this action again after verification."
          : "Set up an authenticator, then review this action again.",
      );
      return true;
    }
    const apiErr = err as { data?: { error?: { message?: string } }; message?: string };
    setErrorMessage(apiErr.data?.error?.message ?? apiErr.message ?? fallback);
    return false;
  }

  async function refreshAfterStepUp() {
    await Promise.all([slotsQuery.refetch(), providersQuery.refetch()]);
    setSuccessMessage("Security check complete. Review the current slot details and confirm the action again.");
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (!providerId) {
      setErrorMessage("Please select a qualified Counselor.");
      return;
    }
    if (!startDateTime) {
      setErrorMessage("Please enter a slot start date and time.");
      return;
    }

    try {
      const startsAt = new Date(startDateTime);
      const endsAt = new Date(startsAt.getTime() + durationMinutes * 60 * 1000);

      await createMutation.mutateAsync({
        serviceId: service.id,
        data: {
          provider_id: providerId,
          delivery_mode: deliveryMode,
          starts_at: startsAt.toISOString(),
          ends_at: endsAt.toISOString(),
          is_published: true,
        },
      });

      await queryClient.invalidateQueries({
        queryKey: getServicesListSlotsQueryKey(service.id),
      });

      setSuccessMessage("Appointment slot published successfully.");
      setCreateOpen(false);
      setStartDateTime("");
    } catch (err: unknown) {
      handleMutationError(err, "Failed to publish appointment slot.");
    }
  };

  const handleTogglePublish = async (slot: ServiceSlotResponse) => {
    setErrorMessage(null);
    try {
      await updateMutation.mutateAsync({
        serviceId: service.id,
        slotId: slot.id,
        data: {
          is_published: !slot.is_published,
        },
      });
      await queryClient.invalidateQueries({
        queryKey: getServicesListSlotsQueryKey(service.id),
      });
    } catch (err: unknown) {
      handleMutationError(err, "Failed to update slot publication.");
    }
  };

  const handleWithdrawConfirm = async () => {
    if (!withdrawSlot) return;
    setErrorMessage(null);
    try {
      await withdrawMutation.mutateAsync({
        serviceId: service.id,
        slotId: withdrawSlot.id,
      });
      await queryClient.invalidateQueries({
        queryKey: getServicesListSlotsQueryKey(service.id),
      });
      setWithdrawSlot(null);
      setSuccessMessage("Slot withdrawn from future booking. Its record and appointment history are preserved.");
    } catch (err: unknown) {
      handleMutationError(err, "Failed to withdraw slot.");
    }
  };

  return (
    <PanelSection title="Fixed-date appointment slots" titleId="service-fixed-slots-heading">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          Publish specific consultation dates and times for Students to book individually.
        </p>
        <Button
          variant="secondary"
          onClick={() => {
            setErrorMessage(null);
            setCreateOpen(true);
          }}
          disabled={!service.is_active || providers.length === 0}
        >
          <Plus className="mr-1.5 h-4 w-4" />
          Publish slot
        </Button>
      </div>

      {successMessage ? (
        <Notice role="status" tone="success" className="mt-4">
          {successMessage}
        </Notice>
      ) : null}
      {errorMessage ? (
        <Notice role="alert" tone="danger" className="mt-4">
          {errorMessage}
        </Notice>
      ) : null}
      {!service.is_active ? (
        <p className="mt-3 text-xs text-muted">
          Existing appointments remain on record. Enable this Service before publishing new slots.
        </p>
      ) : null}
      {providersQuery.isError ? (
        <Notice role="alert" tone="danger" className="mt-4">
          Eligible Counselors could not be loaded. Retry before publishing a slot. {" "}
          <Button variant="quiet" onClick={() => void providersQuery.refetch()}>
            Retry
          </Button>
        </Notice>
      ) : null}

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        {slotsQuery.isPending ? <p role="status" className="p-4 text-sm text-muted">Loading appointment slots…</p> : slotsQuery.isError ? (
          <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void slotsQuery.refetch()}>Retry slots</Button>}>
            {appointmentErrorMessage(slotsQuery.error, "Appointment slots could not be loaded. Try again.")}
          </Notice>
        ) : slots.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted">
            No fixed-date appointment slots published yet.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-line text-sm">
            <thead className="bg-surface-secondary text-left font-semibold text-ink">
              <tr>
                <th className="px-4 py-3">Schedule</th>
                <th className="px-4 py-3">Counselor</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {slots.map((slot) => (
                <tr key={slot.id} className="hover:bg-surface-secondary/50">
                  <td className="px-4 py-3 font-medium text-ink">
                    {formatInstitutionalDateTime(slot.starts_at)}
                  </td>
                  <td className="px-4 py-3 text-ink">{slot.provider_name}</td>
                  <td className="px-4 py-3 text-muted">
                    {slot.delivery_mode === DeliveryMode.IN_PERSON ? "In person" : "Online"}
                  </td>
                  <td className="px-4 py-3">
                    {slot.withdrawn_at ? (
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        Withdrawn
                      </span>
                    ) : slot.is_booked ? (
                      <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                        Booked or used {slot.appointment_reference_code ? `(${slot.appointment_reference_code})` : ""}
                      </span>
                    ) : slot.is_published ? (
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        Available
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                        Unpublished
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {!slot.withdrawn_at ? (
                      <>
                        {slot.is_booked && slot.appointment_id ? (
                          <Link
                            href={`/portal/appointments/${slot.appointment_id}`}
                            className="mr-2 text-xs font-medium text-primary hover:underline"
                          >
                            View Appointment
                          </Link>
                        ) : null}
                        {!slot.is_booked ? (
                          <Button
                            variant="quiet"
                            onClick={() => void handleTogglePublish(slot)}
                            className="mr-2 px-2.5 py-1 text-xs"
                          >
                            {slot.is_published ? "Unpublish" : "Publish"}
                          </Button>
                        ) : null}
                        <Button
                          variant="quiet"
                          onClick={() => setWithdrawSlot(slot)}
                          className="px-2.5 py-1 text-xs text-danger hover:bg-danger/10"
                        >
                          <Ban className="mr-1 h-3.5 w-3.5" />
                          Withdraw
                        </Button>
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create slot dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleCreate}>
            <DialogTitle>Publish appointment slot</DialogTitle>
            <div className="grid gap-4 py-4">
              <div>
                <Label htmlFor="slot-provider">Counselor Provider</Label>
                <Input
                  id="slot-provider-search"
                  aria-label="Search eligible Counselors"
                  value={providerSearch}
                  onChange={(event) => {
                    setProviderSearch(event.target.value);
                    setProviderId("");
                    setProviderPage(1);
                  }}
                  placeholder="Search eligible Counselors"
                  className="mt-1 w-full"
                />
                <Select
                  id="slot-provider"
                  value={providerId}
                  onChange={(e) => setProviderId(e.target.value)}
                  className="mt-1 w-full"
                  required
                >
                  <option value="">
                    {providersQuery.isPending
                      ? "Loading Counselors…"
                      : "Select a qualified Counselor…"}
                  </option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
                </Select>
                {providerPage > 1 || providersQuery.data?.data.has_next ? (
                  <div className="mt-2 flex items-center gap-2 text-xs text-muted">
                    <Button
                      type="button"
                      variant="quiet"
                      disabled={providerPage <= 1}
                      onClick={() => setProviderPage((page) => Math.max(1, page - 1))}
                    >
                      Previous
                    </Button>
                    <span>Page {providerPage}</span>
                    <Button
                      type="button"
                      variant="quiet"
                      disabled={!providersQuery.data?.data.has_next}
                      onClick={() => setProviderPage((page) => page + 1)}
                    >
                      Next
                    </Button>
                  </div>
                ) : null}
                <p className="mt-1 text-xs text-muted">
                  The list follows your Appointment responsibility scope and this Service’s current provider eligibility.
                </p>
              </div>

              <div>
                <Label htmlFor="slot-delivery-mode">Delivery Mode</Label>
                <Select
                  id="slot-delivery-mode"
                  value={deliveryMode}
                  onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
                  className="mt-1 w-full"
                >
                  {service.delivery_modes.map((mode) => (
                    <option key={mode} value={mode}>
                      {mode === DeliveryMode.IN_PERSON ? "In person" : "Online"}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Label htmlFor="slot-datetime">Date & Time</Label>
                <Input
                  id="slot-datetime"
                  type="datetime-local"
                  value={startDateTime}
                  onChange={(e) => setStartDateTime(e.target.value)}
                  className="mt-1 w-full"
                  required
                />
              </div>

              <div>
                <Label htmlFor="slot-duration">Duration (minutes)</Label>
                <Input
                  id="slot-duration"
                  type="number"
                  min="1"
                  max="480"
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(parseInt(e.target.value, 10) || 60)}
                  className="mt-1 w-full"
                  required
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Publishing…" : "Publish slot"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Withdraw confirmation dialog */}
      <ConsequentialActionDialog
        open={Boolean(withdrawSlot)}
        title="Withdraw appointment slot?"
        confirmLabel="Withdraw slot"
        pendingLabel="Withdrawing…"
        error={errorMessage}
        variant="danger"
        pending={withdrawMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setWithdrawSlot(null);
        }}
        onConfirm={handleWithdrawConfirm}
      >
        <p>
          Withdraw the slot scheduled for{" "}
          <strong>{withdrawSlot ? formatInstitutionalDateTime(withdrawSlot.starts_at) : ""}</strong>{" "}
          from future booking? The slot and any Appointment history will remain on record.
        </p>
      </ConsequentialActionDialog>
      <StepUpDialog
        open={stepUpOpen}
        requirement={stepUpKind}
        onOpenChange={setStepUpOpen}
        onVerified={() => refreshAfterStepUp()}
      />
    </PanelSection>
  );
}

export function ServiceFixedSlotsStudentPanel({ service, checkService }: { service: ServiceResponse; checkService?: () => Promise<boolean> }) {
  const { user } = usePortalSession();
  const viewerScope = studentSchedulingScope(user);
  const queryClient = useQueryClient();
  const [selectedSlot, setSelectedSlot] = useState<StudentBookableSlotResponse | null>(null);
  const [bookSuccess, setBookSuccess] = useState<string | null>(null);
  const [bookedApptId, setBookedApptId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uncertainSlot, setUncertainSlot] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);

  const slotsQuery = useServicesListBookableSlots(service.id, undefined, {
    query: { retry: false, queryKey: [...getServicesListBookableSlotsQueryKey(service.id), viewerScope] },
  });
  const bookMutation = useServicesBookSlot();

  const slots = slotsQuery.data?.data ?? [];

  const handleBookSlot = async (slotId: string) => {
    if (uncertainSlot === slotId || checking) return;
    setErrorMessage(null);
    setBookSuccess(null);
    setChecking(true);
    try {
      if (checkService && !(await checkService())) {
        setErrorMessage("This Service could not be confirmed for scheduled slots. Check the Service and try again.");
        return;
      }
      const current = await slotsQuery.refetch();
      if (current.isError) {
        setErrorMessage("The available slots could not be checked. Retry the slot refresh before booking.");
        return;
      }
      if (!current.data?.data.some(slot => slot.id === slotId)) {
        setSelectedSlot(null);
        setErrorMessage("This slot is no longer available. Choose another time.");
        return;
      }
      let appt;
      try {
        appt = (await bookMutation.mutateAsync({ serviceId: service.id, slotId })).data;
        if (!appt || typeof appt.appointment_id !== "string" || !appt.appointment_id || typeof appt.reference_code !== "string" || !appt.reference_code) throw new Error("Unconfirmed booking response");
      } catch (err: unknown) {
        if (bookingResultIsUncertain(err)) {
          setUncertainSlot(slotId);
          setErrorMessage("We could not confirm whether this appointment was booked. Check My appointments before making another booking. Refreshing slots cannot confirm who booked this time.");
        } else if (err instanceof CompassApiError) {
          const code = readApiErrorCode(err.body);
          setErrorMessage(code === "slot_already_booked" || code === "slot_unavailable" || code === "slot_not_found"
            ? "This slot is no longer available. Close this dialog and choose another time."
            : appointmentErrorMessage(err, "The appointment could not be booked. Review the details and try again."));
          if (err.status === 409 || err.status === 404) void slotsQuery.refetch();
        }
        return;
      }
      setBookedApptId(appt.appointment_id);
      setBookSuccess(`Appointment booked successfully! Reference code: ${appt.reference_code}`);
      setSelectedSlot(null);
      const refresh = await Promise.allSettled([
        invalidateStudentScheduling(queryClient),
        queryClient.invalidateQueries({ queryKey: getAppointmentsListMyQueryKey() }, { throwOnError: true }),
      ]);
      setRefreshFailed(refresh.some(result => result.status === "rejected"));
    } finally {
      setChecking(false);
    }
  };

  return (
    <PanelSection title="Available appointment slots" titleId="student-fixed-slots-heading">
      <p className="text-sm text-muted">
        Choose a published date and time to reserve an individual appointment directly.
      </p>

      {service.requires_current_inventory ? <p className="mt-3 text-sm text-muted">A submitted Individual Inventory for the current Academic Year is required to book this Service.</p> : null}
      {bookSuccess ? (
        <Notice role="status" tone="success" className="mt-4">
          <p>{bookSuccess}</p>
          {bookedApptId ? (
            <Link
              href={`/portal/appointments/${bookedApptId}`}
              className="mt-1 block font-semibold underline"
            >
              View your confirmed Appointment
            </Link>
          ) : null}
          <Link href="/portal/appointments/my" className="mt-1 block font-semibold underline">My appointments</Link>
        </Notice>
      ) : null}
      {refreshFailed ? <Notice role="alert" className="mt-4" action={<Button variant="secondary" onClick={() => void Promise.allSettled([invalidateStudentScheduling(queryClient), queryClient.invalidateQueries({ queryKey: getAppointmentsListMyQueryKey() }, { throwOnError: true })]).then(results => setRefreshFailed(results.some(result => result.status === "rejected")))}>Refresh</Button>}>Your appointment was booked, but the latest booking information could not be refreshed.</Notice> : null}
      {uncertainSlot ? <Notice role="alert" tone="warning" className="mt-4" action={<><Button variant="secondary" onClick={() => void slotsQuery.refetch()}>Refresh slots</Button> <Link href="/portal/appointments/my" className="font-semibold underline">My appointments</Link></>}>The booking outcome is unconfirmed. A slot refresh cannot identify who booked it. Check My appointments before making another booking.</Notice> : null}

      {errorMessage && !selectedSlot ? (
        <Notice role="alert" tone="danger" className="mt-4">
          {errorMessage}
        </Notice>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {slotsQuery.isPending ? <p role="status" className="p-4 text-sm text-muted">Loading appointment slots…</p> : slotsQuery.isError ? (
          <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void slotsQuery.refetch()}>Retry slots</Button>}>
            {appointmentErrorMessage(slotsQuery.error, "Appointment slots could not be loaded. Try again.")}
          </Notice>
        ) : slots.length === 0 ? (
          <div className="col-span-full rounded-md border border-dashed border-line p-6 text-center text-sm text-muted">
            No fixed consultation slots are currently available for this Service.
          </div>
        ) : (
          slots.map((slot) => (
            <div
              key={slot.id}
              className="flex flex-col justify-between rounded-md border border-line bg-surface p-4 shadow-xs"
            >
              <div className="space-y-2">
                <div className="flex items-center text-sm font-semibold text-ink">
                  <Calendar className="mr-2 h-4 w-4 text-primary" />
                  {formatInstitutionalDateTime(slot.starts_at)}
                </div>
                <div className="flex items-center text-xs text-muted">
                  <UserIcon className="mr-1.5 h-3.5 w-3.5" />
                  {slot.provider_name}
                </div>
                <div className="flex items-center text-xs text-muted">
                  <Clock className="mr-1.5 h-3.5 w-3.5" />
                  {slot.delivery_mode === DeliveryMode.IN_PERSON ? "In person" : "Online consultation"}
                </div>
              </div>

              <div className="mt-4 border-t border-line/60 pt-3">
                <Button
                  variant="primary"
                  className="w-full text-xs"
                  disabled={uncertainSlot === slot.id || checking}
                  onClick={() => setSelectedSlot(slot)}
                >
                  Book this slot
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Booking confirmation dialog */}
      <ConsequentialActionDialog
        open={Boolean(selectedSlot)}
        title="Confirm appointment booking"
        confirmLabel="Confirm booking"
        pendingLabel="Booking…"
        error={errorMessage}
        variant="primary"
        pending={bookMutation.isPending || checking}
        confirmDisabled={uncertainSlot === selectedSlot?.id}
        onOpenChange={(open) => {
          if (!open) { setSelectedSlot(null); setErrorMessage(null); }
        }}
        onConfirm={() => {
          if (selectedSlot) void handleBookSlot(selectedSlot.id);
        }}
      >
        <p>
          You are booking an appointment for <strong>{service.name}</strong> with{" "}
          <strong>{selectedSlot?.provider_name}</strong> on{" "}
          <strong>{selectedSlot ? formatInstitutionalDateTime(selectedSlot.starts_at) : ""}</strong>.
        </p>
      </ConsequentialActionDialog>
    </PanelSection>
  );
}
