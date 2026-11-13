"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingRegion } from "@/components/ui/loading-region";
import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { getCounselingAccess } from "@/features/counseling/counseling-access";
import {
  counselingDeliveryModeLabel,
  CounselingPageHeading,
  CounselingQueryError,
  CounselingUnavailable,
  EncounterDetailSkeleton,
  formatCounselingDateTime,
} from "@/features/counseling/counseling-shared";
import { GuardedPortalLink as Link } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { portalReturnHref, withWorkflowReturn, workflowBackLabel } from "@/features/portal/workflow-navigation";
import {
  counselingProposeSession,
  getCounselingGetCaseQueryKey,
  useCounselingGetSessionProposalContext,
  useCounselingListSessionProposalSlots,
} from "@/lib/api/generated/counseling/counseling";
import {
  DeliveryMode,
  SessionProposalPurposeValue,
  type SessionProposalCreateRequest,
} from "@/lib/api/generated/model";
import { institutionalDateInputValue } from "@/lib/institutional-time";
import {
  isUncertainProposalResult,
  proposalErrorMessage,
  purposeLabel,
  purposeOptions,
  refusedOption,
} from "./session-proposal-presentation";

type TimeRow = { key: string; mode: DeliveryMode | ""; date: string; startsAt: string };
const MAX_TIMES = 3;

function newRow(): TimeRow {
  return { key: globalThis.crypto?.randomUUID?.() ?? String(Math.random()), mode: "", date: "", startsAt: "" };
}

