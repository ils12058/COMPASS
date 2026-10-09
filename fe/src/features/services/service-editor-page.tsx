"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import {
  useState,
  type Dispatch,
  type FormEvent,
  type ReactNode,
  type SetStateAction,
} from "react";

import { ServiceHelp } from "@/features/services/service-help";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import {
  ServiceConsequenceSummary,
  ServicesDetailSkeleton,
  ServicesPageHeading,
  ServicesQueryError,
  serviceSchedulingConsequenceDetails,
  servicesErrorMessage,
  useServicesAction,
  type ServiceConsequenceChange,
  type ServiceSchedulingConsequenceDetails,
} from "@/features/services/services-shared";
import {
  counselingDeliveryOptions,
  counselingOnlineStatus,
} from "@/features/services/counseling-delivery";
import {
  ServiceProviderPicker,
  type SelectedCounselor,
} from "@/features/services/service-provider-picker";
import {
  DeliveryMode,
  ServiceProviderCoverage,
  type ServiceCreateRequest,
  type ServiceProvidersResponse,
  type ServiceResponse,
  type ServiceUpdateRequest,
} from "@/lib/api/generated/model";
import {
  getServicesGetProvidersQueryKey,
  getServicesGetQueryKey,
  getServicesListQueryKey,
  useServicesCreate,
  useServicesGet,
  useServicesGetProviders,
  useServicesUpdate,
} from "@/lib/api/generated/services/services";

type ServiceFormState = {
  code: string;
  name: string;
  description: string;
  bookingEnabled: boolean;
  defaultDuration: string;
  cancellationCutoff: string;
  requiresCurrentInventory: boolean;
  inPerson: boolean;
  online: boolean;
  providerCoverage: ServiceProviderCoverage;
  selectedCounselors: SelectedCounselor[];
};

function nullableInteger(value: string): number | null {
  const trimmed = value.trim();
  return trimmed ? Number.parseInt(trimmed, 10) : null;
}

function configuredDeliveryModes(values: ServiceFormState): DeliveryMode[] {
  const modes: DeliveryMode[] = [];
  if (values.inPerson) modes.push(DeliveryMode.IN_PERSON);
  if (values.online) modes.push(DeliveryMode.ONLINE);
  return modes;
}

function sameStringSet(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  const rightSet = new Set(right);
  return left.every((value) => rightSet.has(value));
}

function selectedIds(values: ServiceFormState): string[] {
  return values.providerCoverage === ServiceProviderCoverage.SELECTED_COUNSELORS
    ? values.selectedCounselors.map((item) => item.id)
    : [];
}

// What saving would send: Appointment-only settings count only while booking is on, and the
// selected Counselors only with selected coverage. The draft is unsaved when this differs from the
// saved Service.
function savedShape(values: ServiceFormState) {
  return {
    code: values.code,
    name: values.name,
    description: values.description,
    bookingEnabled: values.bookingEnabled,
    defaultDuration: values.bookingEnabled ? values.defaultDuration.trim() : "",
    cancellationCutoff: values.bookingEnabled ? values.cancellationCutoff.trim() : "",
    requiresCurrentInventory: values.bookingEnabled && values.requiresCurrentInventory,
    deliveryModes: configuredDeliveryModes(values),
    providerCoverage: values.providerCoverage,
    selectedCounselorIds: [...selectedIds(values)].sort(),
  };
}

function serviceFormChanged(values: ServiceFormState, saved: ServiceFormState): boolean {
  return JSON.stringify(savedShape(values)) !== JSON.stringify(savedShape(saved));
}

