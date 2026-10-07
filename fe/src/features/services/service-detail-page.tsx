"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Pencil } from "lucide-react";
import { ServiceHelp } from "@/features/services/service-help";
import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelSection } from "@/components/ui/panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  newECounselingAppointmentsLabel,
  PlatformHealthLink,
} from "@/features/services/counseling-delivery";
import {
  activationBlockerLabels,
  ServiceConsequenceSummary,
  serviceBookingLabel,
  serviceCoverageLabels,
  serviceDeliveryLabel,
  serviceSchedulingConsequenceDetails,
  ServicesDetailSkeleton,
  ServicesPageHeading,
  ServicesQueryError,
  ServicesStatusBadge,
  ServicesSystemRequiredBadge,
  useServicesAction,
  type ServiceSchedulingConsequenceDetails,
} from "@/features/services/services-shared";
import {
  DeliveryMode,
  ServiceProviderCoverage,
  type ServiceResponse,
} from "@/lib/api/generated/model";
import {
  getServicesGetQueryKey,
  getServicesListQueryKey,
  useServicesDisable,
  useServicesEnable,
  useServicesGet,
  useServicesGetProviders,
} from "@/lib/api/generated/services/services";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-ink">{children}</dd>
    </div>
  );
}

function BookingFacts({ service }: { service: ServiceResponse }) {
  if (!service.appointment_booking_enabled) {
    return (
      <dl className="mt-4">
        <Fact label="Appointment booking">Not available</Fact>
      </dl>
    );
  }
  return (
    <dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <Fact label="Appointment booking">{serviceBookingLabel(true)}</Fact>
      <Fact label="Duration">
        {service.default_appointment_duration_minutes === null
          ? "Not configured"
          : service.default_appointment_duration_minutes + " minutes"}
      </Fact>
      <Fact label="Cancellation/rescheduling cutoff">
        {service.cancellation_cutoff_minutes === null
          ? "None"
          : service.cancellation_cutoff_minutes + " minutes before"}
      </Fact>
      <Fact label="Booking requirement">
        {service.requires_current_inventory
          ? "Submitted current Individual Inventory"
          : "None"}
      </Fact>
    </dl>
  );
}

// Canonical Counseling: each mode's effect on new work, and what that means for E-Counseling.
function CounselingDeliveryFacts({ service }: { service: ServiceResponse }) {
  const state = {
    inPerson: service.delivery_modes.includes(DeliveryMode.IN_PERSON),
    online: service.delivery_modes.includes(DeliveryMode.ONLINE),
    bookingEnabled: service.appointment_booking_enabled,
  };
  return (
    <PanelSection title="Counseling delivery" titleId="service-delivery-heading">
      <dl className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <Fact label="In person">{state.inPerson ? "Available" : "Not enabled"}</Fact>
        <Fact label="Online counseling">{state.online ? "Available" : "Not enabled"}</Fact>
        <Fact label="New E-Counseling appointments">
          {newECounselingAppointmentsLabel(state)}
        </Fact>
      </dl>
      {state.online ? <PlatformHealthLink /> : null}
    </PanelSection>
  );
}

