"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useCurrentAuth } from "@/features/auth/hooks/use-current-auth";

export function CapabilityGate({
  capability,
  children,
}: {
  capability: string;
  children: ReactNode;
}) {
  const { hasCapability } = useCurrentAuth();

  if (!hasCapability(capability)) {
    return (
      <section className="mx-auto max-w-xl rounded-xl border bg-card p-6 text-center shadow-sm">
        <h1 className="font-heading text-2xl font-bold">This area is unavailable</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Content management for this area is not available to your account.
        </p>
        <Link
          href="/portal/content"
          className="mt-5 inline-flex min-h-10 items-center rounded-lg border bg-card px-4 py-2 text-sm font-semibold no-underline hover:bg-muted"
        >
          Back to Content
        </Link>
      </section>
    );
  }

  return children;
}
