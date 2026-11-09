"use client";

import { ContextHelp } from "@/components/ui/context-help";

export function AvailabilityHelp({ office = false }: { office?: boolean }) {
  return <ContextHelp title={office ? "Office and Counselor Availability" : "Counselor Availability"} sections={[
    { heading: "Weekly hours and time off", content: <p>Weekly hours set the usual schedule. Add time off for leave, closures or other time away. Existing Appointments remain scheduled when hours change.</p> },
    { heading: "Bookable times", content: <p>Flexible Appointments use both Office and Counselor hours, time off, Service rules and delivery mode. Fixed-date slots are checked against Availability when scheduled. Group Sessions use their own event schedule.</p> },
    ...(office ? [{ heading: "Managing a Counselor’s schedule", content: <p>Choose a Counselor to review their weekly hours and time off. Schedule management is available to the Head Guidance Counselor, IT Administrators and staff assigned this responsibility.</p> }] : []),
  ]} />;
}
