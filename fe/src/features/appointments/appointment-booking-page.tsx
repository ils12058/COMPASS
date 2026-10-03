"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
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
import { appointmentErrorCode, appointmentErrorMessage, AppointmentsLocalNavigation, AppointmentsPageHeading, formatAppointmentDateTime, formatAppointmentTime, deliveryModeLabel } from "@/features/appointments/appointments-shared";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { CompassApiError } from "@/lib/api/errors";
import { INSTITUTION_TIME_ZONE, INSTITUTION_TIME_ZONE_LABEL } from "@/lib/institutional-time";

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

      <p className="-mt-3 mb-5 text-sm text-muted">
        Service <span aria-hidden="true">→</span> Delivery <span aria-hidden="true">→</span> Counselor <span aria-hidden="true">→</span> Time <span aria-hidden="true">→</span> Review
      </p>

      {/* One booking sheet: each step opens below the last, and the review closes the sheet with
          the booking action. */}
      <Panel as="div">
        <PanelSection title="1. Choose a Service" titleId="booking-service-heading">
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
                {selectedCounselor?.is_default ? (
                  <p className="text-xs text-muted">Assigned counselor is selected. You can choose another eligible Counselor.</p>
                ) : null}
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
                {slots.isPending ? (
                  <LoadingRegion label="Loading available times…" className="flex flex-wrap gap-2">
                    <Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" /><Skeleton className="h-10 w-24" />
                  </LoadingRegion>
                ) : slots.isError ? (
                  <div role="alert">
                    <p className="text-sm text-danger">Available times could not be loaded.</p>
                    <Button className="mt-3" variant="secondary" onClick={() => void slots.refetch()}>Retry</Button>
                  </div>
                ) : slotItems.length === 0 ? (
                  <p role="status" className="text-sm text-muted">No available appointment times were found for this date. Choose another date.</p>
                ) : (
                  <>
                    <p role="status" className="mb-3 text-sm font-semibold text-ink">Available times · {slots.data?.data.timezone === INSTITUTION_TIME_ZONE ? INSTITUTION_TIME_ZONE_LABEL : slots.data?.data.timezone}</p>
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
                              "min-h-11 rounded-md border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus " +
                              (selected ? "border-brand bg-brand text-on-brand" : "border-border-strong bg-surface-raised text-ink hover:bg-surface-subtle")
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
            </PanelSection>
            <PanelFooter>
              <Button
                disabled={create.isPending || createdAppointment !== null || (hasInventoryRequirement && !inventoryAcknowledged)}
                onClick={() => void bookAppointment()}
                aria-busy={create.isPending}
              >
                {create.isPending ? "Booking…" : "Book appointment"}
              </Button>
              <p className="text-xs text-muted">This Appointment will be scheduled immediately after a successful booking.</p>
            </PanelFooter>
          </>
        ) : null}
      </Panel>

      {error ? <Notice role="alert" tone="danger" className="mt-4">{error}</Notice> : null}
      {createdAppointment ? (
        <Notice
          role="status"
          tone="success"
          className="mt-4"
          action={
            <Link
              href={`/portal/appointments/${createdAppointment.id}`}
              className="text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              View Appointment
            </Link>
          }
        >
          Appointment {createdAppointment.referenceCode} was scheduled.
        </Notice>
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
