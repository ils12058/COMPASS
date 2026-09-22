"use client";

import { Mail, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuthGetSession } from "@/lib/api/generated/auth/auth";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";
import {
  getPortalAccountName,
  getPortalInitials,
  getPortalRoleLabel,
  getPortalRoleLine,
} from "@/features/portal/portal-identity";

export function PortalAccountPage() {
  const sessionQuery = useAuthGetSession({ query: { staleTime: 30_000 } });
  const profileQuery = useProfileGetMyProfile({
    query: {
      retry: false,
      staleTime: 5 * 60_000,
    },
  });
  const session = sessionQuery.data?.data;
  const profile = profileQuery.data?.data;

  if (!session) {
    return (
      <section className="h-72 animate-pulse rounded-3xl bg-card" aria-live="polite" />
    );
  }

  const user = session.user;
  const name = profile?.full_name || getPortalAccountName(user);
  const email = profile?.email || user.email;
  const role = profile?.role
    ? getPortalRoleLabel(profile.role)
    : getPortalRoleLine(user);
  const initials = getPortalInitials(user);

  return (
    <section className="space-y-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.16em] text-[var(--compass-brand-gold)]">
          Account
        </p>
        <h1 className="mt-2 font-heading text-4xl font-bold tracking-tight">
          Your profile
        </h1>
        <p className="mt-3 max-w-2xl leading-7 text-muted-foreground">
          Review the information connected to your COMPASS account.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.7fr)]">
        <section className="rounded-3xl border bg-card p-6 shadow-sm sm:p-8">
          <div className="flex flex-wrap items-center gap-4 border-b pb-6">
            <Avatar size="lg" className="size-16">
              {profile?.profile_photo_url ? (
                <AvatarImage src={profile.profile_photo_url} alt="" />
              ) : null}
              <AvatarFallback className="bg-[var(--compass-brand-maroon)] text-lg font-bold text-white">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <h2 className="truncate font-heading text-2xl font-bold">{name}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{role}</p>
            </div>
          </div>

          <dl className="grid gap-5 pt-6 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Email
              </dt>
              <dd className="mt-1 break-words font-semibold">{email}</dd>
            </div>
            <div>
              <dt className="text-xs font-bold uppercase tracking-[0.12em] text-muted-foreground">
                Institutional ID
              </dt>
              <dd className="mt-1 font-semibold">
                {profile?.institutional_id || "Not listed"}
              </dd>
            </div>
          </dl>

          {profileQuery.isError ? (
            <p className="mt-6 text-sm text-muted-foreground">
              Some profile details are unavailable right now. Your sign-in information is still active.
            </p>
          ) : null}
        </section>

        <aside className="rounded-3xl border border-[var(--compass-support)]/30 bg-[var(--compass-support-soft)] p-6 shadow-sm">
          <ShieldCheck
            aria-hidden="true"
            className="size-8 text-[var(--compass-support-strong)]"
          />
          <h2 className="mt-5 font-heading text-xl font-bold text-[var(--compass-support-strong)]">
            Keep your account secure
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--compass-support-strong)]/85">
            Use your UCN email and keep your password private. If you need to set or reset it, we can guide you through the secure recovery flow.
          </p>
          <Button asChild variant="outline" className="mt-5 border-[var(--compass-support-strong)]/40 bg-transparent">
            <Link href="/password">
              <Mail aria-hidden="true" className="size-4" />
              Manage password
            </Link>
          </Button>
        </aside>
      </div>
    </section>
  );
}
