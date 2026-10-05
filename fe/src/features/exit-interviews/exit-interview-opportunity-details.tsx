"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { exitInterviewErrorMessage } from "@/features/exit-interviews/exit-interview-shared";
import { formatExitInterviewDateTime } from "@/features/exit-interviews/exit-interview-presentation";
import { exitInterviewsRevokeOpportunity, useExitInterviewsGetOpportunity } from "@/lib/api/generated/exit-interviews/exit-interviews";

export function ExitInterviewOpportunityDetails({ opportunityId, onClose, onChanged }: { opportunityId: string; onClose: () => void; onChanged: () => void }) {
  const detail = useExitInterviewsGetOpportunity(opportunityId, { query: { retry: false, staleTime: 0 } });
  const [review, setReview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const revoke = useMutation({ mutationFn: () => exitInterviewsRevokeOpportunity(opportunityId), retry: false });
  const item = detail.data?.data;
  async function confirm() {
    setError(null);
    try {
      await revoke.mutateAsync();
      setCompleted(true);
      onChanged();
    } catch (caught) {
      setError(exitInterviewErrorMessage(caught, "Access could not be revoked. Review its latest state before trying again."));
      void detail.refetch();
      onChanged();
    }
  }
  return <>
    <Dialog open={!review} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent><DialogTitle>Exit Interview access</DialogTitle><DialogDescription>{item && !detail.isError ? `${item.student.display_name} · ${item.academic_year.label}` : "Student Exit Interview opportunity"}</DialogDescription>
        {detail.isPending ? <p role="status" className="mt-5 text-sm text-muted">Loading access…</p> : detail.isError ? <div role="alert" className="mt-5 text-sm text-danger">{exitInterviewErrorMessage(detail.error, "Access could not be confirmed.")}<Button variant="secondary" onClick={() => void detail.refetch()}>Retry</Button></div> : item ? <>
          <dl className="mt-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm"><dt className="text-muted">Reason</dt><dd>{item.source === "GRADUATION" ? "Graduation" : "Manual"}</dd><dt className="text-muted">Status</dt><dd>{item.status === "OPEN" ? "Open" : item.status === "COMPLETED" ? "Completed" : "Revoked"}</dd><dt className="text-muted">Opened by</dt><dd>{item.opened_by.display_name} · {formatExitInterviewDateTime(item.opened_at)}</dd>{item.completed_at ? <><dt className="text-muted">Completed</dt><dd>{formatExitInterviewDateTime(item.completed_at)}</dd></> : null}{item.revoked_at ? <><dt className="text-muted">Revoked</dt><dd>{item.revoked_by?.display_name} · {formatExitInterviewDateTime(item.revoked_at)}</dd></> : null}</dl>
          {item.note ? <p className="mt-5 whitespace-pre-wrap break-words text-sm text-ink">{item.note}</p> : null}
          {item.status === "OPEN" ? <Button variant="danger" className="mt-6" onClick={() => { setError(null); setReview(true); }}>Revoke access</Button> : null}
        </> : null}
      </DialogContent>
    </Dialog>
    <ConsequentialActionDialog open={review} title={`Revoke Exit Interview access for ${item?.student.display_name ?? "this Student"}?`} confirmLabel="Revoke access" pendingLabel="Revoking…" pending={revoke.isPending} confirmDisabled={detail.isError || item?.status !== "OPEN"} error={error} variant="danger" completed={completed ? { title: "Exit Interview access revoked", children: "The opportunity is revoked. Existing responses remain available in history." } : null} onConfirm={() => void confirm()} onOpenChange={(open) => { if (!open) onClose(); }}>
      <p>The Student will no longer be able to start or submit an uncompleted Exit Interview through this opportunity. Existing records will be preserved.</p>
      {item?.source === "GRADUATION" ? <p>A submitted Exit Interview will still be required for graduation Good Moral. Reopen access if the Student needs to complete it.</p> : null}
    </ConsequentialActionDialog>
  </>;
}
