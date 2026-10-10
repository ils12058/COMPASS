"use client";

import Link from "next/link";
import { ArrowLeft, Settings2 } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/features/auth/utils/errors";
import { formatAdminDate } from "@/features/portal/admin/portal-it-admin-shared";
import {
  getServicesGetQueryKey,
  getServicesListQueryKey,
  useServicesDisable,
  useServicesEnable,
  useServicesGet,
  useServicesUpdate,
} from "@/lib/api/generated/services/services";
import type { ServiceUpdateRequest } from "@/lib/api/generated/model";
import {
  PortalItAdminServiceForm,
  serviceToFormValues,
  type ServiceFormValues,
} from "@/features/portal/admin/services/portal-it-admin-service-form";
import {
  ServiceActionMessage,
  ServiceQueryError,
  ServiceSection,
  ServiceStatusBadge,
  formatServiceValue,
  serviceAdminError,
} from "@/features/portal/admin/services/portal-it-admin-services-shared";

function ServiceDetailLoading() {
  return (
    <div className="space-y-5" aria-live="polite">
      <div className="h-8 w-48 animate-pulse rounded-xl bg-muted" />
      <div className="h-64 animate-pulse rounded-3xl bg-card" />
      <div className="h-[38rem] animate-pulse rounded-3xl bg-card" />
    </div>
  );
}

function optionalInteger(value: string) {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function serviceUpdatePayload(values: ServiceFormValues): ServiceUpdateRequest {
  const payload: ServiceUpdateRequest = {
    appointment_policy: values.appointmentPolicy,
    cancellation_cutoff_minutes: optionalInteger(values.cancellationCutoffMinutes),
    default_duration_minutes: optionalInteger(values.defaultDurationMinutes),
    delivery_modes: values.deliveryModes,
    description: values.description.trim(),
    name: values.name.trim(),
    requires_current_inventory: values.requiresCurrentInventory,
  };

  if (values.providerRolesTouched) {
    payload.provider_roles = values.providerRoles;
  }

  return payload;
}

export function PortalItAdminServiceDetailPage({
  canManage,
  serviceId,
}: {
  canManage: boolean;
  serviceId: string;
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const serviceQuery = useServicesGet(serviceId, {
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const updateService = useServicesUpdate();
  const enableService = useServicesEnable();
  const disableService = useServicesDisable();
  const service = serviceQuery.data?.data;
  const isMutating =
    updateService.isPending || enableService.isPending || disableService.isPending;

  async function invalidateServiceQueries() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getServicesGetQueryKey(serviceId) }),
      queryClient.invalidateQueries({ queryKey: getServicesListQueryKey() }),
    ]);
  }

  async function submitUpdate(values: ServiceFormValues) {
    setError(null);
    setMessage(null);

    try {
      await updateService.mutateAsync({
        serviceId,
        data: serviceUpdatePayload(values),
      });
      setMessage("Service settings saved.");
      await invalidateServiceQueries();
    } catch (caught) {
      setError(
        serviceAdminError(
          caught,
          "We couldn’t save these service settings. Please review the details and try again.",
        ),
      );
    }
  }

  async function toggleStatus() {
    if (!service) {
      return;
    }

    const nextAction = service.is_active ? "disable" : "enable";
    if (!window.confirm(`${nextAction === "disable" ? "Disable" : "Enable"} ${service.name}?`)) {
      return;
    }

    setError(null);
    setMessage(null);

    try {
      if (service.is_active) {
        await disableService.mutateAsync({ serviceId });
      } else {
        await enableService.mutateAsync({ serviceId });
      }
      setMessage(`Service ${service.is_active ? "disabled" : "enabled"}.`);
      await invalidateServiceQueries();
    } catch (caught) {
      setError(
        serviceAdminError(
          caught,
          `We couldn’t ${nextAction} this service. Please try again.`,
        ),
      );
    }
  }

  if (serviceQuery.isPending) {
    return <ServiceDetailLoading />;
  }

  if (serviceQuery.isError || !service) {
    return (
      <div className="space-y-5">
        <Button asChild type="button" variant="ghost" className="-ml-2">
          <Link href="/portal/admin/services">
            <ArrowLeft aria-hidden="true" />
            Back to service catalog
          </Link>
        </Button>
        <ServiceQueryError onRetry={() => void serviceQuery.refetch()} />
        {serviceQuery.error ? (
          <p className="text-center text-sm text-muted-foreground">
            {getApiErrorMessage(serviceQuery.error)}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Button asChild type="button" variant="ghost" className="-ml-2">
        <Link href="/portal/admin/services">
          <ArrowLeft aria-hidden="true" />
          Back to service catalog
        </Link>
      </Button>

      <ServiceSection
        icon={Settings2}
        title={service.name}
        description={service.description || "No description has been added for this service yet."}
      >
        <div className="flex flex-col gap-3 border-b border-[var(--compass-border)] pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <ServiceStatusBadge active={service.is_active} />
            <span className="font-mono text-sm text-muted-foreground">{service.code}</span>
          </div>
          {canManage ? (
            <Button
              type="button"
              variant={service.is_active ? "outline" : "default"}
              disabled={isMutating}
              onClick={() => void toggleStatus()}
            >
              {service.is_active ? "Disable service" : "Enable service"}
            </Button>
          ) : null}
        </div>

        <dl className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
            <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
              Appointments
            </dt>
            <dd className="mt-2 font-semibold">{formatServiceValue(service.appointment_policy)}</dd>
          </div>
          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
            <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
              Duration
            </dt>
            <dd className="mt-2 font-semibold">
              {service.default_duration_minutes
                ? `${service.default_duration_minutes} minutes`
                : "Not set"}
            </dd>
          </div>
          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
            <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
              Delivery
            </dt>
            <dd className="mt-2 font-semibold">
              {service.delivery_modes.length
                ? service.delivery_modes.map(formatServiceValue).join(" · ")
                : "Not set"}
            </dd>
          </div>
          <div className="rounded-2xl border border-[var(--compass-border)] bg-[var(--compass-surface-subtle)] p-4">
            <dt className="text-xs font-bold uppercase tracking-[0.1em] text-muted-foreground">
              Updated
            </dt>
            <dd className="mt-2 font-semibold">{formatAdminDate(service.updated_at)}</dd>
          </div>
        </dl>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-[var(--compass-border)] p-4">
            <h3 className="font-semibold">Provider roles</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {service.provider_roles.length
                ? service.provider_roles.map(formatServiceValue).join(" · ")
                : "No provider role is assigned yet."}
            </p>
          </div>
          <div className="rounded-2xl border border-[var(--compass-border)] p-4">
            <h3 className="font-semibold">Inventory requirement</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {service.requires_current_inventory
                ? "This service uses current inventory information."
                : "This service does not require current inventory information."}
            </p>
          </div>
        </div>

        <p className="mt-5 text-xs text-muted-foreground">
          Created {formatAdminDate(service.created_at)} · Last updated {formatAdminDate(service.updated_at)}
        </p>
      </ServiceSection>

      <ServiceActionMessage error={error} message={message} />

      {canManage ? (
        <ServiceSection
          icon={Settings2}
          title="Service settings"
          description="Update the options that guide how this service is offered and scheduled."
        >
          <PortalItAdminServiceForm
            key={`${service.id}-${service.updated_at}`}
            initialValues={serviceToFormValues(service)}
            isSubmitting={isMutating}
            mode="edit"
            onSubmit={submitUpdate}
          />
        </ServiceSection>
      ) : null}
    </div>
  );
}
