"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { GroupSessionsHeading } from "./group-sessions-shared";
import { Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { ServiceGroupSessionsStudentPanel } from "@/features/services/service-group-sessions-panel";
import { useServicesGet } from "@/lib/api/generated/services/services";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function FilteredSessions({ serviceId }: { serviceId: string }) {
  const { user } = usePortalSession();
  const search = useSearchParams();
  const validId = uuid.test(serviceId);
  const canRead = user.capabilities.includes("services.catalog.view");
  const service = useServicesGet(serviceId, { query: { enabled: validId && canRead, retry: false, staleTime: 0, refetchOnWindowFocus: true } });
  if (!validId || !canRead) return <Notice role="alert">This Service cannot be selected. <Link className="font-semibold underline" href="/portal/group-sessions/discover">Browse all Group Sessions</Link>.</Notice>;
  if (service.isPending) return <p role="status">Checking the Service…</p>;
  if (service.isError) return <Notice role="alert" action={<Button variant="secondary" onClick={() => void service.refetch()}>Retry Service</Button>}>Couldn&apos;t confirm Service. <Link className="font-semibold underline" href="/portal/group-sessions/discover">Browse all Group Sessions</Link>.</Notice>;
  if (!service.data?.data.is_active || !service.data.data.booking_pathways.includes("GROUP_SESSION")) return <Notice role="alert">This Service no longer offers Group Sessions. <Link className="font-semibold underline" href="/portal/group-sessions/discover">Browse all Group Sessions</Link>.</Notice>;
  return <><p className="mb-3 text-sm">Showing Group Sessions for <strong>{service.data.data.name}</strong>. <Link className="font-semibold text-brand underline" href="/portal/group-sessions/discover">Browse all</Link>{service.data.data.booking_pathways.includes("FIXED_DATE_SLOT") && user.student_lifecycle_status === "CURRENT" && user.capabilities.includes("appointments.manage_self") ? <> · <Link className="font-semibold text-brand underline" href={`/portal/appointments/book?${new URLSearchParams({ pathway: "FIXED_DATE_SLOT", service_id: serviceId, ...(search.get("slot_search") ? { search: search.get("slot_search")!.slice(0, 160) } : {}), ...(/^[1-9][0-9]{0,3}$/.test(search.get("slot_page") ?? "") ? { page: search.get("slot_page")! } : {}) }).toString()}`}>View scheduled Appointment slots</Link></> : null}</p><p className="mb-3 text-sm text-muted">This Service supports Group Sessions{service.data.data.booking_pathways.includes("FIXED_DATE_SLOT") ? ", scheduled Appointment slots" : ""}{service.data.data.booking_pathways.includes("FLEXIBLE_APPOINTMENT") ? ", and individual Appointment booking" : ""}. Check each pathway for current opportunities.</p>{service.data.data.booking_pathways.includes("FLEXIBLE_APPOINTMENT") && user.student_lifecycle_status === "CURRENT" && user.capabilities.includes("appointments.manage_self") ? <p className="mb-3 text-sm"><Link className="font-semibold text-brand underline" href="/portal/appointments/book">Find an individual Appointment</Link></p> : null}<Panel aria-label="Upcoming Group Sessions and workshops"><ServiceGroupSessionsStudentPanel key={`${user.id}:${user.capabilities.join(",")}:${user.student_lifecycle_status}:${serviceId}`} service={service.data.data} /></Panel></>;
}

export function GroupSessionsDiscoveryPage() {
  const { user } = usePortalSession();
  const search = useSearchParams();
  const serviceId = search.get("service_id");
  if (user.role !== "STUDENT" || !user.capabilities.includes("appointments.view_self")) return <WorkspaceUnavailable title="Group Session access">You don&apos;t have access to browse Group Sessions.</WorkspaceUnavailable>;
  return <><GroupSessionsHeading />{serviceId !== null ? <FilteredSessions key={`${user.id}:${serviceId}`} serviceId={serviceId} /> : <Panel aria-label="Upcoming Group Sessions and workshops"><ServiceGroupSessionsStudentPanel key={`${user.id}:${user.capabilities.join(",")}:${user.student_lifecycle_status}`} /></Panel>}</>;
}
