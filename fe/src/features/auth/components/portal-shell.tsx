"use client";

import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";

import { Button } from "@/components/ui/button";
import { useCurrentAuth } from "@/features/auth/hooks/use-current-auth";
import { roleLabel, userDisplayName } from "@/features/auth/utils/presentation";
import { clearCsrfToken } from "@/lib/api/csrf";
import { CompassApiError } from "@/lib/api/client";
import {
  getAuthGetMfaStatusQueryKey,
  getAuthGetSessionQueryKey,
  getAuthListSessionsQueryKey,
  getAuthListTrustedSessionsQueryKey,
  useAuthLogout,
} from "@/lib/api/generated/auth/auth";
import { cn } from "@/lib/utils/cn";

const NAVIGATION = [
  { href: "/portal", label: "Home" },
  { href: "/portal/account/security", label: "Account & Security" },
] as const;

export function PortalShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { session } = useCurrentAuth();
  const logout = useAuthLogout();
  const [error, setError] = useState<string | null>(null);

  async function finishLogout() {
    clearCsrfToken();
    queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
    queryClient.removeQueries({ queryKey: getAuthGetMfaStatusQueryKey() });
    queryClient.removeQueries({ queryKey: getAuthListSessionsQueryKey() });
    queryClient.removeQueries({ queryKey: getAuthListTrustedSessionsQueryKey() });
    router.replace("/login");
  }

  async function signOut() {
    setError(null);

    try {
      await logout.mutateAsync();
      await finishLogout();
    } catch (caught) {
      if (caught instanceof CompassApiError && caught.status === 401) {
        await finishLogout();
        return;
      }

      setError("Sign out could not be completed. Please try again.");
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-4 px-5 py-4 sm:px-8">
          <Link className="flex items-center gap-3 no-underline" href="/portal">
            <span className="flex items-center gap-2" aria-hidden="true">
              <Image
                src="/brand/ucn-logo.png"
                alt=""
                width={34}
                height={31}
              />
              <span className="h-7 w-px bg-border" />
              <Image
                src="/brand/compass-mark.svg"
                alt=""
                width={36}
                height={36}
                unoptimized
              />
            </span>
            <span>
              <span className="block font-heading text-lg font-bold text-foreground">COMPASS</span>
              <span className="block text-xs text-muted-foreground">
                University of Camarines Norte
              </span>
            </span>
          </Link>

          <nav className="order-3 flex w-full gap-1 sm:order-none sm:ml-4 sm:w-auto" aria-label="Portal">
            {NAVIGATION.map((item) => {
              const active =
                item.href === "/portal"
                  ? pathname === item.href
                  : pathname === item.href || pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm font-semibold no-underline",
                    active
                      ? "bg-accent text-accent-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            <div className="hidden text-right md:block">
              <p className="text-sm font-semibold">{userDisplayName(session.user)}</p>
              <p className="text-xs text-muted-foreground">{roleLabel(session.user.role)}</p>
            </div>
            <Button variant="outline" size="sm" onClick={signOut} disabled={logout.isPending}>
              {logout.isPending ? "Signing out…" : "Sign out"}
            </Button>
          </div>
        </div>

        {error ? (
          <div className="mx-auto w-full max-w-7xl px-5 pb-3 sm:px-8">
            <p role="alert" className="text-sm text-destructive">
              {error}
            </p>
          </div>
        ) : null}
      </header>

      <main className="mx-auto w-full max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}
