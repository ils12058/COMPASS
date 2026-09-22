"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleUserRound,
  Ellipsis,
  LogOut,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  getAuthGetSessionQueryKey,
  useAuthLogout,
} from "@/lib/api/generated/auth/auth";
import {
  getNotificationsGetUnreadCountQueryKey,
  useNotificationsGetUnreadCount,
} from "@/lib/api/generated/notifications/notifications";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";
import type {
  CurrentSessionResponse,
  MyProfileResponse,
} from "@/lib/api/generated/model";
import { CompassApiError } from "@/lib/api/client";
import { friendlyAuthError } from "@/features/auth/utils/errors";
import {
  getPortalAccountName,
  getPortalInitials,
  getPortalRoleLabel,
  getPortalRoleLine,
} from "@/features/portal/portal-identity";
import {
  getVisiblePortalNavigation,
  isPortalNavigationItemActive,
  type PortalNavigationItem,
} from "@/features/portal/config";

const DESKTOP_NAV_LIMIT = 5;
const MOBILE_NAV_LIMIT = 2;

function notificationCountLabel(unreadCount: number | null) {
  if (!unreadCount || unreadCount < 1) {
    return null;
  }

  return unreadCount > 99 ? "99+" : String(unreadCount);
}

function getAccountDetails(
  session: CurrentSessionResponse,
  profile: MyProfileResponse | undefined,
) {
  const user = session.user;
  return {
    name: profile?.full_name || getPortalAccountName(user),
    email: profile?.email || user.email,
    initials: getPortalInitials(user),
    role: profile?.role
      ? getPortalRoleLabel(profile.role)
      : getPortalRoleLine(user),
    photoUrl: profile?.profile_photo_url ?? undefined,
  };
}

function PortalNavigationLink({
  item,
  pathname,
  unreadCount,
  onNavigate,
}: {
  item: PortalNavigationItem;
  pathname: string | null;
  unreadCount: number | null;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const isCurrent = isPortalNavigationItemActive(pathname, item.href);
  const countLabel =
    item.id === "notifications"
      ? notificationCountLabel(unreadCount)
      : null;
  const accessibleLabel = countLabel
    ? `${item.label}, ${unreadCount} unread`
    : item.label;

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={isCurrent ? "page" : undefined}
      aria-label={accessibleLabel}
      className={`relative inline-flex min-h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-sm font-semibold no-underline transition-colors ${
        isCurrent
          ? "bg-[var(--compass-surface-muted)] text-[var(--compass-brand-maroon-strong)]"
          : "text-[var(--compass-text-muted)] hover:bg-[var(--compass-surface-muted)] hover:text-[var(--compass-brand-maroon-strong)]"
      }`}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      <span>{item.label}</span>
      {countLabel ? (
        <span
          aria-hidden="true"
          className="inline-flex min-w-5 items-center justify-center rounded-full bg-[var(--compass-brand-maroon)] px-1.5 py-0.5 text-[0.65rem] font-bold leading-none text-white"
        >
          {countLabel}
        </span>
      ) : null}
      {isCurrent ? (
        <span
          aria-hidden="true"
          className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-[var(--compass-brand-gold)]"
        />
      ) : null}
    </Link>
  );
}

