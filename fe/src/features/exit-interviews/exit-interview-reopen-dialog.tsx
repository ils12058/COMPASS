"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ExitInterviewError } from "@/features/exit-interviews/exit-interview-shared";
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
  const reopen = useMutation({
    mutationFn: (value: string) =>
      exitInterviewsReopen(exitInterviewId, { reason: value }),
    retry: false,
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedReason = reason.trim();
    if (!normalizedReason) return;

    try {
      const result = await reopen.mutateAsync(normalizedReason);
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
      setOpen(false);
      setReason("");
      router.push("/portal/exit-interviews?notice=reopened");
    } catch {
      // Keep the reason and dialog open so the Head can review the failure and retry deliberately.
    }
  }

  return (
    <>
      <Button type="button" onClick={() => setOpen(true)}>
        Reopen for correction
      </Button>
      <Dialog
        open={open}
        onOpenChange={(nextOpen) => {
          if (!reopen.isPending) setOpen(nextOpen);
        }}
      >
        <DialogContent aria-describedby="exit-interview-reopen-description">
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
            {reopen.isError ? (
              <div className="mt-4">
                <ExitInterviewError
                  error={reopen.error}
                  fallback="The Exit Interview could not be reopened. Review the reason and try again."
                />
              </div>
            ) : null}
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <Button
                type="button"
                variant="secondary"
                disabled={reopen.isPending}
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={reopen.isPending || !reason.trim()}>
                {reopen.isPending ? "Reopening…" : "Reopen for correction"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
