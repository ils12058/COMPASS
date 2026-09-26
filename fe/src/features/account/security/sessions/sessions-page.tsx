"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import { SecurityBackLink } from "@/features/account/security/security-shared";
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

type PendingAction =
  | { kind: "session"; id: string }
  | { kind: "other-sessions" }
  | { kind: "trusted"; id: string }
  | { kind: "other-trusted"; currentExists: boolean };

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function SessionRow({ session, onRevoke }: { session: SessionSummary; onRevoke: (id: string) => void }) {
  return (
    <li className="flex flex-col gap-3 py-5 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <p className="font-semibold text-ink">{session.user_agent_summary || "Signed-in session"}</p>
        {session.is_current ? <p className="mt-1 text-sm font-semibold text-success">Current session</p> : null}
        <p className="mt-1 text-sm text-muted">Last active {formatDate(session.last_used_at)}</p>
        <p className="mt-1 text-xs text-muted">Signed in {formatDate(session.created_at)}</p>
      </div>
      {!session.is_current ? <Button variant="secondary" onClick={() => onRevoke(session.id)}>Sign out</Button> : null}
    </li>
  );
}

function TrustedRow({ session, onRevoke }: { session: TrustedSessionSummary; onRevoke: (id: string) => void }) {
  return (
    <li className="flex flex-col gap-3 py-5 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <p className="font-semibold text-ink">{session.user_agent_summary || "Trusted browser"}</p>
        {session.is_current ? <p className="mt-1 text-sm font-semibold text-success">This browser</p> : null}
        <p className="mt-1 text-sm text-muted">Last used {formatDate(session.last_used_at)}</p>
        <p className="mt-1 text-xs text-muted">Trust expires {formatDate(session.expires_at)}</p>
      </div>
      <Button variant="secondary" onClick={() => onRevoke(session.id)}>Remove trust</Button>
    </li>
  );
}

