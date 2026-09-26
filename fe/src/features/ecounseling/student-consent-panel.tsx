"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { captureStatusLabel, consentStatusLabel, ecounselingErrorMessage, formatECounselingDateTime, hasLiveOrTransitionalMedia } from "@/features/ecounseling/ecounseling-shared";
import { ConsentDecisionRequestDecision, ECounselingCaptureStatus, ECounselingConsentDecision, ECounselingConsentScope, type ConsentResponse, type MediaWorkspaceState, type StudentWorkspaceResponse } from "@/lib/api/generated/model";
import {
  getECounselingGetMyWorkspaceQueryKey,
  getECounselingListMyConsentsQueryKey,
  useECounselingDecideMyConsent,
  useECounselingListMyConsents,
  useECounselingWithdrawMyConsent,
} from "@/lib/api/generated/e-counseling/e-counseling";

type StudentAction = { consentId: string; scope: ECounselingConsentScope; decision?: ConsentDecisionRequestDecision; withdraw?: boolean };
const consentScopes = Object.values(ECounselingConsentScope);

const scopeLabels: Record<ECounselingConsentScope, string> = {
  [ECounselingConsentScope.AUDIO_VIDEO_RECORDING]: "Audio/video recording",
  [ECounselingConsentScope.LIVE_TRANSCRIPTION]: "Session transcription",
  [ECounselingConsentScope.TRANSCRIPT_STORAGE]: "Transcript storage",
};

const scopeDescriptions: Record<ECounselingConsentScope, string> = {
  [ECounselingConsentScope.AUDIO_VIDEO_RECORDING]: "Allows audio and video from this Counseling session to be recorded.",
  [ECounselingConsentScope.LIVE_TRANSCRIPTION]: "Allows speech from this session to be processed as text while transcription is active.",
  [ECounselingConsentScope.TRANSCRIPT_STORAGE]: "Allows the transcript produced for this session to be stored by the configured provider.",
};

const withdrawalSubjects: Record<ECounselingConsentScope, string> = {
  [ECounselingConsentScope.AUDIO_VIDEO_RECORDING]: "recording",
  [ECounselingConsentScope.LIVE_TRANSCRIPTION]: "transcription",
  [ECounselingConsentScope.TRANSCRIPT_STORAGE]: "transcript storage",
};

function scopeLabel(scope: ECounselingConsentScope): string {
  return scopeLabels[scope];
}

function scopeDescription(scope: ECounselingConsentScope): string {
  return scopeDescriptions[scope];
}

