"use client";

import { userDisplayName, userRoleLabel } from "@/features/portal/components/portal-presentation";
import { usePortalSession } from "@/features/portal/components/portal-session";

export function PortalHome() {
  const { user } = usePortalSession();

  return (
    <section aria-labelledby="portal-home-heading">
      <h1 id="portal-home-heading" className="font-heading text-4xl font-bold tracking-tight text-ink">Home</h1>
      <div className="mt-8 border-t border-border pt-7">
        <p className="font-heading text-2xl font-semibold text-ink">{userDisplayName(user)}</p>
        <p className="mt-2 text-sm text-muted">{userRoleLabel(user.role)}</p>
        <p className="mt-1 text-sm text-muted">{user.email}</p>
      </div>
    </section>
  );
}
