"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { focusHeading } from "@/lib/focus-heading";
import { GoodMoralSection, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import { institutionalDateInputValue } from "@/lib/institutional-time";
import {
  goodMoralPrepareWithReceipt,
  getGoodMoralGetRequestQueryKey,
  getGoodMoralListRequestsQueryKey,
} from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralOneStepPreparationPayload, GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";

// One panel that records the Official Receipt, the personal physical inspection, and the
// preparation in a single backend transaction. The separate receipt, inspection, and preparation
// controls still work on their own; this is the shorter path for a request that needs preparation.
// Every guarantee (required receipt details, unique number, recorded inspector, version checks,
// idempotency, and audit) stays on the backend.
export function GoodMoralOneStepPreparation({ item, onRefresh, confirmed = true }: {
  item: GoodMoralOperationalDetailResponse;
  confirmed?: boolean;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
}) {
  const client = useQueryClient();
  const today = institutionalDateInputValue();
  const needsDocumentCheck = item.variant === "GRADUATE" && item.graduation_basis !== "REGISTRAR_RECORD";
  const [receiptNumber, setReceiptNumber] = useState(item.official_receipt_number);
  const [receiptDate, setReceiptDate] = useState(item.official_receipt_date ?? today);
  const [receiptAmount, setReceiptAmount] = useState(item.official_receipt_amount ?? item.receipt_fee?.expected_amount ?? "");
  const [affirmed, setAffirmed] = useState(false);
  const [documentChecked, setDocumentChecked] = useState(false);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewedVersion, setReviewedVersion] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const operation = useRef<{ fingerprint: string; receiptId: string; inspectionId: string } | null>(null);
  const prepare = useMutation({
    mutationFn: (payload: GoodMoralOneStepPreparationPayload) => goodMoralPrepareWithReceipt(item.id, payload),
    retry: false,
  });

  const number = receiptNumber.trim();
  const amount = receiptAmount.trim();
  const stale = reviewedVersion !== null && reviewedVersion !== item.actions.request_version;
  const ready = confirmed && item.actions.can_prepare && Boolean(number) && Boolean(receiptDate) && Boolean(amount)
    && affirmed && (!needsDocumentCheck || documentChecked);

  function begin() {
    if (!ready) return;
    setError(null);
    setCompleted(false);
    setReviewedVersion(item.actions.request_version);
    setReviewOpen(true);
  }

  async function refreshAfterCompletion() {
    await client.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) });
    await onRefresh();
  }

  async function confirm() {
    if (!reviewOpen || prepare.isPending || !ready || stale || reviewedVersion === null) return;
    const base = {
      expected_resource_version: reviewedVersion,
      expected_receipt_revision: item.receipt_identity?.revision_id ?? null,
      official_receipt_number: number,
      official_receipt_date: receiptDate,
      official_receipt_amount: amount,
      diploma_tor_checked: needsDocumentCheck && documentChecked,
    };
    const fingerprint = JSON.stringify(base);
    if (!operation.current || operation.current.fingerprint !== fingerprint) {
      if (!globalThis.crypto?.randomUUID) {
        setError("This browser cannot record this preparation safely. Update the browser and try again.");
        return;
      }
      operation.current = { fingerprint, receiptId: globalThis.crypto.randomUUID(), inspectionId: globalThis.crypto.randomUUID() };
    }
    const payload: GoodMoralOneStepPreparationPayload = {
      ...base,
      receipt_operation_id: operation.current.receiptId,
      inspection_operation_id: operation.current.inspectionId,
    };
    setError(null);
    try {
      await prepare.mutateAsync(payload);
      // Keep the confirmation in place with its outcome; the detail itself refreshes on Done so
      // this panel is not unmounted before the reader sees what was recorded.
      setCompleted(true);
      await Promise.all([
        invalidateGuidanceWork(client),
        client.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
      ]);
    } catch (caught) {
      setReviewOpen(false);
      const latest = await onRefresh();
      if (uncertainGoodMoralMutation(caught) && latest?.status === "READY_FOR_ISSUANCE") {
        setCompleted(true);
        setReviewOpen(true);
        setError(null);
        await invalidateGuidanceWork(client);
        return;
      }
      setError(goodMoralErrorMessage(caught, "Couldn't save and mark ready. Review the latest request before trying again."));
    }
  }

  return <>
    <GoodMoralSection
      title="Prepare certificate"
      description="Record the Official Receipt, confirm your physical inspection, and mark this request ready in one step."
    >
      <fieldset disabled={prepare.isPending || !confirmed} className="space-y-5 disabled:opacity-80">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="good-moral-one-step-receipt-number">Receipt number <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-one-step-receipt-number" className="mt-2" maxLength={96} value={receiptNumber} onChange={(event) => { setReceiptNumber(event.target.value); setError(null); }} />
          </div>
          <div>
            <Label htmlFor="good-moral-one-step-receipt-date">Receipt date <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-one-step-receipt-date" className="mt-2" type="date" max={today} value={receiptDate} onChange={(event) => { setReceiptDate(event.target.value); setError(null); }} />
            <p className="mt-1 text-xs text-muted">Defaults to today. Use the date printed on the receipt.</p>
          </div>
          <div>
            <Label htmlFor="good-moral-one-step-receipt-amount">Receipt amount <span aria-hidden="true">*</span></Label>
            <Input id="good-moral-one-step-receipt-amount" className="mt-2" type="number" min="0" max="9999999999.99" step="0.01" inputMode="decimal" value={receiptAmount} onChange={(event) => { setReceiptAmount(event.target.value); setError(null); }} />
            <p className="mt-1 text-xs text-muted">{item.receipt_fee ? `Defaults to the expected fee (${item.receipt_fee.expected_amount} ${item.receipt_fee.currency}). Enter the actual amount printed on the receipt.` : "Enter the actual amount printed on the receipt, up to two decimal places."}</p>
          </div>
        </div>
        <Label className="flex min-h-11 items-start gap-3 font-normal leading-6" htmlFor="good-moral-one-step-attestation">
          <Input id="good-moral-one-step-attestation" type="checkbox" className="mt-1 size-5 min-h-5 w-5 shrink-0 accent-brand" checked={affirmed} disabled={prepare.isPending} onChange={(event) => setAffirmed(event.target.checked)} />
          <span>I personally inspected the physical Official Receipt and confirmed that these details match this Good Moral request.</span>
        </Label>
        {needsDocumentCheck ? <Label className="flex min-h-11 items-start gap-3 font-normal leading-6" htmlFor="good-moral-one-step-document-check">
          <Input id="good-moral-one-step-document-check" type="checkbox" className="mt-1 size-5 min-h-5 w-5 shrink-0 accent-brand" checked={documentChecked} disabled={prepare.isPending} onChange={(event) => setDocumentChecked(event.target.checked)} />
          <span>I checked the diploma or TOR for this graduate.</span>
        </Label> : null}
      </fieldset>
      {!confirmed ? <p role="status" className="mt-3 text-sm text-muted">Confirm the current request before saving.</p> : null}
      {error ? <p role="alert" className="mt-3 text-sm leading-6 text-danger">{error}</p> : null}
      <Button className="mt-4" disabled={!ready || prepare.isPending} onClick={begin}>Save and mark ready</Button>
    </GoodMoralSection>
    <ConsequentialActionDialog
      open={reviewOpen}
      title="Save receipt and mark this request ready?"
      confirmLabel="Save and mark ready"
      pendingLabel="Saving and marking ready…"
      pending={prepare.isPending}
      confirmDisabled={!ready || stale || prepare.isPending}
      error={stale ? "This request changed. Close and review the latest details." : error}
      onConfirm={() => void confirm()}
      onOpenChange={(open) => { if (!open) { setReviewOpen(false); if (completed) void refreshAfterCompletion(); } }}
      onCloseAutoFocus={(event) => { if (completed) { event.preventDefault(); focusHeading("good-moral-counselor-detail-heading"); } }}
      completed={completed ? { title: "Ready for issuance", children: "The receipt, your physical inspection, and the preparation were recorded. A Counselor can now review and issue this certificate." } : null}
    >
      <p className="font-semibold text-ink">{item.applicant_name} · {item.variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate"}</p>
      <p>Recording: Official Receipt {number} dated {receiptDate} for {amount}.</p>
      <p>This records you as the preparer and as the inspector of the physical receipt.{needsDocumentCheck ? " It also records that you checked the diploma or TOR." : ""}</p>
      <p>A Counselor will perform the final review and issuance. Any later certificate correction will require preparation again.</p>
    </ConsequentialActionDialog>
  </>;
}