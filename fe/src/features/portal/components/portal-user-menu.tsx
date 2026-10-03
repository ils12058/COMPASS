"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { AccountMenu } from "@/features/account/components/account-menu";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthLogout } from "@/lib/api/generated/auth/auth";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";

export function PortalUserMenu() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const { confirmDiscard } = useUnsavedNavigation();
  const [error, setError] = useState<string | null>(null);
  const logout = useAuthLogout();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;

  function finishLogout() {
    queryClient.clear();
    router.replace("/");
  }

  async function signOut() {
    if (!confirmDiscard()) return;
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
    <AccountMenu user={user} profile={profile} error={error}>
      <DropdownMenuItem asChild>
        <GuardedPortalLink href="/portal/account/profile">
          <UserRound size={17} className="mr-2" aria-hidden="true" />
          Account
        </GuardedPortalLink>
      </DropdownMenuItem>
      <DropdownMenuSeparator className="my-1 h-px bg-border" />
      <DropdownMenuItem disabled={logout.isPending} onSelect={() => void signOut()}>
        <LogOut size={17} className="mr-2" aria-hidden="true" />
        {logout.isPending ? "Signing out…" : "Sign out"}
      </DropdownMenuItem>
    </AccountMenu>
  );
}
