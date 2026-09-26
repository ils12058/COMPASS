"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DeliveryMode,
  type AppointmentBookingServiceSummary,
} from "@/lib/api/generated/model";
import {
  appointmentsCreateMy,
  getAppointmentsCreateMyMutationKey,
  getAppointmentsListBookableSlotsQueryKey,
  getAppointmentsListMyQueryKey,
  useAppointmentsListBookableSlots,
  useAppointmentsListBookingServices,
  useAppointmentsListEligibleCounselors,
} from "@/lib/api/generated/appointments/appointments";
import { appointmentErrorCode, appointmentErrorMessage, AppointmentsLocalNavigation, AppointmentsPageHeading, formatAppointmentDateTime, formatAppointmentTime, PaginationControls, deliveryModeLabel } from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";

const controlClass = "min-h-10 w-full rounded-md border border-border bg-surface-raised px-3 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus";

function BookingWorkspace() {
  const queryClient = useQueryClient();
  const [serviceSearch, setServiceSearch] = useState("");
  const [servicePage, setServicePage] = useState(1);
  const [service, setService] = useState<AppointmentBookingServiceSummary | null>(null);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode | "">("");
  const [counselorSelection, setCounselorSelection] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [selectedSlotStart, setSelectedSlotStart] = useState("");
  const [inventoryAcknowledged, setInventoryAcknowledged] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdAppointment, setCreatedAppointment] = useState<{
    id: string;
    referenceCode: string;
  } | null>(null);
  const intentRef = useRef<{ fingerprint: string; key: string } | null>(null);

  const bookingServices = useAppointmentsListBookingServices(
    {
      ...(serviceSearch.trim() ? { search: serviceSearch.trim() } : {}),
      page: servicePage,
      page_size: 10,
    },
    { query: { retry: false } },
  );

  const counselors = useAppointmentsListEligibleCounselors(
    {
      service_id: service?.id ?? "",
      delivery_mode: deliveryMode || DeliveryMode.IN_PERSON,
    },
    { query: { enabled: Boolean(service && deliveryMode), retry: false } },
  );

  const counselorItems = counselors.data?.data.items ?? [];
  const defaultCounselor = counselorItems.find((candidate) => candidate.is_default);
  const counselorId =
    counselorSelection === null
      ? defaultCounselor?.id ?? ""
      : counselorSelection;
  const selectedCounselor = counselorItems.find((candidate) => candidate.id === counselorId);

  const slots = useAppointmentsListBookableSlots(
    {
      service_id: service?.id ?? "",
      provider_id: counselorId,
      delivery_mode: deliveryMode || DeliveryMode.IN_PERSON,
      date: date || "1970-01-01",
    },
    {
      query: {
        enabled: Boolean(service && deliveryMode && counselorId && date),
        retry: false,
      },
    },
  );
  const slotItems = slots.data?.data.items ?? [];
  const selectedSlot = slotItems.find((slot) => slot.starts_at === selectedSlotStart);
  const create = useMutation({
    mutationKey: getAppointmentsCreateMyMutationKey(),
    mutationFn: ({
      serviceId,
      providerId,
      mode,
      startsAt,
      key,
    }: {
      serviceId: string;
      providerId: string;
      mode: DeliveryMode;
      startsAt: string;
      key: string;
    }) =>
      appointmentsCreateMy(
        {
          service_id: serviceId,
          provider_id: providerId,
          delivery_mode: mode,
          starts_at: startsAt,
        },
        { headers: { "Idempotency-Key": key } },
      ),
  });

  function changeService(next: AppointmentBookingServiceSummary) {
    setService(next);
    setDeliveryMode(next.delivery_modes.length === 1 ? next.delivery_modes[0] : "");
    setCounselorSelection(null);
    setDate("");
    setSelectedSlotStart("");
    setInventoryAcknowledged(false);
    setError(null);
    setCreatedAppointment(null);
    intentRef.current = null;
  }

  function changeDeliveryMode(next: DeliveryMode) {
    setDeliveryMode(next);
    setCounselorSelection(null);
    setDate("");
    setSelectedSlotStart("");
    setError(null);
    setCreatedAppointment(null);
    intentRef.current = null;
  }

  function changeCounselor(next: string) {
    setCounselorSelection(next);
    setDate("");
    setSelectedSlotStart("");
    setError(null);
    setCreatedAppointment(null);
    intentRef.current = null;
  }

  function changeDate(next: string) {
    setDate(next);
    setSelectedSlotStart("");
    setError(null);
    setCreatedAppointment(null);
    intentRef.current = null;
  }

  function changeSlot(next: string) {
    setSelectedSlotStart(next);
    setError(null);
    setCreatedAppointment(null);
    intentRef.current = null;
  }

  async function bookAppointment() {
    if (!service || !deliveryMode || !selectedCounselor || !selectedSlot) return;
    setError(null);
    if (!globalThis.crypto?.randomUUID) {
      setError("This browser cannot create a secure booking request. Update the browser and try again.");
      return;
    }

    const fingerprint = JSON.stringify({
      service_id: service.id,
      provider_id: selectedCounselor.id,
      delivery_mode: deliveryMode,
      starts_at: selectedSlot.starts_at,
    });
    const key =
      intentRef.current?.fingerprint === fingerprint
        ? intentRef.current.key
        : globalThis.crypto.randomUUID();
    intentRef.current = { fingerprint, key };

    try {
      const response = await create.mutateAsync({
        serviceId: service.id,
        providerId: selectedCounselor.id,
        mode: deliveryMode,
        startsAt: selectedSlot.starts_at,
        key,
      });
      const appointment = response.data;
      intentRef.current = null;
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsListMyQueryKey(),
      });
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsListBookableSlotsQueryKey(),
      });
      setCreatedAppointment({ id: appointment.id, referenceCode: appointment.reference_code });
    } catch (caught) {
      const code = appointmentErrorCode(caught);
      if (code === "appointment_time_unavailable" || code === "appointment_time_conflict") {
        setSelectedSlotStart("");
        setError("That time is no longer available. Available times have been refreshed; choose another time to continue.");
        void slots.refetch();
      } else if (code === "idempotency_key_conflict") {
        intentRef.current = null;
        setError(appointmentErrorMessage(caught, "The booking attempt could not be verified. Review the details and submit again."));
      } else if (caught instanceof CompassApiError) {
        setError(appointmentErrorMessage(caught, "The Appointment could not be booked."));
      } else {
        // Keep the exact-intent key so a retry after an uncertain network response is replay-safe.
        setError("The booking response could not be confirmed. Retry the same booking details to check the result safely.");
      }
    }
  }

  const servicePageData = bookingServices.data?.data;
  const serviceItems = servicePageData?.items ?? [];
  const hasInventoryRequirement = service?.requires_current_inventory ?? false;

  return (
    <section aria-labelledby="book-appointment-heading">
      <AppointmentsLocalNavigation />
      <AppointmentsPageHeading
        headingId="book-appointment-heading"
        title="Book appointment"
      />

      <p className="mb-6 text-sm text-muted">
        Service <span aria-hidden="true">→</span> Delivery <span aria-hidden="true">→</span> Counselor <span aria-hidden="true">→</span> Time <span aria-hidden="true">→</span> Review
      </p>

      <section aria-labelledby="booking-service-heading" className="border-y border-border py-5">
        <h2 id="booking-service-heading" className="font-heading text-xl font-semibold text-ink">1. Choose a Service</h2>
        <div className="mt-4 grid gap-2 sm:max-w-xl">
          <Label htmlFor="booking-service-search">Search Appointment Services</Label>
          <Input
            id="booking-service-search"
            type="search"
            value={serviceSearch}
            onChange={(event) => {
              setServiceSearch(event.target.value);
              setServicePage(1);
            }}
            placeholder="Search by Service name or code"
          />
        </div>

        {bookingServices.isPending ? (
          <div aria-busy="true" className="mt-5 space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <p className="sr-only">Loading Appointment Services…</p>
          </div>
        ) : bookingServices.isError ? (
          <div role="alert" className="mt-5 border-y border-danger/30 py-5">
            <p className="text-sm text-danger">Appointment Services could not be loaded.</p>
            <Button className="mt-3" variant="secondary" onClick={() => void bookingServices.refetch()}>Retry</Button>
          </div>
        ) : serviceItems.length === 0 ? (
          <p className="mt-5 border-y border-border py-6 text-sm text-muted">
            {serviceSearch.trim()
              ? "No Appointment services match your search."
              : "No Appointment services are currently available."}
          </p>
        ) : (
          <>
            <ul className="mt-5 divide-y divide-border border-y border-border">
              {serviceItems.map((item) => {
                const selected = service?.id === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      aria-pressed={selected}
                      onClick={() => changeService(item)}
                      className={
                        "w-full px-3 py-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                        (selected ? "bg-surface-muted" : "hover:bg-surface-muted/60")
                      }
                    >
                      <span className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="font-semibold text-ink">{item.name}</span>
                        <span className="font-mono text-xs text-muted">{item.code}</span>
                      </span>
                      <span className="mt-1 block max-w-4xl text-sm leading-6 text-muted">{item.description || "No description provided."}</span>
                      <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                        <span>{item.default_duration_minutes} minutes</span>
                        <span>{item.delivery_modes.map(deliveryModeLabel).join(" · ")}</span>
                        {item.requires_current_inventory ? <span>Current-year Inventory required</span> : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
            {servicePageData ? (
              <PaginationControls
                page={servicePageData.page}
                hasNext={servicePageData.has_next}
                onPrevious={() => setServicePage(Math.max(1, servicePage - 1))}
                onNext={() => setServicePage(servicePage + 1)}
              />
            ) : null}
          </>
        )}
      </section>

      {service ? (
        <section aria-labelledby="booking-delivery-heading" className="border-b border-border py-5">
          <h2 id="booking-delivery-heading" className="font-heading text-xl font-semibold text-ink">2. Choose delivery mode</h2>
          <fieldset className="mt-4 flex flex-wrap gap-3">
            <legend className="sr-only">Delivery mode</legend>
            {service.delivery_modes.map((mode) => (
              <label key={mode} className="inline-flex min-h-10 items-center gap-2 border border-border bg-surface-raised px-3 text-sm text-ink focus-within:ring-2 focus-within:ring-focus">
                <input
                  type="radio"
                  name="appointment-delivery-mode"
                  value={mode}
                  checked={deliveryMode === mode}
                  onChange={() => changeDeliveryMode(mode)}
                  className="accent-brand"
                />
                {deliveryModeLabel(mode)}
              </label>
            ))}
          </fieldset>
        </section>
      ) : null}

      {service && deliveryMode ? (
        <section aria-labelledby="booking-counselor-heading" className="border-b border-border py-5">
          <h2 id="booking-counselor-heading" className="font-heading text-xl font-semibold text-ink">3. Choose a Counselor</h2>
          {counselors.isPending ? (
            <Skeleton className="mt-4 h-10 w-full max-w-xl" />
          ) : counselors.isError ? (
            <div role="alert" className="mt-4">
              <p className="text-sm text-danger">Eligible Counselors could not be loaded.</p>
              <Button className="mt-3" variant="secondary" onClick={() => void counselors.refetch()}>Retry</Button>
            </div>
          ) : counselorItems.length === 0 ? (
            <p className="mt-3 text-sm text-muted">No eligible Counselors are available for this Service and delivery mode.</p>
          ) : (
            <div className="mt-4 grid gap-2 sm:max-w-xl">
              <Label htmlFor="booking-counselor">Counselor</Label>
              <select
                id="booking-counselor"
                className={controlClass}
                value={counselorId}
                onChange={(event) => changeCounselor(event.target.value)}
              >
                {!counselorId ? <option value="">Choose a Counselor</option> : null}
                {counselorItems.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.display_name}{candidate.is_default ? " — Assigned counselor" : ""}
                  </option>
                ))}
              </select>
              {selectedCounselor?.is_default ? (
                <p className="text-xs text-muted">Assigned counselor is selected. You can choose another eligible Counselor.</p>
              ) : null}
            </div>
          )}
        </section>
      ) : null}

      {service && deliveryMode && selectedCounselor ? (
        <section aria-labelledby="booking-time-heading" className="border-b border-border py-5">
          <h2 id="booking-time-heading" className="font-heading text-xl font-semibold text-ink">4. Choose date and time</h2>
          <div className="mt-4 grid gap-2 sm:max-w-xs">
            <Label htmlFor="booking-date">Appointment date</Label>
            <Input id="booking-date" type="date" value={date} onChange={(event) => changeDate(event.target.value)} />
          </div>
          {date ? (
            <div className="mt-5" aria-live="polite">
              {slots.isPending ? (
                <div aria-busy="true" className="flex flex-wrap gap-2">
                  <Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" />
                  <p className="sr-only">Loading available times…</p>
                </div>
              ) : slots.isError ? (
                <div role="alert">
                  <p className="text-sm text-danger">Available times could not be loaded.</p>
                  <Button className="mt-3" variant="secondary" onClick={() => void slots.refetch()}>Retry</Button>
                </div>
              ) : slotItems.length === 0 ? (
                <p className="text-sm text-muted">No available appointment times were found for this date. Choose another date.</p>
              ) : (
                <>
                  <p className="mb-3 text-sm font-semibold text-ink">Available times · {slots.data?.data.timezone}</p>
                  <div role="group" aria-label="Available appointment times" className="flex flex-wrap gap-2">
                    {slotItems.map((slot) => {
                      const selected = slot.starts_at === selectedSlotStart;
                      return (
                        <button
                          key={slot.starts_at}
                          type="button"
                          aria-pressed={selected}
                          onClick={() => changeSlot(slot.starts_at)}
                          className={
                            "min-h-10 border px-4 py-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                            (selected ? "border-brand bg-brand text-on-brand" : "border-border bg-surface-raised text-ink hover:bg-surface-muted")
                          }
                        >
                          {formatAppointmentTime(slot.starts_at, slots.data?.data.timezone)}
                        </button>
                      );
                    })}
                  </div>
                  {slots.isFetching ? <p role="status" className="mt-3 text-xs text-muted">Refreshing available times…</p> : null}
                </>
              )}
            </div>
          ) : null}
        </section>
      ) : null}

      {service && deliveryMode && selectedCounselor && selectedSlot ? (
        <section aria-labelledby="booking-review-heading" className="py-5">
          <h2 id="booking-review-heading" className="font-heading text-xl font-semibold text-ink">5. Review appointment</h2>
          <dl className="mt-4 grid max-w-3xl gap-x-8 gap-y-4 border-y border-border py-5 sm:grid-cols-2">
            <div><dt className="text-xs font-semibold text-muted">Service</dt><dd className="mt-1 text-sm text-ink">{service.name}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Counselor</dt><dd className="mt-1 text-sm text-ink">{selectedCounselor.display_name}{selectedCounselor.is_default ? " · Assigned counselor" : ""}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Delivery</dt><dd className="mt-1 text-sm text-ink">{deliveryModeLabel(deliveryMode)}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Schedule</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(selectedSlot.starts_at, selectedSlot.ends_at, slots.data?.data.timezone)}</dd></div>
            <div><dt className="text-xs font-semibold text-muted">Duration</dt><dd className="mt-1 text-sm text-ink">{slots.data?.data.duration_minutes ?? service.default_duration_minutes} minutes</dd></div>
            {service.cancellation_cutoff_minutes !== null ? (
              <div><dt className="text-xs font-semibold text-muted">Self-service changes</dt><dd className="mt-1 text-sm text-ink">Available until {service.cancellation_cutoff_minutes} minutes before the Appointment.</dd></div>
            ) : null}
          </dl>
          {hasInventoryRequirement ? (
            <label className="mt-5 flex max-w-3xl items-start gap-3 text-sm leading-6 text-ink">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0 accent-brand"
                checked={inventoryAcknowledged}
                onChange={(event) => setInventoryAcknowledged(event.target.checked)}
              />
              <span>A submitted Individual Inventory for the current Academic Year is required to book this Service.</span>
            </label>
          ) : null}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button
              disabled={create.isPending || createdAppointment !== null || (hasInventoryRequirement && !inventoryAcknowledged)}
              onClick={() => void bookAppointment()}
              aria-busy={create.isPending}
            >
              {create.isPending ? "Booking…" : "Book appointment"}
            </Button>
            <p className="text-xs text-muted">This Appointment will be scheduled immediately after a successful booking.</p>
          </div>
        </section>
      ) : null}

      {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      {createdAppointment ? (
        <div role="status" className="mt-4 flex flex-col gap-3 border-y border-success/30 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-success">Appointment {createdAppointment.referenceCode} was scheduled.</p>
          <Link
            href={`/portal/appointments/${createdAppointment.id}`}
            className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            View Appointment
          </Link>
        </div>
      ) : null}
    </section>
  );
}

export function AppointmentBookingPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.canBook) {
    return (
      <section aria-labelledby="appointment-booking-unavailable-heading">
        <AppointmentsLocalNavigation />
        <h1 id="appointment-booking-unavailable-heading" className="font-heading text-3xl font-bold text-ink">Booking unavailable</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
          {access.isStudent
            ? "Only a current Student with Appointment self-management access can book. Existing Appointments remain available from My Appointments."
            : "Student self-booking is not available to this account."}
        </p>
        {access.canViewSelf ? (
          <Link
            href="/portal/appointments/my"
            className="mt-4 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            Go to My appointments
          </Link>
        ) : null}
      </section>
    );
  }
  return <BookingWorkspace />;
}
