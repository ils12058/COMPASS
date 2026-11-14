"use client";

import { studentSchedulingScope } from "./booking-recovery";
import { StudentBookingPathways } from "./student-booking-pathways";
import { AppointmentFixedDateBooking } from "./appointment-fixed-date-booking";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";

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
  getAppointmentsListBookingServicesQueryKey,
  getAppointmentsListEligibleCounselorsQueryKey,
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
  useSlotSelection,
} from "@/features/appointments/appointment-slot-freshness";
import {
  bookedAppointmentFromResponse,
  classifyBookingFailure,
  type BookedAppointment,
} from "@/features/appointments/appointment-booking-outcome";
import { AppointmentsLocalNavigation, AppointmentsPageHeading, formatAppointmentDateTime, deliveryModeLabel } from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { AppointmentDateCalendar } from "./appointment-date-calendar";
import { AppointmentAvailableTimes } from "./appointment-available-times";
import { BookingCounselorChoice } from "./booking-counselor-choice";
import { PersonAvatar } from "@/features/account/components/person-avatar";
import { isCounselingService } from "@/features/counseling/canonical-counseling-service";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { focusHeading } from "@/lib/focus-heading";
import { institutionalDateInputValue } from "@/lib/institutional-time";

// Offers only the modes the Service currently supports. For canonical Counseling, ONLINE is
// explained as E-Counseling; ordinary Services' ONLINE stays a plain delivery mode.
export function BookingDeliveryModeChoice({
  service,
  value,
  onChange,
  disabled = false,
}: {
  disabled?: boolean;
  service: AppointmentBookingServiceSummary;
  value: DeliveryMode | "";
  onChange: (mode: DeliveryMode) => void;
}) {
  const onlineUsesECounseling =
    isCounselingService(service) && service.delivery_modes.includes(DeliveryMode.ONLINE);
  return (
    <>
      <fieldset disabled={disabled} className="flex flex-wrap gap-3">
        <legend className="sr-only">Delivery mode</legend>
        {service.delivery_modes.map((mode) => (
          <label key={mode} className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-md border border-border-strong bg-surface-raised px-3 text-sm text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:checked]:font-semibold">
            <input
              type="radio"
              name="appointment-delivery-mode"
              value={mode}
              checked={value === mode}
              onChange={() => onChange(mode)}
              aria-describedby={onlineUsesECounseling && mode === DeliveryMode.ONLINE ? "booking-online-help" : undefined}
              className="accent-brand"
            />
            {deliveryModeLabel(mode)}
          </label>
        ))}
      </fieldset>
      {onlineUsesECounseling ? (
        <p id="booking-online-help" className="mt-2 text-xs leading-5 text-muted">
          Use E-Counseling for online Appointments.
        </p>
      ) : null}
    </>
  );
}

