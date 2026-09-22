"use client";

import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCurrentAuth } from "@/features/auth/hooks/use-current-auth";
import { roleLabel, userDisplayName } from "@/features/auth/utils/presentation";

export function PortalHome() {
  const { session } = useCurrentAuth();

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">
          {roleLabel(session.user.role)}
        </p>
        <h1 className="font-heading text-3xl font-bold tracking-tight">
          Welcome, {userDisplayName(session.user)}
        </h1>
        <p className="max-w-2xl text-muted-foreground">
          Your COMPASS session is active. Service areas will appear here as their frontend
          workflows are implemented.
        </p>
      </header>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Account security</CardTitle>
          <CardDescription>
            Manage two-step verification, your password, signed-in sessions, and trusted
            browsers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            href="/portal/account/security"
            className="inline-flex min-h-10 items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground no-underline hover:bg-[var(--compass-brand-maroon-strong)]"
          >
            Open Account &amp; Security
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
