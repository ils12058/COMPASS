"use client";

import { workQueueQueryFamily } from "@/features/work-queue/work-queue-data";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { GoodMoralField, GoodMoralSection, formatGoodMoralDate, goodMoralErrorCode, goodMoralErrorMessage, uncertainGoodMoralMutation } from "@/features/good-moral/good-moral-shared";
import { goodMoralIssueRequest, getGoodMoralGetRequestQueryKey, getGoodMoralListRequestsQueryKey } from "@/lib/api/generated/good-moral/good-moral";
import type { GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";

export function GoodMoralIssueSection({
  item,
  onRefresh,
}: {
  item: GoodMoralOperationalDetailResponse;
  onRefresh: () => Promise<GoodMoralOperationalDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [reviewedPreparedAt, setReviewedPreparedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [blockedUntilRefresh, setBlockedUntilRefresh] = useState(false);
  // Covers the whole confirmation, including the refresh after the request succeeds.
  const [issuing, setIssuing] = useState(false);
  const issue = useMutation({ mutationFn: () => goodMoralIssueRequest(item.id, { expected_preparation_version: reviewedPreparedAt ?? "" }), retry: false });
  const issuePending = issue.isPending || issuing;

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getGoodMoralGetRequestQueryKey(item.id) }),
      queryClient.invalidateQueries({ queryKey: getGoodMoralListRequestsQueryKey() }),
        queryClient.invalidateQueries({ queryKey: workQueueQueryFamily() }),
    ]);
  }

  // Issuance is protected by the good_moral.issue capability, this confirmation, and the recorded
  // issuer; it does not need an authenticator step-up.
  function beginIssue() {
    if (!item.actions.preparation_version || !item.actions.can_issue) return;
    setReviewedPreparedAt(item.actions.preparation_version);
    setError(null);
    setNotice(null);
    setConfirmOpen(true);
  }

  async function confirmIssue() {
    if (!reviewedPreparedAt) return;
    setError(null);
    setNotice(null);
    setIssuing(true);
    try {
      await issue.mutateAsync();
      await invalidate();
      await onRefresh();
      setConfirmOpen(false);
      setNotice("Good Moral certificate issued.");
    } catch (caught) {
      const code = goodMoralErrorCode(caught);
      if (code === "good_moral_preparation_changed" || code === "good_moral_not_ready") {
        setConfirmOpen(false);
        await onRefresh();
        setError(goodMoralErrorMessage(caught, "Review the latest certificate details."));
        return;
      }
      if (code === "current_student_required") {
        await onRefresh();
        setConfirmOpen(false);
        setError("This certificate can no longer be issued because the applicant is no longer a current student.");
        return;
      }
      if (uncertainGoodMoralMutation(caught)) {
        setConfirmOpen(false);
        const refreshed = await onRefresh();
        if (refreshed?.status === "ISSUED") {
          setBlockedUntilRefresh(false);
          await invalidate();
          setError(null);
          setNotice("Good Moral certificate issued.");
        } else if (refreshed?.status === "READY_FOR_ISSUANCE") {
          setBlockedUntilRefresh(false);
          setError("Issuance could not be confirmed. The request is still ready for issuance; review the certificate details before deliberately trying again.");
        } else {
          setBlockedUntilRefresh(true);
          setError("Issuance could not be confirmed and the request could not be refreshed. Do not retry until its current state can be checked.");
        }
        return;
      }
      setError(goodMoralErrorMessage(caught, "The Good Moral certificate could not be issued."));
    } finally {
      setIssuing(false);
    }
  }

  async function refreshRequestState() {
    const refreshed = await onRefresh();
    if (refreshed?.status === "ISSUED") {
      setBlockedUntilRefresh(false);
      await invalidate();
      setError(null);
      setNotice("Good Moral certificate issued.");
    } else if (refreshed?.status === "READY_FOR_ISSUANCE") {
      setBlockedUntilRefresh(false);
      setError(null);
      setNotice("The request is still ready for issuance. Review the current certificate details before deciding whether to issue it.");
    } else if (refreshed?.status === "CANCELLED") {
      setBlockedUntilRefresh(false);
      setError("This request was cancelled and cannot be issued.");
    } else {
      setBlockedUntilRefresh(true);
      setError("The request state still cannot be verified. Issuance remains unavailable until it can be refreshed.");
    }
  }

  return (
    <>
      <GoodMoralSection
        title="Issuance review"
        description="Review certificate details before issuing."
      >
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          <GoodMoralField label="Applicant name" value={item.applicant_name} />
          {item.variant === "CURRENT_STUDENT" ? (
            <>
              <GoodMoralField label="Year level" value={item.year_level} />
              <GoodMoralField label="College" value={item.college} />
              <GoodMoralField label="Course" value={item.course} />
              <GoodMoralField label="Major" value={item.major} />
              <GoodMoralField label="Semester" value={item.semester} />
              <GoodMoralField label="Academic Year" value={item.academic_year?.label} />
            </>
          ) : (
            <>
              <GoodMoralField label="Degree" value={item.degree} />
              <GoodMoralField label="Major" value={item.major} />
              <GoodMoralField label="Graduation date" value={formatGoodMoralDate(item.graduation_date)} />
            </>
          )}
          <GoodMoralField label="Official Receipt number" value={item.official_receipt_number} />
          <GoodMoralField label="Official Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
          <GoodMoralField label="Official Receipt amount" value={item.official_receipt_amount} />
        </dl>
        <div className="mt-5 flex flex-col items-start gap-3 border-t border-border pt-4">
          <Button onClick={beginIssue} disabled={issuePending || blockedUntilRefresh}>
            Issue certificate
          </Button>
          {blockedUntilRefresh ? <Button variant="secondary" onClick={() => void refreshRequestState()}>Refresh request state</Button> : null}
          {error && !confirmOpen ? <p role="alert" className="max-w-2xl text-sm leading-6 text-danger">{error}</p> : null}
          {notice ? <p role="status" className="text-sm text-muted">{notice}</p> : null}
        </div>
      </GoodMoralSection>

      <ConsequentialActionDialog
        open={confirmOpen}
        title="Issue Good Moral certificate?"
        confirmLabel="Issue certificate"
        pendingLabel="Issuing certificate…"
        pending={issuePending}
        confirmDisabled={blockedUntilRefresh}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void confirmIssue()}
      >
        <p>
          The issued certificate will record the approved form revision,
          issuance date, and issuing counselor. Review the details below before issuing.
        </p>
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          <GoodMoralField label="Applicant name" value={item.applicant_name} />
          <GoodMoralField label="Variant" value={item.variant === "CURRENT_STUDENT" ? "Current Student" : "Graduate"} />
          {item.variant === "CURRENT_STUDENT" ? (
            <>
              <GoodMoralField label="Year level" value={item.year_level} />
              <GoodMoralField label="College" value={item.college} />
              <GoodMoralField label="Course" value={item.course} />
              <GoodMoralField label="Semester" value={item.semester} />
            </>
          ) : (
            <>
              <GoodMoralField label="Degree" value={item.degree} />
              <GoodMoralField label="Graduation date" value={formatGoodMoralDate(item.graduation_date)} />
            </>
          )}
        </dl>
      </ConsequentialActionDialog>
    </>
  );
}
