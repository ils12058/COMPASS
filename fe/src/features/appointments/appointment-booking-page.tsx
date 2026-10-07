"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
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
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  appointmentSlotFreshness,
  slotIsOffered,
  SLOT_NO_LONGER_AVAILABLE,
  SLOTS_NOT_RECHECKED,
  useSlotSelection,
} from "@/features/appointments/appointment-slot-freshness";
import {
  bookedAppointmentFromResponse,
  classifyBookingFailure,
  type BookedAppointment,
} from "@/features/appointments/appointment-booking-outcome";
import { AppointmentsLocalNavigation, AppointmentsPageHeading, formatAppointmentDateTime, formatAppointmentTime, deliveryModeLabel } from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { focusHeading } from "@/lib/focus-heading";
import { INSTITUTION_TIME_ZONE, INSTITUTION_TIME_ZONE_LABEL } from "@/lib/institutional-time";

function BookingWorkspace() {
  const queryClient = useQueryClient();
  const [serviceSearch, setServiceSearch] = useState("");
  const [servicePage, setServicePage] = useState(1);
  const [service, setService] = useState<AppointmentBookingServiceSummary | null>(null);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode | "">("");
  const [counselorSelection, setCounselorSelection] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [inventoryAcknowledged, setInventoryAcknowledged] = useState(false);
  // Each failure is held for the step that can resolve it.
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [timeError, setTimeError] = useState<string | null>(null);
  const [bookingError, setBookingError] = useState<{ message: string; uncertain: boolean } | null>(null);
  const [booked, setBooked] = useState<BookedAppointment | null>(null);
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
        ...appointmentSlotFreshness,
      },
    },
  );
  const slotItems = slots.data?.data.items ?? [];
  const slotChoice = useSlotSelection(slots.data?.data.items, slots.dataUpdatedAt);
  const selectedSlot = slotItems.find((slot) => slot.starts_at === slotChoice.selected);
  // A failed recheck keeps the last times visible but does not let them be booked.
  const slotsUnconfirmed = slots.isError && slots.data !== undefined;
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

  function clearStepErrors() {
    setServiceError(null);
    setTimeError(null);
    setBookingError(null);
  }

  function changeService(next: AppointmentBookingServiceSummary | null) {
    setService(next);
    setDeliveryMode(next?.delivery_modes.length === 1 ? next.delivery_modes[0] : "");
    setCounselorSelection(null);
    setDate("");
    slotChoice.clear();
    setInventoryAcknowledged(false);
    clearStepErrors();
    intentRef.current = null;
  }

  function changeDeliveryMode(next: DeliveryMode) {
    setDeliveryMode(next);
    setCounselorSelection(null);
    setDate("");
    slotChoice.clear();
    clearStepErrors();
    intentRef.current = null;
  }

  function changeCounselor(next: string) {
    setCounselorSelection(next);
    setDate("");
    slotChoice.clear();
    clearStepErrors();
    intentRef.current = null;
  }

  function changeDate(next: string) {
    setDate(next);
    slotChoice.clear();
    clearStepErrors();
    intentRef.current = null;
  }

  function changeSlot(next: string) {
    slotChoice.select(next);
    clearStepErrors();
    intentRef.current = null;
  }

  async function bookAppointment() {
    if (!service || !deliveryMode || !selectedCounselor || !selectedSlot) return;
    setBookingError(null);
    setTimeError(null);
    if (!globalThis.crypto?.randomUUID) {
      setBookingError({ message: "This browser cannot create a secure booking request. Update the browser and try again.", uncertain: false });
      return;
    }
    setSubmitting(true);
    try {
      // Check the time is still offered before asking the server to book it. The server decides;
      // this only avoids sending a booking that is already known to be stale. A failed recheck
      // shows in the time step, which keeps the last times and holds booking.
      const recheck = await slots.refetch();
      if (recheck.isError) return;
      if (!slotIsOffered(recheck.data?.data.items, selectedSlot.starts_at)) {
        slotChoice.drop();
        focusHeading("booking-time-heading");
        return;
      }
      await submitBooking(service, deliveryMode, selectedCounselor, selectedSlot.starts_at);
    } finally {
      setSubmitting(false);
    }
  }

  async function submitBooking(
    bookedService: AppointmentBookingServiceSummary,
    mode: DeliveryMode,
    counselor: { id: string; is_default: boolean },
    startsAt: string,
  ) {

    const fingerprint = JSON.stringify({
      service_id: bookedService.id,
      provider_id: counselor.id,
      delivery_mode: mode,
      starts_at: startsAt,
    });
    const key =
      intentRef.current?.fingerprint === fingerprint
        ? intentRef.current.key
        : globalThis.crypto.randomUUID();
    intentRef.current = { fingerprint, key };

    try {
      const response = await create.mutateAsync({
        serviceId: bookedService.id,
        providerId: counselor.id,
        mode,
        startsAt,
        key,
      });
      const appointment = response.data;
      intentRef.current = null;
      // The acknowledgment reads the server's answer, so it states what was actually booked.
      setBooked(bookedAppointmentFromResponse(appointment, {
        assignedCounselor: counselor.is_default,
        timeZone: slots.data?.data.timezone,
      }));
      // The booked time leaves the slot list on the next check; it is no longer a pending choice.
      slotChoice.clear();
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsListMyQueryKey(),
      });
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsListBookableSlotsQueryKey(),
      });
    } catch (caught) {
      const failure = classifyBookingFailure(caught);
      if (failure.step === "time") {
        // The time went between the last check and the booking; show the current times.
        slotChoice.clear();
        setTimeError(failure.message);
        void slots.refetch();
        focusHeading("booking-time-heading");
      } else if (failure.step === "service") {
        // The Service changed since it was chosen; reload the list so only bookable ones show.
        changeService(null);
        setServiceError(failure.message);
        void bookingServices.refetch();
        focusHeading("booking-service-heading");
      } else {
        if (!failure.keepIntent) intentRef.current = null;
        setBookingError({ message: failure.message, uncertain: failure.uncertain });
      }
    }
  }

  // Done: the booking is complete, so the sheet starts over rather than keeping a spent review.
  function finishBooking() {
    setBooked(null);
    changeService(null);
    setServiceSearch("");
    setServicePage(1);
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

      <p className="-mt-3 mb-5 text-sm text-muted">
        Service <span aria-hidden="true">→</span> Delivery <span aria-hidden="true">→</span> Counselor <span aria-hidden="true">→</span> Time <span aria-hidden="true">→</span> Review
      </p>

      {/* One booking sheet: each step opens below the last, and the review closes the sheet with
          the booking action. */}
      <Panel as="div">
        <PanelSection title="1. Choose a Service" titleId="booking-service-heading">
          {serviceError ? (
            <p role="alert" className="mb-4 text-sm leading-6 text-danger">{serviceError}</p>
          ) : null}
          <div className="grid gap-2 sm:max-w-xl">
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
            <div aria-busy="true" className="mt-4 space-y-3">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
              <p className="sr-only">Loading Appointment Services…</p>
            </div>
          ) : bookingServices.isError ? (
            <div role="alert" className="mt-4">
              <p className="text-sm text-danger">Appointment Services could not be loaded.</p>
              <Button className="mt-3" variant="secondary" onClick={() => void bookingServices.refetch()}>Retry</Button>
            </div>
          ) : serviceItems.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              {serviceSearch.trim()
                ? "No appointment services match your search."
                : "No appointment services are currently available."}
            </p>
          ) : (
            <>
              <ul className="mt-4 divide-y divide-border rounded-sm border border-border">
                {serviceItems.map((item) => {
                  const selected = service?.id === item.id;
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() => changeService(item)}
                        className={
                          "w-full px-4 py-3.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus " +
                          (selected ? "bg-brand-wash" : "hover:bg-surface-subtle")
                        }
                      >
                        <span className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className={"font-semibold " + (selected ? "text-brand" : "text-ink")}>{item.name}</span>
                          {selected ? <span className="text-xs font-semibold text-brand">Selected</span> : null}
                        </span>
                        {item.description.trim() ? <span className="mt-1 block max-w-4xl text-sm leading-6 text-muted">{item.description}</span> : null}
                        <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                          <span>{item.default_appointment_duration_minutes} minutes</span>
                          <span>{item.delivery_modes.map(deliveryModeLabel).join(" · ")}</span>
                          {item.requires_current_inventory ? <span>Current-year Inventory required</span> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {servicePageData ? (
                <CanonicalPagination
                  className="border-t-0 pb-0"
                  page={servicePageData.page}
                  hasNext={servicePageData.has_next}
                  label="Service pages"
                  onPageChange={setServicePage}
                />
              ) : null}
            </>
          )}
        </PanelSection>

        {service ? (
          <PanelSection title="2. Choose delivery mode" titleId="booking-delivery-heading">
            <fieldset className="flex flex-wrap gap-3">
              <legend className="sr-only">Delivery mode</legend>
              {service.delivery_modes.map((mode) => (
                <label key={mode} className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-md border border-border-strong bg-surface-raised px-3 text-sm text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:checked]:font-semibold">
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
          </PanelSection>
        ) : null}

        {service && deliveryMode ? (
          <PanelSection title="3. Choose a Counselor" titleId="booking-counselor-heading">
            {counselors.isPending ? (
              <LoadingRegion label="Loading Counselors…">
                <Skeleton className="h-10 w-full max-w-xl" />
              </LoadingRegion>
            ) : counselors.isError ? (
              <div role="alert">
                <p className="text-sm text-danger">Eligible Counselors could not be loaded.</p>
                <Button className="mt-3" variant="secondary" onClick={() => void counselors.refetch()}>Retry</Button>
              </div>
            ) : counselorItems.length === 0 ? (
              <p className="text-sm text-muted">No eligible Counselors are available for this Service and delivery mode.</p>
            ) : (
              <div className="grid gap-2 sm:max-w-xl">
                <Label htmlFor="booking-counselor">Counselor</Label>
                <Select
                  id="booking-counselor"
                  value={counselorId}
                  onChange={(event) => changeCounselor(event.target.value)}
                >
                  {!counselorId ? <option value="">Choose a Counselor</option> : null}
                  {counselorItems.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.display_name}{candidate.is_default ? " — Assigned counselor" : ""}
                    </option>
                  ))}
                </Select>
              </div>
            )}
          </PanelSection>
        ) : null}

        {service && deliveryMode && selectedCounselor ? (
          <PanelSection title="4. Choose date and time" titleId="booking-time-heading">
            <div className="grid gap-2 sm:max-w-xs">
              <Label htmlFor="booking-date">Appointment date</Label>
              <Input id="booking-date" type="date" value={date} onChange={(event) => changeDate(event.target.value)} />
            </div>
            {date ? (
              <div className="mt-5">
                {timeError ? (
                  <p role="alert" className="mb-3 text-sm text-danger">{timeError}</p>
                ) : slotChoice.lost ? (
                  <p role="status" className="mb-3 text-sm text-warning">{SLOT_NO_LONGER_AVAILABLE}</p>
                ) : null}
                {slots.isPending ? (
                  <LoadingRegion label="Loading available times…" className="flex flex-wrap gap-2">
                    <Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" />
                  </LoadingRegion>
                ) : slots.isError && !slotsUnconfirmed ? (
                  <div role="alert">
                    <p className="text-sm text-danger">Available times could not be loaded.</p>
                    <Button className="mt-3" variant="secondary" onClick={() => void slots.refetch()}>Retry</Button>
                  </div>
                ) : slotItems.length === 0 ? (
                  <p role="status" className="text-sm text-muted">No available appointment times were found for this date. Choose another date.</p>
                ) : (
                  <>
                    {slotsUnconfirmed ? (
                      <Notice
                        role="status"
                        tone="warning"
                        className="mb-3"
                        action={<Button variant="secondary" disabled={slots.isFetching} onClick={() => void slots.refetch()}>{slots.isFetching ? "Retrying…" : "Retry"}</Button>}
                      >
                        {SLOTS_NOT_RECHECKED}
                      </Notice>
                    ) : null}
                    <p className="mb-3 text-sm font-semibold text-ink">Available times · {slots.data?.data.timezone === INSTITUTION_TIME_ZONE ? INSTITUTION_TIME_ZONE_LABEL : slots.data?.data.timezone}</p>
                    <div role="group" aria-label="Available appointment times" className="flex flex-wrap gap-2">
                      {slotItems.map((slot) => {
                        const selected = slot.starts_at === slotChoice.selected;
                        return (
                          <button
                            key={slot.starts_at}
                            type="button"
                            aria-pressed={selected}
                            onClick={() => changeSlot(slot.starts_at)}
                            className={
                              "min-h-11 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                              (selected ? "border-brand bg-brand text-on-brand" : "border-border-strong bg-surface-raised text-ink hover:bg-surface-subtle")
                            }
                          >
                            {formatAppointmentTime(slot.starts_at, slots.data?.data.timezone)}
                          </button>
                        );
                      })}
                    </div>

                  </>
                )}
              </div>
            ) : null}
          </PanelSection>
        ) : null}

        {service && deliveryMode && selectedCounselor && selectedSlot ? (
          <>
            <PanelSection title="5. Review appointment" titleId="booking-review-heading">
              <dl className="grid max-w-3xl gap-x-8 gap-y-4 sm:grid-cols-2">
                <div><dt className="text-xs font-semibold text-muted">Service</dt><dd className="mt-1 text-sm text-ink">{service.name}</dd></div>
                <div><dt className="text-xs font-semibold text-muted">Counselor</dt><dd className="mt-1 text-sm text-ink">{selectedCounselor.display_name}{selectedCounselor.is_default ? " · Assigned counselor" : ""}</dd></div>
                <div><dt className="text-xs font-semibold text-muted">Delivery</dt><dd className="mt-1 text-sm text-ink">{deliveryModeLabel(deliveryMode)}</dd></div>
                <div><dt className="text-xs font-semibold text-muted">Schedule</dt><dd className="mt-1 text-sm text-ink">{formatAppointmentDateTime(selectedSlot.starts_at, selectedSlot.ends_at, slots.data?.data.timezone)}</dd></div>
                <div><dt className="text-xs font-semibold text-muted">Duration</dt><dd className="mt-1 text-sm text-ink">{slots.data?.data.duration_minutes ?? service.default_appointment_duration_minutes} minutes</dd></div>
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
              {bookingError ? (
                <Notice
                  role="alert"
                  tone={bookingError.uncertain ? "warning" : "danger"}
                  className="mt-5 max-w-3xl"
                >
                  {bookingError.message}
                </Notice>
              ) : null}
            </PanelSection>
            <PanelFooter>
              <Button
                disabled={submitting || booked !== null || slotsUnconfirmed || (hasInventoryRequirement && !inventoryAcknowledged)}
                onClick={() => void bookAppointment()}
                aria-busy={submitting}
              >
                {submitting ? "Booking…" : bookingError?.uncertain ? "Retry booking" : "Book appointment"}
              </Button>
              <p className="text-xs text-muted">
                {slotsUnconfirmed
                  ? "Booking is held until the available times are rechecked."
                  : "This Appointment will be scheduled immediately after a successful booking."}
              </p>
            </PanelFooter>
          </>
        ) : null}
      </Panel>

      <BookingCompletion booked={booked} onDone={finishBooking} />
    </section>
  );
}

