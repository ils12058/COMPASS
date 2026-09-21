"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { friendlyAuthError } from "@/features/auth/utils/errors";
import {
  getAuthListTrustedSessionsQueryKey,
  useAuthListTrustedSessions,
  useAuthRevokeOtherTrustedSessions,
  useAuthRevokeTrustedSession,
} from "@/lib/api/generated/auth/auth";
import type { TrustedSessionSummary } from "@/lib/api/generated/model";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function TrustedBrowserRow({
  session,
  onRevoke,
  busy,
}: {
  session: TrustedSessionSummary;
  onRevoke: (session: TrustedSessionSummary) => void;
  busy: boolean;
}) {
  return (
    <li className="space-y-3 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-semibold">
            {session.user_agent_summary || "Trusted browser"}
            {session.is_current ? (
              <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
                This browser
              </span>
            ) : null}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Last used {formatDate(session.last_used_at)} · Expires {formatDate(session.expires_at)}
          </p>
          {session.last_ip_address ? (
            <p className="mt-1 text-xs text-muted-foreground">
              Last network address: {session.last_ip_address}
            </p>
          ) : null}
        </div>
        <Button variant="outline" size="sm" onClick={() => onRevoke(session)} disabled={busy}>
          Revoke trust
        </Button>
      </div>
    </li>
  );
}

export function TrustedBrowserList() {
  const queryClient = useQueryClient();
  const trusted = useAuthListTrustedSessions({ query: { retry: false } });
  const revoke = useAuthRevokeTrustedSession();
  const revokeOthers = useAuthRevokeOtherTrustedSessions();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function revokeOne(session: TrustedSessionSummary) {
    setError(null);
    setNotice(null);

    try {
      await revoke.mutateAsync({ sessionId: session.id });
      await queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() });
      setNotice(
        session.is_current
          ? "This browser is no longer trusted. Your current signed-in session remains active."
          : "Trusted-browser access has been revoked.",
      );
    } catch (caught) {
      setError(friendlyAuthError(caught, "The trusted browser could not be revoked."));
    }
  }

  async function revokeAllOthers() {
    setError(null);
    setNotice(null);

    try {
      await revokeOthers.mutateAsync();
      await queryClient.invalidateQueries({ queryKey: getAuthListTrustedSessionsQueryKey() });
      setNotice("Other trusted browsers have been revoked.");
    } catch (caught) {
      setError(friendlyAuthError(caught, "Other trusted browsers could not be revoked."));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trusted browsers</CardTitle>
        <CardDescription>
          A trusted browser can skip two-step verification after your password is verified.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {trusted.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Loading trusted browsers…
          </p>
        ) : null}

        {trusted.isError ? (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-destructive">
              Trusted browsers could not be loaded.
            </p>
            <Button variant="outline" onClick={() => trusted.refetch()}>
              Try again
            </Button>
          </div>
        ) : null}

        {trusted.data ? (
          trusted.data.data.sessions.length ? (
            <>
              <ul>
                {trusted.data.data.sessions.map((session) => (
                  <TrustedBrowserRow
                    key={session.id}
                    session={session}
                    onRevoke={revokeOne}
                    busy={revoke.isPending}
                  />
                ))}
              </ul>

              {trusted.data.data.sessions.some((session) => !session.is_current) ? (
                <Button
                  variant="outline"
                  onClick={revokeAllOthers}
                  disabled={revokeOthers.isPending}
                >
                  {revokeOthers.isPending ? "Revoking…" : "Revoke other trusted browsers"}
                </Button>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">No trusted browsers are active.</p>
          )
        ) : null}

        {notice ? (
          <p role="status" aria-live="polite" className="text-sm text-[var(--compass-success)]">
            {notice}
          </p>
        ) : null}

        {error ? (
          <p role="alert" aria-live="polite" className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