function initialFromService(
  service: ServiceResponse,
  providers: ServiceProvidersResponse,
): ServiceFormState {
  return {
    code: service.code,
    name: service.name,
    description: service.description,
    bookingEnabled: service.appointment_booking_enabled,
    defaultDuration:
      service.default_appointment_duration_minutes === null
        ? ""
        : String(service.default_appointment_duration_minutes),
    cancellationCutoff:
      service.cancellation_cutoff_minutes === null
        ? ""
        : String(service.cancellation_cutoff_minutes),
    requiresCurrentInventory: service.requires_current_inventory,
    inPerson: service.delivery_modes.includes(DeliveryMode.IN_PERSON),
    online: service.delivery_modes.includes(DeliveryMode.ONLINE),
    providerCoverage: service.provider_coverage,
    selectedCounselors: providers.counselors.map((item) => ({
      id: item.id,
      displayName: item.display_name,
      isActive: item.is_active,
    })),
  };
}

function ChoiceRadio({
  name,
  checked,
  onSelect,
  label,
  description,
}: {
  name: string;
  checked: boolean;
  onSelect: () => void;
  label: string;
  description?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-sm border border-border px-3 py-2.5 has-[:checked]:border-brand has-[:checked]:bg-brand-wash">
      <input
        type="radio"
        name={name}
        className="mt-1 h-4 w-4 accent-brand"
        checked={checked}
        onChange={onSelect}
      />
      <span>
        <span className="block text-sm font-semibold text-ink">{label}</span>
        {description ? <span className="mt-0.5 block text-sm leading-6 text-muted">{description}</span> : null}
      </span>
    </label>
  );
}

// Canonical Counseling explains what each mode permits before either box is toggled. ONLINE is
// the delivery mode; E-Counseling is what its scheduled Appointments use.
function CounselingDeliveryFieldset({
  values,
  setValues,
}: {
  values: ServiceFormState;
  setValues: Dispatch<SetStateAction<ServiceFormState>>;
}) {
  return (
    <fieldset
      className="mt-4"
      aria-describedby="counseling-delivery-help counseling-delivery-status"
    >
      {/* The section heading already says "Counseling delivery"; the legend still names the group. */}
      <legend className="sr-only">Counseling delivery modes</legend>
      <p id="counseling-delivery-help" className="max-w-3xl text-xs leading-5 text-muted">
        Choose at least one delivery mode.
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {counselingDeliveryOptions.map((option) => {
          const field = option.mode === DeliveryMode.ONLINE ? "online" : "inPerson";
          const id = "counseling-delivery-" + field;
          return (
            <div
              key={option.mode}
              className="flex items-start gap-3 rounded-sm border border-border px-3 py-2.5 has-[:checked]:border-brand has-[:checked]:bg-brand-wash"
            >
              <input
                id={id}
                type="checkbox"
                className="mt-1 h-4 w-4 shrink-0 accent-brand"
                checked={values[field]}
                aria-describedby={id + "-description"}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field]: event.target.checked }))
                }
              />
              <span>
                <label htmlFor={id} className="block cursor-pointer text-sm font-semibold text-ink">
                  {option.label}
                </label>
                <span id={id + "-description"} className="mt-0.5 block text-xs leading-5 text-muted">
                  {option.description}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <p
        id="counseling-delivery-status"
        role="status"
        className="mt-3 max-w-3xl text-sm leading-6 text-ink"
      >
        {counselingOnlineStatus({
          inPerson: values.inPerson,
          online: values.online,
          bookingEnabled: values.bookingEnabled,
        })}
      </p>
    </fieldset>
  );
}