// A confirmed booking is acknowledged once, in a dialog: the Appointment now exists and has a
// reference, and the natural next step is to open it. Done (or closing) starts a new booking, so a
// spent review never lingers with a disabled Book button.
function BookingCompletion({ booked, onDone }: { booked: BookedAppointment | null; onDone: () => void }) {
  const viewLink = useRef<HTMLAnchorElement>(null);
  return (
    <Dialog open={booked !== null} onOpenChange={(open) => { if (!open) onDone(); }}>
      {booked ? (
        <DialogContent
          closeLabel="Close and start a new booking"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            viewLink.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            // The review that opened this is gone; a new booking starts at the Service search.
            event.preventDefault();
            document.getElementById("booking-service-search")?.focus();
          }}
        >
          <DialogTitle>Appointment scheduled</DialogTitle>
          <DialogDescription asChild>
            <dl className="mt-4 grid gap-x-6 gap-y-3 sm:grid-cols-2">
              {booked.facts.map((fact) => (
                <div key={fact.label} className={fact.label === "Schedule" ? "sm:col-span-2" : undefined}>
                  <dt className="text-xs font-semibold text-muted">{fact.label}</dt>
                  <dd className="mt-0.5 break-words text-sm text-ink">{fact.value}</dd>
                </div>
              ))}
            </dl>
          </DialogDescription>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={onDone}>Done</Button>
            <Link ref={viewLink} href={`/portal/appointments/${booked.id}`} className={buttonVariants({ variant: "primary" })}>
              View appointment
            </Link>
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}

export function AppointmentBookingPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.canBook) {
    return (
      <section aria-labelledby="appointment-booking-unavailable-heading">
        <AppointmentsLocalNavigation />
        <PageHeader title="Booking unavailable" headingId="appointment-booking-unavailable-heading" />
        <Notice
          className="max-w-2xl"
          action={access.canViewSelf ? (
            <Link
              href="/portal/appointments/my"
              className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Go to My appointments
            </Link>
          ) : undefined}
        >
          {access.isStudent
            ? access.canViewSelf
              ? "Only current students can book appointments. You can still view your existing appointments."
              : "Booking is unavailable to this account."
            : "Student self-booking is not available to this account."}
        </Notice>
      </section>
    );
  }
  return <BookingWorkspace />;
}
