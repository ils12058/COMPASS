"use client";

import { ShieldCheck, UserRound } from "lucide-react";

import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import type { MyProfileResponse } from "@/lib/api/generated/model";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";
import { PortalWorkspaceNav } from "@/features/portal/components/portal-workspace-nav";
import { PortalAccountProfile } from "@/features/portal/account/portal-account-profile";
import { PortalAccountSecurity } from "@/features/portal/account/portal-account-security";
import {
  getPortalAccountName,
  getPortalRoleLabel,
} from "@/features/portal/portal-identity";

export type PortalAccountSection = "profile" | "security";

const ACCOUNT_NAV_ITEMS = [
  {
    href: "/portal/account",
    label: "Profile",
    value: "profile",
    icon: UserRound,
  },
  {
    href: "/portal/account/security",
    label: "Security",
    value: "security",
    icon: ShieldCheck,
  },
] as const;

function PortalAccountLoading() {
  return (
    <section className="space-y-6" aria-live="polite">
      <div className="space-y-3">
        <div className="h-4 w-24 animate-pulse rounded-full bg-muted" />
        <div className="h-12 w-64 animate-pulse rounded-2xl bg-muted" />
        <div className="h-5 w-full max-w-2xl animate-pulse rounded-xl bg-muted" />
      </div>
      <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <div className="h-28 animate-pulse rounded-3xl bg-card" />
        <div className="h-[36rem] animate-pulse rounded-3xl bg-card" />
      </div>
    </section>
  );
}

function getDisplayName(
  profile: MyProfileResponse | undefined,
  user: Parameters<typeof getPortalAccountName>[0],
) {
  return profile?.full_name || getPortalAccountName(user);
}

export function PortalAccountPage({
  section,
}: {
  section: PortalAccountSection;
}) {
  const sessionQuery = useAuthGetSession({
    query: { staleTime: 30_000 },
  });
  const profileQuery = useProfileGetMyProfile({
    query: {
      retry: false,
      staleTime: 5 * 60_000,
    },
  });
  const session = sessionQuery.data?.data;

  if (!session) {
    return <PortalAccountLoading />;
  }

  const user = session.user;
  const profile = profileQuery.data?.data;
  const displayName = getDisplayName(profile, user);
  const role = profile?.role ? getPortalRoleLabel(profile.role) : user.role;

  return (
    <section aria-labelledby="portal-account-heading" className="space-y-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
          Account
        </p>
        <h1
          id="portal-account-heading"
          className="mt-2 font-heading text-4xl font-bold tracking-tight"
        >
          Your account
        </h1>
        <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
          Manage your personal details and the protections around your sign-in.
        </p>
        <p className="mt-3 text-sm font-semibold text-[var(--compass-support-strong)]">
          {displayName} · {role}
        </p>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <PortalWorkspaceNav
          activeValue={section}
          ariaLabel="Account sections"
          items={ACCOUNT_NAV_ITEMS}
        />

        {section === "profile" ? (
          <PortalAccountProfile
            key={profile?.user_id ?? "profile-loading"}
            error={profileQuery.error}
            isLoading={profileQuery.isPending}
            profile={profile}
          />
        ) : (
          <PortalAccountSecurity profile={profile} />
        )}
      </div>
    </section>
  );
}
