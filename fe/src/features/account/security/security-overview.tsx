"use client";

import Link from "next/link";
import { KeyRound, Mail, Monitor, ShieldCheck } from "lucide-react";
import { SectionLink } from "@/components/ui/section-link";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAuthGetEmailChangeStatus, useAuthGetMfaStatus } from "@/lib/api/generated/auth/auth";

const securityRows = [
  { title: "Password", detail: "Change your COMPASS sign-in password.", icon: KeyRound, label: "Change password", href: "/portal/account/security/password" },
  { title: "Sessions", detail: "Review signed-in sessions and trusted browsers.", icon: Monitor, label: "Manage sessions", href: "/portal/account/security/sessions" },
] as const;

export function SecurityOverview() {
  const { user } = usePortalSession();
  const mfa = useAuthGetMfaStatus({ query: { retry: false } });
  const emailChange = useAuthGetEmailChangeStatus({
    query: { retry: false, refetchOnMount: "always", refetchOnWindowFocus: true },
  });
  const emailChangeRequest = emailChange.data?.data.request;

  return (
    <section aria-labelledby="security-heading">
      <PageHeader title="Security" headingId="security-heading" />
      {emailChangeRequest?.status === "pending" ? (
        <Notice
          role="status"
          tone="warning"
          className="mb-4"
          title="Verify your new sign-in email"
          action={
            <Link
              href="/portal/account/security/email"
              className="inline-flex min-h-10 items-center font-semibold text-brand underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Verify email
            </Link>
          }
        >
          A verification code was sent to <span className="break-all font-semibold text-ink">{emailChangeRequest.destination_email}</span>. Enter it to finish changing your sign-in email.
        </Notice>
      ) : null}
      {emailChangeRequest && ["expired", "cancelled", "verification_unavailable"].includes(emailChangeRequest.status) ? (
        <Notice role="status" tone="info" className="mb-4">
          This email change is no longer active. Start a new request to try again.
        </Notice>
      ) : null}
      {emailChange.isError ? (
        <Notice
          role="alert"
          tone="danger"
          className="mb-4"
          action={<Button variant="secondary" onClick={() => void emailChange.refetch()}>Retry</Button>}
        >
          Email verification status could not be loaded.
        </Notice>
      ) : null}
      <Panel as="div" className="divide-y divide-border">
        <div className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <h2 className="font-heading text-base font-semibold text-ink">Sign-in email</h2>
            <p className="mt-1 break-all text-sm text-muted">{user.email}</p>
          </div>
          <SectionLink href="/portal/account/security/email" label="Change email" icon={Mail} />
        </div>
        {securityRows.slice(0, 1).map((row) => (
          <div key={row.href} className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div><h2 className="font-heading text-base font-semibold text-ink">{row.title}</h2><p className="mt-1 text-sm text-muted">{row.detail}</p></div>
            <SectionLink href={row.href} label={row.label} icon={row.icon} />
          </div>
        ))}
        <div className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <h2 className="font-heading text-base font-semibold text-ink">Authenticator app</h2>
            {mfa.isPending ? <p className="mt-1 text-sm text-muted">Checking status…</p> : null}
            {mfa.isSuccess ? <p className="mt-1 text-sm text-muted">{mfa.data.data.enabled ? "Enabled" : "Not enabled"}</p> : null}
            {mfa.isError ? <p role="alert" className="mt-1 text-sm text-danger">Status unavailable. <Button variant="quiet" className="min-h-0 px-1 py-0" onClick={() => void mfa.refetch()}>Retry</Button></p> : null}
          </div>
          <SectionLink href="/portal/account/security/authenticator" label="Manage authenticator" icon={ShieldCheck} />
        </div>
        {securityRows.slice(1).map((row) => (
          <div key={row.href} className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div><h2 className="font-heading text-base font-semibold text-ink">{row.title}</h2><p className="mt-1 text-sm text-muted">{row.detail}</p></div>
            <SectionLink href={row.href} label={row.label} icon={row.icon} />
          </div>
        ))}
      </Panel>
    </section>
  );
}