export function SessionsPage() {
  const queryClient = useQueryClient();
  const sessions = useAuthListSessions({ query: { retry: false } });
  const trusted = useAuthListTrustedSessions({ query: { retry: false } });
  const revokeSession = useAuthRevokeSession();
  const revokeOthers = useAuthRevokeOtherSessions();
  const revokeTrusted = useAuthRevokeTrustedSession();
  const revokeOtherTrusted = useAuthRevokeOtherTrustedSessions();
  const [action, setAction] = useState<PendingAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const pending = revokeSession.isPending || revokeOthers.isPending || revokeTrusted.isPending || revokeOtherTrusted.isPending;
  const signedIn = sessions.data?.data.sessions ?? [];
  const browsers = trusted.data?.data.sessions ?? [];
  const currentTrustedExists = browsers.some((item) => item.is_current);
  const otherSessionExists = signedIn.some((item) => !item.is_current);
  const otherTrustedExists = browsers.some((item) => !item.is_current);

  function chooseAction(next: PendingAction) {
    setActionError(null);
    setNotice(null);
    setAction(next);
  }

  async function confirmAction() {
    if (!action) return;
    setActionError(null);
    try {
      let message: string;
      if (action.kind === "session") {
        await revokeSession.mutateAsync({ sessionId: action.id });
        message = "The session was signed out.";
      } else if (action.kind === "other-sessions") {
        const response = await revokeOthers.mutateAsync();
        message = `${response.data.revoked_count} other ${response.data.revoked_count === 1 ? "session was" : "sessions were"} signed out.`;
      } else if (action.kind === "trusted") {
        await revokeTrusted.mutateAsync({ sessionId: action.id });
        message = "Trust was removed from the browser. Your current sign-in is unchanged.";
      } else {
        const response = await revokeOtherTrusted.mutateAsync();
        message = `Trust was removed from ${response.data.revoked_count} ${response.data.revoked_count === 1 ? "browser" : "browsers"}. Your current sign-in is unchanged.`;
      }
      const queryKey = action.kind === "session" || action.kind === "other-sessions"
        ? getAuthListSessionsQueryKey()
        : getAuthListTrustedSessionsQueryKey();
      setAction(null);
      setNotice(message);
      await queryClient.invalidateQueries({ queryKey });
    } catch (caught) {
      setActionError(accountErrorMessage(caught, "This security action could not be completed. Please try again."));
    }
  }

  const title = action?.kind === "session" ? "Sign out this session?"
    : action?.kind === "other-sessions" ? "Sign out other sessions?"
      : action?.kind === "trusted" ? "Remove trust from this browser?"
        : action?.currentExists ? "Remove trust from other browsers?" : "Remove all trusted browsers?";
  const description = action?.kind === "session" ? "This session will need to authenticate again. The physical device is not removed or blocked."
    : action?.kind === "other-sessions" ? "This keeps your current session signed in and signs out your other active COMPASS sessions. Trusted-browser permissions are managed separately."
      : action?.kind === "trusted" ? "This browser will no longer be trusted for future sign-ins. Your active authentication session remains signed in."
        : action?.currentExists ? "This removes trusted-browser permissions from your other browsers and keeps this browser's trust. It does not sign out active sessions."
          : "This removes all listed trusted-browser permissions. It does not sign out active sessions.";
  const actionLabel = action?.kind === "session" ? "Sign out session"
    : action?.kind === "other-sessions" ? "Sign out other sessions"
      : action?.kind === "trusted" ? "Remove trust"
        : action?.currentExists ? "Remove other browsers' trust" : "Remove all trust";
  const pendingLabel = action?.kind === "session" || action?.kind === "other-sessions"
    ? "Signing out…"
    : "Removing trust…";

  return (
    <section aria-labelledby="sessions-heading" className="max-w-3xl">
      <SecurityBackLink />
      <h1 id="sessions-heading" className="font-heading text-3xl font-bold text-ink">Sessions and trusted browsers</h1>
      <p className="mt-2 text-sm leading-6 text-muted">Manage where you are signed in and which browsers are trusted. These are separate security settings.</p>
      {notice ? <p role="status" className="mt-5 text-sm text-success">{notice}</p> : null}

      <section aria-labelledby="signed-in-heading" className="mt-9">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div><h2 id="signed-in-heading" className="font-heading text-2xl font-semibold text-ink">Signed-in sessions</h2><p className="mt-1 text-sm text-muted">Other sessions can be signed out without ending this one.</p></div>
          {sessions.isSuccess && otherSessionExists ? <Button variant="secondary" onClick={() => chooseAction({ kind: "other-sessions" })}>Sign out other sessions</Button> : null}
        </div>
        {sessions.isPending ? <p role="status" className="mt-5 text-sm text-muted">Loading signed-in sessions…</p> : null}
        {sessions.isError ? <div role="alert" className="mt-5"><p className="text-sm text-danger">Signed-in sessions could not be loaded.</p><Button variant="secondary" className="mt-3" onClick={() => void sessions.refetch()}>Retry</Button></div> : null}
        {sessions.isSuccess && signedIn.length === 0 ? <p className="mt-5 border-t border-border py-5 text-sm text-muted">No signed-in sessions are available to display.</p> : null}
        {sessions.isSuccess && signedIn.length > 0 ? <ul className="mt-5 divide-y divide-border border-y border-border">{signedIn.map((item) => <SessionRow key={item.id} session={item} onRevoke={(id) => chooseAction({ kind: "session", id })} />)}</ul> : null}
      </section>

      <section aria-labelledby="trusted-heading" className="mt-11">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div><h2 id="trusted-heading" className="font-heading text-2xl font-semibold text-ink">Trusted browsers</h2><p className="mt-1 text-sm leading-6 text-muted">A trusted browser may reduce MFA prompts on future sign-ins. Removing trust does not sign out an active session.</p></div>
          {trusted.isSuccess && otherTrustedExists ? <Button variant="secondary" onClick={() => chooseAction({ kind: "other-trusted", currentExists: currentTrustedExists })}>{currentTrustedExists ? "Remove trust from other browsers" : "Remove all trusted browsers"}</Button> : null}
        </div>
        {trusted.isPending ? <p role="status" className="mt-5 text-sm text-muted">Loading trusted browsers…</p> : null}
        {trusted.isError ? <div role="alert" className="mt-5"><p className="text-sm text-danger">Trusted browsers could not be loaded.</p><Button variant="secondary" className="mt-3" onClick={() => void trusted.refetch()}>Retry</Button></div> : null}
        {trusted.isSuccess && browsers.length === 0 ? <p className="mt-5 border-t border-border py-5 text-sm text-muted">No trusted browsers are currently listed.</p> : null}
        {trusted.isSuccess && browsers.length > 0 ? <ul className="mt-5 divide-y divide-border border-y border-border">{browsers.map((item) => <TrustedRow key={item.id} session={item} onRevoke={(id) => chooseAction({ kind: "trusted", id })} />)}</ul> : null}
      </section>

      <AlertDialog open={action !== null} onOpenChange={(open) => { if (!open && !pending) { setAction(null); setActionError(null); } }}>
        <AlertDialogContent>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
          {actionError ? <p role="alert" className="mt-3 text-sm text-danger">{actionError}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild><Button variant="secondary" disabled={pending}>Cancel</Button></AlertDialogCancel>
            <Button variant="danger" disabled={pending} onClick={() => void confirmAction()}>{pending ? pendingLabel : actionLabel}</Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
