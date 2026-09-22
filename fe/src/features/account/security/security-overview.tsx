"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAuthGetMfaStatus } from "@/lib/api/generated/auth/auth";

const securityRows = [
  { title: "Password", detail: "Change your COMPASS sign-in password.", label: "Change password", href: "/portal/account/security/password" },
  { title: "Sessions", detail: "Review signed-in sessions and trusted browsers.", label: "Manage sessions", href: "/portal/account/security/sessions" },
] as const;

export function SecurityOverview() {
  const { user } = usePortalSession();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });

  return (
    <section aria-labelledby="security-heading">
      <h1 id="security-heading" className="font-heading text-3xl font-bold text-ink">Security</h1>
      <div className="mt-7 divide-y divide-border border-t border-border">
        <div className="flex flex-col gap-3 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-heading text-xl font-semibold text-ink">Sign-in email</h2>
            <p className="mt-1 break-all text-sm text-muted">{user.email}</p>
          </div>
          <Link href="/portal/account/security/email" className="inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Change email →</Link>
        </div>
        {securityRows.slice(0, 1).map((row) => (
          <div key={row.href} className="flex flex-col gap-3 py-6 sm:flex-row sm:items-center sm:justify-between">
            <div><h2 className="font-heading text-xl font-semibold text-ink">{row.title}</h2><p className="mt-1 text-sm text-muted">{row.detail}</p></div>
            <Link href={row.href} className="inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{row.label} →</Link>
          </div>
        ))}
        <div className="flex flex-col gap-3 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-heading text-xl font-semibold text-ink">Authenticator app</h2>
            {mfa.isPending ? <p className="mt-1 text-sm text-muted">Checking status…</p> : null}
            {mfa.isSuccess ? <p className="mt-1 text-sm text-muted">{mfa.data.data.enabled ? "Enabled" : "Not enabled"}</p> : null}
            {mfa.isError ? <p role="alert" className="mt-1 text-sm text-danger">Status unavailable. <Button variant="quiet" className="min-h-0 px-1 py-0" onClick={() => void mfa.refetch()}>Retry</Button></p> : null}
          </div>
          <Link href="/portal/account/security/authenticator" className="inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">Manage authenticator →</Link>
        </div>
        {securityRows.slice(1).map((row) => (
          <div key={row.href} className="flex flex-col gap-3 py-6 sm:flex-row sm:items-center sm:justify-between">
            <div><h2 className="font-heading text-xl font-semibold text-ink">{row.title}</h2><p className="mt-1 text-sm text-muted">{row.detail}</p></div>
            <Link href={row.href} className="inline-flex min-h-10 items-center text-sm font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">{row.label} →</Link>
          </div>
        ))}
      </div>
    </section>
  );
}