export function ProposeSessionPage({ caseId }: { caseId: string }) {
  const { user } = usePortalSession();
  const access = getCounselingAccess(user);
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const followUpId = params.get("follow_up_id");
  const back = portalReturnHref(params.get("return_to"), `/portal/counseling/cases/${caseId}`);
  const backLink = <Link href={back} className={pageBackLinkClass}>{workflowBackLabel(back)}</Link>;
  const allowed = access.isCounselor && access.canViewAssigned;
  const context = useCounselingGetSessionProposalContext({ case_id: caseId }, {
    query: { enabled: allowed, retry: false, staleTime: 0, refetchOnWindowFocus: "always" },
  });
  const [purpose, setPurpose] = useState<SessionProposalPurposeValue | "">("");
  const [rows, setRows] = useState<TimeRow[]>(() => [newRow()]);
  const [callSlip, setCallSlip] = useState(false);
  const [review, setReview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [badRow, setBadRow] = useState<number | null>(null);
  const [sent, setSent] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const mutation = useMutation({
    mutationFn: (payload: SessionProposalCreateRequest) => counselingProposeSession(payload),
    retry: false,
  });
  const dirty = !sent && (purpose !== "" || rows.some((row) => row.mode || row.date || row.startsAt) || callSlip);
  useUnsavedChangesGuard({ dirty, message: "Your session proposal has not been sent." });

  if (!allowed) return <CounselingUnavailable title="Propose session" />;
  if (context.isPending) return <EncounterDetailSkeleton />;
  if (context.isError || !context.data) {
    return <>
      <CounselingPageHeading title="Propose session" back={backLink} />
      <CounselingQueryError message={proposalErrorMessage(context.error, "Couldn't load this case. Try again.")} onRetry={() => void context.refetch()} />
    </>;
  }
  const info = context.data.data;
  const modes = info.delivery_modes;
  const hasInPerson = rows.some((row) => row.mode === DeliveryMode.IN_PERSON);
  const complete = purpose !== "" && rows.every((row) => row.mode && row.startsAt);
  const chosen = rows.filter((row) => row.startsAt).map((row) => row.startsAt);
  const duplicate = new Set(chosen).size !== chosen.length;

  function update(index: number, change: Partial<TimeRow>) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...change } : row)));
    setError(null);
    setBadRow(null);
  }

  function prepare(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!complete) return setError("Choose a purpose, and a delivery mode, date and time for each option.");
    if (duplicate) return setError("Offer different times.");
    setReview(true);
  }

  async function send() {
    if (mutation.isPending || uncertain) return;
    setError(null);
    try {
      await mutation.mutateAsync({
        case_id: caseId,
        purpose: purpose as SessionProposalPurposeValue,
        options: rows.map((row) => ({ delivery_mode: row.mode as DeliveryMode, starts_at: row.startsAt })),
        call_slip_requested: hasInPerson && callSlip,
        follow_up_id: followUpId,
        expected_case_version: info.authority === "OWNER" ? info.case_version : null,
      });
      setSent(true);
      void queryClient.invalidateQueries({ queryKey: getCounselingGetCaseQueryKey(caseId) });
    } catch (caught) {
      const unknown = isUncertainProposalResult(caught);
      setUncertain(unknown);
      setBadRow(refusedOption(caught));
      setError(unknown
        ? "Couldn't confirm whether the proposal was sent. Go back and check before trying again."
        : proposalErrorMessage(caught, "The proposal couldn't be sent. Try again."));
      setReview(false);
      if (!unknown) void context.refetch();
    }
  }

  return (
    <article>
      <CounselingPageHeading
        title="Propose session"
        description={`${info.student.display_name} · Case ${info.case.reference_code}`}
        back={backLink}
      />
      {info.authority === "COVERAGE" ? <Notice className="mb-5">You are covering this case. The Student will see you as the proposing Counselor, and an accepted session is booked with you.</Notice> : null}
      {info.open_proposal ? (
        <Notice tone="warning" role="status" className="mb-5" action={info.authority === "OWNER" ? <Link href={withWorkflowReturn(`/portal/counseling/cases/${caseId}`, `${pathname}?${params}`)} className={buttonVariants({ variant: "secondary" })}>Open case</Link> : undefined}>
          A proposal sent {formatCounselingDateTime(info.open_proposal.created_at)} is still waiting for {info.student.display_name}. Withdraw it from the case before proposing other times.
        </Notice>
      ) : null}
      <form onSubmit={prepare} aria-busy={mutation.isPending} className="max-w-3xl">
        <Panel as="div">
          <PanelSection title="Purpose" titleId="propose-purpose-heading" description="The Student sees only this label, never case details.">
            <Label htmlFor="propose-purpose">Session purpose</Label>
            <Select id="propose-purpose" value={purpose} disabled={mutation.isPending || sent} onChange={(event) => { setPurpose(event.target.value as SessionProposalPurposeValue | ""); setError(null); }}>
              <option value="">Choose a purpose</option>
              {purposeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </Select>
          </PanelSection>
          <PanelSection title="Times to offer" titleId="propose-times-heading" description={`Offer up to ${MAX_TIMES} times${info.duration_minutes ? ` of ${info.duration_minutes} minutes` : ""}. Nothing is reserved: a time can be taken before the Student answers.`}>
            <ol className="space-y-4">
              {rows.map((row, index) => (
                <TimeOption
                  key={row.key}
                  caseId={caseId}
                  index={index}
                  row={row}
                  modes={modes}
                  invalid={badRow === index + 1}
                  disabled={mutation.isPending || sent || Boolean(info.open_proposal)}
                  onChange={(change) => update(index, change)}
                  onRemove={rows.length > 1 ? () => setRows((current) => current.filter((_, i) => i !== index)) : undefined}
                />
              ))}
            </ol>
            {rows.length < MAX_TIMES ? <Button variant="secondary" className="mt-4" disabled={mutation.isPending || sent || Boolean(info.open_proposal)} onClick={() => setRows((current) => [...current, newRow()])}>Add another time</Button> : null}
            {rows.some((row) => row.mode === DeliveryMode.ONLINE) ? <p className="mt-4 text-sm text-muted">Online sessions use E-Counseling. The Student still gives E-Counseling consent before the session.</p> : null}
          </PanelSection>
          {hasInPerson ? (
            <PanelSection title="Call Slip" titleId="propose-call-slip-heading">
              <label className="flex items-start gap-3 text-sm leading-5 text-ink">
                <input type="checkbox" className="mt-0.5 size-4 accent-brand" checked={callSlip} disabled={mutation.isPending || sent} onChange={(event) => setCallSlip(event.target.checked)} />
                <span>
                  <span className="block font-semibold">Also issue a Call Slip</span>
                  <span className="mt-1 block text-muted">Nothing is issued now. If the Student accepts an In person time, the case shows Issue Call Slip for that Appointment.</span>
                </span>
              </label>
            </PanelSection>
          ) : null}
          <PanelFooter>
            {error && !review ? <p role="alert" className="w-full text-sm text-danger">{error}</p> : null}
            <Button type="submit" disabled={mutation.isPending || sent || uncertain || Boolean(info.open_proposal)}>Review proposal</Button>
            <Link href={back} className={buttonVariants({ variant: "secondary" })}>Cancel</Link>
          </PanelFooter>
        </Panel>
      </form>
      <ConsequentialActionDialog
        open={review}
        title={`Send this proposal to ${info.student.display_name}?`}
        confirmLabel="Send proposal"
        pendingLabel="Sending proposal…"
        pending={mutation.isPending}
        error={null}
        completed={sent ? { title: "Proposal sent", children: <p>{info.student.display_name} can now choose one time or decline. Nothing is booked until they accept.</p>, doneLabel: workflowBackLabel(back) } : null}
        onOpenChange={(open) => { setReview(open); if (!open && sent) router.push(back); }}
        onConfirm={() => void send()}
      >
        <p>The Student is notified that a session time was proposed. The notice has no case details.</p>
        <dl className="grid gap-3 text-sm">
          <div><dt className="text-xs font-semibold text-muted">Purpose</dt><dd className="mt-1 text-ink">{purpose ? purposeLabel(purpose) : "Not chosen"}</dd></div>
          {rows.map((row, index) => <div key={row.key}><dt className="text-xs font-semibold text-muted">Time {index + 1}</dt><dd className="mt-1 text-ink">{row.startsAt ? formatCounselingDateTime(row.startsAt) : "Not chosen"} · {row.mode ? counselingDeliveryModeLabel(row.mode) : ""}</dd></div>)}
          {hasInPerson && callSlip ? <div><dt className="text-xs font-semibold text-muted">Call Slip</dt><dd className="mt-1 text-ink">Issue after the Student accepts an In person time</dd></div> : null}
        </dl>
      </ConsequentialActionDialog>
    </article>
  );
}

