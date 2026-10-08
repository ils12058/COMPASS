"use client";

import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Disclosure } from "@/components/ui/disclosure";
import { Panel, PanelHeader, PanelMessage } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import type { ECounselingAccess } from "@/features/ecounseling/ecounseling-access";
import { ecounselingErrorMessage, formatECounselingDateTime, hasLiveOrTransitionalMedia } from "@/features/ecounseling/ecounseling-shared";
import { ConsentDecisionRequestDecision, ECounselingConsentDecision, ECounselingConsentScope, type ConsentResponse, type MediaWorkspaceState, type StudentWorkspaceResponse } from "@/lib/api/generated/model";
import {
  getECounselingGetMyWorkspaceQueryKey,
  getECounselingListMyConsentsQueryKey,
  useECounselingDecideMyConsent,
  useECounselingListMyConsents,
  useECounselingWithdrawMyConsent,
  type eCounselingListMyConsentsResponseSuccess,
} from "@/lib/api/generated/e-counseling/e-counseling";
import { cn } from "@/lib/utils/cn";

type StudentAction = { consentId: string; scope: ECounselingConsentScope; decision?: ConsentDecisionRequestDecision; withdraw?: boolean };
const v1Scopes = [ECounselingConsentScope.AUDIO_VIDEO_RECORDING, ECounselingConsentScope.LIVE_TRANSCRIPTION, ECounselingConsentScope.TRANSCRIPT_STORAGE];
const v2Scopes = [ECounselingConsentScope.SESSION_MEDIA_CAPTURE, ECounselingConsentScope.TRANSCRIPT_STORAGE];

// What each permission is called and, in one sentence, what it allows. Longer explanation sits under
// Details; the full consequence is repeated in the confirmation, where the decision is made.
type ScopeCopy = { label: string; short: string; details: string; allow: ReactNode; withdrawSubject: string };

const v1Copy: Record<ECounselingConsentScope, ScopeCopy> = {
  [ECounselingConsentScope.AUDIO_VIDEO_RECORDING]: {
    label: "Audio/video recording",
    short: "Allows audio and video from this Counseling session to be recorded.",
    details: "Allowing doesn’t start recording. Your counselor starts it separately.",
    allow: <p>Audio and video from this Counseling session may be recorded. Allowing doesn’t start recording.</p>,
    withdrawSubject: "recording",
  },
  [ECounselingConsentScope.LIVE_TRANSCRIPTION]: {
    label: "Session transcription",
    short: "Allows speech from this session to be processed as text while transcription is active.",
    details: "Allowing doesn’t start transcription. Transcript storage is a separate choice.",
    allow: <p>Speech from this session may be processed as text while transcription is active. Allowing doesn’t start transcription, and transcript storage is a separate choice.</p>,
    withdrawSubject: "transcription",
  },
  [ECounselingConsentScope.TRANSCRIPT_STORAGE]: {
    label: "Transcript storage",
    short: "Allows the transcript of this session to be stored by the video service.",
    details: "A transcript is stored only when transcription is also allowed and your counselor chooses to store it.",
    allow: <p>The transcript of this session may be stored by the video service, only when transcription is also allowed and your counselor chooses to store it.</p>,
    withdrawSubject: "transcript storage",
  },
  [ECounselingConsentScope.SESSION_MEDIA_CAPTURE]: {
    label: "Recording & live transcription",
    short: "Recording creates a saved audio/video file.",
    details: "",
    allow: null,
    withdrawSubject: "recording and live transcription",
  },
};

const v2Copy: Partial<Record<ECounselingConsentScope, ScopeCopy>> = {
  [ECounselingConsentScope.SESSION_MEDIA_CAPTURE]: {
    label: "Recording & live transcription",
    short: "Recording creates a saved audio/video file.",
    details: "Your counselor may record audio/video or use live transcription. Live transcription is only saved when transcript storage is separately allowed. Approval doesn’t start either operation.",
    allow: (
      <>
        <p>Your counselor may record this session, which creates a saved audio/video file, and may use live transcription.</p>
        <p>Live transcription is saved as a transcript only if you also allow transcript storage. Allowing doesn’t start either one.</p>
      </>
    ),
    withdrawSubject: "recording and live transcription",
  },
  [ECounselingConsentScope.TRANSCRIPT_STORAGE]: {
    label: "Transcript storage",
    short: "Allows a transcript file to be saved.",
    details: "A transcript is saved only if your counselor deliberately starts transcription with saving, and only while media permission is allowed. Saved transcripts may be downloaded by your assigned counselor after the session.",
    allow: <p>A transcript file may be saved if your counselor deliberately starts transcription with saving. Saved transcripts may be downloaded by your assigned counselor after the session.</p>,
    withdrawSubject: "transcript storage",
  },
};

