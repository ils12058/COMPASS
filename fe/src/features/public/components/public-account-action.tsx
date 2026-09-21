"use client";

import Link from "next/link";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { cn } from "@/lib/utils/cn";

export function PublicAccountAction({
  className,
  prominence = "primary",
}: {
  className?: string;
  prominence?: "primary" | "outline";
}) {
  const session = useAuthGetSession({
    query: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 60_000,
    },
  });

  const authenticated = session.data?.data.authenticated === true;
  const href = authenticated ? "/portal" : "/login";
  const label = authenticated ? "Open COMPASS" : "Sign in";

  return (
    <Link
      href={href}
      className={cn(
        "inline-flex min-h-10 items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold no-underline transition-colors",
        prominence === "primary"
          ? "bg-primary text-primary-foreground hover:bg-[var(--compass-brand-maroon-strong)]"
          : "border bg-card text-foreground hover:bg-muted",
        className,
      )}
    >
      {label}
    </Link>
  );
}
