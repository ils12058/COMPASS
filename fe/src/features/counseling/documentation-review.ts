import { CounselingDocumentationReviewReason } from "@/lib/api/generated/model";

/** Shown wherever a linked Encounter fails the Counseling identity rule (D-CENC-21). */
export const counselingMismatchNotice =
  "A Counseling Encounter is linked to this Appointment but doesn’t match its Counseling details. This needs administrative review and can’t be corrected here.";

/** Shown when the record exists but the Appointment is still SCHEDULED (D-CENC-05). */
export const counselingReconciliationNotice =
  "This Counseling Encounter is already recorded. Complete the Appointment to reconcile it; this won’t create another Encounter.";

export const documentationReviewReasonCopy: Record<
  CounselingDocumentationReviewReason,
  { label: string; message: string }
> = {
  [CounselingDocumentationReviewReason.MISSING_ENCOUNTER]: {
    label: "Completed without an Encounter",
    message:
      "This Appointment is marked completed, but no Counseling Encounter is recorded. Attendance isn’t assumed; record an Encounter only if Counseling took place.",
  },
  [CounselingDocumentationReviewReason.UNCOMPLETED_APPOINTMENT]: {
    label: "Encounter recorded, Appointment not completed",
    message:
      "The Counseling Encounter is already recorded. Completing the Appointment won’t create another Encounter.",
  },
  [CounselingDocumentationReviewReason.LINKED_CONFLICT]: {
    label: "Encounter link needs review",
    message: counselingMismatchNotice,
  },
};

const plainCompleteDescription =
  "This appointment will be marked completed and will no longer be scheduled.";

const reconciliationCompleteDescription =
  "This Appointment will be marked completed. The Counseling Encounter already recorded for it will be kept; no second Encounter will be created.";

export function completeConfirmationDescription({
  reconciliation,
}: {
  reconciliation: boolean;
}): string {
  return reconciliation ? reconciliationCompleteDescription : plainCompleteDescription;
}

export function reviewPageFromParam(value: string | null): number {
  const parsed = Number.parseInt(value ?? "1", 10);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : 1;
}

/** Only the review list's own page moves; every other query parameter is carried over. */
export function reviewHref(
  pathname: string,
  current: URLSearchParams,
  page: number,
): string {
  const next = new URLSearchParams(current);
  if (page > 1) next.set("review_page", String(page));
  else next.delete("review_page");
  const query = next.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function appointmentDetailHref(id: string): string {
  return `/portal/appointments/${id}`;
}

export function encounterDetailHref(id: string): string {
  return `/portal/counseling/encounters/${id}`;
}
