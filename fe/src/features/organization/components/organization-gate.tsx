"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";

function Unavailable({ management = false }: { management?: boolean }) {
  return (
    <section
      aria-labelledby="organization-denied-heading"
      className="max-w-xl border-y border-border py-8"
    >
      <h1
        id="organization-denied-heading"
        className="font-heading text-3xl font-bold text-ink"
      >
        Organization unavailable
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        {management
          ? "Your current access does not include Organization management."
          : "Your current access does not include Organization functionality."}
      </p>
      <Link
        className="mt-5 inline-block text-sm font-semibold text-brand underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        href="/portal"
      >
        Return to Home
      </Link>
    </section>
  );
}

export function OrganizationGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  const allowed =
    user.capabilities.includes("organization.view") ||
    user.capabilities.includes("organization.manage");
  return allowed ? children : <Unavailable />;
}

export function OrganizationManageGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  return user.capabilities.includes("organization.manage") ? (
    children
  ) : (
    <Unavailable management />
  );
}
