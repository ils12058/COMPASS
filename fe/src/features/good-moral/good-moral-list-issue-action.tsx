"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GoodMoralIssueReviewDialog } from "@/features/good-moral/good-moral-issue-review-dialog";
import { goodMoralErrorCode, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import {
  goodMoralDownloadCertificate,
  goodMoralGetRequest,
  goodMoralIssueRequest,
  getGoodMoralGetRequestQueryKey,
  getGoodMoralListRequestsQueryKey,
} from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralIssuePayload, GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";
import { downloadBinaryResponse } from "@/lib/browser-download";
import { institutionalPdfFallbackFilename } from "@/lib/institutional-pdf-filenames";

// Offered right in the success state so the Counselor can download the finalized PDF without
// leaving the queue. This read has no path back to the issue mutation.
function DownloadCertificate({ requestId }: { requestId: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function download() {
    setBusy(true);
    setError(null);
    try {
      const response = await goodMoralDownloadCertificate(requestId);
      downloadBinaryResponse(response, institutionalPdfFallbackFilename("goodMoral", requestId));
    } catch {
      setError("Couldn't prepare the certificate PDF. Try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-2">
      <Button variant="secondary" onClick={() => void download()} disabled={busy}>
        <Download aria-hidden="true" size={16} />{busy ? "Preparing PDF…" : "Download certificate (PDF)"}
      </Button>
      {error ? <p role="alert" className="text-sm leading-6 text-danger">{error}</p> : null}
    </div>
  );
}

// A contextual row action for a ready request. It loads the full record (the queue summary does
// not carry the receipt or preparation versions), opens the same issuance review confirmation used
// on the detail page, and offers the certificate download right after issuing. Issuance remains
// restricted to an authorized Counselor by the backend good_moral.issue capability.
export function GoodMoralListIssueAction({ requestId }: { requestId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detail, setDetail] = useState<GoodMoralOperationalDetailResponse | null>(null);
  const [reviewed, setReviewed] = useState<GoodMoralOperationalDetailResponse | null>(null);
  const [intent, setIntent] = useState<GoodMoralIssuePayload | null>(null);
  const [preparedAt, setPreparedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const issue = useMutation({
    mutationFn: () => goodMoralIssueRequest(requestId, intent ?? { expected_preparation_version: "" }),
    retry: false,
  });

  const staleReview = Boolean(intent && detail && intent.expected_resource_version !== detail.actions.request_version);

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(requestId) }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
      invalidateGuidanceWork(queryClient),
    ]);
  }

  function capture(item: GoodMoralOperationalDetailResponse) {
    setDetail(item);
    setReviewed(structuredClone(item));
    setPreparedAt(item.actions.preparation_version);
    setIntent({
      expected_preparation_version: item.actions.preparation_version ?? "",
      expected_resource_version: item.actions.request_version,
      expected_receipt_revision: item.receipt_identity?.revision_id,
      expected_receipt_verification: item.receipt_inspection?.verification_id,
    });
  }

  async function reload(): Promise<GoodMoralOperationalDetailResponse | undefined> {
    try {
      const latest = (await goodMoralGetRequest(requestId)).data;
      capture(latest);
      return latest;
    } catch {
      return undefined;
    }
  }

  async function begin() {
    setLoading(true);
    setLoadError(null);
    setError(null);
    setCompleted(false);
    try {
      const item = (await goodMoralGetRequest(requestId)).data;
      if (!item.actions.can_issue || !item.actions.preparation_version) {
        setLoadError("This request is not ready to issue. Open it to review its current status.");
        return;
      }
      capture(item);
      setOpen(true);
    } catch (caught) {
      setLoadError(goodMoralErrorMessage(caught, "Couldn't load this request. Try again."));
    } finally {
      setLoading(false);
    }
  }

  async function confirm() {
    if (!preparedAt || !intent || issue.isPending || !detail?.actions.can_issue || staleReview) return;
    setError(null);
    try {
      await issue.mutateAsync();
      setCompleted(true);
      await invalidate();
    } catch (caught) {
      const code = goodMoralErrorCode(caught);
      if (code === "good_moral_preparation_changed" || code === "good_moral_not_ready" || code?.startsWith("good_moral_receipt_")) {
        setOpen(false);
        await reload();
        setError(goodMoralErrorMessage(caught, "Review the latest certificate details.", true));
        return;
      }
      if (code === "current_student_required") {
        setOpen(false);
        await reload();
        setError("This certificate can no longer be issued because the applicant is no longer a current Student.");
        return;
      }
      if (uncertainGoodMoralMutation(caught)) {
        const latest = await reload();
        if (latest?.status === "ISSUED") {
          setCompleted(true);
          setError(null);
          await invalidate();
        } else {
          setOpen(false);
          setError("Couldn't confirm the issuance. Open the request to check its status before trying again.");
        }
        return;
      }
      setError(goodMoralErrorMessage(caught, "Couldn't issue the Good Moral Certificate. Try again.", true));
    }
  }

  return (
    <div className="flex flex-col items-start gap-1">
      <Button variant="secondary" className="min-h-9 px-3 py-1 text-sm" disabled={loading || issue.isPending} onClick={() => void begin()}>
        {loading ? "Loading…" : "Issue"}
      </Button>
      {loadError ? <p role="alert" className="max-w-48 text-xs leading-5 text-danger">{loadError}</p> : null}
      {error && !open ? <p role="alert" className="max-w-48 text-xs leading-5 text-danger">{error}</p> : null}
      {reviewed ? (
        <GoodMoralIssueReviewDialog
          open={open}
          reviewed={reviewed}
          pending={issue.isPending}
          confirmDisabled={issue.isPending || staleReview || !detail?.actions.can_issue}
          error={staleReview && !issue.isPending ? "This request changed. Close and review the latest details before issuing." : error}
          onOpenChange={(next) => { if (!next) setOpen(false); }}
          onConfirm={() => void confirm()}
          completed={completed ? {
            title: "Good Moral Certificate issued",
            children: (
              <>
                <p>The certificate was issued and recorded under your account.</p>
                <DownloadCertificate requestId={requestId} />
              </>
            ),
          } : null}
        />
      ) : null}
    </div>
  );
}