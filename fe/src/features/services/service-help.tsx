"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const serviceHelpSections: readonly HelpSection[] = [
  { heading: "Appointment booking", content: "Available allows students to book when the Service, counselor availability, and booking requirements permit. Duration, cancellation cutoff, and Inventory requirements apply to new Appointments; existing Appointments keep their saved settings." },
  { heading: "Delivery", content: "An active Service needs at least one delivery mode. Removing a mode stops new work in that mode. Existing Appointments keep their saved mode. Changes that affect scheduled work require a consequence review." },
  { heading: "Provider coverage", content: "All active Counselors permits any active Counselor to provide new work. Selected Counselors limits new work to those selected. College responsibility supplies default routing; it does not restrict student choice to one College counselor." },
  { heading: "Required Counseling Service", content: "Counseling also supports Routine Interviews and E-Counseling and must stay active. Other settings can be changed." },
  { heading: "Online counseling", content: "Scheduled Online Counseling appointments use E-Counseling. Enabling Online delivery permits scheduling; video availability still depends on separate video-service settings." },
];

export function ServiceHelp({ counseling = false }: { counseling?: boolean }) {
  const sections = counseling ? serviceHelpSections : serviceHelpSections.filter((section) => section.heading !== "Required Counseling Service" && section.heading !== "Online counseling");
  return <ContextHelp title="About Service configuration" sections={sections} />;
}
