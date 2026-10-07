"use client";

import { ContextHelp, type HelpSection } from "@/components/ui/context-help";

export const platformHelpSections: readonly HelpSection[] = [
  { heading: "Health checks", content: "Passive Health covers only the dependencies listed in its result. It does not establish worker, scheduler, Daily.co, or Turnstile runtime reachability." },
  { heading: "Background worker", content: "The on-demand check runs a harmless queued task to verify that a worker can receive and complete it. Its result belongs to this page session." },
  { heading: "Environment", content: "These are resolved non-secret settings, not raw environment variables. Configuration does not prove external service reachability. Startup-only settings need a restart before changes take effect." },
];

export function PlatformHelp({ startupLimitation }: { startupLimitation?: string }) {
  const sections = startupLimitation ? [...platformHelpSections, { heading: "Startup settings", content: startupLimitation }] : platformHelpSections;
  return <ContextHelp title="About Platform diagnostics" sections={sections} />;
}
