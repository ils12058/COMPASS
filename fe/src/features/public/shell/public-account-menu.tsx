"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { AccountMenu } from "@/features/account/components/account-menu";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthLogout } from "@/lib/api/generated/auth/auth";
import type { UserSummary } from "@/lib/api/generated/model";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";

// The signed-in reader's menu on the public site. Signing out keeps the reader on the page they
// are reading; resetting the cached queries drops their account data and refetches the session,
// so the header returns to "Sign in".
export function PublicAccountMenu({ user }: { user: UserSummary }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const logout = useAuthLogout();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;

  async function signOut() {
    setError(null);
    try {
      await logout.mutateAsync();
    } catch (caught) {
      if (!(caught instanceof CompassApiError && caught.status === 401)) {
        setError(authErrorMessage(caught, "Sign out could not be completed. Please try again."));
        return;
      }
    }
    await queryClient.resetQueries();
  }

  return (
    <AccountMenu user={user} profile={profile} error={error}>
      <DropdownMenuItem asChild>
        <Link href="/portal">
          <LayoutDashboard size={17} className="mr-2" aria-hidden="true" />
          Open COMPASS
        </Link>
      </DropdownMenuItem>
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
    </AccountMenu>
  );
}
