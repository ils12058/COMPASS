import type { GoodMoralReceiptInspectionResponse } from "@/lib/api/generated/model";

export const receiptStatuses = {
  MISSING: { label: "Missing receipt", description: "Record the Official Receipt before preparing this certificate." },
  INCOMPLETE: { label: "Receipt incomplete", description: "Complete the receipt number, date and actual amount before inspection." },
  NEEDS_VERIFICATION: { label: "Receipt needs verification", description: "Show your Official Receipt at the Guidance Office." },
  VERIFIED: { label: "Receipt verified", description: "The physical receipt inspection has been recorded." },
  DISPUTED: { label: "Receipt disputed", description: "This receipt number can't be checked right now. Ask the Guidance Office to review it." },
  POLICY_UNAVAILABLE: { label: "Fee needs confirmation", description: "The Guidance Office must confirm the fee before this receipt can be checked and the certificate prepared." },
} satisfies Record<GoodMoralReceiptInspectionResponse["status"], { label: string; description: string }>;

export function receiptBlockerMessage(blocker: string | null | undefined): string | null {
  switch (blocker) {
    case "good_moral_receipt_missing": return receiptStatuses.MISSING.description;
    case "good_moral_receipt_incomplete": return receiptStatuses.INCOMPLETE.description;
    case "good_moral_receipt_unverified": return receiptStatuses.NEEDS_VERIFICATION.description;
    case "good_moral_receipt_conflict": return "Ask the Guidance Office to review this receipt before preparing or issuing the certificate.";
    case "good_moral_receipt_fee_mismatch": return "The amount doesn't match the fee. Ask the Guidance Office to review it and keep the amount printed on the receipt.";
    case "good_moral_receipt_policy_unresolved": return receiptStatuses.POLICY_UNAVAILABLE.description;
    case "good_moral_receipt_changed": return "This receipt changed. Review the latest details before continuing.";
    default: return null;
  }
}

// Presentation only. Authority, applicability and amount comparisons always come from the API.
export function receiptAmount(amount: string | null | undefined, currency?: "PHP" | null): string {
  if (amount == null || amount === "") return "Not recorded";
  return currency === "PHP" && Number.isFinite(Number(amount))
    ? new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(Number(amount))
    : amount;
}
