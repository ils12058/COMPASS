"use client";

import { FormEvent, useState } from "react";
import { LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  AppointmentPolicy,
  ConfigurableProviderRoleCode,
  DeliveryMode,
  ProviderRoleCode,
  ServiceResponse,
} from "@/lib/api/generated/model";
import {
  AppointmentPolicy as AppointmentPolicyValues,
  ConfigurableProviderRoleCode as ConfigurableProviderRoleCodeValues,
  DeliveryMode as DeliveryModeValues,
} from "@/lib/api/generated/model";
import { formatServiceValue, serviceSelectClassName } from "@/features/portal/admin/services/portal-it-admin-services-shared";

export type ServiceFormValues = {
  appointmentPolicy: AppointmentPolicy;
  cancellationCutoffMinutes: string;
  code: string;
  defaultDurationMinutes: string;
  deliveryModes: DeliveryMode[];
  description: string;
  legacyProviderRoles: ProviderRoleCode[];
  name: string;
  providerRoles: ConfigurableProviderRoleCode[];
  providerRolesTouched: boolean;
  requiresCurrentInventory: boolean;
};

export const EMPTY_SERVICE_FORM: ServiceFormValues = {
  appointmentPolicy: AppointmentPolicyValues.NONE,
  cancellationCutoffMinutes: "",
  code: "",
  defaultDurationMinutes: "",
  deliveryModes: [],
  description: "",
  legacyProviderRoles: [],
  name: "",
  providerRoles: [],
  providerRolesTouched: false,
  requiresCurrentInventory: false,
};

export function serviceToFormValues(service: ServiceResponse): ServiceFormValues {
  const legacyProviderRoles = service.provider_roles.filter(
    (role) => role !== ConfigurableProviderRoleCodeValues.COUNSELOR,
  );

  return {
    appointmentPolicy: service.appointment_policy,
    cancellationCutoffMinutes: service.cancellation_cutoff_minutes?.toString() ?? "",
    code: service.code,
    defaultDurationMinutes: service.default_duration_minutes?.toString() ?? "",
    deliveryModes: service.delivery_modes,
    description: service.description,
    legacyProviderRoles,
    name: service.name,
    providerRoles: service.provider_roles.filter(
      (role): role is ConfigurableProviderRoleCode =>
        role === ConfigurableProviderRoleCodeValues.COUNSELOR,
    ),
    providerRolesTouched: false,
    requiresCurrentInventory: service.requires_current_inventory,
  };
}

function toggleValue<T extends string>(values: T[], value: T) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

