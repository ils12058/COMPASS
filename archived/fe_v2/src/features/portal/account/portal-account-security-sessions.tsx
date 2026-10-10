"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Clock3, Laptop, MonitorSmartphone } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  getAuthListSessionsQueryKey,
  getAuthListTrustedSessionsQueryKey,
  useAuthListSessions,
  useAuthListTrustedSessions,
  useAuthRevokeOtherSessions,
  useAuthRevokeOtherTrustedSessions,
  useAuthRevokeSession,
  useAuthRevokeTrustedSession,
} from "@/lib/api/generated/auth/auth";
import type { SessionSummary, TrustedSessionSummary } from "@/lib/api/generated/model";
import type { RequestSecurityConfirmation } from "@/features/portal/account/portal-account-security-shared";
import {
  SecuritySectionHeading,
  SessionRow,
  TrustedBrowserRow,
} from "@/features/portal/account/portal-account-security-shared";

export function PortalAccountSecuritySessions({
  onRequestConfirmation,
}: {
  onRequestConfirmation: RequestSecurityConfirmation;
}) {
  const queryClient = useQueryClient();
  const sessionsQuery = useAuthListSessions({
    query: { retry: false, staleTime: 30_000 },
  });
  const trustedSessionsQuery = useAuthListTrustedSessions({
    query: { retry: false, staleTime: 30_000 },
  });
  const revokeOtherSessions = useAuthRevokeOtherSessions();
  const revokeSession = useAuthRevokeSession();
  const revokeOtherTrustedSessions = useAuthRevokeOtherTrustedSessions();
  const revokeTrustedSession = useAuthRevokeTrustedSession();
  const sessions = sessionsQuery.data?.data.sessions ?? [];
  const trustedSessions = trustedSessionsQuery.data?.data.sessions ?? [];

  function confirmRevokeSession(session: SessionSummary) {
    onRequestConfirmation({
      title: "Sign out this device?",
      description: `This will end the session shown as “${session.user_agent_summary || "Browser session"}”.`,
      confirmLabel: "Sign out device",
      run: async () => {
        await revokeSession.mutateAsync({ sessionId: session.id });
        await queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() });
      },
    });
  }

  function confirmRevokeOtherSessions() {
    onRequestConfirmation({
      title: "Sign out other devices?",
      description: "Every active session except this device will be signed out.",
      confirmLabel: "Sign out other devices",
      run: async () => {
        await revokeOtherSessions.mutateAsync();
        await queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() });
      },
    });
  }

  function confirmRevokeTrustedSession(session: TrustedSessionSummary) {
    onRequestConfirmation({
      title: "Remove this browser’s trust?",
      description: "This browser will need to complete verification again the next time it needs trusted access.",
      confirmLabel: "Remove trust",
      run: async () => {
        await revokeTrustedSession.mutateAsync({ sessionId: session.id });
        await queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() });
      },
    });
  }

  function confirmRevokeOtherTrustedSessions() {
    onRequestConfirmation({
      title: "Remove trust from other browsers?",
      description: "Every trusted browser except this device will need to complete verification again.",
      confirmLabel: "Remove other trust",
      run: async () => {
        await revokeOtherTrustedSessions.mutateAsync();
        await queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() });
      },
    });
  }

  return (
    <>
      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <SecuritySectionHeading
          icon={MonitorSmartphone}
          title="Active sessions"
          description="Review where your account is signed in. Sign out a device you no longer recognize."
        />
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock3 aria-hidden="true" className="size-4" />
            <span>{sessions.length} active {sessions.length === 1 ? "session" : "sessions"}</span>
          </div>
          {sessions.some((session) => !session.is_current) ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={confirmRevokeOtherSessions}
              disabled={revokeOtherSessions.isPending}
            >
              {revokeOtherSessions.isPending ? "Signing out…" : "Sign out other devices"}
            </Button>
          ) : null}
        </div>
        {sessionsQuery.isPending ? (
          <div className="mt-4 h-40 animate-pulse rounded-2xl bg-muted" aria-live="polite" />
        ) : sessionsQuery.isError ? (
          <p className="mt-4 text-sm text-destructive" role="alert">We couldn’t load active sessions right now.</p>
        ) : sessions.length ? (
          <ul className="mt-4 space-y-3">
            {sessions.map((session) => (
              <SessionRow key={session.id} session={session} onRevoke={confirmRevokeSession} />
            ))}
          </ul>
        ) : (
          <p className="mt-4 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">No active sessions were found.</p>
        )}
      </section>

      <section className="rounded-3xl border border-[var(--compass-border)] bg-card p-5 shadow-sm sm:p-7">
        <SecuritySectionHeading
          icon={Laptop}
          title="Trusted browsers"
          description="Browsers you chose to remember are listed separately from your active sign-in sessions."
        />
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MonitorSmartphone aria-hidden="true" className="size-4" />
            <span>{trustedSessions.length} trusted {trustedSessions.length === 1 ? "browser" : "browsers"}</span>
          </div>
          {trustedSessions.some((session) => !session.is_current) ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={confirmRevokeOtherTrustedSessions}
              disabled={revokeOtherTrustedSessions.isPending}
            >
              {revokeOtherTrustedSessions.isPending ? "Removing…" : "Remove other trust"}
            </Button>
          ) : null}
        </div>
        {trustedSessionsQuery.isPending ? (
          <div className="mt-4 h-40 animate-pulse rounded-2xl bg-muted" aria-live="polite" />
        ) : trustedSessionsQuery.isError ? (
          <p className="mt-4 text-sm text-destructive" role="alert">We couldn’t load trusted browsers right now.</p>
        ) : trustedSessions.length ? (
          <ul className="mt-4 space-y-3">
            {trustedSessions.map((session) => (
              <TrustedBrowserRow key={session.id} session={session} onRevoke={confirmRevokeTrustedSession} />
            ))}
          </ul>
        ) : (
          <p className="mt-4 rounded-2xl border border-dashed p-4 text-sm text-muted-foreground">No trusted browsers were found.</p>
        )}
      </section>
    </>
  );
}
