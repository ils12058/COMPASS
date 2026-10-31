"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { facultyPortalPathAvailable } from "@/features/portal/components/faculty-access";
import { WorkspaceUnavailable } from "@/features/portal/components/workspace-unavailable";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { loginPathForPortal, safePortalDestination } from "@/features/auth/utils/redirect";
import { UnsavedChangesProvider } from "@/features/form-safety/unsaved-changes-provider";
import { useServerBoundary } from "@/features/freshness/use-server-boundary";
import { PortalSessionProvider } from "@/features/portal/components/portal-session";
import { PortalSessionLoading } from "@/features/portal/components/portal-session-loading";
import { PortalShell } from "@/features/portal/components/portal-shell";
import { PortalUserMenu } from "@/features/portal/components/portal-user-menu";
import { AccessibilityControl } from "@/features/accessibility/accessibility-control";
import { ActiveECounselingRuntimeProvider, type PortalAuthState } from "@/features/ecounseling/runtime/active-call-runtime";
import { ECounselingConsentFreshnessProvider } from "@/features/ecounseling/consent-freshness-provider";
import { PortalMaintenanceGate } from "@/features/platform/maintenance-presentation";
import { RealtimeProvider } from "@/features/realtime/realtime-provider";
import { realtimeAccount } from "@/features/realtime/realtime-runtime";
import { hasPlatformView } from "@/features/platform/platform-gate";
import { CompassApiError } from "@/lib/api/errors";
import { getAuthGetSessionQueryKey, useAuthGetSession } from "@/lib/api/generated/auth/auth";
import type { UserSummary } from "@/lib/api/generated/model";
import { requestSessionRevalidation, subscribeSessionRevalidation } from "@/lib/auth/session-revalidation";

const queryCacheOwners = new WeakMap<object, string>();

export function PortalBoundary({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const session = useAuthGetSession({ query: { retry: false } });
  const [verificationRequired, setVerificationRequired] = useState(false);
  const [dataOwner, setDataOwner] = useState<string | null>(() => queryCacheOwners.get(queryClient) ?? null);
  const verifying = useRef(false);
  const cleared = useRef(false);
  const currentSession = session.data?.data?.session;
  const invalidProjection = session.isSuccess && !currentSession;
  const currentPath = safePortalDestination(
    `${pathname}${searchParams.size > 0 ? `?${searchParams.toString()}` : ""}`,
  );
  const confirmedSignedOut =
    session.isError && session.error instanceof CompassApiError && session.error.status === 401;
  // The E-Counseling call belongs to the authenticated portal session, not to a page (ADR-094). It
  // keeps the last confirmed user while the session is being checked again, and ends only when the
  // server confirms the session is gone ("signed-out"), never because a check couldn't complete.
  const confirmedUser = currentSession ? session.data?.data?.user ?? null : null;
  const [callUser, setCallUser] = useState<UserSummary | null>(null);
  if (confirmedUser && confirmedUser !== callUser) setCallUser(confirmedUser);
  // Do not render the next account using cached protected data from the previous account.
  // The session query stays intact while all other account-owned projections are removed.
  useEffect(() => {
    if (!confirmedUser || dataOwner === confirmedUser.id) return;
    let cancelled = false;
    const userId = confirmedUser.id;
    const sessionKey = getAuthGetSessionQueryKey()[0];
    const protectedData = { predicate: (query: { queryKey: readonly unknown[] }) => query.queryKey[0] !== sessionKey };
    void (async () => {
      if (dataOwner !== null) {
        await queryClient.cancelQueries(protectedData);
        if (cancelled) return;
        queryClient.removeQueries(protectedData);
      }
      if (!cancelled) { queryCacheOwners.set(queryClient, userId); setDataOwner(userId); }
    })();
    return () => { cancelled = true; };
  }, [confirmedUser, dataOwner, queryClient]);

  const authState: PortalAuthState = confirmedSignedOut
    ? "signed-out"
    : session.isPending
      ? "pending"
      : currentSession && !session.isError && !verificationRequired
        ? "confirmed"
        : "unverified";

  const verifySession = useCallback(async (failClosed: boolean) => {
    if (failClosed) setVerificationRequired(true);
    if (verifying.current) return;
    verifying.current = true;
    try {
      const result = await session.refetch();
      if (result.isSuccess && result.data?.data?.session) setVerificationRequired(false);
    } finally {
      verifying.current = false;
    }
  }, [session]);

  useEffect(() => subscribeSessionRevalidation((reason) => {
    void verifySession(reason === "session");
  }), [verifySession]);

  useServerBoundary({
    boundary: currentSession?.expires_at,
    serverDate: session.data?.headers.date,
    receivedAt: session.dataUpdatedAt,
    onBoundary: () => requestSessionRevalidation("session"),
  });

  useEffect(() => {
    if (!confirmedSignedOut) return;
    if (!cleared.current) {
      cleared.current = true;
      queryClient.clear();
    }
    router.replace(loginPathForPortal(currentPath));
  }, [confirmedSignedOut, currentPath, queryClient, router]);

  let content: ReactNode;
  if (session.isPending || confirmedSignedOut || (verificationRequired && session.isFetching) || (confirmedUser && dataOwner !== confirmedUser.id)) {
    content = <PortalSessionLoading />;
  } else if (session.isError || verificationRequired || invalidProjection || !session.data?.data) {
    content = (
      <main className="mx-auto flex min-h-dvh max-w-lg items-center px-5">
        <Notice
          role="alert"
          className="w-full px-5 py-6 sm:px-6"
          title={<h1 className="font-heading text-2xl font-bold text-ink">We could not verify your session.</h1>}
          action={
            <Button variant="secondary" onClick={() => void verifySession(true)}>
              Retry
            </Button>
          }
        >
          We could not check your session, so this page cannot be shown yet.
        </Notice>
      </main>
    );
  } else {
    const user = session.data.data.user;
    const pageContent = (user.role === "FACULTY" && !facultyPortalPathAvailable(pathname)) ||
      (user.role !== "FACULTY" && (pathname === "/portal/faculty" || pathname.startsWith("/portal/faculty/")))
      ? <WorkspaceUnavailable title="Workspace unavailable">This account cannot open this workspace.</WorkspaceUnavailable>
      : children;
    content = (
      <PortalSessionProvider value={session.data.data}>
        <PortalMaintenanceGate
          pathname={pathname}
          canOperate={hasPlatformView(user)}
          workspace={<PortalShell>{pageContent}</PortalShell>}
          page={pageContent}
          controls={<><AccessibilityControl placement="header" /><PortalUserMenu /></>}
          loading={<PortalSessionLoading />}
        />
      </PortalSessionProvider>
    );
  }

  // The unsaved-changes guard and the call runtime sit above the session, maintenance and loading
  // presentations, so swapping those never unmounts a live call. Keyed by user: another account
  // never inherits a call. The realtime runtime (ADR-100) connects only for a confirmed account:
  // a session being checked again, signed out, or replaced by another account closes its socket
  // first. It is not keyed, so a session check never remounts the page.
  return (
    <UnsavedChangesProvider>
      <RealtimeProvider account={realtimeAccount(authState, confirmedUser?.id)}>
        <ECounselingConsentFreshnessProvider user={authState === "confirmed" ? confirmedUser : null}>
          <ActiveECounselingRuntimeProvider key={callUser?.id ?? "anonymous"} user={callUser} authState={authState}>
            {content}
          </ActiveECounselingRuntimeProvider>
        </ECounselingConsentFreshnessProvider>
      </RealtimeProvider>
    </UnsavedChangesProvider>
  );
}
