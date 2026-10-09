"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const responsibilitiesHelpSections: readonly HelpSection[] = [
  { heading: "Default routing", content: "One responsible Counselor may be assigned to each College. When none is assigned, routing uses the Head Guidance Counselor only when exactly one active Head Guidance Counselor can be identified." },
  { heading: "Confidential records", content: "Responsibility determines default institutional routing. It does not automatically grant blanket access to confidential records." },
  { heading: "Staff supervision", content: "Guidance Services Staff handle their supervisor's assigned Colleges. Under Head Guidance, this also includes Colleges routed to the unique active Head when no valid Counselor is assigned. Staff do not inherit Head oversight authority. Changing or removing a supervisor changes their handled scope." },
];

export function ResponsibilitiesHelp() {
  return <ContextHelp title="About Responsibilities" sections={responsibilitiesHelpSections} />;
}
