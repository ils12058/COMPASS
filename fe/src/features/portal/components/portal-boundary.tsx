"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { loginPathForPortal, safePortalDestination } from "@/features/auth/utils/redirect";
import { UnsavedChangesProvider } from "@/features/form-safety/unsaved-changes-provider";
import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { PortalSessionProvider } from "@/features/portal/components/portal-session";
import { PortalSessionLoading } from "@/features/portal/components/portal-session-loading";
import { PortalShell } from "@/features/portal/components/portal-shell";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { requestSessionRevalidation, subscribeSessionRevalidation } from "@/lib/auth/session-revalidation";

export function PortalBoundary({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const session = useAuthGetSession({ query: { retry: false } });
  const [verificationRequired, setVerificationRequired] = useState(false);
  const verifying = useRef(false);
  const cleared = useRef(false);
  const currentSession = session.data?.data?.session;
  const invalidProjection = session.isSuccess && !currentSession;
  const currentPath = safePortalDestination(
    `${pathname}${searchParams.size > 0 ? `?${searchParams.toString()}` : ""}`,
  );
  const confirmedSignedOut =
    session.isError && session.error instanceof CompassApiError && session.error.status === 401;

  const verifySession = useCallback(async (failClosed: boolean) => {
    if (failClosed) setVerificationRequired(true);
    if (verifying.current) return;
    verifying.current = true;
    try {
      const result = await session.refetch();
      if (result.isSuccess && result.data?.data?.session) setVerificationRequired(false);
    } finally {
      verifying.current = false;
    }
  }, [session]);

  useEffect(() => subscribeSessionRevalidation((reason) => {
    void verifySession(reason === "session");
  }), [verifySession]);

  useServerBoundary({
    boundary: currentSession?.expires_at,
    serverDate: session.data?.headers.date,
    receivedAt: session.dataUpdatedAt,
    onBoundary: () => requestSessionRevalidation("session"),
  });

  useEffect(() => {
    if (!confirmedSignedOut) return;
    if (!cleared.current) {
      cleared.current = true;
      queryClient.clear();
    }
    router.replace(loginPathForPortal(currentPath));
  }, [confirmedSignedOut, currentPath, queryClient, router]);

  if (session.isPending || confirmedSignedOut || (verificationRequired && session.isFetching)) {
    return <PortalSessionLoading />;
  }

  if (session.isError || verificationRequired || invalidProjection || !session.data?.data) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-lg items-center px-5">
        <section role="alert" className="border-y border-border py-7">
          <h1 className="font-heading text-3xl font-bold text-ink">We could not verify your session.</h1>
          <p className="mt-3 text-sm leading-6 text-muted">
            We could not check your session, so this page cannot be shown yet.
          </p>
          <Button className="mt-5" variant="secondary" onClick={() => void verifySession(true)}>
            Retry
          </Button>
        </section>
      </main>
    );
  }

  return (
    <PortalSessionProvider value={session.data.data}>
      <UnsavedChangesProvider>
        <PortalShell>{children}</PortalShell>
      </UnsavedChangesProvider>
    </PortalSessionProvider>
  );
}
