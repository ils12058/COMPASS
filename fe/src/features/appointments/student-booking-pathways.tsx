"use client";

import Link from "next/link";
import { ContextHelp } from "@/components/ui/context-help";
import { Panel, PanelSection } from "@/components/ui/panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { canBrowseGroupSessions } from "@/features/group-sessions/group-sessions-access";

export function StudentBookingPathways() {
  const { user } = usePortalSession();
  const group = canBrowseGroupSessions(user);
  return <Panel className="mb-5">
    <PanelSection title="Ways to get support" titleId="booking-pathways-heading" actions={<ContextHelp title="Choosing a booking" sections={[
      { heading: "Appointments", content: <p>Choose an individual time with a counselor, or select a scheduled slot published by the office. The times shown are checked before booking.</p> },
      { heading: "Group sessions", content: <p>Group activities have their own registration and capacity. A published session may not be open to every student.</p> },
      { heading: "After booking", content: <p>Find individual appointments in My appointments and group activities in My Registrations. If a result cannot be confirmed, check your records before trying again.</p> },
    ]} />}>
      <p className="mt-2 text-sm text-muted">Choose how you would like to meet. Times and registration depend on current schedules and eligibility.</p>
      <ul className="mt-4 divide-y divide-border">
        <li className="py-3"><h3 className="font-semibold">Individual appointment</h3><p className="text-sm text-muted">Choose a Service, delivery mode, counselor and available time.</p><a href="#booking-service-heading" className="inline-flex min-h-11 items-center font-semibold text-brand underline underline-offset-4">Find an appointment</a></li>
        <li className="py-3"><h3 className="font-semibold">Scheduled appointment slot</h3><p className="text-sm text-muted">Choose a specific individual time published by the office.</p>{user.capabilities.includes("appointments.view_self") && user.capabilities.includes("services.catalog.view") ? <Link href="/portal/appointments/book?pathway=FIXED_DATE_SLOT" className="inline-flex min-h-11 items-center font-semibold text-brand underline underline-offset-4">View scheduled slots</Link> : <p className="mt-2 text-sm text-muted">Scheduled slot browsing is unavailable to this account.</p>}</li>
        <li className="py-3"><h3 className="font-semibold">Group session or event</h3><p className="text-sm text-muted">Browse group activities and register when eligible.</p>{group ? <Link href="/portal/group-sessions/discover" className="inline-flex min-h-11 items-center font-semibold text-brand underline underline-offset-4">Browse group sessions</Link> : <p className="mt-2 text-sm text-muted">Group session browsing is unavailable to this account.</p>}</li>
      </ul>
      {user.capabilities.includes("appointments.view_self") ? <p className="mt-2 text-sm text-muted"><Link className="font-semibold text-brand underline underline-offset-4" href="/portal/appointments/my">My appointments</Link>{group ? <> · <Link className="font-semibold text-brand underline underline-offset-4" href="/portal/group-sessions/my">My Registrations</Link></> : null}</p> : null}
    </PanelSection>
  </Panel>;
}
