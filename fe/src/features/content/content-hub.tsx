"use client";

import { FileText, Megaphone } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useCurrentAuth } from "@/features/auth/hooks/use-current-auth";

export function ContentHub() {
  const { hasCapability } = useCurrentAuth();
  const canAnnouncements = hasCapability("announcements.manage");
  const canResources = hasCapability("resources.manage");

  if (!canAnnouncements && !canResources) {
    return (
      <section className="mx-auto max-w-xl rounded-xl border bg-card p-6 text-center shadow-sm">
        <h1 className="font-heading text-2xl font-bold">Content is unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Content management is not available to your account.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <p className="text-sm font-semibold text-[var(--compass-support-strong)]">GCO content</p>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Content</h1>
        <p className="max-w-2xl text-muted-foreground">
          Manage information shared through COMPASS.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        {canAnnouncements ? (
          <Link href="/portal/content/announcements" className="no-underline">
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardHeader>
                <Megaphone aria-hidden="true" className="size-6 text-primary" />
                <CardTitle className="pt-2">Announcements</CardTitle>
                <CardDescription>
                  Updates, reminders, and time-sensitive office notices.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-sm font-semibold text-primary">Manage announcements →</span>
              </CardContent>
            </Card>
          </Link>
        ) : null}

        {canResources ? (
          <Link href="/portal/content/resources" className="no-underline">
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardHeader>
                <FileText aria-hidden="true" className="size-6 text-primary" />
                <CardTitle className="pt-2">Resources</CardTitle>
                <CardDescription>
                  Articles, trusted links, forms, guides, and PDF resources.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <span className="text-sm font-semibold text-primary">Manage resources →</span>
              </CardContent>
            </Card>
          </Link>
        ) : null}
      </div>
    </div>
  );
}
