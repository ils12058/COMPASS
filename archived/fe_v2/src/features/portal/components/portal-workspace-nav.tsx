import Link from "next/link";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export type PortalWorkspaceNavItem = {
  href: string;
  label: string;
  value: string;
  icon?: LucideIcon;
};

export function PortalWorkspaceNav({
  activeValue,
  ariaLabel,
  items,
}: {
  activeValue: string;
  ariaLabel: string;
  items: readonly PortalWorkspaceNavItem[];
}) {
  return (
    <nav
      aria-label={ariaLabel}
      className="min-w-0 overflow-x-auto rounded-3xl border border-[var(--compass-border)] bg-card p-2 shadow-sm lg:sticky lg:top-6 lg:overflow-visible"
    >
      <ul className="flex w-max min-w-full gap-1 lg:grid lg:w-auto lg:min-w-0">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = item.value === activeValue;

          return (
            <li key={item.value} className="min-w-[9rem] flex-1 lg:min-w-0">
              <Link
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "group flex min-h-12 items-center gap-3 rounded-2xl border-b-2 px-3 py-2 text-sm font-semibold transition-colors lg:border-b-0 lg:border-l-4",
                  isActive
                    ? "border-[var(--compass-brand-gold)] bg-[var(--compass-support-soft)] text-[var(--compass-support-strong)] lg:border-l-[var(--compass-brand-maroon)]"
                    : "border-transparent text-muted-foreground hover:bg-[var(--compass-surface-subtle)] hover:text-foreground",
                )}
              >
                {Icon ? (
                  <Icon
                    aria-hidden="true"
                    className={cn(
                      "size-4 shrink-0",
                      isActive
                        ? "text-[var(--compass-brand-maroon)]"
                        : "text-muted-foreground group-hover:text-foreground",
                    )}
                  />
                ) : null}
                <span className="whitespace-nowrap">{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
