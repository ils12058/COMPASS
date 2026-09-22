"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { loginPathForPortal, safePortalDestination } from "@/features/auth/utils/redirect";
import { PortalSessionProvider } from "@/features/portal/components/portal-session";
import { PortalShell } from "@/features/portal/components/portal-shell";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";

export function PortalBoundary({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const session = useAuthGetSession({ query: { retry: false } });
  const currentPath = safePortalDestination(
    `${pathname}${searchParams.size > 0 ? `?${searchParams.toString()}` : ""}`,
  );
  const confirmedSignedOut =
    session.isError && session.error instanceof CompassApiError && session.error.status === 401;

  useEffect(() => {
    if (confirmedSignedOut) router.replace(loginPathForPortal(currentPath));
  }, [confirmedSignedOut, currentPath, router]);

  if (session.isPending || confirmedSignedOut) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-md items-center px-5" aria-busy="true">
        <div className="w-full">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="mt-4 h-5 w-full" />
          <p className="sr-only">Checking your session…</p>
        </div>
      </main>
    );
  }

  if (session.isError) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-lg items-center px-5">
        <section role="alert" className="border-y border-border py-7">
          <h1 className="font-heading text-3xl font-bold text-ink">We could not verify your session.</h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            Protected COMPASS content remains unavailable until the session check succeeds.
          </p>
          <Button className="mt-5" variant="secondary" onClick={() => void session.refetch()}>
            Retry
          </Button>
        </section>
      </main>
    );
  }

  return (
    <PortalSessionProvider value={session.data.data}>
      <PortalShell>{children}</PortalShell>
    </PortalSessionProvider>
  );
}
