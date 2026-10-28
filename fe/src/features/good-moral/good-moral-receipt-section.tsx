"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { ContextHelp } from "@/components/ui/context-help";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { focusHeading } from "@/lib/focus-heading";
import type { GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";
import { GoodMoralField, GoodMoralSection, formatGoodMoralDate, formatGoodMoralDateTime } from "./good-moral-shared";
import { receiptAmount, receiptAvailability, receiptBlockerMessage, receiptStatuses } from "./receipt-presentation";
import { useReceiptInspection } from "./use-receipt-inspection";

// Keep a focus target while all mutation controls are disabled; Radix owns the trap.
function RecordingInspection() {
  const status = useRef<HTMLParagraphElement>(null);
  useEffect(() => { status.current?.focus(); }, []);
  return <p ref={status} role="status" tabIndex={0} className="mt-3 text-sm text-muted focus-visible:outline-2 focus-visible:outline-focus">Recording inspection…</p>;
}

function ReceiptFacts({ item, review = false }: { item: GoodMoralOperationalDetailResponse; review?: boolean }) {
  const fee = item.receipt_inspection;
  return <dl className={`grid min-w-0 gap-x-6 gap-y-4 sm:grid-cols-2 ${review ? "" : "lg:grid-cols-3"}`}>
    {review ? <><GoodMoralField label="Applicant name" value={item.applicant_name} /><GoodMoralField label="Request reference" value={item.id} /></> : null}
    <GoodMoralField label="Receipt number" value={item.official_receipt_number} />
    <GoodMoralField label="Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
    <GoodMoralField label="Actual amount" value={receiptAmount(item.official_receipt_amount, fee?.currency)} />
    {fee?.currency === "PHP" && fee.expected_amount !== null ? <GoodMoralField label="Approved expected amount" value={receiptAmount(fee.expected_amount, fee.currency)} /> : null}
  </dl>;
}

export function GoodMoralReceiptSection({ item, confirmed, editorOpen, onRefresh, onActivityChange }: {
  item: GoodMoralOperationalDetailResponse;
  confirmed: boolean;
  editorOpen: boolean;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
  onActivityChange: (active: boolean) => void;
}) {
  const inspection = useReceiptInspection({ item, confirmed, onRefresh, onActivityChange });
  const data = item.receipt_inspection;
  const mode = item.receipt_identity?.ledger_mode;
  const status = data ? receiptStatuses[data.status] : receiptStatuses.LEGACY_UNKNOWN;
  const availability = receiptAvailability(item);
  const blocker = receiptBlockerMessage(data?.blocker);
  const history = item.receipt_identity?.history ?? [];
  const mayOffer = mode === "ACTIVE" && data?.can_verify && confirmed && !editorOpen;
  return <>
    <GoodMoralSection title="Official Receipt" labelledBy="good-moral-receipt-heading" actions={<ContextHelp title="Official Receipt inspection" sections={[
      { heading: "Record, then inspect", content: <p>Save the details printed on the receipt using Correct certificate details. Verification is a separate personal inspection of the physical receipt; it does not confirm Cashier records or cleared funds.</p> },
      { heading: "Fees and corrections", content: <p>An expected fee appears only when an approved applicable decision is available. A receipt correction needs a new inspection. Other certificate corrections retain an unchanged receipt inspection but require preparation again.</p> },
    ]} />}>
      <ReceiptFacts item={item} />
      <div className="mt-5 space-y-2 border-t border-border pt-4">
        <p className={`text-sm font-semibold ${data?.status === "VERIFIED" ? "text-success" : "text-ink"}`}>{status.label}</p>
        <p className="max-w-2xl text-sm leading-6 text-muted">{blocker ?? status.description}</p>
        {availability ? <p className="max-w-2xl text-sm leading-6 text-muted">{availability}</p> : null}
        {data?.verified_by_id ? <dl className="grid gap-4 pt-2 sm:grid-cols-2">
          <GoodMoralField label="Inspector account reference" value={data.verified_by_id} />
          <GoodMoralField label="Inspected at" value={formatGoodMoralDateTime(data.verified_at)} />
        </dl> : null}
      </div>
      {mayOffer ? <Button id="good-moral-verify-trigger" className="mt-4" disabled={inspection.working} onClick={inspection.begin}>{inspection.uncertain ? "Review inspection retry" : "Verify receipt"}</Button> : null}
      {editorOpen && mode === "ACTIVE" ? <p className="mt-3 text-sm text-muted">Finish reviewing saved corrections before inspecting the receipt.</p> : null}
      {inspection.error && !inspection.review ? <p role="alert" className="mt-3 text-sm leading-6 text-danger">{inspection.error}</p> : null}
      {inspection.message ? <p role="status" className="mt-3 text-sm leading-6 text-muted">{inspection.message}</p> : null}
      {inspection.uncertain ? <Button className="mt-3" variant="secondary" disabled={inspection.working} onClick={() => void inspection.checkOutcome()}>{inspection.working ? "Checking request…" : "Check current request"}</Button> : null}
      {history.length ? <details className="mt-5 border-t border-border pt-3">
        <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-focus">Receipt change history ({history.length})</summary>
        <p className="my-2 text-xs leading-5 text-muted">Saved change metadata, newest first. Earlier receipt contents and historical inspection details are not included in this view.</p>
        <ol className="divide-y divide-border">
          {history.map((revision) => <li key={revision.id} className="space-y-1 py-3 text-sm">
            <p className="font-semibold">Revision {revision.sequence} · {({ ASSIGNED: "Receipt recorded", REVISED: "Details revised", REPLACED: "Receipt replaced", REMOVED: "Receipt removed", LEGACY: "Historical observation" } as Record<string, string>)[revision.change_kind] ?? "Receipt change"} · {revision.is_current ? "Current attachment" : "Historical change"}</p>
            <p className="text-muted">Recorded in COMPASS: {formatGoodMoralDateTime(revision.recorded_at)}</p>
            {revision.recorded_by_id ? <p className="break-words text-muted">Recorder account reference: {revision.recorded_by_id}</p> : null}
          </li>)}
        </ol>
      </details> : null}
    </GoodMoralSection>
    <ConsequentialActionDialog
      open={inspection.review !== null}
      title="Verify this physical receipt?"
      confirmLabel="Verify receipt"
      pendingLabel="Recording inspection…"
      pending={inspection.working}
      confirmDisabled={!inspection.affirmed || !confirmed || inspection.stale}
      error={inspection.stale && !inspection.completed ? "This receipt or request changed. Close this confirmation and review the latest saved details." : inspection.error}
      onOpenChange={(open) => { if (!open) inspection.close(); }}
      onConfirm={() => void inspection.confirm()}
      onCloseAutoFocus={(event) => { event.preventDefault(); const trigger = document.getElementById("good-moral-verify-trigger"); if (trigger) trigger.focus(); else focusHeading("good-moral-receipt-heading"); }}
      completed={inspection.completed ? { title: "Receipt inspection recorded", children: "The saved physical receipt inspection is current. Preparation and issuance availability have been refreshed." } : null}
      choices={<div><Label className="flex min-h-11 items-start gap-3 font-normal leading-6" htmlFor="good-moral-inspection-attestation">
        <Input id="good-moral-inspection-attestation" type="checkbox" className="mt-1 size-5 min-h-5 w-5 shrink-0 accent-brand" checked={inspection.affirmed} disabled={inspection.working} onChange={(event) => inspection.setAffirmed(event.target.checked)} />
        <span>I personally inspected the physical Official Receipt and confirmed that these details match this Good Moral request.</span>
      </Label>{inspection.working ? <RecordingInspection /> : null}</div>}
    >
      <p>Review the saved details of the physical receipt you inspected.</p>
      {inspection.review ? <ReceiptFacts item={inspection.review.item} review /> : null}
    </ConsequentialActionDialog>
  </>;
}
