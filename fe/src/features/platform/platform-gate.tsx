"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";

export function hasPlatformView(user: { capabilities: string[] }): boolean {
  return user.capabilities.includes("platform_operations.view");
}

export function hasPlatformManage(user: { capabilities: string[] }): boolean {
  return user.capabilities.includes("platform_operations.manage");
}

export function PlatformGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();

  if (hasPlatformView(user)) return children;

  return (
    <section
      aria-labelledby="platform-unavailable-heading"
      className="max-w-xl border-y border-border py-8"
    >
      <h1
        id="platform-unavailable-heading"
        className="font-heading text-3xl font-bold text-ink"
      >
        Platform Operations unavailable
      </h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        Your current access does not include Platform Operations.
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