function PortalMoreMenu({
  items,
  pathname,
  unreadCount,
}: {
  items: readonly PortalNavigationItem[];
  pathname: string | null;
  unreadCount: number | null;
}) {
  if (!items.length) {
    return null;
  }

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className="min-h-10 rounded-xl px-3 text-sm font-semibold text-[var(--compass-text-muted)] hover:bg-[var(--compass-surface-muted)] hover:text-[var(--compass-brand-maroon-strong)]"
          aria-label="Open more portal destinations"
        >
          <Ellipsis aria-hidden="true" className="size-4" />
          <span>More</span>
          <ChevronDown aria-hidden="true" className="size-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side="top"
        align="start"
        sideOffset={12}
        className="w-64 rounded-2xl border-[var(--compass-border)] bg-[var(--compass-surface-raised)] p-2 shadow-[var(--compass-shadow-md)]"
      >
        {items.map((item) => {
          const Icon = item.icon;
          const isCurrent = isPortalNavigationItemActive(pathname, item.href);
          const countLabel =
            item.id === "notifications"
              ? notificationCountLabel(unreadCount)
              : null;

          return (
            <DropdownMenuItem
              key={item.id}
              asChild
              className={isCurrent ? "bg-[var(--compass-surface-muted)]" : ""}
            >
              <Link href={item.href} aria-current={isCurrent ? "page" : undefined}>
                <Icon aria-hidden="true" className="size-4" />
                <span>{item.label}</span>
                {countLabel ? (
                  <span className="ml-auto text-xs font-bold text-[var(--compass-brand-maroon)]">
                    {countLabel}
                  </span>
                ) : null}
              </Link>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function PortalAccountMenu({
  session,
  profile,
  onSignedOut,
}: {
  session: CurrentSessionResponse;
  profile: MyProfileResponse | undefined;
  onSignedOut: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const logout = useAuthLogout();
  const account = getAccountDetails(session, profile);

  async function signOut() {
    setSignOutError(null);

    try {
      await logout.mutateAsync();
    } catch (error) {
      if (!(error instanceof CompassApiError) || error.status !== 401) {
        setSignOutError(
          friendlyAuthError(error, "We couldn’t sign you out. Please try again."),
        );
        return;
      }
    }

    queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
    queryClient.removeQueries({
      queryKey: getNotificationsGetUnreadCountQueryKey(),
    });
    queryClient.clear();
    setSignOutOpen(false);
    onSignedOut();
    router.replace("/login");
    router.refresh();
  }

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="h-11 max-w-64 rounded-xl border-[var(--compass-border-strong)] bg-[var(--compass-surface-raised)] px-2.5 text-left hover:bg-[var(--compass-surface-muted)]"
            aria-label={`Open account menu for ${account.name}`}
          >
            <Avatar size="sm" className="border border-[var(--compass-border)]">
              {account.photoUrl ? (
                <AvatarImage src={account.photoUrl} alt="" />
              ) : null}
              <AvatarFallback className="bg-[var(--compass-brand-maroon)] text-xs font-bold text-white">
                {account.initials}
              </AvatarFallback>
            </Avatar>
            <span className="hidden min-w-0 sm:block">
              <span className="block truncate text-xs font-bold text-[var(--compass-ink)]">
                {account.name}
              </span>
              <span className="block truncate text-[0.68rem] text-[var(--compass-text-muted)]">
                {account.role}
              </span>
            </span>
            <ChevronUp aria-hidden="true" className="ml-1 hidden size-4 sm:block" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          side="top"
          align="end"
          sideOffset={12}
          className="w-72 rounded-2xl border-[var(--compass-border)] bg-[var(--compass-surface-raised)] p-2 shadow-[var(--compass-shadow-md)]"
        >
          <DropdownMenuLabel className="px-3 py-2">
            <div className="flex items-center gap-3">
              <Avatar size="lg">
                {account.photoUrl ? (
                  <AvatarImage src={account.photoUrl} alt="" />
                ) : null}
                <AvatarFallback className="bg-[var(--compass-brand-maroon)] font-bold text-white">
                  {account.initials}
                </AvatarFallback>
              </Avatar>
              <span className="min-w-0">
                <span className="block truncate font-bold text-[var(--compass-ink)]">
                  {account.name}
                </span>
                <span className="block truncate text-xs font-normal text-[var(--compass-text-muted)]">
                  {account.email}
                </span>
                <span className="mt-0.5 block text-xs font-normal text-[var(--compass-support-strong)]">
                  {account.role}
                </span>
              </span>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <Link href="/portal/account">
              <CircleUserRound aria-hidden="true" className="size-4" />
              <span>View your profile</span>
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            onSelect={(event) => {
              event.preventDefault();
              setSignOutError(null);
              setSignOutOpen(true);
            }}
          >
            <LogOut aria-hidden="true" className="size-4" />
            <span>Sign out</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Sign out of COMPASS?</AlertDialogTitle>
            <AlertDialogDescription>
              You can sign in again whenever you need to return to your workspace.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {signOutError ? (
            <p role="alert" className="text-sm text-destructive">
              {signOutError}
            </p>
          ) : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={logout.isPending}>
              Stay signed in
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={logout.isPending}
              onClick={(event) => {
                event.preventDefault();
                void signOut();
              }}
            >
              {logout.isPending ? "Signing out…" : "Sign out"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export function PortalDock({ session }: { session: CurrentSessionResponse }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const profileQuery = useProfileGetMyProfile({
    query: {
      retry: false,
      staleTime: 5 * 60_000,
    },
  });
  const unreadQuery = useNotificationsGetUnreadCount({
    query: {
      retry: false,
      refetchInterval: 60_000,
      staleTime: 30_000,
    },
  });
  const profile = profileQuery.data?.data;
  const unreadCount = unreadQuery.data?.data.unread_count ?? null;
  const navigation = useMemo(
    () => getVisiblePortalNavigation(session.user.capabilities),
    [session.user.capabilities],
  );
  const desktopNavigation = navigation.slice(0, DESKTOP_NAV_LIMIT);
  const desktopOverflow = navigation.slice(DESKTOP_NAV_LIMIT);
  const mobileNavigation = navigation.slice(0, MOBILE_NAV_LIMIT);
  const mobileOverflow = navigation.slice(MOBILE_NAV_LIMIT);

  return (
    <header className="portal-dock pointer-events-none fixed inset-x-0 z-40 px-2 sm:px-4">
      <div
        id="portal-dock-content"
        className={`pointer-events-auto mx-auto flex items-center gap-2 border border-[var(--compass-border)] bg-[color-mix(in_srgb,var(--compass-surface-raised)_96%,transparent)] p-2 shadow-[var(--compass-shadow-md)] backdrop-blur-md transition-[max-width,border-radius] duration-200 ${
          collapsed
            ? "w-fit max-w-20 rounded-2xl"
            : "w-full max-w-[76rem] rounded-2xl md:grid md:grid-cols-[auto_minmax(0,1fr)_auto] md:gap-3"
        }`}
      >
        {collapsed ? (
          <Button
            variant="ghost"
            className="size-11 rounded-xl text-[var(--compass-brand-maroon)] hover:bg-[var(--compass-surface-muted)]"
            onClick={() => setCollapsed(false)}
            aria-controls="portal-dock-content"
            aria-expanded={false}
            aria-label="Expand portal dock"
            title="Expand portal dock"
          >
            <Image
              src="/brand/compass-mark.svg"
              alt=""
              width={30}
              height={30}
              unoptimized
              aria-hidden="true"
            />
            <ChevronUp aria-hidden="true" className="hidden size-3 md:block" />
            <ChevronRight aria-hidden="true" className="size-3 md:hidden" />
          </Button>
        ) : (
          <>
            <div className="flex shrink-0 items-center gap-2">
              <Link
                href="/"
                className="inline-flex size-11 items-center justify-center rounded-xl border border-transparent no-underline transition-colors hover:border-[var(--compass-brand-maroon)] hover:bg-[var(--compass-surface-muted)]"
                aria-label="Open COMPASS home"
                title="Open COMPASS home"
              >
                <Image
                  src="/brand/compass-mark.svg"
                  alt=""
                  width={32}
                  height={32}
                  unoptimized
                  aria-hidden="true"
                />
              </Link>
              <span aria-hidden="true" className="hidden h-8 w-px bg-[var(--compass-border)] md:block" />
            </div>

            <nav
              aria-label="Portal navigation"
              className="hidden min-w-0 items-center gap-1 overflow-x-auto md:flex"
            >
              {desktopNavigation.map((item) => (
                <PortalNavigationLink
                  key={item.id}
                  item={item}
                  pathname={pathname}
                  unreadCount={unreadCount}
                />
              ))}
              <PortalMoreMenu
                items={desktopOverflow}
                pathname={pathname}
                unreadCount={unreadCount}
              />
            </nav>

            <nav
              aria-label="Mobile portal navigation"
              className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto md:hidden"
            >
              {mobileNavigation.map((item) => (
                <PortalNavigationLink
                  key={item.id}
                  item={item}
                  pathname={pathname}
                  unreadCount={unreadCount}
                />
              ))}
              <PortalMoreMenu
                items={mobileOverflow}
                pathname={pathname}
                unreadCount={unreadCount}
              />
            </nav>

            <div className="flex shrink-0 items-center gap-1.5">
              <Button
                variant="ghost"
                className="size-11 rounded-xl text-[var(--compass-text-muted)] hover:bg-[var(--compass-surface-muted)] hover:text-[var(--compass-brand-maroon)]"
                onClick={() => setCollapsed(true)}
                aria-controls="portal-dock-content"
                aria-expanded={true}
                aria-label="Collapse portal dock"
                title="Collapse portal dock"
              >
                <ChevronDown aria-hidden="true" className="hidden size-4 md:block" />
                <ChevronLeft aria-hidden="true" className="size-4 md:hidden" />
              </Button>
              <PortalAccountMenu
                session={session}
                profile={profile}
                onSignedOut={() => setCollapsed(false)}
              />
            </div>
          </>
        )}
      </div>
    </header>
  );
}
