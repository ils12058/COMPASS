"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelSection } from "@/components/ui/panel";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { ServiceFixedSlotsStudentPanel } from "@/features/services/service-fixed-slots-panel";
import { useServicesList } from "@/lib/api/generated/services/services";
import type { ServiceResponse } from "@/lib/api/generated/model";
import { AppointmentsLocalNavigation, AppointmentsPageHeading, appointmentErrorMessage } from "./appointments-shared";

// A reachable presentation of the existing Student slot-booking API. Services configuration keeps
// its own management gate; this view inherits the current-Student booking gate from its parent.
export function AppointmentFixedDateBooking() {
  const { user } = usePortalSession();
  const canRead = user.capabilities.includes("services.catalog.view");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<ServiceResponse | null>(null);
  const catalog = useServicesList({ page, page_size: 50, search: search || undefined }, { query: { retry: false, enabled: canRead } });
  const services = (catalog.data?.data.items ?? []).filter(item => item.is_active && item.booking_pathways.includes("FIXED_DATE_SLOT"));
  return <>
    <AppointmentsLocalNavigation />
    <AppointmentsPageHeading title="Scheduled appointment slots" description="Choose a Service to view its published appointment slots." />
    <Link href="/portal/appointments/book" className={pageBackLinkClass}>Back to regular appointment booking</Link>
    <Panel className="mt-5">
      <PanelSection title="Choose a Service" titleId="scheduled-slot-service-heading">
        {!canRead ? <Notice role="alert">Service catalog access is needed to find scheduled appointment slots.</Notice> : <div className="space-y-3">
          <Label htmlFor="scheduled-service-search">Search Services</Label>
          <Input id="scheduled-service-search" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} />
          {catalog.isPending ? <p role="status">Loading Services…</p> : catalog.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void catalog.refetch()}>Retry Services</Button>}>{appointmentErrorMessage(catalog.error, "Services could not be loaded.")}</Notice> : <>
            <Label htmlFor="scheduled-service">Service</Label>
            <Select id="scheduled-service" value={selected?.id ?? ""} onChange={event => setSelected(services.find(item => item.id === event.target.value) ?? null)}>
              <option value="">Choose a Service…</option>
              {selected && !services.some(item => item.id === selected.id) ? <option value={selected.id}>{selected.name}</option> : null}
              {services.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
            {services.length === 0 ? <p className="text-sm text-muted">No Services with scheduled appointment slots on this page. Try another search or page.</p> : null}
          </>}
          <div className="flex flex-wrap gap-2">
            <Button variant="quiet" disabled={page === 1 || catalog.isFetching} onClick={() => setPage(value => value - 1)}>Previous Services</Button>
            <Button variant="quiet" disabled={!catalog.data?.data.has_next || catalog.isFetching} onClick={() => setPage(value => value + 1)}>More Services</Button>
          </div>
        </div>}
      </PanelSection>
      {selected && !catalog.isError ? <ServiceFixedSlotsStudentPanel key={selected.id} service={selected} /> : null}
    </Panel>
  </>;
}
