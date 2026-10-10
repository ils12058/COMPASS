"use client";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";
import { Compass } from "lucide-react";
import { getPortalAccountName, getPortalRoleLine } from "@/features/portal/portal-identity";
import {
  getPortalCapabilityWidgets,
  PortalAccountWidget,
  PortalCapabilityWidget,
  PortalDateTimeWidget,
  PortalNotificationWidget,
} from "@/features/portal/home/portal-overview-widgets";
import { useNotificationsGetUnreadCount } from "@/lib/api/generated/notifications/notifications";

function PortalHomeLoading() {
  return (
    <section className="space-y-8" aria-live="polite">
      <header className="relative overflow-hidden rounded-3xl bg-[linear-gradient(120deg,var(--compass-brand-maroon),#8a3340_58%,var(--compass-support-strong))] px-6 py-8 shadow-[var(--compass-shadow-md)] sm:px-10 sm:py-10">
        <div className="relative z-10 space-y-4">
          <div className="h-4 w-32 animate-pulse rounded-full bg-white/25" />
          <div className="h-14 w-full max-w-xl animate-pulse rounded-2xl bg-white/25" />
          <div className="h-6 w-full max-w-2xl animate-pulse rounded-xl bg-white/20" />
        </div>
        <div className="absolute -right-5 -bottom-8 size-48 animate-pulse rounded-full bg-white/10 sm:size-64" />
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(15rem,0.72fr)_minmax(0,1.28fr)]">
        <div className="space-y-3 rounded-[1.75rem] bg-[var(--compass-brand-maroon)] p-4">
          <div className="h-5 w-24 animate-pulse rounded-full bg-white/20" />
          <div className="h-32 animate-pulse rounded-2xl bg-white/85" />
          <div className="h-36 animate-pulse rounded-2xl bg-white/85" />
          <div className="h-28 animate-pulse rounded-2xl bg-white/85" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <div
              key={index}
              className="h-44 animate-pulse rounded-3xl bg-card"
            />
          ))}
        </div>
      </div>
    </section>
  );
}

export function PortalHome() {
  const sessionQuery = useAuthGetSession({
    query: {
      staleTime: 30_000,
    },
  });
  const unreadQuery = useNotificationsGetUnreadCount({
    query: {
      retry: false,
      staleTime: 30_000,
    },
  });
  const profileQuery = useProfileGetMyProfile({
    query: {
      retry: false,
      staleTime: 5 * 60_000,
    },
  });
  const session = sessionQuery.data?.data;

  if (!session) {
    return <PortalHomeLoading />;
  }

  const user = session.user;
  const name = getPortalAccountName(user);
  const firstName = name.split(" ")[0] || name;
  const capabilityWidgets = getPortalCapabilityWidgets(user.capabilities ?? []);
  const unreadCount = unreadQuery.data?.data.unread_count ?? 0;
  const profilePhotoUrl = profileQuery.data?.data.profile_photo_url;

  return (
    <section aria-labelledby="portal-home-heading" className="space-y-8">
      <header className="relative overflow-hidden rounded-3xl bg-[linear-gradient(120deg,var(--compass-brand-maroon),#8a3340_58%,var(--compass-support-strong))] px-6 py-8 text-white shadow-[var(--compass-shadow-md)] sm:px-10 sm:py-10">
        <div className="relative z-10 max-w-3xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-white/75">
            COMPASS workspace
          </p>
        <h1
          id="portal-home-heading"
            className="mt-3 font-heading text-4xl font-bold tracking-tight text-white sm:text-5xl"
        >
            <span className="text-[var(--compass-brand-gold)]">Welcome back,</span>{" "}
          {firstName}.
        </h1>
          <p className="mt-5 text-sm font-semibold text-white/75">
            {getPortalRoleLine(user)}
          </p>
        </div>
        <Compass
          aria-hidden="true"
          className="absolute -right-5 -bottom-8 size-48 rotate-12 text-white/10 sm:size-64"
          strokeWidth={1}
        />
      </header>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(15rem,0.72fr)_minmax(0,1.28fr)]">
        <section
          aria-label="Overview"
          className="rounded-[1.75rem] border border-[var(--compass-border)] bg-[var(--compass-support-soft)] p-3 text-[var(--compass-support-strong)] shadow-[var(--compass-shadow-md)] sm:p-4"
        >
          <div className="px-3 pb-3 pt-1 sm:px-2">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--compass-support-strong)]/70">
              Overview
            </p>
          </div>

          <div className="grid gap-3">
            <PortalDateTimeWidget />
            <PortalAccountWidget
              name={name}
              photoUrl={profilePhotoUrl}
              role={getPortalRoleLine(user)}
              user={user}
            />
            <PortalNotificationWidget unreadCount={unreadCount} />
          </div>
        </section>

        <section aria-labelledby="portal-available-heading" className="space-y-4">
          <header className="space-y-1 px-1">
            <h2
              id="portal-available-heading"
              className="font-heading text-3xl font-bold tracking-tight"
            >
              What&apos;s ready for you
            </h2>
          </header>

          {capabilityWidgets.length ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {capabilityWidgets.map((widget) => (
                <PortalCapabilityWidget key={widget.capability} widget={widget} />
              ))}
            </div>
          ) : (
            <div className="rounded-3xl border border-dashed bg-card p-6 text-sm leading-6 text-muted-foreground">
              There are no additional areas to show right now.
            </div>
          )}
        </section>
      </div>
    </section>
  );
}
