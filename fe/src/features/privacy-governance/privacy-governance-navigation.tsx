"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  WorkspaceTabs,
  workspaceTabClass,
} from "@/components/ui/workspace-tabs";
import { usePortalSession } from "@/features/portal/components/portal-session";
import {
  canViewPrivacyGovernance,
  canViewRetention,
} from "./privacy-governance-access";

const links: { href: string; label: string; related?: string }[] = [
  {
    href: "/portal/privacy/notices",
    label: "Privacy Notices",
    related: "/portal/privacy/notice-revisions",
  },
  { href: "/portal/privacy/retention", label: "Retention & Disposition" },
  { href: "/portal/privacy/activity", label: "Privacy & Security Activity" },
];

function isWithin(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

export function PrivacyGovernanceNavigation() {
  const pathname = usePathname();
  const { user } = usePortalSession();

  return (
    <WorkspaceTabs label="Privacy Governance navigation">
      {links
        .filter(({ href }) =>
          href === "/portal/privacy/retention"
            ? canViewRetention(user)
            : canViewPrivacyGovernance(user),
        )
        .map(({ href, label, related }) => {
          const current =
            isWithin(pathname, href) ||
            (related !== undefined && isWithin(pathname, related));
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
