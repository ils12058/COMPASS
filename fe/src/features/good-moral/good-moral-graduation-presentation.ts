import type { GraduationBasis } from "@/lib/api/generated/model";

export function graduateBasisMessage(basis: GraduationBasis | null | undefined, staff = false): string {
  if (basis === "REGISTRAR_RECORD") return "Confirmed from the Registrar's record";
  return staff
    ? "Not in the Registrar's record. Check the diploma or TOR before preparing."
    : "Bring your diploma or TOR when you present your Official Receipt.";
}

export const inventoryCollegeMismatchStaffMessage = "The Inventory's College doesn't match the Student's current College. Reopen the Inventory for correction, then have the Student choose a Program from their current College and resubmit.";