function ServiceForm({
  initial,
  active,
  systemRequired = false,
  submitting,
  submitLabel,
  pendingLabel,
  messages,
  codeReadOnly = false,
  saveUnavailable = false,
  onSubmit,
}: {
  // The saved Service. The form keeps its own draft and compares it with this.
  initial: ServiceFormState;
  active: boolean;
  systemRequired?: boolean;
  submitting: boolean;
  submitLabel: string;
  pendingLabel: string;
  messages: ReactNode;
  codeReadOnly?: boolean;
  // Set while the saved Service could not be confirmed; the draft stays editable.
  saveUnavailable?: boolean;
  onSubmit: (values: ServiceFormState) => Promise<void>;
}) {
  const [values, setValues] = useState(initial);
  const bookingClearsSavedSettings = initial.bookingEnabled && !values.bookingEnabled;
  useUnsavedChangesGuard({
    dirty: serviceFormChanged(values, initial),
    message: "Discard your unsaved Service changes?",
  });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveUnavailable) return;
    await onSubmit(values);
  }

  function setBooking(enabled: boolean) {
    // Appointment-only settings exist only while booking is available.
    setValues((current) => ({
      ...current,
      bookingEnabled: enabled,
      ...(enabled
        ? {}
        : { defaultDuration: "", cancellationCutoff: "", requiresCurrentInventory: false }),
    }));
  }

  return (
    <form className="mt-5" onSubmit={submit}>
      <Panel as="div">
      <PanelSection title="Service identity" titleId="service-identity-heading">
        <div className="mt-4 grid gap-5 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="service-code">Service code</Label>
            <Input
              id="service-code"
              required
              maxLength={64}
              readOnly={codeReadOnly}
              value={values.code}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  code: event.target.value,
                }))
              }
            />
            <p className="text-xs leading-5 text-muted">
              The code cannot be changed after creation.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="service-name">Name</Label>
            <Input
              id="service-name"
              required
              maxLength={160}
              value={values.name}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  name: event.target.value,
                }))
              }
            />
          </div>
        </div>
        <div className="mt-5 grid gap-2">
          <Label htmlFor="service-description">Description</Label>
          <Textarea
            id="service-description"
            maxLength={2000}
            rows={5}
            value={values.description}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
          />
        </div>
      </PanelSection>

      <PanelSection
        title={systemRequired ? "Counseling delivery" : "Service delivery"}
        titleId="service-delivery-heading"
      >
        {systemRequired ? (
          <CounselingDeliveryFieldset values={values} setValues={setValues} />
        ) : (
          <fieldset className="mt-4" aria-describedby="service-delivery-help">
            <legend className="text-sm font-semibold text-ink">
              Supported delivery modes
            </legend>
            <div className="mt-3 flex flex-wrap gap-x-6 gap-y-3">
              <label className="inline-flex min-h-10 items-center gap-3 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={values.inPerson}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      inPerson: event.target.checked,
                    }))
                  }
                />
                In person
              </label>
              <label className="inline-flex min-h-10 items-center gap-3 text-sm text-ink">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-brand"
                  checked={values.online}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      online: event.target.checked,
                    }))
                  }
                />
                Online
              </label>
            </div>
            <p id="service-delivery-help" className="mt-2 text-xs leading-5 text-muted">
              Choose at least one delivery mode before enabling this Service.
            </p>
          </fieldset>
        )}
        {(initial.inPerson && !values.inPerson) || (initial.online && !values.online) ? (
          <p role="status" className="mt-3 text-sm text-warning">Saving stops new work in the removed delivery mode. Existing Appointments keep their saved mode.</p>
        ) : null}
      </PanelSection>

      <PanelSection title="Appointment booking" titleId="service-appointment-heading">
        <fieldset className="mt-4">
          <legend className="sr-only">Appointment booking</legend>
          <div className="grid gap-3 md:grid-cols-2">
            <ChoiceRadio
              name="service-booking"
              checked={!values.bookingEnabled}
              onSelect={() => setBooking(false)}
              label="Not available"
            />
            <ChoiceRadio
              name="service-booking"
              checked={values.bookingEnabled}
              onSelect={() => setBooking(true)}
              label="Available"
            />
          </div>
        </fieldset>
        {bookingClearsSavedSettings ? (
          <p className="mt-3 max-w-3xl text-xs leading-5 text-muted">
            Saving clears this Service&rsquo;s Appointment duration, cutoff, and Inventory
            requirement. Existing Appointments keep their saved timing and cutoff.
          </p>
        ) : null}
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="service-default-duration">
              Duration (minutes)
            </Label>
            <Input
              id="service-default-duration"
              type="number"
              inputMode="numeric"
              min={1}
              max={480}
              step={1}
              disabled={!values.bookingEnabled}
              required={active && values.bookingEnabled}
              value={values.defaultDuration}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  defaultDuration: event.target.value,
                }))
              }
            />
            <p className="text-xs leading-5 text-muted">
              1–480 minutes. Required for booking.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="service-cancellation-cutoff">
              Cancellation/rescheduling cutoff (minutes)
            </Label>
            <Input
              id="service-cancellation-cutoff"
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              disabled={!values.bookingEnabled}
              value={values.cancellationCutoff}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  cancellationCutoff: event.target.value,
                }))
              }
            />
            <p className="text-xs leading-5 text-muted">
              Optional. Student self-service changes stop this many minutes before the
              Appointment.
            </p>
          </div>
        </div>
        <label className="mt-5 flex max-w-3xl items-start gap-3 text-sm leading-6 text-ink">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 shrink-0 accent-brand"
            disabled={!values.bookingEnabled}
            checked={values.requiresCurrentInventory}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                requiresCurrentInventory: event.target.checked,
              }))
            }
          />
          <span>
            Require a submitted current Individual Inventory
          </span>
        </label>
      </PanelSection>

      <PanelSection title="Provider coverage" titleId="service-provider-heading">
        <dl className="mt-4">
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Provider type</dt>
          <dd className="mt-1 text-sm text-ink">Counselor</dd>
        </dl>
        <fieldset className="mt-5">
          <legend className="text-sm font-semibold text-ink">Who may provide this Service?</legend>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <ChoiceRadio
              name="service-coverage"
              checked={values.providerCoverage === ServiceProviderCoverage.ALL_COUNSELORS}
              onSelect={() =>
                setValues((current) => ({
                  ...current,
                  providerCoverage: ServiceProviderCoverage.ALL_COUNSELORS,
                }))
              }
              label="All active Counselors"
            />
            <ChoiceRadio
              name="service-coverage"
              checked={values.providerCoverage === ServiceProviderCoverage.SELECTED_COUNSELORS}
              onSelect={() =>
                setValues((current) => ({
                  ...current,
                  providerCoverage: ServiceProviderCoverage.SELECTED_COUNSELORS,
                }))
              }
              label="Selected Counselors"
            />
          </div>
        </fieldset>
        {values.providerCoverage === ServiceProviderCoverage.SELECTED_COUNSELORS ? (
          <>
            <ServiceProviderPicker
              selected={values.selectedCounselors}
              disabled={submitting}
              onChange={(next) =>
                setValues((current) => ({ ...current, selectedCounselors: next }))
              }
            />
          </>
        ) : null}
      </PanelSection>

      {/* Messages render nothing until there is an error or a notice. */}
      <div className="px-4 empty:hidden sm:px-5 [&>p:last-child]:mb-4">{messages}</div>

      <PanelFooter className="justify-end">
        <Button type="submit" disabled={submitting || saveUnavailable}>
          {submitting ? pendingLabel : submitLabel}
        </Button>
      </PanelFooter>
      </Panel>
    </form>
  );
}

