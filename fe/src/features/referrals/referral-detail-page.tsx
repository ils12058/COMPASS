"use client";

import { PageAction } from "@/components/ui/page-action";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useState, type ReactNode } from "react";

import { ReferralHelp } from "@/features/referrals/referral-help";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader, PanelSection } from "@/components/ui/panel";
import { getCallSlipAccess } from "@/features/call-slips/call-slips-access";
import { callSlipErrorMessage } from "@/features/call-slips/call-slips-shared";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { ReferralActionsSection } from "@/features/referrals/referral-action-section";
import { getReferralAccess } from "@/features/referrals/referrals-access";
import { ReferralCallSlipSection } from "@/features/referrals/referral-call-slip-section";
import {
  keepStatusNoteText,
  reconcileStatusNote,
  startStatusNoteDraft,
  statusNoteConflict,
} from "@/features/referrals/referral-status-note";
import { canViewStudentSupportContext } from "@/features/student-support/student-support-access";
import { StudentSupportContextSection } from "@/features/student-support/student-support-context-section";
import {
  ReferralAccessUnavailable,
  ReferralDetailSkeleton,
  ReferralHeading,
  ReferralQueryError,
  referralErrorCode,
  referralErrorMessage,
  uncertainReferralMutation,
} from "@/features/referrals/referrals-shared";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";
import {
  getReferralsGetQueryKey,
  getReferralsListQueryKey,
  referralsDownloadPdf,
  referralsUpdateStatus,
  referralsVoid,
  useReferralsGet,
} from "@/lib/api/generated/referrals/referrals";
import { getCallSlipsListQueryKey, useCallSlipsList } from "@/lib/api/generated/call-slips/call-slips";
import { CallSlipLifecycleStateValue, type ReferralDetailResponse } from "@/lib/api/generated/model";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

