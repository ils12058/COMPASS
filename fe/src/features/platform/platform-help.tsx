"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const platformHelpSections: readonly HelpSection[] = [
  { heading: "Health checks", content: "The health check covers only the connections listed in its result. It doesn't check the worker, scheduler, Daily.co or Turnstile." },
  { heading: "Background worker", content: "Run this check to see whether a worker can receive and complete a test task. The result stays on this page until you leave." },
  { heading: "Environment", content: "These settings show the current configuration without secrets; they don't confirm whether external services can be reached. Restart COMPASS to apply changes to settings loaded at startup." },
];

export function PlatformHelp({ startupLimitation }: { startupLimitation?: string }) {
  const sections = startupLimitation ? [...platformHelpSections, { heading: "Startup settings", content: startupLimitation }] : platformHelpSections;
  return <ContextHelp title="About Platform diagnostics" sections={sections} />;
}
