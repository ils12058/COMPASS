import type { GoodMoralOperationalDetailResponse, GoodMoralReceiptVerificationPayload } from "@/lib/api/generated/model";

export type ReceiptReview = { item: GoodMoralOperationalDetailResponse; payload: GoodMoralReceiptVerificationPayload };

export function sameReceiptReview(item: GoodMoralOperationalDetailResponse, review: ReceiptReview): boolean {
  return item.id === review.item.id && item.actions.request_version === review.payload.expected_resource_version
    && item.receipt_identity?.revision_id === review.payload.assignment_id;
}

export function reviewedInspectionIsCurrent(item: GoodMoralOperationalDetailResponse, review: ReceiptReview): boolean {
  return item.id === review.item.id && item.receipt_identity?.revision_id === review.payload.assignment_id
    && item.receipt_inspection?.status === "VERIFIED" && Boolean(item.receipt_inspection.verification_id);
}

export function inspectionReview(item: GoodMoralOperationalDetailResponse, operationId: string): ReceiptReview | null {
  const assignment = item.receipt_identity?.revision_id;
  if (!assignment || item.receipt_identity?.ledger_mode !== "ACTIVE" || !item.receipt_inspection?.can_verify) return null;
  return {
    item: structuredClone(item),
    payload: { assignment_id: assignment, expected_resource_version: item.actions.request_version, operation_id: operationId, method: "PHYSICAL_OR_INSPECTION" },
  };
}
