"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const sections = [
  { href: "/portal/account/profile", label: "Profile" },
  { href: "/portal/account/security", label: "Security" },
  { href: "/portal/account/activity", label: "Activity" },
  { href: "/portal/account/preferences", label: "Preferences" },
  { href: "/portal/account/privacy", label: "Privacy" },
] as const;

export function AccountNavigation() {
  const pathname = usePathname();

  return (
    <div className="mb-8 border-b border-border">
      <p className="font-heading text-sm font-semibold text-brand">Account</p>
      <nav aria-label="Account" className="mt-4 flex flex-wrap gap-x-6 gap-y-1">
        {sections.map(({ href, label }) => {
          const current = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={href}
              href={href}
              aria-current={current ? "page" : undefined}
              className={`-mb-px inline-flex min-h-11 items-center border-b-2 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${current ? "border-brand text-brand" : "border-transparent text-muted hover:text-ink"}`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
