"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { canViewOrganizationStructure } from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { WorkspaceTabs, workspaceTabClass } from "@/components/ui/workspace-tabs";

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const pathname = usePathname();
  const current = pathname === href;
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={workspaceTabClass(current)}
    >
      {children}
    </Link>
  );
}

// Rendered inside OrganizationGate: reference structure is read-only, while relationship tabs remain manageable.
export function OrganizationNavigation() {
  const { user } = usePortalSession();
  const canViewStructure = canViewOrganizationStructure(user);

  return (
    <WorkspaceTabs label="Organization navigation">
      {canViewStructure ? (
        <NavLink href="/portal/organization">Structure</NavLink>
      ) : null}
      <NavLink href="/portal/organization/responsibilities">
        Responsibilities
      </NavLink>
      <NavLink href="/portal/organization/student-affiliations">
        Student affiliations
      </NavLink>
    </WorkspaceTabs>
  );
}
