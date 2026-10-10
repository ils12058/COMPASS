"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { useOptionalActiveECounselingCall } from "@/features/ecounseling/runtime/active-call-context";
import { activeCaptureKinds } from "@/features/ecounseling/runtime/runtime-model";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedNavigation } from "@/features/form-safety/unsaved-changes-provider";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { AccountMenu } from "@/features/account/components/account-menu";
import { authErrorMessage } from "@/features/auth/utils/errors";
import { CompassApiError } from "@/lib/api/errors";
import { useAuthLogout } from "@/lib/api/generated/auth/auth";
import { useProfileGetMyProfile } from "@/lib/api/generated/profile/profile";

export function PortalUserMenu() {
  const { user } = usePortalSession();
  const queryClient = useQueryClient();
  const router = useRouter();
  const { confirmDiscard } = useUnsavedNavigation();
  const [error, setError] = useState<string | null>(null);
  const [endCallOpen, setEndCallOpen] = useState(false);
  const [ending, setEnding] = useState(false);
  const call = useOptionalActiveECounselingCall();
  const logout = useAuthLogout();
  const profile = useProfileGetMyProfile({ query: { retry: false, staleTime: 60_000 } }).data?.data;

  function finishLogout() {
    queryClient.clear();
    router.replace("/");
  }

  async function performSignOut() {
    setError(null);
    try {
      await logout.mutateAsync();
      finishLogout();
    } catch (caught) {
      if (caught instanceof CompassApiError && caught.status === 401) {
        finishLogout();
        return;
      }
      setError(authErrorMessage(caught, "Sign out could not be completed. Please try again."));
    }
  }

  async function signOut() {
    if (!confirmDiscard()) return;
    // A live E-Counseling call ends with the portal session, so signing out asks first (ADR-094).
    if (call?.live) {
      setEndCallOpen(true);
      return;
    }
    await performSignOut();
  }

  // Leaves the call first, then signs out. Leaving the call doesn't stop recording or transcription.
  async function endCallAndSignOut() {
    setEnding(true);
    try {
      await call?.end();
    } finally {
      setEnding(false);
      setEndCallOpen(false);
    }
    await performSignOut();
  }

  const runningCapture = call?.role === "COUNSELOR" ? activeCaptureKinds(call.canonical.media) : [];

  return (
    <>
    <AccountMenu user={user} profile={profile} error={error}>
      <DropdownMenuItem asChild>
        <GuardedPortalLink href="/portal/account/profile">
          <UserRound size={17} className="mr-2" aria-hidden="true" />
          Account
        </GuardedPortalLink>
      </DropdownMenuItem>
      <DropdownMenuSeparator className="my-1 h-px bg-border" />
      <DropdownMenuItem disabled={logout.isPending} onSelect={() => void signOut()}>
        <LogOut size={17} className="mr-2" aria-hidden="true" />
        {logout.isPending ? "Signing out…" : "Sign out"}
      </DropdownMenuItem>
    </AccountMenu>
    <ConsequentialActionDialog
      open={endCallOpen}
      title="Sign out and end this call?"
      confirmLabel="Sign out"
      pendingLabel="Signing out…"
      pending={ending || logout.isPending}
      error={null}
      onOpenChange={setEndCallOpen}
      onConfirm={() => void endCallAndSignOut()}
    >
      <p>Signing out ends your E-Counseling call.</p>
      {runningCapture.length ? (
        <p>
          {runningCapture.length > 1 ? "Recording and transcription are" : runningCapture[0] === "recording" ? "Recording is" : "Transcription is"} still
          active. Ending your call doesn’t confirm that {runningCapture.length > 1 ? "they have" : "it has"} stopped.
        </p>
      ) : null}
    </ConsequentialActionDialog>
    </>
  );
}