function BookingWorkspace() {
  const { user } = usePortalSession();
  const viewerScope = studentSchedulingScope(user);
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
    { query: { retry: false, queryKey: [...getAppointmentsListBookingServicesQueryKey(), viewerScope, serviceSearch, servicePage] } },
  );

  const counselors = useAppointmentsListEligibleCounselors(
    {
      service_id: service?.id ?? "",
      delivery_mode: deliveryMode || DeliveryMode.IN_PERSON,
    },
    { query: { enabled: Boolean(service && deliveryMode), retry: false, queryKey: [...getAppointmentsListEligibleCounselorsQueryKey(), viewerScope, service?.id ?? "", deliveryMode] } },
  );

  const counselorItems = counselors.data?.data.items ?? [];
  const defaultCounselor = counselorItems.find((candidate) => candidate.is_default);
  const counselorId =
    counselorSelection === null
      ? defaultCounselor?.id ?? (counselorItems.length === 1 ? counselorItems[0].id : "")
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
        enabled: Boolean(service && deliveryMode && selectedCounselor && !counselors.isError && date),
        queryKey: [...getAppointmentsListBookableSlotsQueryKey(), viewerScope, service?.id ?? "", counselorId, deliveryMode, date],
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
      await invalidateGuidanceWork(queryClient);
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
        title="Book Appointment"
      />

      <StudentBookingPathways illustration={!service && !booked && !serviceError && !bookingServices.isPending && !bookingServices.isError && serviceItems.length > 0 ? "/illustrations/service-catalog-3d.webp" : undefined} />


      {/* One booking sheet: each step opens below the last, and the review closes the sheet with
          the booking action. */}
      <Panel as="div">
        <PanelSection title="1. Choose a Service" titleId="booking-service-heading" data-guide-target="booking-service">
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
              <p className="text-sm text-danger">Couldn&apos;t load Appointment Services. Try again.</p>
              <Button className="mt-3" variant="secondary" onClick={() => void bookingServices.refetch()}>Retry</Button>
            </div>
          ) : serviceItems.length === 0 ? (
            <p className="mt-4 text-sm text-muted">
              {serviceSearch.trim()
                ? "No Appointment Services match your search."
                : "No Appointment Services are currently available."}
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
                        disabled={submitting}
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
                          {item.requires_current_inventory ? <span>Current Academic Year Individual Inventory required</span> : null}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
              {servicePageData ? (
                <CanonicalPagination
                  className="flex-wrap border-t-0 pb-0 [&>button]:max-w-full [&>button]:[overflow-wrap:anywhere]"
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
          <PanelSection title="2. Choose delivery mode" titleId="booking-delivery-heading" data-guide-target="booking-delivery">
            <BookingDeliveryModeChoice
              service={service}
              value={deliveryMode}
              onChange={changeDeliveryMode}
              disabled={submitting}
            />
          </PanelSection>
        ) : null}

        {service && deliveryMode ? (
          <PanelSection title="3. Choose a Counselor" titleId="booking-counselor-heading" data-guide-target="booking-counselor">
            {counselors.isPending ? (
              <LoadingRegion label="Loading Counselors…">
                <Skeleton className="h-10 w-full max-w-xl" />
              </LoadingRegion>
            ) : counselors.isError ? (
              <div role="alert">
                <p className="text-sm text-danger">Couldn&apos;t load Counselors. Try again.</p>
                <Button className="mt-3" variant="secondary" onClick={() => void counselors.refetch()}>Retry</Button>
              </div>
            ) : counselorItems.length === 0 ? (
              <p className="text-sm text-muted">No Counselors are available for this Service and delivery mode.</p>
            ) : (
              <BookingCounselorChoice items={counselorItems} value={counselorId} onChange={changeCounselor} disabled={submitting} />
            )}
          </PanelSection>
        ) : null}

        {service && deliveryMode && selectedCounselor ? (
          <PanelSection title="4. Choose date and time" titleId="booking-time-heading" data-guide-target="booking-time">
            <div className="@container">
              <div className="grid items-start gap-5 @min-[42rem]:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
                <AppointmentDateCalendar key={`${service.id}:${deliveryMode}:${counselorId}`} min={institutionalDateInputValue()} value={date} onChange={changeDate} disabled={submitting} />
                <AppointmentAvailableTimes
                  date={date} items={slotItems} selected={slotChoice.selected} timezone={slots.data?.data.timezone}
                  pending={slots.isPending} fetching={slots.isFetching} failed={slots.isError}
                  unconfirmed={slotsUnconfirmed} lost={slotChoice.lost} error={timeError} disabled={submitting}
                  onSelect={changeSlot} onRefresh={() => void slots.refetch()}
                />
              </div>
            </div>
          </PanelSection>
        ) : null}

        {service && deliveryMode && selectedCounselor && selectedSlot ? (
          <>
            <PanelSection title="5. Review Appointment" titleId="booking-review-heading" data-guide-target="booking-review">
              <dl className="grid max-w-3xl gap-x-8 gap-y-4 sm:grid-cols-2">
                <div><dt className="text-xs font-semibold text-muted">Service</dt><dd className="mt-1 text-sm text-ink">{service.name}</dd></div>
                <div><dt className="text-xs font-semibold text-muted">Counselor</dt><dd className="mt-1 flex items-center gap-2 text-sm text-ink"><PersonAvatar displayName={selectedCounselor.display_name} photoUrl={selectedCounselor.profile_photo_url} photoUpdatedAt={selectedCounselor.profile_photo_updated_at} size="compact" />{selectedCounselor.display_name}{selectedCounselor.is_default ? " · Assigned Counselor" : ""}</dd></div>
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
                {submitting ? "Booking…" : bookingError?.uncertain ? "Retry booking" : "Book Appointment"}
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
  const { user } = usePortalSession();
  const canView = user.capabilities.includes("appointments.view_self");
  return (
    <Dialog open={booked !== null} onOpenChange={(open) => { if (!open) onDone(); }}>
      {booked ? (
        <DialogContent
          closeLabel="Close and start a new booking"
          onOpenAutoFocus={(event) => {
            if (viewLink.current) {
              event.preventDefault();
              viewLink.current.focus();
            }
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
            {canView ? <Link ref={viewLink} href={`/portal/appointments/${booked.id}`} className={buttonVariants({ variant: "primary" })}>
              View Appointment
            </Link> : <p className="text-sm text-muted">You don&apos;t have access to Appointment details.</p>}
          </div>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}

export function AppointmentBookingPage({ scheduledSlots = false, serviceId, initialSearch, initialPage }: { scheduledSlots?: boolean; serviceId?: string; initialSearch?: string; initialPage?: string } = {}) {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  if (!access.canBook) {
    return (
      <section aria-labelledby="appointment-booking-unavailable-heading">
        <AppointmentsLocalNavigation />
        <PageHeader title="Appointment booking access" headingId="appointment-booking-unavailable-heading" />
        <Notice
          className="max-w-2xl"
          action={access.canViewSelf ? (
            <Link
              href="/portal/appointments/my"
              className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Go to My Appointments
            </Link>
          ) : undefined}
        >
          {access.isStudent
            ? user.student_lifecycle_status !== "CURRENT"
              ? access.canViewSelf ? "Only current Students can book Appointments. You can still view your existing Appointments." : "Only current Students can book Appointments."
              : access.canViewSelf ? "You don't have access to book Appointments. You can still view your existing Appointments." : "You don't have access to book Appointments."
            : "You don't have access to Student Appointment booking."}
        </Notice>
      </section>
    );
  }
  return scheduledSlots ? <AppointmentFixedDateBooking key={`${user.id}:${user.capabilities.join(",")}:${serviceId ?? ""}`} initialServiceId={serviceId} initialSearch={initialSearch} initialPage={initialPage} /> : <BookingWorkspace key={`${user.id}:${user.capabilities.join(",")}`} />;
}
