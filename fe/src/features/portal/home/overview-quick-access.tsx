import Link from "next/link";

import type { OverviewQuickAccessLink } from "@/features/portal/home/overview-presentation";

export function OverviewQuickAccess({ links }: { links: OverviewQuickAccessLink[] }) {
  if (links.length === 0) return null;

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-quick-access-heading">
      <h2 id="overview-quick-access-heading" className="font-heading text-xl font-semibold text-ink">
        Quick access
      </h2>
      <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {links.map((link) => (
          <li key={link.href}>
            <Link
              href={link.href}
              className="flex min-h-11 items-center border border-border bg-surface-raised px-3 text-sm font-semibold text-ink hover:border-border-strong hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
