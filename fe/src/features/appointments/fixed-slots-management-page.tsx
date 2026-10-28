"use client";

import { useState } from "react";

import { Panel, PanelSection } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { AppointmentsLocalNavigation, appointmentErrorMessage } from "@/features/appointments/appointments-shared";
import { ServiceFixedSlotsStaffPanel } from "@/features/services/service-fixed-slots-panel";
import { getAppointmentAccess } from "@/features/appointments/appointments-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useServicesGet, useServicesList } from "@/lib/api/generated/services/services";
import { BookingPathway } from "@/lib/api/generated/model";

export function FixedSlotsManagementPage() {
  const { user } = usePortalSession();
  const access = getAppointmentAccess(user);
  const [serviceId, setServiceId] = useState("");
  const [page, setPage] = useState(1);
  const services = useServicesList(
    { page, page_size: 20 },
    { query: { retry: false, enabled: access.canManageSlots } },
  );
  const service = useServicesGet(serviceId, {
    query: { retry: false, enabled: Boolean(serviceId) && access.canManageSlots },
  });

  if (!access.canManageSlots) {
    return (
      <Notice role="alert" tone="danger">
        Appointment slot management is unavailable to this account.
      </Notice>
    );
  }

  const items = services.data?.data.items ?? [];
  return (
    <section aria-labelledby="appointment-slots-heading" className="space-y-5">
      <AppointmentsLocalNavigation />
      <PageHeader
        title="Manage appointment slots"
        description="Publish and maintain scheduled individual appointment opportunities within your authorized provider scope."
      />
      <Panel>
        <PanelSection title="Select a Service" titleId="appointment-slots-heading">
          <p className="text-sm text-muted">
            Select an active Service to review its fixed-date slots. Pathway configuration and
            provider eligibility are checked again by the protected slot operations.
          </p>
          {services.isError ? (
            <Notice role="alert" tone="danger" className="mt-4">
              {appointmentErrorMessage(services.error, "Services could not be loaded. Try again.")}
            </Notice>
          ) : (
            <>
              <Select
                aria-label="Service for appointment slots"
                value={serviceId}
                onChange={(event) => setServiceId(event.target.value)}
                className="mt-4 max-w-xl"
              >
                <option value="">Choose a Service…</option>
                {items.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.code} — {item.name}
                  </option>
                ))}
              </Select>
              <div className="mt-3 flex items-center gap-2">
                <Button
                  type="button"
                  variant="quiet"
                  disabled={page <= 1 || services.isPending}
                  onClick={() => {
                    setPage((current) => Math.max(1, current - 1));
                    setServiceId("");
                  }}
                >
                  Previous Services
                </Button>
                <span className="text-xs text-muted">Catalog page {page}</span>
                <Button
                  type="button"
                  variant="quiet"
                  disabled={!services.data?.data.has_next || services.isPending}
                  onClick={() => {
                    setPage((current) => current + 1);
                    setServiceId("");
                  }}
                >
                  Next Services
                </Button>
              </div>
            </>
          )}
          <p className="mt-2 text-xs text-muted">
            This selector uses bounded catalog pages; an empty page is not treated as proof that no
            other Service has scheduled slots.
          </p>
        </PanelSection>
      </Panel>
      {service.isError ? (
        <Notice role="alert" tone="danger">
          {appointmentErrorMessage(service.error, "The selected Service could not be loaded.")}
        </Notice>
      ) : service.data?.data ? (
        service.data.data.booking_pathways?.includes(BookingPathway.FIXED_DATE_SLOT) ? (
          <Panel>
            <ServiceFixedSlotsStaffPanel service={service.data.data} />
          </Panel>
        ) : (
          <Notice role="status">
            This Service has no scheduled appointment-slot pathway configured.
          </Notice>
        )
      ) : null}
    </section>
  );
}
