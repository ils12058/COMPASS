"use client";

import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { CurrentAuthProvider } from "@/features/auth/hooks/use-current-auth";
import { CompassApiError } from "@/lib/api/client";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";

export function PortalAuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const sessionQuery = useAuthGetSession({
    query: {
      retry: false,
      refetchOnWindowFocus: true,
    },
  });

  const unauthenticated =
    sessionQuery.error instanceof CompassApiError && sessionQuery.error.status === 401;

  useEffect(() => {
    if (!unauthenticated) {
      return;
    }

    const next = pathname || "/portal";
    router.replace(`/login?next=${encodeURIComponent(next)}`);
  }, [pathname, router, unauthenticated]);

  if (sessionQuery.isPending || unauthenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center px-5">
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
          {unauthenticated ? "Returning to sign in…" : "Checking your COMPASS session…"}
        </p>
      </main>
    );
  }

  if (sessionQuery.isError || !sessionQuery.data?.data.authenticated) {
    return (
      <main className="flex min-h-screen items-center justify-center px-5">
        <section className="w-full max-w-md rounded-xl border bg-card p-6 text-center shadow-sm">
          <h1 className="font-heading text-2xl font-bold">COMPASS is unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Your session could not be checked right now. This is different from being signed out.
          </p>
          <Button className="mt-5" onClick={() => sessionQuery.refetch()}>
            Try again
          </Button>
        </section>
      </main>
    );
  }

  return (
    <CurrentAuthProvider session={sessionQuery.data.data}>
      {children}
    </CurrentAuthProvider>
  );
}
