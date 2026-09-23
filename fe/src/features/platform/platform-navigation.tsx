"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function PlatformNavigation() {
  const pathname = usePathname();
  const links = [
    ["/portal/platform/health", "Health"],
    ["/portal/platform/maintenance", "Maintenance"],
    ["/portal/platform/email-delivery", "Email delivery"],
    ["/portal/platform/environment", "Environment"],
    ["/portal/platform/activity", "Technical activity"],
    ["/portal/platform/commands", "Operator commands"],
  ] as const;

  return (
    <nav aria-label="Platform Operations" className="mb-8 border-b border-border">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {links.map(([href, label]) => {
          const current = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={current ? "page" : undefined}
              className={`inline-flex min-h-10 items-center border-b-2 px-1 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                current
                  ? "border-brand text-brand"
                  : "border-transparent text-muted hover:text-ink"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
