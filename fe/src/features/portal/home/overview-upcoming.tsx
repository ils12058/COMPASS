import Link from "next/link";

import type { OverviewUpcomingItem } from "@/features/portal/home/overview-presentation";

export function OverviewUpcoming({ items }: { items: OverviewUpcomingItem[] }) {
  if (items.length === 0) return null;

  return (
    <section className="mt-8 border-t border-border pt-6" aria-labelledby="overview-upcoming-heading">
      <h2 id="overview-upcoming-heading" className="font-heading text-xl font-semibold text-ink">
        Upcoming
      </h2>
      <ul className="mt-3 divide-y divide-border border-y border-border">
        {items.map((item, index) => (
          <li
            key={item.href + "-" + index}
            className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <p className="text-sm leading-6 text-ink">{item.message}</p>
            <Link
              href={item.href}
              className="inline-flex min-h-10 items-center self-start rounded-sm text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:self-auto"
            >
              {item.linkLabel} <span aria-hidden="true" className="ml-1">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
