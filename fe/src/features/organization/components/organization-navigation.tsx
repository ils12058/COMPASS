"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { canViewOrganizationStructure } from "@/features/institution-configuration/institution-access";
import { usePortalSession } from "@/features/portal/components/portal-session";

function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const pathname = usePathname();
  const current = pathname === href;
  return (
    <Link
      href={href}
      aria-current={current ? "page" : undefined}
      className={`inline-flex min-h-10 items-center border-b-2 px-1 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
        current
          ? "border-brand text-brand"
          : "border-transparent text-muted hover:text-ink"
      }`}
    >
      {children}
    </Link>
  );
}

// Rendered inside OrganizationGate, so management tabs are always available.
export function OrganizationNavigation() {
  const { user } = usePortalSession();
  const canViewStructure = canViewOrganizationStructure(user);

  return (
    <div className="mb-8 border-b border-border">
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        {canViewStructure ? (
          <>
            <NavLink href="/portal/organization/campuses">Campuses</NavLink>
            <NavLink href="/portal/organization/colleges">Colleges</NavLink>
            <NavLink href="/portal/organization/programs">Programs</NavLink>
          </>
        ) : null}
        <NavLink href="/portal/organization/responsibilities">
          Responsibilities
        </NavLink>
        <NavLink href="/portal/organization/student-affiliations">
          Student affiliations
        </NavLink>
      </div>
    </div>
  );
}
