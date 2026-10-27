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
import { useServicesGet, useServicesList } from "@/lib/api/generated/services/services";
import { AppointmentsLocalNavigation, AppointmentsPageHeading, appointmentErrorMessage } from "./appointments-shared";

export function AppointmentFixedDateBooking({ initialServiceId, initialSearch, initialPage }: { initialServiceId?: string; initialSearch?: string; initialPage?: string }) {
  const validInitialId = Boolean(initialServiceId && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(initialServiceId));
  const { user } = usePortalSession();
  const canRead = user.capabilities.includes("services.catalog.view") && user.capabilities.includes("appointments.view_self");
  const [page, setPage] = useState(() => initialPage && /^[1-9][0-9]{0,3}$/.test(initialPage) ? Number(initialPage) : 1);
  const [search, setSearch] = useState(() => (initialSearch ?? "").slice(0, 160));
  const [selectedId, setSelectedId] = useState(validInitialId ? initialServiceId! : "");
  const catalog = useServicesList({ page, page_size: 50, search: search || undefined }, { query: { retry: false, enabled: canRead } });
  const selectedQuery = useServicesGet(selectedId, { query: { enabled: canRead && Boolean(selectedId), retry: false, staleTime: 0, refetchOnWindowFocus: true } });
  const selected = selectedQuery.data?.data;
  const valid = Boolean(selected && selected.is_active && selected.booking_pathways.includes("FIXED_DATE_SLOT"));
  const services = (catalog.data?.data.items ?? []).filter(item => item.is_active && item.booking_pathways.includes("FIXED_DATE_SLOT"));
  const checkService = async () => {
    const result = await selectedQuery.refetch();
    return !result.isError && Boolean(result.data?.data.is_active && result.data.data.booking_pathways.includes("FIXED_DATE_SLOT"));
  };
  return <>
    <AppointmentsLocalNavigation />
    <AppointmentsPageHeading title="Scheduled appointment slots" description="Choose a Service to view its published individual appointment slots." />
    <Link href="/portal/appointments/book" className={pageBackLinkClass}>Back to booking choices</Link>
    <Panel className="mt-5">
      <PanelSection title="Choose a Service" titleId="scheduled-slot-service-heading">
        {initialServiceId && !validInitialId ? <Notice role="alert">The Service link is invalid. Choose a Service below.</Notice> : null}
        {!canRead ? <Notice role="alert">Service catalog and appointment viewing access are needed to find scheduled appointment slots.</Notice> : <div className="space-y-3">
          <Label htmlFor="scheduled-service-search">Search Services</Label>
          <Input id="scheduled-service-search" type="search" maxLength={160} value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} />
          {catalog.isPending ? <p role="status">Loading Services…</p> : catalog.isError ? <Notice role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void catalog.refetch()}>Retry Services</Button>}>{appointmentErrorMessage(catalog.error, "Services could not be loaded.")}</Notice> : <>
            <Label htmlFor="scheduled-service">Service</Label>
            <Select id="scheduled-service" value={selectedId} onChange={event => setSelectedId(event.target.value)}>
              <option value="">Choose a Service…</option>
              {selectedId && !services.some(item => item.id === selectedId) ? <option value={selectedId}>{selected?.name ?? "Selected Service"}</option> : null}
              {services.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
            {services.length === 0 ? <p className="text-sm text-muted">No Services with scheduled slots on this page.{catalog.data?.data.has_next ? " Try another page or search." : page > 1 ? " Try a previous page or another search." : " Try another search."}</p> : null}
          </>}
          <div className="flex flex-wrap gap-2">
            <Button variant="quiet" disabled={page === 1 || catalog.isFetching} onClick={() => setPage(value => value - 1)}>Previous Services</Button>
            <Button variant="quiet" disabled={!catalog.data?.data.has_next || catalog.isFetching} onClick={() => setPage(value => value + 1)}>More Services</Button>
          </div>
        </div>}
      </PanelSection>
      {canRead && selectedId && (selectedQuery.isPending) ? <p className="px-5 pb-4" role="status">Checking the selected Service…</p> : null}
      {canRead && selectedId && selectedQuery.isError ? <Notice className="m-4" role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void selectedQuery.refetch()}>Retry Service</Button>}>The selected Service could not be confirmed. Check it again before booking.</Notice> : null}
      {canRead && selectedId && !selectedQuery.isPending && !selectedQuery.isError && !valid ? <Notice className="m-4" role="alert">This Service no longer offers scheduled slots. Choose another Service.</Notice> : null}
      {canRead && selected && valid && !selectedQuery.isError ? <>
        <div className="px-5 pt-4 text-sm"><p><strong>{selected.name}</strong> supports scheduled appointment slots{selected.booking_pathways.includes("FLEXIBLE_APPOINTMENT") ? ", individual appointment booking" : ""}{selected.booking_pathways.includes("GROUP_SESSION") ? ", and group sessions" : ""}. Check each pathway for current opportunities.</p>{selected.booking_pathways.includes("FLEXIBLE_APPOINTMENT") ? <Link className="font-semibold text-brand underline" href="/portal/appointments/book">Find an individual appointment</Link> : null}</div>
        {selected.booking_pathways.includes("GROUP_SESSION") && user.capabilities.includes("appointments.view_self") ? <p className="px-5 pt-4 text-sm"><Link className="font-semibold text-brand underline" href={`/portal/group-sessions/discover?${new URLSearchParams({ service_id: selected.id, ...(search ? { slot_search: search } : {}), ...(page > 1 ? { slot_page: String(page) } : {}) }).toString()}`}>Browse group sessions for {selected.name}</Link></p> : null}
        <ServiceFixedSlotsStudentPanel key={selected.id} service={selected} checkService={checkService} />
      </> : null}
    </Panel>
  </>;
}
