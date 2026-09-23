"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ServicesDetailSkeleton,
  ServicesPageHeading,
  ServicesQueryError,
  servicesSelectClass,
  useServicesAction,
} from "@/features/services/services-shared";
import {
  AppointmentPolicy,
  ConfigurableProviderRoleCode,
  DeliveryMode,
  ProviderRoleCode,
  type ServiceCreateRequest,
  type ServiceResponse,
  type ServiceUpdateRequest,
} from "@/lib/api/generated/model";
import {
  getServicesGetQueryKey,
  getServicesListQueryKey,
  useServicesCreate,
  useServicesGet,
  useServicesUpdate,
} from "@/lib/api/generated/services/services";

type ServiceFormState = {
  code: string;
  name: string;
  description: string;
  appointmentPolicy: AppointmentPolicy;
  defaultDuration: string;
  cancellationCutoff: string;
  requiresCurrentInventory: boolean;
  inPerson: boolean;
  online: boolean;
  counselor: boolean;
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

function initialFromService(service: ServiceResponse): ServiceFormState {
  return {
    code: service.code,
    name: service.name,
    description: service.description,
    appointmentPolicy: service.appointment_policy,
    defaultDuration:
      service.default_duration_minutes === null
        ? ""
        : String(service.default_duration_minutes),
    cancellationCutoff:
      service.cancellation_cutoff_minutes === null
        ? ""
        : String(service.cancellation_cutoff_minutes),
    requiresCurrentInventory: service.requires_current_inventory,
    inPerson: service.delivery_modes.includes(DeliveryMode.IN_PERSON),
    online: service.delivery_modes.includes(DeliveryMode.ONLINE),
    counselor: service.provider_roles.includes(ProviderRoleCode.COUNSELOR),
  };
}

function ServiceForm({
  initial,
  active,
  legacyProviderAssignment = false,
  submitting,
  submitLabel,
  pendingLabel,
  messages,
  codeReadOnly = false,
  onSubmit,
}: {
  initial: ServiceFormState;
  active: boolean;
  legacyProviderAssignment?: boolean;
  submitting: boolean;
  submitLabel: string;
  pendingLabel: string;
  messages: ReactNode;
  codeReadOnly?: boolean;
  onSubmit: (values: ServiceFormState) => Promise<void>;
}) {
  const [values, setValues] = useState(initial);
  const appointmentEnabled =
    values.appointmentPolicy !== AppointmentPolicy.NONE;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(values);
  }

  function setPolicy(next: AppointmentPolicy) {
    setValues((current) => ({
      ...current,
      appointmentPolicy: next,
      cancellationCutoff:
        next === AppointmentPolicy.NONE ? "" : current.cancellationCutoff,
    }));
  }

  return (
    <form className="mt-8 space-y-9" onSubmit={submit}>
      <section aria-labelledby="service-identity-heading">
        <h2
          id="service-identity-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Service identity
        </h2>
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
              The Service code is a stable system identifier and cannot be
              changed after creation.
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
          <textarea
            id="service-description"
            maxLength={2000}
            rows={5}
            className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm leading-6 text-ink outline-none placeholder:text-muted focus:border-focus focus:ring-2 focus:ring-focus/25"
            value={values.description}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                description: event.target.value,
              }))
            }
          />
        </div>
      </section>

      <section
        aria-labelledby="service-delivery-heading"
        className="border-t border-border pt-8"
      >
        <h2
          id="service-delivery-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Service delivery
        </h2>
        <fieldset className="mt-4">
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
          <p className="mt-2 text-xs leading-5 text-muted">
            An active Service requires at least one delivery mode.
          </p>
        </fieldset>
      </section>

      <section
        aria-labelledby="service-appointment-heading"
        className="border-t border-border pt-8"
      >
        <h2
          id="service-appointment-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Appointment settings
        </h2>
        <div className="mt-4 grid gap-5 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="service-appointment-policy">
              Appointment policy
            </Label>
            <select
              id="service-appointment-policy"
              className={servicesSelectClass}
              value={values.appointmentPolicy}
              onChange={(event) =>
                setPolicy(event.target.value as AppointmentPolicy)
              }
            >
              <option value={AppointmentPolicy.NONE}>No appointment</option>
              <option value={AppointmentPolicy.OPTIONAL}>
                Appointment optional
              </option>
              <option value={AppointmentPolicy.REQUIRED}>
                Appointment required
              </option>
            </select>
            <p className="text-xs leading-5 text-muted">
              Optional and required are both schedulable under the current
              backend contract. No additional workflow distinction is applied
              here.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="service-default-duration">
              Default appointment duration
            </Label>
            <Input
              id="service-default-duration"
              type="number"
              inputMode="numeric"
              min={1}
              max={480}
              step={1}
              required={
                active &&
                values.appointmentPolicy !== AppointmentPolicy.NONE
              }
              value={values.defaultDuration}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  defaultDuration: event.target.value,
                }))
              }
            />
            <p className="text-xs leading-5 text-muted">
              1–480 minutes when configured. Active optional or required
              Services need a default duration.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="service-cancellation-cutoff">
              Student cancellation/rescheduling cutoff
            </Label>
            <Input
              id="service-cancellation-cutoff"
              type="number"
              inputMode="numeric"
              min={0}
              step={1}
              disabled={!appointmentEnabled}
              value={values.cancellationCutoff}
              onChange={(event) =>
                setValues((current) => ({
                  ...current,
                  cancellationCutoff: event.target.value,
                }))
              }
            />
            <p className="text-xs leading-5 text-muted">
              Minutes before the Appointment when Student self-service changes
              stop. No appointment policy clears this value.
            </p>
          </div>
        </div>
        <p className="mt-4 max-w-3xl text-xs leading-5 text-muted">
          Scheduling changes apply to future Appointments; existing
          Appointments retain their saved timing and cancellation cutoff.
        </p>
      </section>

      <section
        aria-labelledby="service-requirements-heading"
        className="border-t border-border pt-8"
      >
        <h2
          id="service-requirements-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Student requirements
        </h2>
        <label className="mt-4 flex max-w-3xl items-start gap-3 text-sm leading-6 text-ink">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 shrink-0 accent-brand"
            checked={values.requiresCurrentInventory}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                requiresCurrentInventory: event.target.checked,
              }))
            }
          />
          <span>
            Require a submitted current Individual Inventory before appointment
            booking
          </span>
        </label>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
          This requirement is preserved even when appointment policy is No
          appointment; COMPASS does not invent an incompatibility the backend
          does not enforce.
        </p>
      </section>

      <section
        aria-labelledby="service-provider-heading"
        className="border-t border-border pt-8"
      >
        <h2
          id="service-provider-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Provider eligibility
        </h2>
        <label className="mt-4 inline-flex min-h-10 items-center gap-3 text-sm text-ink">
          <input
            type="checkbox"
            className="h-4 w-4 accent-brand"
            checked={values.counselor}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                counselor: event.target.checked,
              }))
            }
          />
          Counselor
        </label>
        <p className="mt-2 max-w-3xl text-xs leading-5 text-muted">
          Provider eligibility is role-level configuration. It does not assign
          specific Counselors or define their availability.
        </p>
        {legacyProviderAssignment ? (
          <p className="mt-3 max-w-3xl border-l-2 border-warning pl-3 text-xs leading-5 text-muted">
            This Service has a historical Guidance Services Staff provider
            assignment. It remains readable for compatibility but is not
            selectable for current provider configuration. Unrelated edits
            leave that historical assignment untouched.
          </p>
        ) : null}
      </section>

      {messages}

      <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-6">
        <Button type="submit" disabled={submitting}>
          {submitting ? pendingLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}

