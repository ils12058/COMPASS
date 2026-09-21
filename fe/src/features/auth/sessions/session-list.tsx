"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { friendlyAuthError } from "@/features/auth/utils/errors";
import {
  getAuthGetSessionQueryKey,
  getAuthListSessionsQueryKey,
  useAuthListSessions,
  useAuthRevokeOtherSessions,
  useAuthRevokeSession,
} from "@/lib/api/generated/auth/auth";
import type { SessionSummary } from "@/lib/api/generated/model";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function SessionRow({
  session,
  onRevoke,
  busy,
}: {
  session: SessionSummary;
  onRevoke: (session: SessionSummary) => void;
  busy: boolean;
}) {
  return (
    <li className="space-y-3 border-t py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">
            {session.user_agent_summary || "Browser session"}
            {session.is_current ? (
              <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-foreground">
                This session
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
          {session.is_current ? "Sign out this session" : "Revoke"}
        </Button>
      </div>
    </li>
  );
}

export function SessionList() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const sessions = useAuthListSessions({ query: { retry: false } });
  const revoke = useAuthRevokeSession();
  const revokeOthers = useAuthRevokeOtherSessions();
  const [error, setError] = useState<string | null>(null);

  async function revokeOne(session: SessionSummary) {
    setError(null);

    try {
      await revoke.mutateAsync({ sessionId: session.id });

      if (session.is_current) {
        queryClient.removeQueries({ queryKey: getAuthGetSessionQueryKey() });
        router.replace("/login");
        return;
      }

      await queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() });
    } catch (caught) {
      setError(friendlyAuthError(caught, "The session could not be revoked."));
    }
  }

  async function revokeAllOthers() {
    setError(null);

    try {
      await revokeOthers.mutateAsync();
      await queryClient.invalidateQueries({ queryKey: getAuthListSessionsQueryKey() });
    } catch (caught) {
      setError(friendlyAuthError(caught, "Other sessions could not be signed out."));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Signed-in sessions</CardTitle>
        <CardDescription>
          Review browsers currently signed in to your COMPASS account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {sessions.isPending ? (
          <p role="status" className="text-sm text-muted-foreground">
            Loading signed-in sessions…
          </p>
        ) : null}

        {sessions.isError ? (
          <div className="space-y-3">
            <p role="alert" className="text-sm text-destructive">
              Signed-in sessions could not be loaded.
            </p>
            <Button variant="outline" onClick={() => sessions.refetch()}>
              Try again
            </Button>
          </div>
        ) : null}

        {sessions.data ? (
          <>
            <ul>
              {sessions.data.data.sessions.map((session) => (
                <SessionRow
                  key={session.id}
                  session={session}
                  onRevoke={revokeOne}
                  busy={revoke.isPending}
                />
              ))}
            </ul>

            {sessions.data.data.sessions.some((session) => !session.is_current) ? (
              <Button
                variant="outline"
                onClick={revokeAllOthers}
                disabled={revokeOthers.isPending}
              >
                {revokeOthers.isPending ? "Signing out…" : "Sign out other sessions"}
              </Button>
            ) : null}
          </>
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
