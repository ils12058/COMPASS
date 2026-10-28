"use client";

import Link from "next/link";
import { IllustratedIntroduction } from "@/components/ui/illustrated-introduction";
import { ContextHelp } from "@/components/ui/context-help";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { canBrowseGroupSessions } from "@/features/group-sessions/group-sessions-access";

const pathwayLink = "inline-flex min-h-11 items-center font-semibold text-brand underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus";

export function StudentBookingPathways({ illustration }: { illustration?: string }) {
  const { user } = usePortalSession();
  const group = canBrowseGroupSessions(user);
  const fixed = user.capabilities.includes("appointments.view_self") && user.capabilities.includes("services.catalog.view");
  return (
    <section aria-labelledby="booking-pathways-heading" className="mb-5">
      <IllustratedIntroduction src={illustration} edgeFade>
        <div className="flex flex-wrap items-center gap-x-2">
          <h2 id="booking-pathways-heading" className="font-heading text-lg font-semibold text-ink">Ways to get support</h2>
          <ContextHelp title="Choosing a booking" sections={[
            { heading: "Appointments", content: <p>Choose an individual time with a counselor, or select a scheduled slot published by the office. The times shown are checked before booking.</p> },
            { heading: "Group sessions", content: <p>Group activities have their own registration and capacity. A published session may not be open to every student.</p> },
            { heading: "After booking", content: <p>Find individual appointments in My appointments and group activities in My Registrations. If a result cannot be confirmed, check your records before trying again.</p> },
          ]} />
        </div>
        <p className="mt-1 text-sm text-muted">Choose how you would like to meet. Times and registration depend on current schedules and eligibility.</p>
        <nav aria-label="Booking and registrations" className="mt-1 flex flex-wrap items-center gap-x-5">
          <a href="#booking-service-heading" className={pathwayLink}>Find an appointment</a>
          {fixed ? <Link href="/portal/appointments/book?pathway=FIXED_DATE_SLOT" className={pathwayLink}>View scheduled slots</Link> : <p className="py-2 text-sm text-muted">Scheduled slot browsing is unavailable to this account.</p>}
          {group ? <Link href="/portal/group-sessions/discover" className={pathwayLink}>Browse group sessions</Link> : <p className="py-2 text-sm text-muted">Group session browsing is unavailable to this account.</p>}
          {group && user.capabilities.includes("appointments.view_self") ? <Link className={pathwayLink} href="/portal/group-sessions/my">My Registrations</Link> : null}
        </nav>
      </IllustratedIntroduction>
    </section>
  );
}
