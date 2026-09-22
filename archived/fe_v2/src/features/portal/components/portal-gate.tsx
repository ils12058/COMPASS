"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { PortalShell } from "@/features/portal/components/portal-shell";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { CompassApiError } from "@/lib/api/client";
import { getApiRequestReference } from "@/lib/api/request-reference";
import { SystemErrorPage } from "@/features/system/components/system-error-page";

function PortalGateLoading() {
  return (
    <main className="grid min-h-screen place-items-center bg-[var(--compass-surface-muted)] px-5 py-12">
      <section
        className="w-full max-w-md rounded-3xl border bg-card p-8 text-center shadow-sm"
        aria-live="polite"
      >
        <div
          className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-[var(--compass-brand-maroon)] text-xl font-bold text-white"
          aria-hidden="true"
        >
          C
        </div>
        <p className="mt-5 font-heading text-xl font-bold">Opening your workspace</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Checking your COMPASS sign-in so we can show the right tools for you.
        </p>
      </section>
    </main>
  );
}

export function PortalGate({ children }: { children: ReactNode }) {
  const pathname = usePathname() ?? "/portal";
  const router = useRouter();
  const sessionQuery = useAuthGetSession({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const session = sessionQuery.data?.data;
  const isUnauthorized =
    sessionQuery.error instanceof CompassApiError &&
    sessionQuery.error.status === 401;
  const isUnauthenticated = session !== undefined && !session.authenticated;

  useEffect(() => {
    if (!isUnauthorized && !isUnauthenticated) {
      return;
    }

    router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [isUnauthenticated, isUnauthorized, pathname, router]);

  if (sessionQuery.isPending || isUnauthorized || isUnauthenticated) {
    return <PortalGateLoading />;
  }

  if (sessionQuery.isError || !session) {
    return (
      <SystemErrorPage
        code="We couldn’t check your sign-in"
        title="Your workspace is unavailable right now."
        description="Please try again. If the problem continues, return to COMPASS and try signing in again."
        requestReference={getApiRequestReference(sessionQuery.error)}
        primaryAction={
          <Button onClick={() => void sessionQuery.refetch()}>Try again</Button>
        }
      />
    );
  }

  return <PortalShell session={session}>{children}</PortalShell>;
}
