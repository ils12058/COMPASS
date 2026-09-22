"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { userRoleLabel } from "@/features/portal/components/portal-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { AccountAvatar, accountDisplayName } from "@/features/account/components/account-avatar";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthLogout } from "@/lib/api/generated/auth/auth";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";

export function PortalUserMenu() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const logout = useAuthLogout();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;
  const name = accountDisplayName(user, profile);

  function finishLogout() {
    queryClient.clear();
    router.replace("/");
  }

  async function signOut() {
    setError(null);
    try {
      await logout.mutateAsync();
      finishLogout();
    } catch (caught) {
      if (caught instanceof CompassApiError && caught.status === 401) {
        finishLogout();
        return;
      }
      setError(authErrorMessage(caught, "Sign out could not be completed. Please try again."));
    }
  }

  return (
    <div className="flex flex-col items-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Open user menu for ${name}`}
            className="inline-flex min-h-11 items-center gap-2 rounded-md px-3 text-left text-sm hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <AccountAvatar user={user} profile={profile} />
            <span className="hidden sm:block">
              <span className="block font-semibold text-ink">{name}</span>
              <span className="block text-xs text-muted">{userRoleLabel(user.role)}</span>
            </span>
            <ChevronDown size={17} aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>
            <span className="flex items-center gap-3">
              <AccountAvatar user={user} profile={profile} />
              <span>
                <span className="block text-sm font-semibold text-ink">{name}</span>
                <span className="block text-xs font-normal text-muted">{userRoleLabel(user.role)}</span>
                <span className="mt-1 block text-xs font-normal text-muted">{user.email}</span>
              </span>
            </span>
          </DropdownMenuLabel>
          <DropdownMenuItem asChild>
            <Link href="/portal/account/profile">
              <UserRound size={17} className="mr-2" aria-hidden="true" />
              Account
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator className="my-1 h-px bg-border" />
          <DropdownMenuItem disabled={logout.isPending} onSelect={() => void signOut()}>
            <LogOut size={17} className="mr-2" aria-hidden="true" />
            {logout.isPending ? "Signing out…" : "Sign out"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {error ? <p role="alert" className="mt-1 max-w-xs text-right text-xs text-danger">{error}</p> : null}
    </div>
  );
}