export function StudentConsentPanel({
  appointmentId,
  access,
  media,
}: {
  appointmentId: string;
  access: ECounselingAccess;
  media: MediaWorkspaceState;
}) {
  const queryClient = useQueryClient();
  const consents = useECounselingListMyConsents(appointmentId, {
    query: { enabled: access.canConsentSelf, retry: false },
  });
  const decide = useECounselingDecideMyConsent({ mutation: { retry: false } });
  const withdraw = useECounselingWithdrawMyConsent({ mutation: { retry: false } });
  const [action, setAction] = useState<StudentAction | null>(null);
  const [error, setError] = useState<{ scope: ECounselingConsentScope | null; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const rows = consents.data?.data.items ?? [];
  const latestWorkspace = queryClient.getQueryData<{ data: StudentWorkspaceResponse }>(getECounselingGetMyWorkspaceQueryKey(appointmentId));
  const latestMedia = latestWorkspace?.data.media ?? media;
  const scopeRows = consentScopes.flatMap((scope): Array<{ scope: ECounselingConsentScope; row: ConsentResponse | null }> => {
    const matches = rows.filter((row) => row.scope === scope);
    return matches.length ? matches.map((row) => ({ scope, row })) : [{ scope, row: null }];
  });

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingListMyConsentsQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getECounselingGetMyWorkspaceQueryKey(appointmentId) }),
    ]);
    return {
      rows: queryClient.getQueryData<Awaited<ReturnType<typeof import("@/lib/api/generated/e-counseling/e-counseling").eCounselingListMyConsents>>>(getECounselingListMyConsentsQueryKey(appointmentId))?.data.items ?? [],
    };
  }

  async function confirmAction() {
    if (!action) return;
    setError(null);
    setNotice(null);
    let mutationError: unknown;
    try {
      if (action.withdraw) {
        await withdraw.mutateAsync({ appointmentId, consentId: action.consentId });
      } else if (action.decision) {
        await decide.mutateAsync({ appointmentId, consentId: action.consentId, data: { decision: action.decision } });
      }
    } catch (caught) {
      mutationError = caught;
    }

    const canonicalState = await refreshCanonicalState();
    if (action.withdraw) {
      const canonical = canonicalState.rows.find((row) => row.id === action.consentId);
      if (canonical?.withdrawn_at && !canonical.effective) {
        setNotice("Consent has been withdrawn.");
      } else {
        setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "Consent withdrawal could not be confirmed. The current session state has been refreshed.") });
      }
    } else if (mutationError) {
      setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "The consent decision could not be saved. The current session state has been refreshed.") });
    } else {
      setNotice(action.decision === "APPROVED" ? "Your consent choice has been saved." : "Your choice has been saved. Counseling remains available.");
    }
    setAction(null);
  }

  return (
    <section aria-labelledby="e-counseling-consent-heading" className="min-w-0 border-t border-border pt-5">
      <h2 id="e-counseling-consent-heading" className="font-heading text-lg font-semibold text-ink">Media consent</h2>
      <p className="mt-2 text-sm leading-6 text-muted">Your media-consent choice does not affect your ability to receive Counseling.</p>
      {access.canConsentSelf ? (
        consents.isPending ? <div aria-busy="true"><span className="sr-only">Loading your session consent…</span><Skeleton className="mt-4 h-16 w-full" /><Skeleton className="mt-3 h-16 w-full" /></div> :
          consents.isError ? <div role="alert" className="mt-4 border-y border-danger/30 py-4"><p className="text-sm text-danger">Session consent could not be loaded.</p><Button className="mt-3" variant="secondary" onClick={() => void consents.refetch()}>Retry</Button></div> :
            <ul className="mt-4 divide-y divide-border border-y border-border">{scopeRows.map(({ scope, row }) => {
              const withdrawn = Boolean(row?.withdrawn_at);
              const canWithdraw = row?.decision === ECounselingConsentDecision.APPROVED && row.effective && !withdrawn;
              return (
                <li key={row?.id ?? scope} className="py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1"><h3 className="font-semibold text-ink">{scopeLabel(scope)}</h3><span className="text-sm text-muted">{row ? consentStatusLabel(row) : "Not requested"}</span></div>
                  <p className="mt-1 text-sm leading-6 text-muted">{scopeDescription(scope)}</p>
                  {row ? <p className="mt-1 text-xs text-muted">Requested {formatECounselingDateTime(row.requested_at)}{row.decided_at ? ` · Decided ${formatECounselingDateTime(row.decided_at)}` : ""}</p> : null}
                  {row?.decision === ECounselingConsentDecision.PENDING && !withdrawn ? <div className="mt-3 flex flex-wrap gap-2"><Button variant="primary" disabled={decide.isPending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.APPROVED }); }}>Approve</Button><Button variant="secondary" disabled={decide.isPending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.DENIED }); }}>Decline</Button></div> : null}
                  {canWithdraw && row ? <Button className="mt-3" variant="secondary" disabled={withdraw.isPending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, withdraw: true }); }}>Withdraw consent</Button> : null}
                  {row?.decision === ECounselingConsentDecision.DENIED && !withdrawn ? <p className="mt-2 text-sm text-muted">This media option will not be requested again for this session.</p> : null}
                  {error?.scope === scope ? <p role="alert" className="mt-3 text-sm text-danger">{scopeLabel(scope)}: {error.message}</p> : null}
                </li>
              );
            })}</ul>
      ) : <p className="mt-4 border-y border-border py-4 text-sm text-muted">Consent decisions are not available in your current access.</p>}
      {error && !rows.some((row) => row.scope === error.scope) ? <p role="alert" className="mt-3 text-sm text-danger">{error.message}</p> : null}
      {notice ? <p role="status" className="mt-3 text-sm text-success">{notice}</p> : null}
      {notice === "Consent has been withdrawn." && hasLiveOrTransitionalMedia(latestMedia) ? <p role="status" className="mt-2 text-sm text-muted">The provider is still reconciling the media state.</p> : null}
      <section aria-labelledby="e-counseling-media-activity-heading" className="mt-6 border-t border-border pt-4">
        <h3 id="e-counseling-media-activity-heading" className="text-sm font-semibold text-ink">Session media activity</h3>
        <dl className="mt-2 grid gap-3 sm:grid-cols-2"><div><dt className="text-xs font-semibold text-muted">Recording</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(media.recording.capture_status)}</dd></div><div><dt className="text-xs font-semibold text-muted">Transcription</dt><dd className="mt-1 text-sm text-ink">{captureStatusLabel(media.transcription.capture_status)}</dd></div></dl>
        {media.recording.capture_status === ECounselingCaptureStatus.ACTIVE ? <p role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm font-semibold text-ink">Recording active</p> : null}
        {media.transcription.capture_status === ECounselingCaptureStatus.ACTIVE ? <p role="status" className="mt-2 border-l-2 border-info pl-3 text-sm font-semibold text-ink">Session transcription active</p> : null}
      </section>
      <AlertDialog open={Boolean(action)} onOpenChange={(open) => { if (!open && !decide.isPending && !withdraw.isPending) setAction(null); }}>
        {action ? <AlertDialogContent>
          <AlertDialogTitle>{action.withdraw ? `Withdraw ${withdrawalSubjects[action.scope]} consent?` : `${action.decision === ConsentDecisionRequestDecision.APPROVED ? "Approve" : "Decline"} ${scopeLabel(action.scope).toLowerCase()}?`}</AlertDialogTitle>
          <AlertDialogDescription>{action.withdraw ? "This withdraws your consent for the rest of this session. Counseling continues to be available." : action.decision === ConsentDecisionRequestDecision.APPROVED ? scopeDescription(action.scope) : "This media option will not be requested again for this session. Your decision does not affect Counseling."}</AlertDialogDescription>
          <div className="mt-6 flex justify-end gap-2"><AlertDialogCancel asChild><Button variant="secondary" disabled={decide.isPending || withdraw.isPending}>Cancel</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="secondary" disabled={decide.isPending || withdraw.isPending} onClick={(event) => { event.preventDefault(); void confirmAction(); }}>{decide.isPending || withdraw.isPending ? "Saving…" : action.withdraw ? "Withdraw consent" : action.decision === ConsentDecisionRequestDecision.APPROVED ? "Approve" : "Decline"}</Button></AlertDialogAction></div>
        </AlertDialogContent> : null}
      </AlertDialog>
    </section>
  );
}
