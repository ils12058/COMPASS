import type { LucideIcon } from "lucide-react";
import Link from "next/link";

// Compact icon + label navigation for a named section; never a consequential command.
export function SectionLink({ href, label, accessibleLabel = label, icon: Icon }: {
  href: string; label: string; accessibleLabel?: string; icon: LucideIcon;
}) {
  return <Link href={href} aria-label={accessibleLabel} className="inline-flex min-h-11 max-w-full items-center gap-2 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
    <Icon size={16} aria-hidden="true" /><span>{label}</span>
  </Link>;
}
