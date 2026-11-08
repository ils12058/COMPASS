import type { EncounterOriginPreset } from "@/features/counseling/record-encounter-form";
import {
  CounselingContextAnchorType,
  CounselingEntryMode,
  DeliveryMode,
  type CounselingContextOverviewResponse,
} from "@/lib/api/generated/model";

// EC-WS-2: Counseling Encounters are recorded on their own page, never inside a workspace. The
// page builds its origin from the same server-checked Counseling context the workspaces read, so
// an Appointment or Routine Interview id in the address is only a reference: the backend validates
// the relationship again when the Encounter is created.

export type EncounterReturnTarget = "workspace" | "ecounseling";

function isDeliveryMode(value: string): value is DeliveryMode {
  return Object.values(DeliveryMode).includes(value as DeliveryMode);
}

function directEntryMode(value: string): CounselingEntryMode | undefined {
  return value === CounselingEntryMode.WALK_IN || value === CounselingEntryMode.CALLED_IN || value === CounselingEntryMode.REFERRED
    ? value
    : undefined;
}

/** The origin a context can record from, or undefined when it cannot record from here. */
export function contextEncounterPreset(
  anchorType: CounselingContextAnchorType,
  anchorId: string,
  overview: CounselingContextOverviewResponse,
): EncounterOriginPreset | undefined {
  if (!isDeliveryMode(overview.delivery_mode)) return undefined;
  if (anchorType === CounselingContextAnchorType.APPOINTMENT) {
    return {
      entryMode: CounselingEntryMode.APPOINTMENT,
      appointmentId: anchorId,
      studentName: overview.student.display_name,
      institutionalId: overview.student.institutional_id,
      deliveryMode: overview.delivery_mode,
    };
  }
  const entryMode = directEntryMode(overview.entry_mode);
  if (!entryMode) return undefined;
  return {
    entryMode,
    studentId: overview.student.id,
    studentName: overview.student.display_name,
    institutionalId: overview.student.institutional_id,
    deliveryMode: overview.delivery_mode,
    // Recorded for this Routine Interview, so COMPASS links it on creation.
    routineInterviewId: anchorId,
  };
}

/** The dedicated Record Counseling Encounter page for one Appointment or Routine Interview. */
export function recordEncounterPath(
  anchorType: CounselingContextAnchorType,
  anchorId: string,
  from: EncounterReturnTarget = "workspace",
): string {
  const segment = anchorType === CounselingContextAnchorType.APPOINTMENT ? "appointment" : "routine-interview";
  const query = from === "ecounseling" ? "?from=ecounseling" : "";
  return `/portal/counseling/encounters/new/${segment}/${encodeURIComponent(anchorId)}${query}`;
}

/** Where Cancel and Back go: only these two known portal pages, never a supplied address. */
export function encounterReturnPath(
  anchorType: CounselingContextAnchorType,
  anchorId: string,
  from: EncounterReturnTarget,
): { href: string; label: string } {
  const id = encodeURIComponent(anchorId);
  if (from === "ecounseling" && anchorType === CounselingContextAnchorType.APPOINTMENT) {
    return { href: `/portal/e-counseling/${id}`, label: "Back to session" };
  }
  return anchorType === CounselingContextAnchorType.APPOINTMENT
    ? { href: `/portal/counseling/workspace/appointment/${id}`, label: "Back to Counseling workspace" }
    : { href: `/portal/counseling/workspace/routine-interview/${id}`, label: "Back to Counseling workspace" };
}

export function encounterReturnTarget(value: string | string[] | undefined): EncounterReturnTarget {
  return value === "ecounseling" ? "ecounseling" : "workspace";
}
