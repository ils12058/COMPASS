"use client";

import { studentActionsQueryFamily } from "@/features/student-actions/student-actions-data";

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
const scopes = [ECounselingConsentScope.AUDIO_VIDEO_RECORDING];

// What the permission is called and, in one sentence, what it allows. Longer explanation sits under
// Details; the full consequence is repeated in the confirmation, where the decision is made.
// E-Counseling is recording-only: there is no transcription or transcript permission.
type ScopeCopy = { label: string; short: string; details: string; allow: ReactNode; withdrawSubject: string };

const copyByScope: Record<ECounselingConsentScope, ScopeCopy> = {
  [ECounselingConsentScope.AUDIO_VIDEO_RECORDING]: {
    label: "Audio/video recording",
    short: "Recording is optional and creates a saved audio/video file.",
    details: "If you agree, your counselor may start an audio/video recording of this session. Allowing doesn’t start it. You may withdraw permission during the session.",
    allow: (
      <>
        <p>Recording is optional. If you agree, your counselor may start an audio/video recording of this E-Counseling session. Allowing doesn’t start recording.</p>
        <p>You may withdraw permission during the session. If you do, COMPASS will ask the recording to stop. Anything already recorded stays subject to the University’s privacy and records requirements.</p>
      </>
    ),
    withdrawSubject: "recording",
  },
};

function scopeCopy(scope: ECounselingConsentScope): ScopeCopy {
  return copyByScope[scope];
}

// A Student's words for a decision: they allowed or declined it.
function decisionLabel(row: ConsentResponse | null): string {
  if (!row) return "Not requested";
  if (row.withdrawn_at) return "Withdrawn";
  if (row.decision === ECounselingConsentDecision.APPROVED) return row.effective ? "Allowed" : "No longer valid";
  if (row.decision === ECounselingConsentDecision.DENIED) return "Declined";
  return "Pending";
}

