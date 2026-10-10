"use client";

import { RotateCcw } from "lucide-react";
import { PageAction } from "@/components/ui/page-action";
import { useState, type FormEvent } from "react";
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
import { exitInterviewErrorMessage } from "@/features/exit-interviews/exit-interview-shared";
import {
  exitInterviewsReopen,
  getExitInterviewsGetQueryKey,
  getExitInterviewsListQueryKey,
} from "@/lib/api/generated/exit-interviews/exit-interviews";

export function ExitInterviewReopenAction({
  exitInterviewId,
}: {
  exitInterviewId: string;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reviewReason, setReviewReason] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const reopen = useMutation({
    mutationFn: (value: string) =>
      exitInterviewsReopen(exitInterviewId, { reason: value }),
    retry: false,
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (!normalizedReason) return;
    setReviewError(null);
    setReviewReason(normalizedReason);
    setOpen(false);
  }

  async function confirmReopen() {
    if (!reviewReason) return;
    const reviewed = reviewReason;
    setReviewError(null);
    try {
      const result = await reopen.mutateAsync(reviewed);
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
      router.push("/portal/exit-interviews?notice=reopened");
    } catch (caught) {
      setReviewError(
        exitInterviewErrorMessage(
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
                disabled={reopen.isPending}
                onChange={(event) => setReason(event.target.value)}
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
              <Button type="submit" disabled={!reason.trim()}>
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
            <dl>
              <dt className="text-muted">Reason for correction</dt>
              <dd className="mt-1 whitespace-pre-wrap break-words font-semibold text-ink">
                {reviewReason}
              </dd>
            </dl>
          </>
        ) : null}
      </ConsequentialActionDialog>
    </>
  );
}
