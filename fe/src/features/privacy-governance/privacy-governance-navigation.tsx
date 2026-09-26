"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links: { href: string; label: string; related?: string }[] = [
  { href: "/portal/privacy/processing-activities", label: "Processing Activities" },
  { href: "/portal/privacy/reviews", label: "Reviews & PIAs" },
  {
    href: "/portal/privacy/notices",
    label: "Privacy Notices",
    related: "/portal/privacy/notice-revisions",
  },
  { href: "/portal/privacy/retention-policies", label: "Retention Policies" },
  { href: "/portal/privacy/incidents", label: "Incidents" },
  { href: "/portal/privacy/activity", label: "Privacy & Security Activity" },
];

function isWithin(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function PrivacyGovernanceNavigation() {
  const pathname = usePathname();

  return (
    <nav aria-label="Privacy Governance" className="mb-8 border-b border-border">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {links.map(({ href, label, related }) => {
          const current =
            isWithin(pathname, href) ||
            (related !== undefined && isWithin(pathname, related));
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