function dialogFor(action: StudentAction): { title: string; confirm: string; body: ReactNode } {
  const copy = scopeCopy(action.scope);
  const counseling = <p>Your choice doesn’t affect your access to Counseling.</p>;
  if (action.withdraw) {
    return {
      title: `Withdraw ${copy.withdrawSubject} permission?`,
      confirm: "Withdraw permission",
      body: (
        <>
          <p>This withdraws your permission for the rest of this session. A recording that’s running will be asked to stop.</p>
          <p>Withdrawing doesn’t delete files already created. They remain subject to the University’s records and privacy requirements, and copies already downloaded can’t be recalled. Counseling continues.</p>
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
}: {
  appointmentId: string;
  access: Pick<ECounselingAccess, "canConsentSelf">;
  media: MediaWorkspaceState;
  inCall?: boolean;
}) {
  const queryClient = useQueryClient();
  const consents = useECounselingListMyConsents(appointmentId, {
    // The single portal consent coordinator owns event/fallback freshness before and during calls.
    query: { enabled: access.canConsentSelf, retry: false, refetchInterval: false },
  });
  const decide = useECounselingDecideMyConsent({ mutation: { retry: false } });
  const withdraw = useECounselingWithdrawMyConsent({ mutation: { retry: false } });
  const [action, setAction] = useState<StudentAction | null>(null);
  const [error, setError] = useState<{ scope: ECounselingConsentScope | null; message: string } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const rows = consents.data?.data.items ?? [];
  const latestWorkspace = queryClient.getQueryData<{ data: StudentWorkspaceResponse }>(getECounselingGetMyWorkspaceQueryKey(appointmentId));
  const latestMedia = latestWorkspace?.data.media ?? media;
  const scopeRows = scopes.flatMap((scope): Array<{ scope: ECounselingConsentScope; row: ConsentResponse | null }> => {
    const matches = rows.filter((row) => row.scope === scope);
    return matches.length ? matches.map((row) => ({ scope, row })) : [{ scope, row: null }];
  });
  const pending = decide.isPending || withdraw.isPending;

  async function refreshCanonicalState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() }),
      queryClient.invalidateQueries({ queryKey: getECounselingListMyConsentsQueryKey(appointmentId) }, { cancelRefetch: false }),
      queryClient.invalidateQueries({ queryKey: getECounselingGetMyWorkspaceQueryKey(appointmentId) }, { cancelRefetch: false }),
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
      else setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "Couldn't confirm whether permission was withdrawn. The session has been refreshed.") });
    } else if (mutationError) {
      setError({ scope: action.scope, message: ecounselingErrorMessage(mutationError, "Couldn't save your choice. The session has been refreshed.") });
    } else {
      setNotice(action.decision === ConsentDecisionRequestDecision.APPROVED ? "Choice saved." : "Choice saved. Counseling remains available.");
    }
    setAction(null);
  }

  const dialog = action ? dialogFor(action) : null;

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
          <PanelMessage role="alert" tone="danger" action={<Button variant="secondary" onClick={() => void consents.refetch()}>Retry</Button>}>Couldn&apos;t load your recording permission. Try again.</PanelMessage>
        ) : (
          <ul className="divide-y divide-border">
            {scopeRows.map(({ scope, row }) => {
              const copy = scopeCopy(scope);
              const withdrawn = Boolean(row?.withdrawn_at);
              const awaiting = row?.decision === ECounselingConsentDecision.PENDING && !withdrawn;
              const approved = row?.decision === ECounselingConsentDecision.APPROVED && row.effective && !withdrawn;
              const invalid = row?.decision === ECounselingConsentDecision.APPROVED && !row.effective && !withdrawn;
              const canWithdraw = approved;
              const declined = row?.decision === ECounselingConsentDecision.DENIED && !withdrawn;
              const subject = copy.label.toLowerCase();
              const explanation = awaiting
                ? copy.short
                : declined
                  ? "This won’t be requested again for this session."
                  : withdrawn
                    ? "This permission is withdrawn for this session."
                    : invalid
                      ? "This permission is no longer valid."
                      : null;
              return (
                <li key={row?.id ?? scope} className="px-4 py-2.5 sm:px-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                    <h3 className="font-semibold text-ink">{copy.label}</h3>
                    <span className={cn("text-sm", awaiting ? "font-semibold text-ink" : "text-muted")}>{decisionLabel(row)}</span>
                  </div>
                  {row ? (
                    <>
                      {explanation ? <p className="mt-0.5 text-sm leading-5 text-muted">{explanation}</p> : null}
                      <Disclosure summary="Details" summaryClassName="min-h-10 text-xs">
                        <div className="space-y-1 pb-1 text-sm leading-6 text-muted">
                          {approved ? <p>{copy.short}</p> : null}
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
                      <Button className="min-h-11 min-w-11" aria-label={`Allow ${subject}`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.APPROVED }); }}>Allow</Button>
                      <Button className="min-h-11 min-w-11" variant="secondary" aria-label={`Decline ${subject}`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, decision: ConsentDecisionRequestDecision.DENIED }); }}>Decline</Button>
                    </div>
                  ) : null}
                  {canWithdraw && row ? (
                    <Button className="mt-1 min-h-11 px-3 py-1" variant="secondary" aria-label={`Withdraw ${copy.withdrawSubject} permission`} disabled={pending} onClick={() => { setError(null); setAction({ consentId: row.id, scope, withdraw: true }); }}>Withdraw permission</Button>
                  ) : null}
                  {error?.scope === scope ? <p role="alert" className="mt-2 text-sm text-danger">{copy.label}: {error.message}</p> : null}
                </li>
              );
            })}
          </ul>
        )
      ) : <PanelMessage>You don&apos;t have access to recording permission decisions.</PanelMessage>}
      {(error && !rows.some((row) => row.scope === error.scope)) || notice ? (
        <div className="border-t border-brand-line px-4 py-3 sm:px-5">
          {error && !rows.some((row) => row.scope === error.scope) ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
          {notice ? <p role="status" className="text-sm text-success">{notice}</p> : null}
          {notice === "Permission withdrawn." && hasLiveOrTransitionalMedia(latestMedia) ? <p className="mt-1 text-sm text-muted">Recording is still stopping.</p> : null}
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