function scopeCopy(scope: ECounselingConsentScope, isV2: boolean): ScopeCopy {
  return (isV2 ? v2Copy[scope] : undefined) ?? v1Copy[scope];
}

// A Student's words for a decision: they allowed or declined it.
function decisionLabel(row: ConsentResponse | null): string {
  if (!row) return "Not requested";
  if (row.withdrawn_at) return "Withdrawn";
  if (row.decision === ECounselingConsentDecision.APPROVED) return row.effective ? "Allowed" : "No longer valid";
  if (row.decision === ECounselingConsentDecision.DENIED) return "Declined";
  return "Pending";
}

function dialogFor(action: StudentAction, isV2: boolean): { title: string; confirm: string; body: ReactNode } {
  const copy = scopeCopy(action.scope, isV2);
  const counseling = <p>Your choice doesn’t affect your access to Counseling.</p>;
  if (action.withdraw) {
    return {
      title: `Withdraw ${copy.withdrawSubject} permission?`,
      confirm: "Withdraw permission",
      body: (
        <>
          <p>This withdraws your permission for the rest of this session. Recording or transcription that’s running will be asked to stop.</p>
          <p>Files already created aren’t deleted right away; institutional retention rules and holds govern them. Counseling continues.</p>
        </>
      ),
    };
  }
  if (action.decision === ConsentDecisionRequestDecision.APPROVED) {
    return { title: `Allow ${copy.label.toLowerCase()}?`, confirm: "Allow", body: <>{copy.allow}{counseling}</> };
  }
  return {
    title: `Decline ${copy.label.toLowerCase()}?`,
    confirm: "Decline",
    body: <><p>This won’t be requested again for this session.</p>{counseling}</>,
  };
}

