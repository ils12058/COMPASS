"use client";

import Link from "next/link";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";

// The footer's account link follows the same session check as the site header and hero.
export function FooterAccountLink({ className }: { className: string }) {
  const session = useAuthGetSession({ query: { retry: false, staleTime: 60_000 } });
  const authenticated = session.isSuccess && session.data.data.authenticated;

  return (
    <Link className={className} href={authenticated ? "/portal" : "/login"}>
      {authenticated ? "Open COMPASS" : "Sign in"}
    </Link>
  );
}
