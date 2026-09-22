"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut } from "lucide-react";
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
import { userDisplayName, userRoleLabel } from "@/features/portal/components/portal-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError } from "@/lib/api/errors";
import {
  getAuthGetSessionQueryKey,
  useAuthLogout,
} from "@/lib/api/generated/auth/auth";

export function PortalUserMenu() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const logout = useAuthLogout();
  const name = userDisplayName(user);

  function finishLogout() {
    queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
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
            className="inline-flex min-h-11 items-center gap-2 rounded-md px-3 text-left text-sm hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <span className="hidden sm:block">
              <span className="block font-semibold text-ink">{name}</span>
              <span className="block text-xs text-muted">{userRoleLabel(user.role)}</span>
            </span>
            <ChevronDown size={17} aria-hidden="true" />
            <span className="sr-only sm:hidden">Open user menu for {name}</span>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>
            <span className="block text-sm font-semibold text-ink">{name}</span>
            <span className="mt-1 block text-xs font-normal text-muted">{user.email}</span>
          </DropdownMenuLabel>
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
