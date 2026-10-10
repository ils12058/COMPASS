"use client";

import Link from "next/link";
import { ArrowLeft, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  useServicesCreate,
} from "@/lib/api/generated/services/services";
import type { ServiceCreateRequest } from "@/lib/api/generated/model";
import {
  EMPTY_SERVICE_FORM,
  PortalItAdminServiceForm,
  type ServiceFormValues,
} from "@/features/portal/admin/services/portal-it-admin-service-form";
import {
  ServiceActionMessage,
  ServiceSection,
  serviceAdminError,
} from "@/features/portal/admin/services/portal-it-admin-services-shared";

function optionalInteger(value: string) {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function serviceCreatePayload(values: ServiceFormValues): ServiceCreateRequest {
  return {
    appointment_policy: values.appointmentPolicy,
    cancellation_cutoff_minutes: optionalInteger(values.cancellationCutoffMinutes),
    code: values.code.trim(),
    default_duration_minutes: optionalInteger(values.defaultDurationMinutes),
    delivery_modes: values.deliveryModes,
    description: values.description.trim(),
    name: values.name.trim(),
    provider_roles: values.providerRoles,
    requires_current_inventory: values.requiresCurrentInventory,
  };
}

export function PortalItAdminServiceCreatePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const createService = useServicesCreate();

  async function submitCreate(values: ServiceFormValues) {
    setError(null);

    try {
      const response = await createService.mutateAsync({
        data: serviceCreatePayload(values),
      });
      router.push(`/portal/admin/services/${response.data.id}`);
    } catch (caught) {
      setError(
        serviceAdminError(
          caught,
          "We couldn’t create this service. Please review the details and try again.",
        ),
      );
    }
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
        icon={Plus}
        title="Add a service"
        description="Describe the service and choose the settings staff will use when offering it."
      >
        <ServiceActionMessage error={error} />
        <div className="mt-5">
          <PortalItAdminServiceForm
            initialValues={EMPTY_SERVICE_FORM}
            isSubmitting={createService.isPending}
            mode="create"
            onCancel={() => router.push("/portal/admin/services")}
            onSubmit={submitCreate}
          />
        </div>
      </ServiceSection>
    </div>
  );
}