export function PortalItAdminServiceForm({
  initialValues,
  isSubmitting,
  mode,
  onCancel,
  onSubmit,
}: {
  initialValues: ServiceFormValues;
  isSubmitting: boolean;
  mode: "create" | "edit";
  onCancel?: () => void;
  onSubmit: (values: ServiceFormValues) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState(initialValues);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(draft);
  }

  return (
    <form className="space-y-6" onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="service-code">Service code</Label>
          <Input
            id="service-code"
            className="mt-2 h-10"
            disabled={mode === "edit"}
            maxLength={80}
            placeholder="e.g. CAREER_COUNSELING"
            required
            value={draft.code}
            onChange={(event) =>
              setDraft((current) => ({ ...current, code: event.target.value }))
            }
          />
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            {mode === "edit"
              ? "The code identifies this service and cannot be changed here."
              : "Use a stable code that staff can recognize later."}
          </p>
        </div>
        <div>
          <Label htmlFor="service-name">Service name</Label>
          <Input
            id="service-name"
            className="mt-2 h-10"
            maxLength={160}
            placeholder="Career counseling"
            required
            value={draft.name}
            onChange={(event) =>
              setDraft((current) => ({ ...current, name: event.target.value }))
            }
          />
        </div>
      </div>

      <div>
        <Label htmlFor="service-description">Description</Label>
        <Textarea
          id="service-description"
          className="mt-2 min-h-28"
          maxLength={1000}
          placeholder="Explain what this service helps with."
          value={draft.description}
          onChange={(event) =>
            setDraft((current) => ({ ...current, description: event.target.value }))
          }
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="service-appointment-policy">Appointment policy</Label>
          <select
            id="service-appointment-policy"
            className={`${serviceSelectClassName} mt-2`}
            value={draft.appointmentPolicy}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                appointmentPolicy: event.target.value as AppointmentPolicy,
              }))
            }
          >
            {Object.values(AppointmentPolicyValues).map((policy) => (
              <option key={policy} value={policy}>
                {formatServiceValue(policy)}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Choose whether a request needs an appointment.
          </p>
        </div>
        <div>
          <Label htmlFor="service-default-duration">Default duration (minutes)</Label>
          <Input
            id="service-default-duration"
            className="mt-2 h-10"
            min={1}
            placeholder="60"
            step={1}
            type="number"
            value={draft.defaultDurationMinutes}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                defaultDurationMinutes: event.target.value,
              }))
            }
          />
        </div>
        <div>
          <Label htmlFor="service-cancellation-cutoff">
            Cancellation cutoff (minutes)
          </Label>
          <Input
            id="service-cancellation-cutoff"
            className="mt-2 h-10"
            min={0}
            placeholder="Optional"
            step={1}
            type="number"
            value={draft.cancellationCutoffMinutes}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                cancellationCutoffMinutes: event.target.value,
              }))
            }
          />
        </div>
      </div>

      <fieldset>
        <legend className="text-sm font-semibold">Delivery modes</legend>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Tell people how this service can be provided.
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {Object.values(DeliveryModeValues).map((modeValue) => {
            const checked = draft.deliveryModes.includes(modeValue);

            return (
              <label
                key={modeValue}
                className="flex cursor-pointer items-start gap-3 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4"
              >
                <input
                  className="mt-1 size-4 accent-[var(--compass-brand-maroon)]"
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    setDraft((current) => ({
                      ...current,
                      deliveryModes: toggleValue(current.deliveryModes, modeValue),
                    }))
                  }
                />
                <span>
                  <span className="block text-sm font-semibold">
                    {formatServiceValue(modeValue)}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                    {modeValue === DeliveryModeValues.IN_PERSON
                      ? "A face-to-face appointment or office visit."
                      : "A session or interaction held online."}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-sm font-semibold">Provider options</legend>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Choose which provider role can handle this service.
        </p>
        {draft.legacyProviderRoles.length ? (
          <p className="mt-3 rounded-2xl border border-[var(--compass-brand-gold)]/30 bg-[var(--compass-brand-gold)]/10 p-3 text-sm leading-6 text-[var(--compass-brand-maroon)]">
            This service already has an older provider setting. It will be kept unless you change the provider option below.
          </p>
        ) : null}
        <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
          <input
            className="mt-1 size-4 accent-[var(--compass-brand-maroon)]"
            type="checkbox"
            checked={draft.providerRoles.includes(
              ConfigurableProviderRoleCodeValues.COUNSELOR,
            )}
            onChange={() =>
              setDraft((current) => ({
                ...current,
                providerRoles: toggleValue(
                  current.providerRoles,
                  ConfigurableProviderRoleCodeValues.COUNSELOR,
                ),
                providerRolesTouched: true,
              }))
            }
          />
          <span>
            <span className="block text-sm font-semibold">Counselor</span>
            <span className="mt-1 block text-xs leading-5 text-muted-foreground">
              Route this service to counselors who are assigned to it.
            </span>
          </span>
        </label>
      </fieldset>

      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
        <input
          className="mt-1 size-4 accent-[var(--compass-brand-maroon)]"
          type="checkbox"
          checked={draft.requiresCurrentInventory}
          onChange={(event) =>
            setDraft((current) => ({
              ...current,
              requiresCurrentInventory: event.target.checked,
            }))
          }
        />
        <span>
          <span className="block text-sm font-semibold">
            Requires current inventory
          </span>
          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
            Use this when the service depends on currently available items or slots.
          </span>
        </span>
      </label>

      <div className="flex flex-col-reverse gap-3 border-t border-[var(--compass-border)] pt-5 sm:flex-row sm:justify-end">
        {onCancel ? (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : null}
          {isSubmitting
            ? mode === "create"
              ? "Creating…"
              : "Saving…"
            : mode === "create"
              ? "Create service"
              : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