export function ReferralDetailPage({ referralId }: { referralId: string }) {
  const { user } = usePortalSession();
  const referralAccess = getReferralAccess(user);
  const callSlipAccess = getCallSlipAccess(user);
  const canViewSupportContext = canViewStudentSupportContext(user);
  const referral = useReferralsGet(referralId, {
    query: { enabled: referralAccess.canView, retry: false },
  });
  const linkedCurrent = useCallSlipsList(
    { referral_id: referralId, include_voided: false, page: 1, page_size: 1 },
    { query: { enabled: referralAccess.canView && callSlipAccess.canViewOperational, retry: false } },
  );

  // A refresh that fails for a transient reason keeps the last confirmed Referral on the page, with
  // its open editors. A refusal, a missing Referral, or a first load that fails replaces it.
  const referralData = safeQueryData(referral);

  if (!referralAccess.canView) {
    return <ReferralAccessUnavailable title="Referral unavailable" message="You don’t have access to review referrals." />;
  }
  if (referral.isPending) {
    return <ReferralDetailSkeleton />;
  }
  if (!referralData) {
    if (referralErrorCode(referral.error) === "referral_not_found") {
      return <ReferralAccessUnavailable title="Referral not found" message="This referral could not be found or is unavailable to you." />;
    }
    return (
      <div className="space-y-5">
        <ReferralHeading title="Referral" backHref="/portal/referrals" />
        <ReferralQueryError error={referral.error} fallback="Referral detail could not be loaded." onRetry={() => void referral.refetch()} />
      </div>
    );
  }

  const item = referralData.data;
  const refreshFailed = referral.isError;
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
    <div className="space-y-5">
      <ReferralHeading
        title={item.reference_code}
        help={<ReferralHelp />}
        backHref="/portal/referrals"
        action={<ReferralPdfDownload referral={item} />}
      />

      {refreshFailed ? (
        <RefreshFailureNotice
          message="The latest Referral details could not be refreshed. Showing the last confirmed record. Saving the status note and voiding wait until it refreshes."
          retrying={referral.isFetching}
          onRetry={() => void referral.refetch()}
        />
      ) : null}

      {isVoided ? (
        <Notice role="status" tone="warning" title={<span className="text-warning">Voided</span>}>
          <p className="text-ink">{item.void_reason}</p>
          <p className="mt-1 text-muted">Voided {formatInstitutionalDateTime(item.voided_at)}</p>
          {item.voided_by ? <p className="mt-1 text-muted">Voided by {item.voided_by.display_name}</p> : null}
        </Notice>
      ) : null}

      {/* One record sheet in the order of the paper referral; the source note follows it. */}
      <Panel as="div">
      <RecordSection title="Referral identity">
        <div>
          <dt className="text-xs font-semibold text-muted">Reference</dt>
          <dd className="mt-1 font-mono text-sm font-semibold text-ink">{item.reference_code}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Form revision</dt>
          <dd className="mt-1 text-sm text-ink">{item.form_revision.official_code ?? "Official code not recorded"}{item.form_revision.official_revision ? ` · Revision ${item.form_revision.official_revision}` : ""}</dd>
        </div>
      </RecordSection>

      <RecordSection title="Student on referral">
        <div>
          <dt className="text-xs font-semibold text-muted">Name on referral</dt>
          <dd className="mt-1 text-sm text-ink">{item.student_name_snapshot}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Course / Year / Block on referral</dt>
          <dd className="mt-1 text-sm text-ink">{item.course_year_block_snapshot}</dd>
        </div>
      </RecordSection>

      <RecordSection title="Current Student account">
        <div><dt className="text-xs font-semibold text-muted">Name</dt><dd className="mt-1 text-sm text-ink">{item.student.display_name}</dd></div>
        <div><dt className="text-xs font-semibold text-muted">Institutional ID</dt><dd className="mt-1 text-sm text-ink">{item.student.institutional_id ?? "Not recorded"}</dd></div>
      </RecordSection>

      <RecordSection title="Chronology">
        <div>
          <dt className="text-xs font-semibold text-muted">Date referred</dt>
          <dd className="mt-1 text-sm text-ink">{formatDateOnly(item.referred_on)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Received by Guidance/GCO</dt>
          <dd className="mt-1 text-sm text-ink">{formatInstitutionalDateTime(item.received_at)}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Recorded in COMPASS</dt>
          <dd className="mt-1 text-sm text-ink">{formatInstitutionalDateTime(item.created_at)}</dd>
        </div>
        <div><dt className="text-xs font-semibold text-muted">Encoded by</dt><dd className="mt-1 text-sm text-ink">{item.recorded_by?.display_name ?? "Not recorded"}</dd></div>
      </RecordSection>

      <RecordSection title="Referral">
        <div>
          <dt className="text-xs font-semibold text-muted">Referrer name</dt>
          <dd className="mt-1 text-sm text-ink">{item.referrer_name}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-xs font-semibold text-muted">Reason for referral</dt>
          <dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere] text-sm leading-6 text-ink">{item.reason}</dd>
        </div>
      </RecordSection>

      <PanelSection title="Status note" titleId="referral-status-note-heading">
        <p className="whitespace-pre-wrap break-words text-sm leading-6 text-ink">{item.status_note || "No status note recorded."}</p>
        {referralAccess.canManage && !isVoided ? (
          <StatusNoteEditor key={item.id} referralId={item.id} statusNote={item.status_note} saveUnavailable={refreshFailed} />
        ) : null}
      </PanelSection>
      </Panel>

      {canViewSupportContext ? <StudentSupportContextSection studentId={item.student.id} /> : null}

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

      {/* Accounts that can only read a Referral have no operational actions to look for. */}
      {referralAccess.canManage ? (
      <Panel aria-labelledby="referral-operational-actions-heading">
        <PanelHeader title="Operational actions" titleId="referral-operational-actions-heading" />
        <PanelBody className="*:first:mt-0">
        {!isVoided ? (
          refreshFailed ? (
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">Voiding is unavailable until the Referral refreshes.</p>
          ) : canCheckCallSlips && linkedCurrent.isPending ? (
            <p role="status" className="mt-3 text-sm text-muted">Checking linked Call Slip state before enabling Referral void.</p>
          ) : canCheckCallSlips && linkedCurrent.isError ? (
            <div className="mt-3 max-w-2xl">
              <p role="alert" className="text-sm text-danger">{callSlipErrorMessage(linkedCurrent.error, "Linked Call Slip state could not be checked. Refresh before voiding this Referral.")}</p>
              <Button className="mt-3" variant="secondary" onClick={() => void linkedCurrent.refetch()}>Refresh linked Call Slip state</Button>
            </div>
          ) : currentCallSlip ? (
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
              {currentCallSlip.state === CallSlipLifecycleStateValue.COMPLETED
                ? "This Referral cannot be voided because the linked Call Slip records a completed interview."
                : "This Referral cannot be voided while its linked Call Slip is active. Void the Call Slip first."}
            </p>
          ) : (
            <VoidReferralButton
              referral={item}
              onRefresh={refreshDetail}
            />
          )
        ) : (
          <p className="mt-3 text-sm text-muted">This Referral is voided. Its source content and PDF remain available for review.</p>
        )}
        </PanelBody>
      </Panel>
      ) : null}
    </div>
  );

}

function RecordSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <PanelSection title={title} titleId={"referral-" + title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}>
      <dl className="grid grid-cols-[minmax(0,1fr)] gap-x-8 gap-y-4 sm:grid-cols-2">{children}</dl>
    </PanelSection>
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
      downloadBinaryResponse(response, institutionalPdfFallbackFilename("referralSlip", referral.id));
    } catch (caught) {
      setError(referralErrorMessage(caught, "The document could not be released right now. Try again later."));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <PageAction icon={Download} variant="secondary" onClick={() => void download()} disabled={pending} aria-busy={pending} label={pending ? "Preparing…" : "Download Referral Slip"} />
      {error ? <p role="alert" className="max-w-sm text-sm text-danger">{error}</p> : null}
    </div>
  );
}

function StatusNoteEditor({
  referralId,
  statusNote,
  saveUnavailable,
}: {
  referralId: string;
  // The saved note. A reload never replaces text the person changed (referral-status-note.ts).
  statusNote: string;
  saveUnavailable: boolean;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => startStatusNoteDraft(statusNote));
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: (statusNoteValue: string) => referralsUpdateStatus(referralId, { status_note: statusNoteValue }),
    retry: false,
  });
  // A newer saved note replaces unchanged text while rendering, before it can be shown or saved.
  const reconciled = reconcileStatusNote(draft, statusNote);
  if (reconciled !== draft) setDraft(reconciled);
  const conflict = statusNoteConflict(reconciled, statusNote);
  const { editing, value } = reconciled;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (conflict || saveUnavailable) return;
    setError(null);
    setNotice(null);
    try {
      const response = await update.mutateAsync(value);
      // The saved note is the new baseline before the Referral reloads, so the reload is not a change.
      setDraft(startStatusNoteDraft(response.data.status_note));
      setNotice("Status note updated.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getReferralsGetQueryKey(referralId) }),
        queryClient.invalidateQueries({ queryKey: getReferralsListQueryKey() }),
      ]);
    } catch (caught) {
      setError(referralErrorMessage(caught, "The status note could not be updated."));
    }
  }

  return (
    <div className="mt-3">
      {!editing ? (
        <Button variant="secondary" onClick={() => { setDraft({ ...reconciled, editing: true }); setError(null); setNotice(null); }}>
          Update status note
        </Button>
      ) : (
        <form className="max-w-2xl space-y-3 rounded-sm bg-surface-subtle px-4 py-4" onSubmit={submit} aria-busy={update.isPending}>
          {conflict ? (
            <Notice
              role="status"
              tone="warning"
              action={<Button variant="secondary" onClick={() => setDraft(keepStatusNoteText(reconciled, statusNote))}>Keep my text</Button>}
            >
              The saved status note changed while you were editing. Review it above. Your text is kept here; keep it to save it in place of the saved note.
            </Notice>
          ) : null}
          <div className="grid gap-2">
            <Label htmlFor="referral-status-note-editor">Status note</Label>
            <Textarea id="referral-status-note-editor" rows={4} maxLength={1_000} value={value} disabled={update.isPending} onChange={(event) => setDraft({ ...reconciled, value: event.target.value })} />
            <p className="text-xs text-muted">{value.length} / 1,000 characters. Leave blank to clear the note.</p>
          </div>
          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={update.isPending || conflict || saveUnavailable}>{update.isPending ? "Saving…" : "Save status note"}</Button>
            <Button type="button" variant="secondary" disabled={update.isPending} onClick={() => { setDraft(startStatusNoteDraft(statusNote)); setError(null); }}>Cancel</Button>
          </div>
        </form>
      )}
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
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
  // Covers the whole confirmation, including the refresh after the request succeeds.
  const [voiding, setVoiding] = useState(false);
  const voidMutation = useMutation({
    mutationFn: () => referralsVoid(referral.id, { reason: reason.trim() }),
    retry: false,
  });
  const voidPending = voidMutation.isPending || voiding;

  async function confirmVoid() {
    setError(null);
    setNotice(null);
    if (!reason.trim()) {
      setError("Void reason is required.");
      return;
    }
    setVoiding(true);
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
      if (
        code === "referral_conflict" ||
        code === "referral_active_call_slip_conflict" ||
        code === "referral_completed_call_slip_conflict" ||
        uncertainReferralMutation(caught)
      ) {
        const refreshed = await onRefresh();
        if (refreshed?.voided_at) {
          setOpen(false);
          setNotice("The Referral is already voided.");
        } else if (!refreshed) {
          setError("The Referral could not be refreshed. Do not retry the void until the current record can be checked.");
        } else if (
          code === "referral_conflict" ||
          code === "referral_active_call_slip_conflict" ||
          code === "referral_completed_call_slip_conflict"
        ) {
          setError(referralErrorMessage(caught, "The Referral could not be voided."));
        } else {
          setError("The Referral is not shown as voided after refreshing. Review the current record before confirming again.");
        }
      } else {
        setError(referralErrorMessage(caught, "The Referral could not be voided."));
      }
    } finally {
      setVoiding(false);
    }
  }

  return (
    <>
      <Button variant="danger" onClick={() => { setOpen(true); setError(null); setNotice(null); }}>
        Void Referral
      </Button>
      {notice ? <p role="status" className="mt-3 text-sm text-muted">{notice}</p> : null}
      <ConsequentialActionDialog
        open={open}
        title={`Void Referral ${referral.reference_code}?`}
        confirmLabel="Void Referral"
        pendingLabel="Voiding…"
        pending={voidPending}
        confirmDisabled={!reason.trim()}
        error={error}
        variant="danger"
        onOpenChange={setOpen}
        onConfirm={() => void confirmVoid()}
      >
        <p>
          Voiding keeps the Referral for review but prevents status-note
          updates, new actions, and linked Call Slip issuance. This does not
          delete the Referral.
        </p>
        <div className="grid gap-2">
          <Label htmlFor="referral-void-reason">Void reason</Label>
          <Textarea
            id="referral-void-reason"
            rows={3}
            maxLength={1_000}
            required
            value={reason}
            disabled={voidPending}
            onChange={(event) => setReason(event.target.value)}
          />
          <p className="text-xs text-muted">{reason.length} / 1,000 characters</p>
        </div>
      </ConsequentialActionDialog>
    </>
  );
}