function SelectedProviders({ serviceId }: { serviceId: string }) {
  const providers = useServicesGetProviders(serviceId, { query: { retry: false } });
  if (providers.isPending) {
    return <p className="mt-3 text-sm text-muted">Loading selected Counselors…</p>;
  }
  if (providers.isError) {
    return (
      <p role="alert" className="mt-3 text-sm text-danger">
        Selected Counselors could not be loaded.{" "}
        <button
          type="button"
          className="font-semibold underline"
          onClick={() => void providers.refetch()}
        >
          Retry
        </button>
      </p>
    );
  }
  const counselors = providers.data.data.counselors;
  if (counselors.length === 0) {
    return <p className="mt-3 text-sm text-muted">No Counselors are selected.</p>;
  }
  return (
    <ul className="mt-3 divide-y divide-border rounded-sm border border-border">
      {counselors.map((counselor) => (
        <li key={counselor.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm text-ink">
          {counselor.display_name}
          {!counselor.is_active ? (
            <span className="text-xs text-muted">Inactive account · not eligible</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function formatDate(value: string): string {
  return formatInstitutionalDateTime(value);
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
  // Set when disabling needs the operator to review its effect on scheduled Appointments.
  const [disableReview, setDisableReview] =
    useState<ServiceSchedulingConsequenceDetails | null>(null);
  const [disableReviewRequired, setDisableReviewRequired] = useState(false);

  if (detail.isPending) return <ServicesDetailSkeleton />;

  if (detail.isError) {
    return (
      <section>
        <ServicesPageHeading
          title="Service unavailable"
          backHref="/portal/services"
          backLabel="Services"
        />
        <div className="mt-5">
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
  const systemRequired = service.is_system_required;
  const blockers = service.activation_blockers;

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

  function closeLifecycle() {
    setLifecycleOpen(false);
    setDisableReview(null);
    setDisableReviewRequired(false);
    action.setError(null);
  }

  async function confirmLifecycle() {
    const wasActive = service.is_active;
    const acknowledged = disableReviewRequired;
    const response = await action.run(
      () =>
        wasActive
          ? disable.mutateAsync({
              serviceId,
              data: { acknowledge_scheduling_consequences: acknowledged },
            })
          : enable.mutateAsync({ serviceId }),
      "The service status could not be changed.",
      {
        onStepUpRequired: () => setLifecycleOpen(false),
        onStepUpVerified: () => setLifecycleOpen(true),
        onError: (caught, code) => {
          if (code !== "service_scheduling_consequence_review_required") return false;
          setDisableReview(serviceSchedulingConsequenceDetails(caught));
          setDisableReviewRequired(true);
          return true;
        },
      },
    );
    if (!response) return;
    closeLifecycle();
    action.setNotice(wasActive ? "Service disabled." : "Service enabled.");
    await refresh();
  }

  const createdNotice = searchParams.get("created") === "true";
  const updatedNotice = searchParams.get("updated") === "true";

  return (
    <section>
      <ServicesPageHeading
        title={service.name}
        help={<ServiceHelp counseling={systemRequired} />}
        backHref="/portal/services"
        backLabel="Services"
        action={
          canManage ? (
            <Link
              href={"/portal/services/" + service.id + "/edit"}
              className={buttonVariants({ variant: "secondary" })}
            >
              <Pencil aria-hidden="true" size={16} /> Edit
            </Link>
          ) : null
        }
      >
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <p className="font-mono text-xs text-muted">{service.code}</p>
          {canManage ? <ServicesStatusBadge active={service.is_active} /> : null}
          {systemRequired ? <ServicesSystemRequiredBadge /> : null}
        </div>
      </ServicesPageHeading>

      {createdNotice ? (
        <Notice role="status" tone="success" className="mt-5">
          Service created. It remains inactive until enabled.
        </Notice>
      ) : null}
      {updatedNotice ? (
        <Notice role="status" tone="success" className="mt-5">
          Service updated.
        </Notice>
      ) : null}
      {action.notice || (action.error && !lifecycleOpen) ? action.messages : null}

      {canManage && !service.is_active && blockers.length > 0 ? (
        <Notice role="status" tone="warning" className="mt-5" title="Needs configuration before it can be enabled">
          <ul className="mt-1 list-disc pl-5">
            {blockers.map((blocker) => (
              <li key={blocker}>{activationBlockerLabels[blocker]}</li>
            ))}
          </ul>
        </Notice>
      ) : null}

      <Panel as="div" className="mt-5">
        {service.description.trim() ? <PanelSection title="Description" titleId="service-description-heading">
          <p className="mt-3 max-w-4xl whitespace-pre-wrap text-sm leading-7 text-muted">
            {service.description.trim()}
          </p>
        </PanelSection> : null}

        {systemRequired ? (
          <CounselingDeliveryFacts service={service} />
        ) : (
          <PanelSection title="Service delivery" titleId="service-delivery-heading">
            <p className="mt-3 text-sm text-ink">
              {service.delivery_modes.length === 0
                ? "No delivery mode configured."
                : serviceDeliveryLabel(service.delivery_modes)}
            </p>
          </PanelSection>
        )}

        <PanelSection title="Appointment booking" titleId="service-appointment-heading">
          <BookingFacts service={service} />
        </PanelSection>

        <PanelSection title="Provider coverage" titleId="service-provider-heading">
          <dl className="mt-4 grid gap-5 sm:grid-cols-2">
            <Fact label="Provider type">Counselor</Fact>
            <Fact label="Coverage">{serviceCoverageLabels[service.provider_coverage]}</Fact>
          </dl>
          {canManage &&
          service.provider_coverage === ServiceProviderCoverage.SELECTED_COUNSELORS ? (
            <SelectedProviders serviceId={service.id} />
          ) : null}
        </PanelSection>

        {canManage ? (
          <PanelSection title="Record dates" titleId="service-lifecycle-heading">
            <dl className="mt-4 grid gap-5 sm:grid-cols-3">
              <Fact label="Created">{formatDate(service.created_at)}</Fact>
              <Fact label="Updated">{formatDate(service.updated_at)}</Fact>
            </dl>
          </PanelSection>
        ) : null}
      </Panel>

      {canManage ? (
        <Panel className="mt-5" aria-label="Service actions">
          <PanelSection title="Actions" titleId="service-actions-heading">
            <div>
              {systemRequired && service.is_active ? (
                <p className="text-sm text-muted">
                  Counseling must stay active.
                </p>
              ) : (
                <Button
                  variant={service.is_active ? "danger" : "primary"}
                  disabled={!service.is_active && blockers.length > 0}
                  onClick={() => {
                    action.setError(null);
                    action.setNotice(null);
                    setLifecycleOpen(true);
                  }}
                >
                  {service.is_active ? "Disable Service" : "Enable Service"}
                </Button>
              )}
            </div>
          </PanelSection>
        </Panel>
      ) : null}

      <ConsequentialActionDialog
        open={lifecycleOpen}
        title={
          service.is_active
            ? "Disable " + service.name + "?"
            : "Enable " + service.name + "?"
        }
        confirmLabel={service.is_active ? "Disable Service" : "Enable Service"}
        pendingLabel={service.is_active ? "Disabling…" : "Enabling…"}
        pending={lifecyclePending}
        error={action.error}
        variant={service.is_active ? "danger" : "primary"}
        onOpenChange={(open) => {
          if (open) setLifecycleOpen(true);
          else closeLifecycle();
        }}
        onConfirm={() => void confirmLifecycle()}
      >
        <p>
          {service.is_active
            ? "This Service will no longer be available for new work. Existing records and Appointments are preserved."
            : "This Service will become operational for workflows that support it. Appointment booking is available only when it is enabled in this Service's booking settings."}
        </p>
        {disableReviewRequired ? <ServiceConsequenceSummary details={disableReview} /> : null}
      </ConsequentialActionDialog>

      {action.stepUpDialog}
    </section>
  );
}