export function StudentConsentPanel({
  appointmentId,
  access,
  media,
  inCall = false,
}: {
  appointmentId: string;
  access: Pick<ECounselingAccess, "canConsentSelf">;
  media: MediaWorkspaceState;
  inCall?: boolean;
}) {
  const queryClient = useQueryClient();
  const consents = useECounselingListMyConsents(appointmentId, {
    // A counselor's request made during the call appears without reloading.
    query: { enabled: access.canConsentSelf, retry: false, refetchInterval: inCall ? 7000 : false },
  });
  const decide = useECounselingDecideMyConsent({ mutation: { retry: false } });
  const withdraw = useECounselingWithdrawMyConsent({ mutation: { retry: false } });
  const [action, setAction] = useState<StudentAction | null>(null);
  const [error, setError] = useState<{ scope: ECounselingConsentScope | null; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const rows = consents.data?.data.items ?? [];
  const latestWorkspace = queryClient.getQueryData<{ data: StudentWorkspaceResponse }>(getECounselingGetMyWorkspaceQueryKey(appointmentId));
  const latestMedia = latestWorkspace?.data.media ?? media;
  const isV2 = latestMedia.media_policy_version === 2;
  const scopeRows = (isV2 ? v2Scopes : v1Scopes).flatMap((scope): Array<{ scope: ECounselingConsentScope; row: ConsentResponse | null }> => {
    const matches = rows.filter((row) => row.scope === scope);
    return matches.length ? matches.map((row) => ({ scope, row })) : [{ scope, row: null }];
  });
  const pending = decide.isPending || withdraw.isPending;

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getECounselingListMyConsentsQueryKey(appointmentId) }),
      queryClient.invalidateQueries({ queryKey: getECounselingGetMyWorkspaceQueryKey(appointmentId) }),
    ]);
    return queryClient.getQueryData<eCounselingListMyConsentsResponseSuccess>(getECounselingListMyConsentsQueryKey(appointmentId))?.data.items ?? [];
  }

  async function confirmAction() {
    if (!action) return;
    setError(null);
    setNotice(null);
    let mutationError: unknown;
    try {
      if (action.withdraw) await withdraw.mutateAsync({ appointmentId, consentId: action.consentId });
      else if (action.decision) await decide.mutateAsync({ appointmentId, consentId: action.consentId, data: { decision: action.decision } });
    } catch (caught) {
      mutationError = caught;
    }

    const canonicalRows = await refreshCanonicalState();
    if (action.withdraw) {
      const canonical = canonicalRows.find((row) => row.id === action.consentId);
      if (canonical?.withdrawn_at && !canonical.effective) setNotice("Permission withdrawn.");
      else setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "Your withdrawal couldn’t be confirmed. The session has been refreshed.") });
    } else if (mutationError) {
      setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "Your choice couldn’t be saved. The session has been refreshed.") });
    } else {
      setNotice(action.decision === ConsentDecisionRequestDecision.APPROVED ? "Your choice has been saved." : "Your choice has been saved. Counseling remains available.");
    }
    setAction(null);
  }

  const dialog = action ? dialogFor(action, isV2) : null;

  return (
    <Panel aria-labelledby="e-counseling-consent-heading">
      <PanelHeader
        title="Media permissions"
        titleId="e-counseling-consent-heading"
        description="Your choices don’t affect your access to Counseling."
      />
      {access.canConsentSelf ? (
        consents.isPending ? (
          <div aria-busy="true" className="px-4 py-4 sm:px-5"><span className="sr-only">Loading your media permissions…</span><Skeleton className="h-12 w-full" /><Skeleton className="mt-3 h-12 w-full" /></div>
        ) : consents.isError ? (
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void consents.refetch()}>Retry</Button>}>Your media permissions couldn’t be loaded.</PanelMessage>
        ) : (
          <ul className="divide-y divide-border">
            {scopeRows.map(({ scope, row }) => {
              const copy = scopeCopy(scope, isV2);
              const withdrawn = Boolean(row?.withdrawn_at);
              const awaiting = row?.decision === ECounselingConsentDecision.PENDING && !withdrawn;
              const canWithdraw = row?.decision === ECounselingConsentDecision.APPROVED && row.effective && !withdrawn;
              const declined = row?.decision === ECounselingConsentDecision.DENIED && !withdrawn;
              const subject = copy.label.toLowerCase();
              return (
                <li key={row?.id ?? scope} className="px-4 py-3 sm:px-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                    <h3 className="font-semibold text-ink">{copy.label}</h3>
                    <span className={cn("text-sm", awaiting ? "font-semibold text-ink" : "text-muted")}>{decisionLabel(row)}</span>
                  </div>
                  {row ? (
                    <>
                      <p className="mt-0.5 text-sm leading-6 text-muted">{declined ? "This won’t be requested again for this session." : copy.short}</p>
                      <Disclosure summary="Details" summaryClassName="min-h-9 text-xs">
                        <div className="space-y-1 pb-1 text-sm leading-6 text-muted">
                          {copy.details ? <p>{copy.details}</p> : null}
                          <p className="text-xs">
                            Requested {formatECounselingDateTime(row.requested_at)}
                            {row.decided_at ? ` · Decided ${formatECounselingDateTime(row.decided_at)}` : ""}
                            {row.withdrawn_at ? ` · Withdrawn ${formatECounselingDateTime(row.withdrawn_at)}` : ""}
                          </p>
                        </div>
                      </Disclosure>
                    </>
                  ) : null}
                  {awaiting && row ? (
                    <div className="mt-1.5 flex flex-wrap gap-2">
                      <Button aria-label={`Allow ${subject}`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.APPROVED }); }}>Allow</Button>
                      <Button variant="secondary" aria-label={`Decline ${subject}`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.DENIED }); }}>Decline</Button>
                    </div>
                  ) : null}
                  {canWithdraw && row ? (
                    <Button className="mt-1 min-h-9 px-3 py-1" variant="secondary" aria-label={`Withdraw ${copy.withdrawSubject} permission`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, withdraw: true }); }}>Withdraw permission</Button>
                  ) : null}
                  {error?.scope === scope ? <p role="alert" className="mt-2 text-sm text-danger">{copy.label}: {error.message}</p> : null}
                </li>
              );
            })}
          </ul>
        )
      ) : <PanelMessage>Media permission decisions are unavailable to this account.</PanelMessage>}
      {(error && !rows.some((row) => row.scope === error.scope)) || notice ? (
        <div className="border-t border-brand-line px-4 py-3 sm:px-5">
          {error && !rows.some((row) => row.scope === error.scope) ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
          {notice ? <p role="status" className="text-sm text-success">{notice}</p> : null}
          {notice === "Permission withdrawn." && hasLiveOrTransitionalMedia(latestMedia) ? <p className="mt-1 text-sm text-muted">Recording or transcription is still stopping.</p> : null}
        </div>
      ) : null}
      <ConsequentialActionDialog
        open={Boolean(action)}
        title={dialog?.title ?? ""}
        confirmLabel={dialog?.confirm ?? ""}
        pendingLabel="Saving…"
        pending={pending}
        error={null}
        onOpenChange={(open) => {
          if (!open && !pending) setAction(null);
        }}
        onConfirm={() => void confirmAction()}
      >
        {dialog?.body}
      </ConsequentialActionDialog>
    </Panel>
  );
}
