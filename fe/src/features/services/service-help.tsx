"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const serviceHelpSections: readonly HelpSection[] = [
  { heading: "Booking pathways", content: "Flexible Appointments use Counselor Availability; staff publish Appointment slots for specific times. Group Sessions have separate registration and attendance, and enabling a pathway does not publish slots or events." },
  { heading: "Appointment booking", content: "Flexible Appointment settings apply only to flexible Appointments. Duration, cancellation cutoff, and Individual Inventory requirements apply to new Appointments; existing Appointments keep their saved settings." },
  { heading: "Delivery", content: "An active Service needs at least one delivery mode; removing a mode stops new work in that mode, while existing Appointments keep their saved mode. Review any changes that affect scheduled work before saving." },
  { heading: "Who provides this Service", content: "Choose all active Counselors or only selected Counselors for new work. College responsibility sets the default Counselor; Students can choose another listed Counselor." },
  { heading: "Required Counseling Service", content: "Counseling also supports Routine Interviews and E-Counseling and must stay active. Other settings can be changed." },
  { heading: "Online counseling", content: "Enabling E-Counseling allows you to schedule online Appointments. Video calls also need the video calling to be set up." },
];

export function ServiceHelp({ counseling = false }: { counseling?: boolean }) {
  const sections = counseling ? serviceHelpSections : serviceHelpSections.filter((section) => section.heading !== "Required Counseling Service" && section.heading !== "Online counseling");
  return <ContextHelp title="About Service configuration" sections={sections.map((section) => ({ ...section, heading: section.heading.replace("Online counseling", "E-Counseling") }))} />;
}
