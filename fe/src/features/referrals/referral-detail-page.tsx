"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState, type ReactNode } from "react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { StepUpDialog } from "@/features/account/security/security-shared";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { callSlipErrorMessage } from "@/features/call-slips/call-slips-shared";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { ReferralActionsSection } from "@/features/referrals/referral-action-section";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { ReferralCallSlipSection } from "@/features/referrals/referral-call-slip-section";
import {
  ReferralAccessUnavailable,
  ReferralHeading,
  ReferralQueryError,
  referralErrorCode,
  referralErrorMessage,
  uncertainReferralMutation,
} from "@/features/referrals/referrals-shared";
import { downloadBinaryResponse } from "@/lib/browser-download";
import {
  getReferralsGetQueryKey,
  getReferralsListQueryKey,
  referralsDownloadPdf,
  referralsUpdateStatus,
  referralsVoid,
  useReferralsGet,
} from "@/lib/api/generated/referrals/referrals";
import { getCallSlipsListQueryKey, useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import type { ReferralDetailResponse } from "@/lib/api/generated/model";
import { formatDateOnly, formatDateTime } from "@/lib/date-time";

export function ReferralDetailPage({ referralId }: { referralId: string }) {
  const { user } = usePortalSession();
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const referral = useReferralsGet(referralId, {
    query: { enabled: referralAccess.canView, retry: false },
  });
  const linkedCurrent = useCallSlipsList(
    { referral_id: referralId, include_voided: false, page: 1, page_size: 1 },
    { query: { enabled: referralAccess.canView && callSlipAccess.canViewOperational, retry: false } },
  );

  if (!referralAccess.canView) {
    return <ReferralAccessUnavailable title="Referral unavailable" message="Your current access does not include Referral review." />;
  }
  if (referral.isError) {
    if (referralErrorCode(referral.error) === "referral_not_found") {
      return <ReferralAccessUnavailable title="Referral not found" message="This Referral does not exist or is outside your Referral scope." />;
    }
    return (
      <div className="space-y-7">
        <ReferralHeading title="Referral" backHref="/portal/referrals" />
        <ReferralQueryError error={referral.error} fallback="Referral detail could not be loaded." onRetry={() => void referral.refetch()} />
      </div>
    );
  }
  if (referral.isPending) {
    return <div className="space-y-4" aria-busy="true"><span className="sr-only">Loading Referral…</span><Skeleton className="h-16 w-full" /><Skeleton className="h-40 w-full" /><Skeleton className="h-64 w-full" /></div>;
  }

  const item = referral.data.data;
  const isVoided = Boolean(item.voided_at);
  const currentCallSlip = linkedCurrent.data?.data.items[0];
  const canCheckCallSlips = callSlipAccess.canViewOperational;

  async function refreshDetail(): Promise<ReferralDetailResponse | undefined> {
    const [detailResult] = await Promise.all([
      referral.refetch(),
      canCheckCallSlips ? linkedCurrent.refetch() : Promise.resolve(undefined),
    ]);
    return detailResult.isSuccess ? detailResult.data.data : undefined;
  }

  return (
    <div className="space-y-7">
      <ReferralHeading
        title={item.reference_code}
        description="Referral source record"
        backHref="/portal/referrals"
        action={<ReferralPdfDownload referral={item} />}
      />

      {isVoided ? (
        <div role="status" className="border-y border-warning/30 py-4">
          <p className="font-semibold text-warning">Voided</p>
          <p className="mt-1 text-sm text-ink">{item.void_reason}</p>
          <p className="mt-1 text-sm text-muted">Voided {formatDateTime(item.voided_at)}</p>
        </div>
      ) : null}

      <RecordSection title="Referral identity">
        <div>
          <dt className="text-xs font-semibold text-muted">Reference</dt>
          <dd className="mt-1 font-mono text-sm font-semibold text-ink">{item.reference_code}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Form revision</dt>
          <dd className="mt-1 text-sm text-ink">{item.form_revision.official_code ?? "Official code not recorded"}{item.form_revision.official_revision ? ` · Revision ${item.form_revision.official_revision}` : ""}</dd>
          <dd className="mt-1 text-xs text-muted">Internal schema version {item.form_revision.internal_schema_version}</dd>
        </div>
      </RecordSection>

      <RecordSection title="Student">
        <div>
          <dt className="text-xs font-semibold text-muted">Name on source Referral</dt>
          <dd className="mt-1 text-sm text-ink">{item.student_name_snapshot}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Course / Year / Block snapshot</dt>
          <dd className="mt-1 text-sm text-ink">{item.course_year_block_snapshot}</dd>
        </div>
      </RecordSection>

      <RecordSection title="Chronology">
        <div>
          <dt className="text-xs font-semibold text-muted">Date referred</dt>
          <dd className="mt-1 text-sm text-ink">{formatDateOnly(item.referred_on)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Received by Guidance/GCO</dt>
          <dd className="mt-1 text-sm text-ink">{formatDateTime(item.received_at)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Recorded in COMPASS</dt>
          <dd className="mt-1 text-sm text-ink">{formatDateTime(item.created_at)}</dd>
        </div>
      </RecordSection>

      <RecordSection title="Referral">
        <div>
          <dt className="text-xs font-semibold text-muted">Referrer name</dt>
          <dd className="mt-1 text-sm text-ink">{item.referrer_name}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs font-semibold text-muted">Reason for referral</dt>
          <dd className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{item.reason}</dd>
        </div>
      </RecordSection>

      <section aria-labelledby="referral-status-note-heading" className="border-t border-border py-6">
        <h2 id="referral-status-note-heading" className="font-heading text-xl font-semibold text-ink">Status note</h2>
        <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">{item.status_note || "No status note recorded."}</p>
        {referralAccess.canManage && !isVoided ? (
          <StatusNoteEditor key={`${item.id}-${item.updated_at}`} referralId={item.id} statusNote={item.status_note} />
        ) : null}
      </section>

      <ReferralActionsSection
        referral={item}
        canManage={referralAccess.canManage}
        isVoided={isVoided}
        canManageCallSlips={callSlipAccess.canManageOperational && canCheckCallSlips}
        onRefresh={refreshDetail}
      />

      <ReferralCallSlipSection
        referral={item}
        canManageReferral={referralAccess.canManage}
        canViewCallSlips={canCheckCallSlips}
        canManageCallSlips={callSlipAccess.canManageOperational}
        currentItems={linkedCurrent.data?.data.items ?? []}
        currentPending={linkedCurrent.isPending}
        currentError={linkedCurrent.isError ? linkedCurrent.error : null}
        retryCurrent={() => void linkedCurrent.refetch()}
        onRefresh={refreshDetail}
      />

      <section aria-labelledby="referral-operational-actions-heading" className="border-t border-border py-6">
        <h2 id="referral-operational-actions-heading" className="font-heading text-xl font-semibold text-ink">Operational actions</h2>
        {referralAccess.canManage && !isVoided ? (
          canCheckCallSlips && linkedCurrent.isPending ? (
            <p role="status" className="mt-3 text-sm text-muted">Checking linked Call Slip state before enabling Referral void.</p>
          ) : canCheckCallSlips && linkedCurrent.isError ? (
            <div className="mt-3 max-w-2xl">
              <p role="alert" className="text-sm text-danger">{callSlipErrorMessage(linkedCurrent.error, "Linked Call Slip state could not be checked. Refresh before voiding this Referral.")}</p>
              <Button className="mt-3" variant="secondary" onClick={() => void linkedCurrent.refetch()}>Refresh linked Call Slip state</Button>
            </div>
          ) : currentCallSlip ? (
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">This Referral cannot be voided while it has a non-voided linked Call Slip.</p>
          ) : (
            <VoidReferralButton
              referral={item}
              onRefresh={refreshDetail}
            />
          )
        ) : referralAccess.canManage && isVoided ? (
          <p className="mt-3 text-sm text-muted">This Referral is voided. Its source content and PDF remain available for review.</p>
        ) : (
          <p className="mt-3 text-sm text-muted">Your current access is read-only for this Referral.</p>
        )}
      </section>
    </div>
  );

}

function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="border-t border-border py-6">
      <h2 className="font-heading text-xl font-semibold text-ink">{title}</h2>
      <dl className="mt-4 grid gap-x-8 gap-y-5 sm:grid-cols-2">{children}</dl>
    </section>
  );
}

function ReferralPdfDownload({ referral }: { referral: ReferralDetailResponse }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setPending(true);
    setError(null);
    try {
      const response = await referralsDownloadPdf(referral.id);
      downloadBinaryResponse(response, `referral-${referral.reference_code}.pdf`);
    } catch (caught) {
      setError(referralErrorMessage(caught, "The document could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <Button variant="secondary" onClick={() => void download()} disabled={pending}>
        <Download aria-hidden="true" size={16} />
        {pending ? "Preparing…" : "Download Referral Slip"}
      </Button>
      {error ? <p role="alert" className="max-w-sm text-sm text-danger">{error}</p> : null}
    </div>
  );
}

function StatusNoteEditor({ referralId, statusNote }: { referralId: string; statusNote: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(statusNote);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const update = useMutation({
    mutationFn: () => referralsUpdateStatus(referralId, { status_note: value }),
    retry: false,
  });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await update.mutateAsync();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getReferralsGetQueryKey(referralId) }),
        queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() }),
      ]);
      setEditing(false);
      setNotice("Status note updated.");
    } catch (caught) {
      if (referralErrorCode(caught) === "recent_mfa_required") {
        setNotice("Verify your authenticator, then submit the status note again.");
        setStepUpOpen(true);
      } else {
        setError(referralErrorMessage(caught, "The status note could not be updated."));
      }
    }
  }

  return (
    <div className="mt-3">
      {!editing ? (
        <Button variant="secondary" onClick={() => { setEditing(true); setError(null); setNotice(null); }}>
          Update status note
        </Button>
      ) : (
        <form className="max-w-2xl space-y-3 border-l-2 border-border pl-4" onSubmit={submit} aria-busy={update.isPending}>
          <div className="grid gap-2">
            <Label htmlFor="referral-status-note-editor">Status note</Label>
            <Textarea id="referral-status-note-editor" rows={4} maxLength={1_000} value={value} disabled={update.isPending} onChange={(event) => setValue(event.target.value)} />
            <p className="text-xs text-muted">{value.length} / 1,000 characters. Leave blank to clear the note.</p>
          </div>
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save status note"}</Button>
            <Button type="button" variant="secondary" disabled={update.isPending} onClick={() => { setEditing(false); setValue(statusNote); setError(null); }}>Cancel</Button>
          </div>
        </form>
      )}
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      <StepUpDialog open={stepUpOpen} onOpenChange={setStepUpOpen} onVerified={() => setNotice("Verification complete. Submit the status note again to continue.")} />
    </div>
  );
}