function TimeOption({ caseId, index, row, modes, invalid, disabled, onChange, onRemove }: {
  caseId: string;
  index: number;
  row: TimeRow;
  modes: DeliveryMode[];
  invalid: boolean;
  disabled: boolean;
  onChange: (change: Partial<TimeRow>) => void;
  onRemove?: () => void;
}) {
  const ready = Boolean(row.mode && row.date);
  const slots = useCounselingListSessionProposalSlots(
    { case_id: caseId, delivery_mode: (row.mode || DeliveryMode.IN_PERSON) as DeliveryMode, date: row.date },
    { query: { enabled: ready, retry: false, staleTime: 0 } },
  );
  const items = slots.data?.data.items ?? [];
  const label = `Time ${index + 1}`;
  return (
    <li className="rounded-sm border border-border p-3 sm:p-4">
      <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold text-ink">{label}</legend>
        <div className="grid gap-1">
          <Label htmlFor={`propose-mode-${row.key}`}>Delivery</Label>
          <Select id={`propose-mode-${row.key}`} value={row.mode} onChange={(event) => onChange({ mode: event.target.value as DeliveryMode | "", startsAt: "" })}>
            <option value="">Choose</option>
            {modes.map((mode) => <option key={mode} value={mode}>{counselingDeliveryModeLabel(mode)}</option>)}
          </Select>
        </div>
        <div className="grid gap-1">
          <Label htmlFor={`propose-date-${row.key}`}>Date</Label>
          <Input id={`propose-date-${row.key}`} type="date" min={institutionalDateInputValue()} value={row.date} onChange={(event) => onChange({ date: event.target.value, startsAt: "" })} />
        </div>
        <div className="grid gap-1">
          <Label htmlFor={`propose-time-${row.key}`}>Time</Label>
          {!ready ? <Select id={`propose-time-${row.key}`} value="" disabled><option value="">Choose delivery and date</option></Select>
            : slots.isPending ? <LoadingRegion label={`Loading times for ${label}`}><Select id={`propose-time-${row.key}`} value="" disabled><option value="">Loading times…</option></Select></LoadingRegion>
            : slots.isError ? <div role="alert" className="text-sm text-danger">{proposalErrorMessage(slots.error, "Couldn't load times.")} <Button variant="quiet" onClick={() => void slots.refetch()}>Retry</Button></div>
            : <Select id={`propose-time-${row.key}`} value={row.startsAt} aria-invalid={invalid || undefined} onChange={(event) => onChange({ startsAt: event.target.value })}>
              <option value="">{items.length ? "Choose a time" : "No open times on this date"}</option>
              {items.map((slot) => <option key={slot.starts_at} value={slot.starts_at}>{formatCounselingDateTime(slot.starts_at)}</option>)}
            </Select>}
        </div>
      </fieldset>
      {invalid ? <p role="alert" className="mt-2 text-sm text-danger">This time is no longer available. Choose another.</p> : null}
      {onRemove ? <Button variant="quiet" className="mt-2" disabled={disabled} aria-label={`Remove ${label.toLowerCase()}`} onClick={onRemove}>Remove</Button> : null}
    </li>
  );
}
