"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  getAppointmentsGetMyCounselorRequestQueryKey,
  getAppointmentsListEligibleCounselorsQueryKey,
  useAppointmentsCreateCounselorRequest,
  useAppointmentsGetMyCounselorRequest,
} from "@/lib/api/generated/appointments/appointments";
import { CounselorBookingRequestState } from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

import {
  COUNSELOR_BOOKING_HELP_TEXT,
  COUNSELOR_REQUEST_PENDING_LABEL,
  counselorRequestErrorMessage,
} from "./counselor-request-presentation";

export function useStudentCounselorRequestState() {
  return useAppointmentsGetMyCounselorRequest({
    query: { retry: false, refetchOnWindowFocus: true },
  });
}

export function StudentCounselorRequestSection({
  mode = "banner",
}: {
  mode?: "banner" | "inline";
}) {
  const queryClient = useQueryClient();
  const stateQuery = useStudentCounselorRequestState();
  const createRequest = useAppointmentsCreateCounselorRequest({
    mutation: { retry: false },
  });
  const [dialogOpen, setDialogOpen] = useState(false);
  const [preferredId, setPreferredId] = useState("");
  const [reason, setReason] = useState("");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submittedNotice, setSubmittedNotice] = useState(false);

  const state = stateQuery.data?.data;
  const pending = state?.pending_request ?? null;
  const latestDecision = state?.latest_decision ?? null;
  const activeApproval = state?.active_approval ?? null;
  const headAvailable = state?.head_available ?? true;
  const options = state?.requestable_counselors ?? [];

  function openDialog() {
    setPreferredId("");
    setReason("");
    setSubmitError(null);
    setDialogOpen(true);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitError(null);
    try {
      await createRequest.mutateAsync({
        data: {
          preferred_counselor_id: preferredId || null,
          reason: reason.trim() || null,
        },
      });
      setDialogOpen(false);
      setPreferredId("");
      setReason("");
      setSubmittedNotice(true);
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsGetMyCounselorRequestQueryKey(),
      });
      await queryClient.invalidateQueries({
        queryKey: getAppointmentsListEligibleCounselorsQueryKey(),
      });
    } catch (caught) {
      setSubmitError(
        counselorRequestErrorMessage(caught, "Couldn't send your request. Try again."),
      );
    }
  }

  const actionButton = pending ? null : headAvailable ? (
    <Button type="button" variant="secondary" onClick={openDialog}>
      Ask for a different counselor
    </Button>
  ) : (
    <p className="text-sm text-muted">
      Requests for a different counselor aren&apos;t available right now. Please contact the Guidance Office.
    </p>
  );

  return (
    <>
      {mode === "banner" ? (
        <div className="mb-5 space-y-3 rounded-sm border border-border bg-surface-subtle px-4 py-3.5 sm:px-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-3xl text-sm leading-6 text-ink">{COUNSELOR_BOOKING_HELP_TEXT}</p>
            {stateQuery.isPending ? null : actionButton}
          </div>

          {submittedNotice && pending ? (
            <Notice role="status" tone="success">
              Your request was sent. {COUNSELOR_REQUEST_PENDING_LABEL}.
            </Notice>
          ) : null}

          {pending && !submittedNotice ? (
            <Notice role="status" tone="info">
              <p className="font-semibold text-ink">{COUNSELOR_REQUEST_PENDING_LABEL}</p>
              <p className="mt-0.5 text-sm text-muted">
                Submitted {formatInstitutionalDateTime(pending.created_at)}
                {pending.preferred_counselor
                  ? ` · Preferred counselor: ${pending.preferred_counselor.display_name}`
                  : ""}
              </p>
            </Notice>
          ) : null}

          {!pending && activeApproval ? (
            <p className="text-sm text-muted">
              Approved by the Head Guidance Counselor:{" "}
              <strong className="font-semibold text-ink">
                {activeApproval.counselor.display_name}
              </strong>
              .
            </p>
          ) : null}

          {!pending && latestDecision?.state === CounselorBookingRequestState.DECLINED ? (
            <Notice role="status">
              <p className="font-semibold text-ink">
                Your last request for a different counselor was declined
              </p>
              <p className="mt-0.5 text-sm text-muted">
                Decided {formatInstitutionalDateTime(latestDecision.decided_at)}
                {latestDecision.decision_note ? ` — ${latestDecision.decision_note}` : ""}
              </p>
            </Notice>
          ) : null}
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          {pending ? (
            <p role="status" className="text-sm font-medium text-ink">
              {COUNSELOR_REQUEST_PENDING_LABEL}
              {pending.preferred_counselor
                ? ` (${pending.preferred_counselor.display_name})`
                : ""}
              .
            </p>
          ) : (
            actionButton
          )}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={(next) => { if (!createRequest.isPending) setDialogOpen(next); }}>
        <DialogContent closeLabel="Close counselor request dialog">
          <form onSubmit={(event) => void handleSubmit(event)}>
            <DialogTitle>Ask for a different counselor</DialogTitle>
            <DialogDescription className="mt-2 text-sm leading-6 text-muted">
              Your request goes directly to the Head Guidance Counselor. If approved, you will be
              able to book with that counselor until the Head Guidance Counselor changes or ends the
              approval.
            </DialogDescription>

            <div className="mt-4 space-y-4">
              {submitError ? (
                <Notice role="alert" tone="danger">
                  {submitError}
                </Notice>
              ) : null}

              <div className="grid gap-1.5">
                <Label htmlFor="counselor-request-preferred">
                  Preferred counselor (optional)
                </Label>
                <Select
                  id="counselor-request-preferred"
                  value={preferredId}
                  onChange={(event) => setPreferredId(event.target.value)}
                  disabled={createRequest.isPending}
                >
                  <option value="">No preference — let the Head Guidance Counselor choose</option>
                  {options.map((counselor) => (
                    <option key={counselor.id} value={counselor.id}>
                      {counselor.display_name}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="counselor-request-reason">Reason (optional)</Label>
                <Textarea
                  id="counselor-request-reason"
                  rows={4}
                  maxLength={2000}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  disabled={createRequest.isPending}
                  placeholder="Share why you would like to see a different counselor"
                />
                <p className="text-xs leading-5 text-muted">
                  Only the Head Guidance Counselor can read your reason. It is not shared with your
                  College&apos;s counselor, the counselor you request, office assistants, or IT staff.
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                disabled={createRequest.isPending}
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createRequest.isPending}
                aria-busy={createRequest.isPending}
              >
                {createRequest.isPending ? "Sending…" : "Send request"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