function VoidReferralButton({
  referral,
  onRefresh,
}: {
  referral: ReferralDetailResponse;
  onRefresh: () => Promise<ReferralDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stepUpOpen, setStepUpOpen] = useState(false);
  const voidMutation = useMutation({
    mutationFn: () => referralsVoid(referral.id, { reason: reason.trim() }),
    retry: false,
  });

  async function confirmVoid() {
    setError(null);
    setNotice(null);
    if (!reason.trim()) {
      setError("Void reason is required.");
      return;
    }
    try {
      await voidMutation.mutateAsync();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getReferralsGetQueryKey(referral.id) }),
        queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getCallSlipsListQueryKey() }),
      ]);
      setOpen(false);
      setNotice("Referral voided.");
      setReason("");
    } catch (caught) {
      const code = referralErrorCode(caught);
      if (code === "recent_mfa_required") {
        setOpen(false);
        setNotice("Verify your authenticator, then review and confirm the void again.");
        setStepUpOpen(true);
      } else if (code === "referral_conflict" || uncertainReferralMutation(caught)) {
        const refreshed = await onRefresh();
        if (refreshed?.voided_at) {
          setOpen(false);
          setNotice("The Referral is already voided.");
        } else if (code === "referral_conflict") {
          setError(referralErrorMessage(caught, "The Referral could not be voided."));
        } else if (refreshed) {
          setError("The Referral is not shown as voided after refreshing. Review the current record before confirming again.");
        } else {
          setError("The Referral could not be refreshed. Do not retry the void until the current record can be checked.");
        }
      } else {
        setError(referralErrorMessage(caught, "The Referral could not be voided."));
      }
    }
  }

  return (
    <>
      <Button variant="danger" onClick={() => { setOpen(true); setError(null); setNotice(null); }}>
        Void Referral
      </Button>
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      <AlertDialog open={open} onOpenChange={(next) => { if (!voidMutation.isPending) setOpen(next); }}>
        <AlertDialogContent onEscapeKeyDown={(event) => { if (voidMutation.isPending) event.preventDefault(); }}>
          <AlertDialogTitle>Void Referral {referral.reference_code}?</AlertDialogTitle>
          <AlertDialogDescription>
            Voiding keeps the source record for review but prevents status-note updates, new actions, and linked Call Slip issuance. This does not delete the Referral.
          </AlertDialogDescription>
          <div className="mt-4 grid gap-2">
            <Label htmlFor="referral-void-reason">Void reason</Label>
            <Textarea id="referral-void-reason" rows={3} maxLength={1_000} required value={reason} disabled={voidMutation.isPending} onChange={(event) => setReason(event.target.value)} />
            <p className="text-xs text-muted">{reason.length} / 1,000 characters</p>
          </div>
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={voidMutation.isPending}>Cancel</Button>
            </AlertDialogCancel>
            <Button variant="danger" disabled={voidMutation.isPending || !reason.trim()} onClick={() => void confirmVoid()}>
              {voidMutation.isPending ? "Voiding…" : "Void Referral"}
            </Button>
          </div>
        </AlertDialogContent>
      </AlertDialog>
      <StepUpDialog
        open={stepUpOpen}
        onOpenChange={setStepUpOpen}
        onVerified={() => {
          setNotice("Verification complete. Review the reason and confirm the void again.");
          setOpen(true);
        }}
      />
    </>
  );
}
