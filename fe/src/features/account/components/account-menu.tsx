"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AccountAvatar, accountDisplayName } from "@/features/account/components/account-avatar";
import { userRoleLabel } from "@/features/portal/components/portal-presentation";
import type { MyProfileResponse, UserSummary } from "@/lib/api/generated/model";

// The signed-in person's menu: their photo or initials and name, opening onto the account actions
// the surrounding shell supplies. The portal top bar and the public site header both use it, so a
// signed-in reader finds the same control in both places.
export function AccountMenu({
  user,
  profile,
  error,
  children,
}: {
  user: UserSummary;
  profile?: MyProfileResponse;
  // A sign-out failure, shown under the trigger.
  error?: string | null;
  // DropdownMenuItem and DropdownMenuSeparator elements.
  children: ReactNode;
}) {
  const name = accountDisplayName(user, profile);
  const role = userRoleLabel(user.role);

  return (
    <div className="flex flex-col items-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Open user menu for ${name}`}
            className="inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-left text-sm hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:px-3"
          >
            <AccountAvatar user={user} profile={profile} />
            <span className="hidden max-w-48 sm:block">
              <span className="block truncate font-semibold text-ink">{name}</span>
              <span className="block truncate text-xs text-muted">{role}</span>
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
                <span className="block text-xs font-normal text-muted">{role}</span>
                <span className="mt-1 block text-xs font-normal text-muted">{user.email}</span>
              </span>
            </span>
          </DropdownMenuLabel>
          {children}
        </DropdownMenuContent>
      </DropdownMenu>
      {error ? <p role="alert" className="mt-1 max-w-xs text-right text-xs text-danger">{error}</p> : null}
    </div>
  );
}