const emptyCreateState: ServiceFormState = {
  code: "",
  name: "",
  description: "",
  appointmentPolicy: AppointmentPolicy.NONE,
  defaultDuration: "",
  cancellationCutoff: "",
  requiresCurrentInventory: false,
  inPerson: false,
  online: false,
  counselor: false,
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
      appointment_policy: values.appointmentPolicy,
      default_duration_minutes: nullableInteger(values.defaultDuration),
      cancellation_cutoff_minutes: nullableInteger(values.cancellationCutoff),
      requires_current_inventory: values.requiresCurrentInventory,
      delivery_modes: configuredDeliveryModes(values),
      provider_roles: values.counselor
        ? [ConfigurableProviderRoleCode.COUNSELOR]
        : [],
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
      />
      <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
        New Services are created inactive. Review the configuration on the
        Service detail page, then enable it separately when ready.
      </p>
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

export function EditServicePage() {
  const params = useParams<{ serviceId: string }>();
  const serviceId = params.serviceId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const detail = useServicesGet(serviceId, {
    query: { retry: false },
  });
  const update = useServicesUpdate();
  const action = useServicesAction();

  if (detail.isPending) return <ServicesDetailSkeleton />;

  if (detail.isError) {
    return (
      <ServicesQueryError
        error={detail.error}
        fallback="The Service could not be loaded."
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const service = detail.data.data;
  const initial = initialFromService(service);
  const hasLegacyProvider = service.provider_roles.includes(
    ProviderRoleCode.GUIDANCE_SERVICES_STAFF,
  );

  async function submit(values: ServiceFormState) {
    const changes: ServiceUpdateRequest = {};
    const nextDuration = nullableInteger(values.defaultDuration);
    const nextCutoff = nullableInteger(values.cancellationCutoff);
    const nextModes = configuredDeliveryModes(values);
    const hadCounselor = service.provider_roles.includes(
      ProviderRoleCode.COUNSELOR,
    );

    if (values.name !== service.name) changes.name = values.name;
    if (values.description !== service.description) {
      changes.description = values.description;
    }
    if (values.appointmentPolicy !== service.appointment_policy) {
      changes.appointment_policy = values.appointmentPolicy;
    }
    if (nextDuration !== service.default_duration_minutes) {
      changes.default_duration_minutes = nextDuration;
    }
    if (nextCutoff !== service.cancellation_cutoff_minutes) {
      changes.cancellation_cutoff_minutes = nextCutoff;
    }
    if (
      values.requiresCurrentInventory !== service.requires_current_inventory
    ) {
      changes.requires_current_inventory = values.requiresCurrentInventory;
    }
    if (!sameStringSet(nextModes, service.delivery_modes)) {
      changes.delivery_modes = nextModes;
    }
    if (values.counselor !== hadCounselor) {
      changes.provider_roles = values.counselor
        ? [ConfigurableProviderRoleCode.COUNSELOR]
        : [];
    }

    if (Object.keys(changes).length === 0) {
      action.setError(null);
      action.setNotice("No changes to save.");
      return;
    }

    const response = await action.run(
      () => update.mutateAsync({ serviceId, data: changes }),
      "The Service could not be updated.",
    );
    if (!response) return;

    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getServicesGetQueryKey(serviceId),
      }),
      queryClient.invalidateQueries({
        queryKey: getServicesListQueryKey(),
      }),
    ]);
    router.push("/portal/services/" + serviceId + "?updated=true");
  }

  return (
    <section>
      <ServicesPageHeading
        title={"Edit " + service.name}
        backHref={"/portal/services/" + serviceId}
        backLabel="Service detail"
      />
      <p className="mt-3 font-mono text-xs text-muted">{service.code}</p>
      <ServiceForm
        initial={initial}
        active={service.is_active}
        legacyProviderAssignment={hasLegacyProvider}
        submitting={update.isPending}
        submitLabel="Save changes"
        pendingLabel="Saving…"
        messages={action.messages}
        codeReadOnly
        onSubmit={submit}
      />
      {action.stepUpDialog}
    </section>
  );
}
