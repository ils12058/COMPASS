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
  containerResponsive = false,
}: {
  user: UserSummary;
  profile?: MyProfileResponse;
  // A sign-out failure, shown under the trigger.
  error?: string | null;
  // DropdownMenuItem and DropdownMenuSeparator elements.
  children: ReactNode;
  containerResponsive?: boolean;
}) {
  const name = accountDisplayName(user, profile);
  const role = userRoleLabel(user.role);

  return (
    <div className="flex min-w-0 flex-col items-end">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Open user menu for ${name}`}
            className={`inline-flex min-h-11 min-w-0 max-w-full items-center gap-2 rounded-md px-2 text-left text-sm hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus sm:px-3 ${containerResponsive ? "@max-[16rem]:px-1" : ""}`}
          >
            <AccountAvatar user={user} profile={profile} />
            <span className={`hidden min-w-0 max-w-[min(12rem,calc(100vw-4rem))] ${containerResponsive ? "@min-[42rem]:block" : "sm:block"}`}>
              <span className="block truncate font-semibold text-ink">{name}</span>
              <span className="block break-words text-xs leading-5 text-muted">{role}</span>
            </span>
            <ChevronDown size={17} aria-hidden="true" className={containerResponsive ? "shrink-0 @max-[16rem]:hidden" : "shrink-0"} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="max-h-[var(--radix-dropdown-menu-content-available-height)] min-w-[min(14rem,calc(100vw-2rem))] w-[min(20rem,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] overflow-y-auto"
        >
          <DropdownMenuLabel>
            <span className="flex min-w-0 flex-wrap items-start gap-3">
              <AccountAvatar user={user} profile={profile} />
              <span className="min-w-0 flex-1 basis-40 [overflow-wrap:anywhere]">
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
