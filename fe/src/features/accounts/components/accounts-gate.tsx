"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { usePortalSession } from "@/features/portal/components/portal-session";

export function AccountsGate({ children }: { children: ReactNode }) {
  const { user } = usePortalSession();
  if (!user.capabilities.includes("accounts.manage")) {
    return (
      <section
        aria-labelledby="accounts-denied-heading"
        className="max-w-xl border-y border-border py-8"
      >
        <h1
          id="accounts-denied-heading"
          className="font-heading text-3xl font-bold text-ink"
        >
          Accounts unavailable
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted">
          Your current access does not include managed account administration.
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
  return children;
}
