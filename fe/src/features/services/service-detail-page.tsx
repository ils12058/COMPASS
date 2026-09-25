"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  ServicesDetailSkeleton,
  ServicesPageHeading,
  ServicesQueryError,
  ServicesStatusBadge,
  useServicesAction,
} from "@/features/services/services-shared";
import {
  AppointmentPolicy,
  DeliveryMode,
  ProviderRoleCode,
} from "@/lib/api/generated/model";
import {
  getServicesGetQueryKey,
  getServicesListQueryKey,
  useServicesDisable,
  useServicesEnable,
  useServicesGet,
} from "@/lib/api/generated/services/services";

function policyLabel(policy: AppointmentPolicy): string {
  if (policy === AppointmentPolicy.NONE) return "No appointment";
  if (policy === AppointmentPolicy.OPTIONAL) return "Appointment optional";
  return "Appointment required";
}

function policyDescription(policy: AppointmentPolicy): string {
  if (policy === AppointmentPolicy.NONE) {
    return "This Service does not accept Appointment scheduling.";
  }
  return "Appointments can be scheduled for this Service when its booking requirements are met.";
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-PH", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function ServiceDetailPage() {
  const params = useParams<{ serviceId: string }>();
  const serviceId = params.serviceId;
  const searchParams = useSearchParams();
  const { user } = usePortalSession();
  const canManage = user.capabilities.includes("services.manage");
  const queryClient = useQueryClient();
  const detail = useServicesGet(serviceId, {
    query: { retry: false },
  });
  const enable = useServicesEnable();
  const disable = useServicesDisable();
  const action = useServicesAction();
  const [lifecycleOpen, setLifecycleOpen] = useState(false);

  if (detail.isPending) return <ServicesDetailSkeleton />;

  if (detail.isError) {
    return (
      <section>
        <ServicesPageHeading
          title="Service unavailable"
          backHref="/portal/services"
          backLabel="Services"
        />
        <div className="mt-6">
          <ServicesQueryError
            error={detail.error}
            fallback="The Service could not be loaded."
            onRetry={() => void detail.refetch()}
          />
        </div>
      </section>
    );
  }

  const service = detail.data.data;
  const lifecyclePending = enable.isPending || disable.isPending;
  const hasCounselor = service.provider_roles.includes(
    ProviderRoleCode.COUNSELOR,
  );
  const hasLegacyGss = service.provider_roles.includes(
    ProviderRoleCode.GUIDANCE_SERVICES_STAFF,
  );

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getServicesGetQueryKey(serviceId),
      }),
      queryClient.invalidateQueries({
        queryKey: getServicesListQueryKey(),
      }),
    ]);
  }

  async function confirmLifecycle() {
    const wasActive = service.is_active;
    const response = await action.run(
      () =>
        wasActive
          ? disable.mutateAsync({ serviceId })
          : enable.mutateAsync({ serviceId }),
      "The Service lifecycle could not be changed.",
      {
        onStepUpRequired: () => setLifecycleOpen(false),
        onStepUpVerified: () => setLifecycleOpen(true),
      },
    );
    if (!response) return;
    setLifecycleOpen(false);
    action.setNotice(wasActive ? "Service disabled." : "Service enabled.");
    await refresh();
  }

  const createdNotice = searchParams.get("created") === "true";
  const updatedNotice = searchParams.get("updated") === "true";

  return (
    <section>
      <ServicesPageHeading
        title={service.name}
        backHref="/portal/services"
        backLabel="Services"
        action={
          canManage ? (
            <Link
              href={"/portal/services/" + service.id + "/edit"}
              className="inline-flex min-h-10 items-center justify-center rounded-md border border-border-strong bg-surface-raised px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-body"
            >
              Edit Service
            </Link>
          ) : null
        }
      />

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <p className="font-mono text-xs text-muted">{service.code}</p>
        {canManage ? <ServicesStatusBadge active={service.is_active} /> : null}
      </div>

      {createdNotice ? (
        <p role="status" className="mt-5 text-sm text-success">
          Service created. It remains inactive until enabled.
        </p>
      ) : null}
      {updatedNotice ? (
        <p role="status" className="mt-5 text-sm text-success">
          Service updated.
        </p>
      ) : null}
      {action.notice || action.error ? action.messages : null}

      <div className="mt-8 divide-y divide-border border-y border-border">
        <section className="py-7" aria-labelledby="service-description-heading">
          <h2
            id="service-description-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Description
          </h2>
          <p className="mt-3 max-w-4xl whitespace-pre-wrap text-sm leading-7 text-muted">
            {service.description.trim() || "No description provided."}
          </p>
        </section>

        <section className="py-7" aria-labelledby="service-delivery-heading">
          <h2
            id="service-delivery-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Service delivery
          </h2>
          <p className="mt-3 text-sm text-ink">
            {service.delivery_modes.length === 0
              ? "No delivery mode configured."
              : [
                  service.delivery_modes.includes(DeliveryMode.IN_PERSON)
                    ? "In person"
                    : null,
                  service.delivery_modes.includes(DeliveryMode.ONLINE)
                    ? "Online"
                    : null,
                ]
                  .filter(Boolean)
                  .join(", ")}
          </p>
        </section>

        <section className="py-7" aria-labelledby="service-appointment-heading">
          <h2
            id="service-appointment-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Appointment settings
          </h2>
          <dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Policy
              </dt>
              <dd className="mt-1 text-sm font-medium text-ink">
                {policyLabel(service.appointment_policy)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Default appointment duration
              </dt>
              <dd className="mt-1 text-sm text-ink">
                {service.default_duration_minutes === null
                  ? "Not configured"
                  : service.default_duration_minutes + " minutes"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                Student cancellation/rescheduling cutoff
              </dt>
              <dd className="mt-1 text-sm text-ink">
                {service.appointment_policy === AppointmentPolicy.NONE
                  ? "Not applicable"
                  : service.cancellation_cutoff_minutes === null
                    ? "Not configured"
                    : service.cancellation_cutoff_minutes + " minutes before"}
              </dd>
            </div>
          </dl>
          <p className="mt-4 max-w-4xl text-sm leading-6 text-muted">
            {policyDescription(service.appointment_policy)}
          </p>
          {canManage ? (
            <p className="mt-2 max-w-4xl text-xs leading-5 text-muted">
              Service scheduling changes apply to future Appointments. Existing
              Appointments retain their saved timing and cancellation cutoff.
            </p>
          ) : null}
        </section>

        <section className="py-7" aria-labelledby="service-requirements-heading">
          <h2
            id="service-requirements-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Student requirements
          </h2>
          <p className="mt-3 text-sm leading-6 text-ink">
            {service.requires_current_inventory
              ? "A submitted current Individual Inventory is required before appointment booking for this Service."
              : "This Service does not require a submitted current Individual Inventory before appointment booking."}
          </p>
        </section>

        <section className="py-7" aria-labelledby="service-provider-heading">
          <h2
            id="service-provider-heading"
            className="font-heading text-xl font-semibold text-ink"
          >
            Provider eligibility
          </h2>
          {canManage ? (
            <div className="mt-3 space-y-2 text-sm leading-6 text-ink">
              {hasCounselor ? <p>Counselor</p> : null}
              {hasLegacyGss ? (
                <p>
                  Guidance Services Staff — historical assignment retained for
                  compatibility; not configurable as current provider
                  eligibility.
                </p>
              ) : null}
              {!hasCounselor && !hasLegacyGss ? (
                <p>No provider role configured.</p>
              ) : null}
              <p className="text-xs text-muted">
                This is role-level eligibility only. Specific Counselor
                assignment and Availability are managed elsewhere.
              </p>
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-ink">
              {hasCounselor
                ? "Counselors may provide this Service."
                : hasLegacyGss
                  ? "This Service contains a historical provider configuration maintained by the Guidance and Counseling Office."
                  : "Provider eligibility is not configured."}
            </p>
          )}
        </section>

        {canManage ? (
          <section className="py-7" aria-labelledby="service-lifecycle-heading">
            <h2
              id="service-lifecycle-heading"
              className="font-heading text-xl font-semibold text-ink"
            >
              Lifecycle
            </h2>
            <dl className="mt-4 grid gap-5 sm:grid-cols-3">
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Status
                </dt>
                <dd className="mt-1">
                  <ServicesStatusBadge active={service.is_active} />
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Created
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {formatDate(service.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
                  Updated
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {formatDate(service.updated_at)}
                </dd>
              </div>
            </dl>
            <div className="mt-5">
              <Button
                variant={service.is_active ? "danger" : "primary"}
                onClick={() => {
                  action.setError(null);
                  action.setNotice(null);
                  setLifecycleOpen(true);
                }}
              >
                {service.is_active ? "Disable Service" : "Enable Service"}
              </Button>
            </div>
          </section>
        ) : null}
      </div>

      <AlertDialog
        open={lifecycleOpen}
        onOpenChange={(open) => {
          if (lifecyclePending) return;
          setLifecycleOpen(open);
          if (!open) {
            action.setError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>
            {service.is_active
              ? "Disable " + service.name + "?"
              : "Enable " + service.name + "?"}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {service.is_active
              ? "The Service will no longer be available for new Appointment scheduling. Scheduling changes such as rescheduling or reassignment may also be unavailable while it remains inactive. Existing Appointment records will remain."
              : "COMPASS will validate the complete active configuration before enabling this Service. If required configuration is missing, the Service will remain inactive."}
          </AlertDialogDescription>
          {action.messages}
          <div className="mt-6 flex justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={lifecyclePending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <Button
              variant={service.is_active ? "danger" : "primary"}
              disabled={lifecyclePending}
              onClick={() => void confirmLifecycle()}
            >
              {lifecyclePending
                ? service.is_active
                  ? "Disabling…"
                  : "Enabling…"
                : service.is_active
                  ? "Disable Service"
                  : "Enable Service"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>

      {action.stepUpDialog}
    </section>
  );
}
