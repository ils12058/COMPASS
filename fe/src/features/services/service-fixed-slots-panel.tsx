"use client";

import { useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Ban, Calendar, Clock, User as UserIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { PanelSection } from "@/components/ui/panel";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";
import {
  useServicesListSlots,
  useServicesCreateSlot,
  useServicesUpdateSlot,
  useServicesWithdrawSlot,
  useServicesGetProviders,
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
  const canManageServices = user.capabilities.includes("services.manage");
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [withdrawSlot, setWithdrawSlot] = useState<ServiceSlotResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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

  const slotsQuery = useServicesListSlots(service.id, undefined, {
    query: { retry: false },
  });
  const providersQuery = useServicesGetProviders(service.id, {
    query: { retry: false, enabled: canManageServices },
  });

  const createMutation = useServicesCreateSlot();
  const updateMutation = useServicesUpdateSlot();
  const withdrawMutation = useServicesWithdrawSlot();

  const slots = slotsQuery.data?.data ?? [];
  const fetchedProviders = providersQuery.data?.data.counselors ?? [];
  const providers =
    fetchedProviders.length > 0
      ? fetchedProviders
      : user.role === "COUNSELOR"
        ? [
            {
              id: user.id,
              display_name: `${user.first_name} ${user.last_name}`.trim() || user.email,
              is_active: true,
            },
          ]
        : [];

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
      const apiErr = err as { data?: { error?: { message?: string } }; message?: string };
      setErrorMessage(
        apiErr.data?.error?.message ?? apiErr.message ?? "Failed to publish appointment slot."
      );
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
      const apiErr = err as { data?: { error?: { message?: string } }; message?: string };
      setErrorMessage(
        apiErr.data?.error?.message ?? apiErr.message ?? "Failed to update slot publication."
      );
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
      const apiErr = err as { data?: { error?: { message?: string } }; message?: string };
      setErrorMessage(
        apiErr.data?.error?.message ?? apiErr.message ?? "Failed to withdraw slot."
      );
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

      <div className="mt-4 overflow-hidden rounded-md border border-line">
        {slots.length === 0 ? (
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
                <Select
                  id="slot-provider"
                  value={providerId}
                  onChange={(e) => setProviderId(e.target.value)}
                  className="mt-1 w-full"
                  required
                >
                  <option value="">Select a qualified Counselor…</option>
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
                </Select>
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
    </PanelSection>
  );
}

export function ServiceFixedSlotsStudentPanel({ service }: { service: ServiceResponse }) {
  const queryClient = useQueryClient();
  const [selectedSlot, setSelectedSlot] = useState<StudentBookableSlotResponse | null>(null);
  const [bookSuccess, setBookSuccess] = useState<string | null>(null);
  const [bookedApptId, setBookedApptId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const slotsQuery = useServicesListBookableSlots(service.id, undefined, {
    query: { retry: false },
  });
  const bookMutation = useServicesBookSlot();

  const slots = slotsQuery.data?.data ?? [];

  const handleBookSlot = async (slotId: string) => {
    setErrorMessage(null);
    setBookSuccess(null);
    try {
      const res = await bookMutation.mutateAsync({
        serviceId: service.id,
        slotId,
      });

      const appt = res.data;
      setBookedApptId(appt.appointment_id);
      setBookSuccess(`Appointment booked successfully! Reference code: ${appt.reference_code}`);
      setSelectedSlot(null);

      await queryClient.invalidateQueries({
        queryKey: getServicesListBookableSlotsQueryKey(service.id),
      });
    } catch (err: unknown) {
      const apiErr = err as { data?: { error?: { message?: string } }; message?: string };
      setErrorMessage(
        apiErr.data?.error?.message ?? apiErr.message ?? "Failed to book appointment slot."
      );
    }
  };

  return (
    <PanelSection title="Available appointment slots" titleId="student-fixed-slots-heading">
      <p className="text-sm text-muted">
        Choose a published date and time to reserve an individual appointment directly.
      </p>

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
        </Notice>
      ) : null}

      {errorMessage ? (
        <Notice role="alert" tone="danger" className="mt-4">
          {errorMessage}
        </Notice>
      ) : null}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {slots.length === 0 ? (
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
        pending={bookMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setSelectedSlot(null);
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
