"use client";

import { ConsequentialActionDialog, type ConsequentialActionCompletion } from "@/components/ui/consequential-action-dialog";
import { Notice } from "@/components/ui/notice";
import { GoodMoralField, formatGoodMoralDate } from "@/features/good-moral/good-moral-shared";
import { receiptStatuses } from "./receipt-presentation";
import type { GoodMoralOperationalDetailResponse } from "@/lib/api/generated/model";

// The issuance review confirmation shared by the detail page and the queue's row action. It is
// presentational: the caller owns the reviewed snapshot, the mutation, and the outcome. Issuance
// stays protected by the good_moral.issue capability and the recorded issuer on the backend.
export function GoodMoralIssueReviewDialog({
  open,
  reviewed,
  pending,
  confirmDisabled,
  error,
  onOpenChange,
  onConfirm,
  completed = null,
}: {
  open: boolean;
  reviewed: GoodMoralOperationalDetailResponse;
  pending: boolean;
  confirmDisabled: boolean;
  error: string | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  completed?: ConsequentialActionCompletion | null;
}) {
  return (
    <ConsequentialActionDialog
      open={open}
      title="Issue Good Moral Certificate?"
      confirmLabel="Issue certificate"
      pendingLabel="Issuing certificate…"
      pending={pending}
      confirmDisabled={confirmDisabled}
      error={error}
      onOpenChange={onOpenChange}
      onConfirm={onConfirm}
      completed={completed}
    >
      <p>
        The issued certificate will record the approved form revision, issuance date, and issuing Counselor. Review the details below before issuing.
      </p>
      {reviewed.variant === "GRADUATE" ? <Notice>Confirm the degree and date with the Registrar before issuing a Good Moral Certificate for UCN Bachelor&apos;s graduates (F6).</Notice> : null}
      {reviewed.receipt_inspection ? <p className="text-sm">{receiptStatuses[reviewed.receipt_inspection.status].label} · Receipt {reviewed.official_receipt_number || "not recorded"}</p> : null}
      <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
        <GoodMoralField label="Applicant name" value={reviewed.applicant_name} />
        <GoodMoralField label="Variant" value={reviewed.variant === "CURRENT_STUDENT" ? "Current Student" : "UCN Bachelor's degree"} />
        {reviewed.variant === "CURRENT_STUDENT" ? (
          <>
            <GoodMoralField label="Year level" value={reviewed.year_level} />
            <GoodMoralField label="College" value={reviewed.college} />
            <GoodMoralField label="Course" value={reviewed.course} />
            <GoodMoralField label="Semester" value={reviewed.semester} />
          </>
        ) : (
          <>
            <GoodMoralField label="Degree" value={reviewed.degree} />
            <GoodMoralField label="Graduation date" value={formatGoodMoralDate(reviewed.graduation_date)} />
          </>
        )}
      </dl>
    </ConsequentialActionDialog>
  );
}