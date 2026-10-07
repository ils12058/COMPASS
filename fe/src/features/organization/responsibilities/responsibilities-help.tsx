"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const responsibilitiesHelpSections: readonly HelpSection[] = [
  { heading: "Default routing", content: "One responsible Counselor may be assigned to each College. When none is assigned, routing uses the Head Guidance Counselor only when exactly one active Head Guidance Counselor can be identified." },
  { heading: "Confidential records", content: "Responsibility determines default institutional routing. It does not automatically grant blanket access to confidential records." },
  { heading: "Staff supervision", content: "Guidance Services Staff inherit their supervising counselor's assigned College responsibilities, or institution-wide responsibilities when the supervisor holds them. Changing or removing a supervisor changes this scope." },
];

export function ResponsibilitiesHelp() {
  return <ContextHelp title="About Responsibilities" sections={responsibilitiesHelpSections} />;
}