const emptyCreateState: ServiceFormState = {
  code: "",
  name: "",
  description: "",
  bookingEnabled: false,
  defaultDuration: "",
  cancellationCutoff: "",
  requiresCurrentInventory: false,
  inPerson: false,
  online: false,
  providerCoverage: ServiceProviderCoverage.ALL_COUNSELORS,
  selectedCounselors: [],
};

export function CreateServicePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = useServicesCreate();
  const action = useServicesAction();

  async function submit(values: ServiceFormState) {
    const data: ServiceCreateRequest = {
      code: values.code,
      name: values.name,
      description: values.description,
      appointment_booking_enabled: values.bookingEnabled,
      default_appointment_duration_minutes: values.bookingEnabled
        ? nullableInteger(values.defaultDuration)
        : null,
      cancellation_cutoff_minutes: values.bookingEnabled
        ? nullableInteger(values.cancellationCutoff)
        : null,
      requires_current_inventory: values.bookingEnabled && values.requiresCurrentInventory,
      delivery_modes: configuredDeliveryModes(values),
      provider_coverage: values.providerCoverage,
      selected_counselor_ids: selectedIds(values),
    };
    const response = await action.run(
      () => create.mutateAsync({ data }),
      "The Service could not be created.",
    );
    if (!response) return;
    await queryClient.invalidateQueries({
      queryKey: getServicesListQueryKey(),
    });
    router.push("/portal/services/" + response.data.id + "?created=true");
  }

  return (
    <section>
      <ServicesPageHeading
        title="Create Service"
        backHref="/portal/services"
        backLabel="Services"
        description="New Services start inactive."
        help={<ServiceHelp />}
      />
      <ServiceForm
        initial={emptyCreateState}
        active={false}
        submitting={create.isPending}
        submitLabel="Create Service"
        pendingLabel="Creating…"
        messages={action.messages}
        onSubmit={submit}
      />
      {action.stepUpDialog}

    </section>
  );
}

