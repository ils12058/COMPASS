"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";

const sections = [
  { href: "/portal/account/profile", label: "Profile" },
  { href: "/portal/account/security", label: "Security" },
  { href: "/portal/account/activity", label: "Activity" },
  { href: "/portal/account/preferences", label: "Preferences" },
  { href: "/portal/account/privacy", label: "Privacy" },
] as const;

export function AccountNavigation() {
  const pathname = usePathname();

  // No label above the tabs: the page title below names the section, as in the other workspaces.
  return (
    <WorkspaceTabs label="Account navigation">
      {sections.map(({ href, label }) => {
        const current = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={workspaceTabClass(current)}
          >
            {label}
          </Link>
        );
      })}
    </WorkspaceTabs>
  );
}
