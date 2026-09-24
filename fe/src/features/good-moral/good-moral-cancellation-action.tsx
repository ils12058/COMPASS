"use client";

import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { goodMoralCancelMyRequest, goodMoralCancelRequest, getGoodMoralGetMyRequestQueryKey, getGoodMoralGetRequestQueryKey, getGoodMoralListMyRequestsQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralCancellationPayload, GoodMoralDetailResponse } from "@/lib/api/generated/model";
import { GoodMoralNotice, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";

export function GoodMoralCancelAction({
  requestId,
  studentFacing,
  onRefresh,
}: {
  requestId: string;
  studentFacing: boolean;
  onRefresh: () => Promise<GoodMoralDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockedUntilRefresh, setBlockedUntilRefresh] = useState(false);
  const cancel = useMutation({
    mutationFn: (payload: GoodMoralCancellationPayload) =>
      studentFacing
        ? goodMoralCancelMyRequest(requestId, payload)
        : goodMoralCancelRequest(requestId, payload),
    retry: false,
  });

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getGoodMoralGetMyRequestQueryKey(requestId) }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(requestId) }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralListMyRequestsQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
    ]);
  }

  function closeAndClear() {
    setOpen(false);
    setReason("");
    setError(null);
    setBlockedUntilRefresh(false);
  }

  async function completed() {
    await invalidate();
    setNotice("The request is cancelled.");
    closeAndClear();
  }

  async function reconcile() {
    const refreshed = await onRefresh();
    if (refreshed?.status === "CANCELLED") {
      await completed();
      return;
    }
    if (refreshed?.status === "REQUESTED") {
      setBlockedUntilRefresh(false);
      setError("The request is still Requested. Review it, then deliberately retry with the same reason if cancellation is still intended.");
      return;
    }
    setBlockedUntilRefresh(true);
    setError("The request could not be refreshed. Do not retry until its current state can be checked.");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const cleanedReason = reason.trim();
    if (!cleanedReason) {
      setError("Enter a reason for cancelling this request.");
      return;
    }

    try {
      const response = await cancel.mutateAsync({ reason: cleanedReason });
      if (response.data.status === "CANCELLED") {
        await completed();
      } else {
        await reconcile();
      }
    } catch (caught) {
      if (uncertainGoodMoralMutation(caught)) {
        await reconcile();
        return;
      }
      setError(goodMoralErrorMessage(caught, "The Good Moral request could not be cancelled."));
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (cancel.isPending) return;
    if (!nextOpen) {
      closeAndClear();
      return;
    }
    setError(null);
    setNotice(null);
    setBlockedUntilRefresh(false);
    setOpen(true);
  }

  return (
    <div className="space-y-3">
      <Button variant="danger" onClick={() => handleOpenChange(true)}>Cancel request</Button>
      {notice ? <GoodMoralNotice>{notice}</GoodMoralNotice> : null}
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent aria-describedby="good-moral-cancel-description">
          <DialogTitle>Cancel this Good Moral request?</DialogTitle>
          <DialogDescription id="good-moral-cancel-description">
            {studentFacing
              ? "The request will remain in your history and cannot be issued after cancellation."
              : "The request will remain in the historical record and cannot be issued after cancellation."}
          </DialogDescription>
          <form onSubmit={submit} aria-busy={cancel.isPending} className="mt-5 space-y-4">
            <div>
              <Label htmlFor={`good-moral-cancel-reason-${requestId}`}>Reason for cancellation</Label>
              <Textarea
                id={`good-moral-cancel-reason-${requestId}`}
                className="mt-2"
                value={reason}
                maxLength={1000}
                onChange={(event) => setReason(event.target.value)}
                required
                aria-describedby={error ? `good-moral-cancel-error-${requestId}` : undefined}
              />
            </div>
            {error ? <p id={`good-moral-cancel-error-${requestId}`} role="alert" className="text-sm leading-6 text-danger">{error}</p> : null}
            {blockedUntilRefresh ? <Button type="button" variant="secondary" onClick={() => void reconcile()} disabled={cancel.isPending}>Refresh request state</Button> : null}
            <div className="flex flex-wrap justify-end gap-3">
              <Button variant="secondary" onClick={closeAndClear} disabled={cancel.isPending}>Keep request</Button>
              <Button type="submit" variant="danger" disabled={cancel.isPending || blockedUntilRefresh || !reason.trim()}>
                {cancel.isPending ? "Cancelling…" : "Cancel request"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
