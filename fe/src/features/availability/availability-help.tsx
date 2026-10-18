"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function AvailabilityHelp({ office = false }: { office?: boolean }) {
  return <ContextHelp title={office ? "Office and Counselor availability" : "Counselor availability"} sections={[
    { heading: "Weekly hours and unavailable dates", content: <p>Weekly hours set the usual schedule. Add unavailable dates for leave, closures or other time away. Existing appointments remain scheduled when hours change.</p> },
    { heading: "Bookable times", content: <p>Flexible appointments use both Office and Counselor hours, unavailable dates, Service rules and delivery mode. Fixed-date slots are checked against availability when scheduled. Group Sessions use their own event schedule.</p> },
    ...(office ? [{ heading: "Managing a Counselor’s schedule", content: <p>Choose a Counselor to review their weekly hours and unavailable dates. Schedule management is available to the Head Guidance Counselor, IT Administrators and staff assigned this responsibility.</p> }] : []),
  ]} />;
}