type PendingServiceConsequenceReview = {
  changes: ServiceUpdateRequest;
  details: ServiceSchedulingConsequenceDetails | null;
};

function reviewedChange(
  service: ServiceResponse,
  changes: ServiceUpdateRequest,
): ServiceConsequenceChange {
  const nextModes = changes.delivery_modes;
  return {
    counselingOnlineRemoved:
      service.is_system_required &&
      service.delivery_modes.includes(DeliveryMode.ONLINE) &&
      Array.isArray(nextModes) &&
      !nextModes.includes(DeliveryMode.ONLINE),
    bookingTurnedOff:
      service.appointment_booking_enabled && changes.appointment_booking_enabled === false,
  };
}

export function EditServicePage() {
  const params = useParams<{ serviceId: string }>();
  const serviceId = params.serviceId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const detail = useServicesGet(serviceId, {
    query: { retry: false },
  });
  const providers = useServicesGetProviders(serviceId, {
    query: { retry: false },
  });
  const update = useServicesUpdate();
  const action = useServicesAction();
  const [review, setReview] =
    useState<PendingServiceConsequenceReview | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // A refresh that fails for a transient reason keeps the editor, and the unsaved draft, on the last
  // confirmed Service. A refusal, a missing Service, or a first load that fails replaces it.
  const detailData = safeQueryData(detail);
  const providersData = safeQueryData(providers);
  if (detail.isPending || providers.isPending) return <ServicesDetailSkeleton />;

  if (!detailData || !providersData) {
    return (
      <ServicesQueryError
        error={detailData ? providers.error : detail.error}
        fallback="The Service could not be loaded."
        onRetry={() => {
          void detail.refetch();
          void providers.refetch();
        }}
      />
    );
  }

  const refreshFailed = detail.isError || providers.isError;
  const service = detailData.data;
  const savedProviders = providersData.data;
  const initial = initialFromService(service, savedProviders);

  async function submit(values: ServiceFormState) {
    const changes: ServiceUpdateRequest = {};
    const nextDuration = values.bookingEnabled ? nullableInteger(values.defaultDuration) : null;
    const nextCutoff = values.bookingEnabled ? nullableInteger(values.cancellationCutoff) : null;
    const nextRequirement = values.bookingEnabled && values.requiresCurrentInventory;
    const nextModes = configuredDeliveryModes(values);
    const nextSelected = selectedIds(values);

    if (values.name !== service.name) changes.name = values.name;
    if (values.description !== service.description) {
      changes.description = values.description;
    }
    if (values.bookingEnabled !== service.appointment_booking_enabled) {
      changes.appointment_booking_enabled = values.bookingEnabled;
    }
    // Turning booking off clears Appointment-only settings on the server.
    if (values.bookingEnabled) {
      if (nextDuration !== service.default_appointment_duration_minutes) {
        changes.default_appointment_duration_minutes = nextDuration;
      }
      if (nextCutoff !== service.cancellation_cutoff_minutes) {
        changes.cancellation_cutoff_minutes = nextCutoff;
      }
      if (nextRequirement !== service.requires_current_inventory) {
        changes.requires_current_inventory = nextRequirement;
      }
    }
    if (!sameStringSet(nextModes, service.delivery_modes)) {
      changes.delivery_modes = nextModes;
    }
    if (
      values.providerCoverage !== savedProviders.provider_coverage ||
      !sameStringSet(
        nextSelected,
        savedProviders.provider_coverage === ServiceProviderCoverage.SELECTED_COUNSELORS
          ? savedProviders.counselors.map((item) => item.id)
          : [],
      )
    ) {
      changes.provider_coverage = values.providerCoverage;
      changes.selected_counselor_ids = nextSelected;
    }

    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }

    const response = await action.run(
      () => update.mutateAsync({ serviceId, data: changes }),
      "The Service could not be updated.",
      {
        onError: (caught, code) => {
          if (code !== "service_scheduling_consequence_review_required") {
            return false;
          }
          setReview({
            changes,
            details: serviceSchedulingConsequenceDetails(caught),
          });
          setReviewError(null);
          return true;
        },
      },
    );
    if (!response) return;
    await finishUpdate();
  }

  async function finishUpdate() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getServicesGetQueryKey(serviceId),
      }),
      queryClient.invalidateQueries({
        queryKey: getServicesGetProvidersQueryKey(serviceId),
      }),
      queryClient.invalidateQueries({
        queryKey: getServicesListQueryKey(),
      }),
    ]);
    router.push("/portal/services/" + serviceId + "?updated=true");
  }

  async function confirmConsequenceReview() {
    if (!review) return;
    setReviewError(null);
    const pendingReview = review;
    const response = await action.run(
      () =>
        update.mutateAsync({
          serviceId,
          data: {
            ...pendingReview.changes,
            acknowledge_scheduling_consequences: true,
          },
        }),
      "The Service could not be updated.",
      {
        onStepUpRequired: () => setReview(null),
        onStepUpVerified: () => setReview(pendingReview),
        onError: (caught, code) => {
          if (code === "service_scheduling_consequence_review_required") {
            setReview({
              changes: pendingReview.changes,
              details: serviceSchedulingConsequenceDetails(caught),
            });
            setReviewError(null);
            return true;
          }
          setReviewError(
            servicesErrorMessage(caught, "The Service could not be updated."),
          );
          return true;
        },
      },
    );
    if (!response) return;
    setReview(null);
    await finishUpdate();
  }

  return (
    <section>
      <ServicesPageHeading
        title={"Edit " + service.name}
        help={<ServiceHelp counseling={service.is_system_required} />}
        backHref={"/portal/services/" + serviceId}
        backLabel="Service detail"
      >
        <p className="mt-1.5 font-mono text-xs text-muted">{service.code}</p>
      </ServicesPageHeading>
      {refreshFailed ? (
        <RefreshFailureNotice
          message="The latest Service details could not be refreshed. Your changes are kept here, and you can save them once the details refresh."
          retrying={detail.isFetching || providers.isFetching}
          onRetry={() => {
            if (detail.isError) void detail.refetch();
            if (providers.isError) void providers.refetch();
          }}
        />
      ) : null}
      <ServiceForm
        initial={initial}
        active={service.is_active}
        systemRequired={service.is_system_required}
        submitting={update.isPending}
        submitLabel="Save changes"
        pendingLabel="Saving…"
        messages={action.messages}
        codeReadOnly
        saveUnavailable={refreshFailed}
        onSubmit={submit}
      />
      <ConsequentialActionDialog
        open={review !== null}
        title="Review Service scheduling consequences"
        confirmLabel="Save Service changes"
        pendingLabel="Saving…"
        pending={update.isPending}
        error={reviewError}
        onOpenChange={(open) => {
          if (!open) {
            setReview(null);
            setReviewError(null);
          }
        }}
        onConfirm={() => void confirmConsequenceReview()}
      >
        <p>Review what this Service change means before saving it.</p>
        <ServiceConsequenceSummary
          details={review?.details ?? null}
          change={review ? reviewedChange(service, review.changes) : undefined}
        />
      </ConsequentialActionDialog>
      {action.stepUpDialog}
    </section>
  );
}
