"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { goodMoralVerifyReceipt, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralOperationalDetailResponse, GoodMoralReceiptVerificationPayload } from "@/lib/api/generated/model";
import { goodMoralErrorCode, goodMoralErrorMessage, uncertainGoodMoralMutation } from "./good-moral-shared";
import { inspectionReview, reviewedInspectionIsCurrent, sameReceiptReview, type ReceiptReview } from "./receipt-review";

export function useReceiptInspection({ item, confirmed, onRefresh, onActivityChange }: {
  item: GoodMoralOperationalDetailResponse;
  confirmed: boolean;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
  onActivityChange: (active: boolean) => void;
}) {
  const client = useQueryClient();
  const alive = useRef(false);
  const sending = useRef(false);
  const intent = useRef<ReceiptReview | null>(null);
  const [review, setReview] = useState<ReceiptReview | null>(null);
  const [affirmed, setAffirmed] = useState(false);
  const [working, setWorking] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const mutation = useMutation({ mutationFn: (payload: GoodMoralReceiptVerificationPayload) => goodMoralVerifyReceipt(item.id, payload), retry: false });
  const stale = Boolean(review && (!sameReceiptReview(item, review) || !item.receipt_inspection?.can_verify));
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { onActivityChange(Boolean(review || working || uncertain)); }, [review, working, uncertain, onActivityChange]);

  async function invalidate() {
    await Promise.all([
      client.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id), refetchType: "none" }),
      client.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
      invalidateGuidanceWork(client),
    ]);
  }

  function begin() {
    if (!confirmed || working || !item.receipt_inspection?.can_verify || item.receipt_identity?.ledger_mode !== "ACTIVE") return;
    if (!intent.current || !sameReceiptReview(item, intent.current)) {
      if (!globalThis.crypto?.randomUUID) { setError("This browser cannot record an inspection safely. Update the browser and try again."); return; }
      intent.current = inspectionReview(item, globalThis.crypto.randomUUID());
    }
    if (!intent.current) return;
    setAffirmed(false);
    setCompleted(false);
    setError(null);
    setMessage(null);
    setReview(intent.current);
  }

  function close() {
    if (sending.current) return;
    if (stale) intent.current = null;
    setReview(null);
    setAffirmed(false);
    setCompleted(false);
  }

  async function reconcile(original: ReceiptReview, committed?: GoodMoralOperationalDetailResponse) {
    const latest = await onRefresh();
    if (!alive.current) return;
    if (!latest) {
      setReview(null);
      setUncertain(true);
      setError("The inspection outcome cannot be confirmed. Check the current request before continuing.");
      return;
    }
    const result = committed?.receipt_verification_result;
    if (reviewedInspectionIsCurrent(latest, original)) {
      setUncertain(false);
      intent.current = null;
      await invalidate();
      if (!alive.current) return;
      if (result && !result.invalidated_at && result.verification_id === latest.receipt_inspection?.verification_id) {
        setCompleted(true);
        setError(null);
      } else {
        setReview(null);
        setError(null);
        setMessage("The receipt is already verified. The recorded inspector and time are shown with this receipt.");
      }
    } else if (!sameReceiptReview(latest, original) || latest.receipt_identity?.ledger_mode !== "ACTIVE" || !latest.receipt_inspection?.can_verify) {
      intent.current = null;
      setUncertain(false);
      setReview(null);
      setError("This receipt or request changed. Review the latest details before continuing. Earlier inspection evidence is not a current verification.");
    } else {
      setReview(null);
      setUncertain(true);
      setError("The inspection could not be confirmed. No current inspection is shown. Deliberately review the same receipt before retrying this inspection.");
    }
  }

  async function confirm() {
    if (!review || !affirmed || sending.current || !confirmed || stale) return;
    sending.current = true;
    setWorking(true);
    setError(null);
    try {
      const response = await mutation.mutateAsync(review.payload);
      if (!alive.current) return;
      await invalidate();
      if (!alive.current) return;
      await reconcile(review, response.data);
    } catch (caught) {
      if (!alive.current) return;
      const code = goodMoralErrorCode(caught);
      if (uncertainGoodMoralMutation(caught)) {
        setUncertain(true);
        await reconcile(review);
      } else if (code === "good_moral_receipt_already_verified") {
        await reconcile(review);
      } else if (code?.startsWith("good_moral_receipt_") || code === "permission_denied" || code === "idempotency_key_conflict" || code === "good_moral_conflict") {
        intent.current = null;
        setReview(null);
        setUncertain(false);
        setError(goodMoralErrorMessage(caught, "The inspection was refused. Review the latest request."));
        await onRefresh();
      } else {
        setError(goodMoralErrorMessage(caught, "Receipt inspection could not be recorded. Review the request before trying again."));
      }
    } finally {
      sending.current = false;
      if (alive.current) setWorking(false);
    }
  }

  async function checkOutcome() {
    const original = intent.current;
    if (!original || sending.current) return;
    setWorking(true);
    try { await reconcile(original); } finally { if (alive.current) setWorking(false); }
  }

  return { review, affirmed, setAffirmed, working, uncertain, error, message, completed, stale, begin, close, confirm, checkOutcome };
}
