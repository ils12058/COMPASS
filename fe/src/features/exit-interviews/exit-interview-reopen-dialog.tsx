"use client";

import { RotateCcw } from "lucide-react";
import { PageAction } from "@/components/ui/page-action";
import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ExitInterviewCorrectionTargetChooser } from "@/features/exit-interviews/exit-interview-correction-target-chooser";
import {
  allowedExitInterviewCorrectionTargets,
  exitInterviewCorrectionTargetTitle,
} from "@/features/exit-interviews/exit-interview-correction-targets";
import { exitInterviewErrorMessage } from "@/features/exit-interviews/exit-interview-shared";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  exitInterviewsReopen,
  getExitInterviewsGetQueryKey,
  getExitInterviewsListQueryKey,
} from "@/lib/api/generated/exit-interviews/exit-interviews";
import type { ExitInterviewCorrectionTarget, ReopenRequest } from "@/lib/api/generated/model";

// The reopen request's reason limit (ReopenRequest maxLength).
const MAX_REASON_LENGTH = 1000;

export function ExitInterviewReopenAction({
  exitInterviewId,
  collegeFeedbackItemCodes,
}: {
  exitInterviewId: string;
  // The record's saved College Feedback items; they decide which targets exist on its form.
  collegeFeedbackItemCodes: readonly string[];
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [targets, setTargets] = useState<ExitInterviewCorrectionTarget[]>([]);
  const [reviewReason, setReviewReason] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const allowed = useMemo(() => allowedExitInterviewCorrectionTargets(collegeFeedbackItemCodes), [collegeFeedbackItemCodes]);
  // Never send a code this record's form does not have.
  const reviewedTargets = useMemo(() => targets.filter((target) => allowed.includes(target)), [targets, allowed]);
  const reopen = useMutation({
    mutationFn: (request: ReopenRequest) => exitInterviewsReopen(exitInterviewId, request),
    retry: false,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (!normalizedReason || reason.length > MAX_REASON_LENGTH) return;
    setReviewError(null);
    setReviewReason(normalizedReason);
    setOpen(false);
  }

  async function confirmReopen() {
    if (!reviewReason) return;
    const reviewed = reviewReason;
    setReviewError(null);
    try {
      // Targets are optional; a request without them is the same reason-only request as before.
      const result = await reopen.mutateAsync({
        reason: reviewed,
        ...(reviewedTargets.length ? { targets: reviewedTargets } : {}),
      });
      const summary = result.data;
      await queryClient.cancelQueries({
        queryKey: getExitInterviewsGetQueryKey(summary.id),
        exact: true,
      });
      queryClient.removeQueries({
        queryKey: getExitInterviewsGetQueryKey(summary.id),
        exact: true,
      });
      void queryClient.invalidateQueries({
        queryKey: getExitInterviewsListQueryKey(),
      });
      setReviewReason(null);
      setReason("");
      setTargets([]);
      router.push("/portal/exit-interviews?notice=reopened");
    } catch (caught) {
      const code = caught instanceof CompassApiError ? readApiErrorCode(caught.body) : undefined;
      setReviewError(
        code === "invalid_exit_interview_request"
          ? "This correction request could not be saved. Check the reason and the answers to review, then try again."
          : exitInterviewErrorMessage(
            caught,
            "The Exit Interview could not be reopened. Review the reason and try again.",
          ),
      );
    }
  }

  return (
    <>
      <PageAction icon={RotateCcw} label="Reopen for correction" onClick={() => setOpen(true)} />
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          aria-describedby="exit-interview-reopen-description"
          dismissible={!reopen.isPending}
        >
          <DialogTitle>Reopen Exit Interview for correction?</DialogTitle>
          <DialogDescription id="exit-interview-reopen-description">
            The Student will be able to edit this response again. The reason you provide will be visible to the Student.
          </DialogDescription>
          <form onSubmit={(event) => void handleSubmit(event)}>
            <div className="mt-5">
              <Label htmlFor="exit-interview-reopen-reason">Reason for correction</Label>
              <Textarea
                id="exit-interview-reopen-reason"
                className="mt-2 min-h-28"
                value={reason}
                required
                maxLength={MAX_REASON_LENGTH}
                aria-describedby="exit-interview-reopen-count"
                disabled={reopen.isPending}
                onChange={(event) => setReason(event.target.value)}
              />
              <p id="exit-interview-reopen-count" className="mt-1 text-right text-xs text-muted">
                {reason.length} / {MAX_REASON_LENGTH} characters
              </p>
            </div>
            <div className="mt-4">
              <ExitInterviewCorrectionTargetChooser
                allowed={allowed}
                value={reviewedTargets}
                onChange={setTargets}
                disabled={reopen.isPending}
              />
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                disabled={reopen.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!reason.trim() || reason.length > MAX_REASON_LENGTH}>
                Review reopening
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
      <ConsequentialActionDialog
        open={reviewReason !== null}
        title="Reopen Exit Interview for correction?"
        confirmLabel="Reopen for correction"
        pendingLabel="Reopening…"
        pending={reopen.isPending}
        error={reviewError}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setReviewReason(null);
        }}
        onConfirm={() => void confirmReopen()}
      >
        {reviewReason ? (
          <>
            <p>
              The Student will be able to edit this response again. The reason
              below will be visible to the Student.
            </p>
            <dl className="space-y-3">
              <div>
                <dt className="text-muted">Reason for correction</dt>
                <dd className="mt-1 whitespace-pre-wrap break-words font-semibold text-ink">
                  {reviewReason}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Answers to review</dt>
                <dd className="mt-1 text-ink">
                  {reviewedTargets.length ? (
                    <ul className="list-disc space-y-1 pl-5">
                      {reviewedTargets.map((target) => (
                        <li key={target}>{exitInterviewCorrectionTargetTitle(target)}</li>
                      ))}
                    </ul>
                  ) : (
                    "None. The Student will see only the reason."
                  )}
                </dd>
              </div>
            </dl>
          </>
        ) : null}
      </ConsequentialActionDialog>
    </>
  );
}
