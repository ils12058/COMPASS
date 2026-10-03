"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";

export function PlatformNavigation() {
  const pathname = usePathname();
  const links = [
    ["/portal/platform/health", "Health"],
    ["/portal/platform/maintenance", "Maintenance"],
    ["/portal/platform/email-delivery", "Email delivery"],
    ["/portal/platform/environment", "Environment"],
    ["/portal/platform/activity", "Technical activity"],
  ] as const;

  return (
    <WorkspaceTabs label="Platform Operations navigation">
      {links.map(([href, label]) => {
        const current = pathname === href;
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
