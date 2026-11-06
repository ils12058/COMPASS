// What the Counselor's session workspace says about its Counseling Encounter, and what it offers
// next. Kept apart from the section markup so the decision and its copy are testable without the
// call runtime (mirrors finish-counseling-availability.ts on the Appointment surfaces).
import { unconfirmedFinishMessage } from "@/features/counseling/finish-counseling-availability";
import type { FinishCounselingState } from "@/features/counseling/finish-counseling-availability";
import { unconfirmedEncounterMessage } from "@/features/counseling/counseling-shared";
import { ECounselingJoinState } from "@/lib/api/generated/model";

export type EncounterSectionState =
  | "RECORDED"
  | "UNCERTAIN"
  | "MISMATCH"
  | "READ_ONLY"
  | "WINDOW_OPEN"
  | "FINISH"
  | "FALLBACK_RECORD"
  | "NOT_AVAILABLE";

export type EncounterSectionAction =
  | "view-encounter"
  | "view-encounters"
  | "view-appointment"
  | "finish"
  | "record"
  | "check-again";

export type UncertainSave = "FINISH" | "RECORD" | null;

export type EncounterSectionInputs = {
  // `counseling.manage_assigned` on this session's Counselor, i.e. whether they may document here.
  canManageAssigned: boolean;
  // Only a successful Appointment read counts. Last-known data never confirms anything.
  appointmentReadConfirmed: boolean;
  // `finishCounselingState` for that read, or "UNAVAILABLE" when the read is not confirmed.
  finishState: FinishCounselingState;
  joinState: ECounselingJoinState | undefined;
  // Whatever Encounter is linked to this Appointment, matching or not; used only for review links.
  encounterId: string | undefined;
  // The workspace's own documentation fact: an Appointment-origin Encounter for this Appointment.
  recorded: boolean;
  uncertainSave: UncertainSave;
};

export type EncounterSectionView = {
  state: EncounterSectionState;
  status: string;
  message: string;
  actions: EncounterSectionAction[];
};

const NOT_RECORDED = "Not yet recorded";

export function encounterSectionView({
  canManageAssigned,
  appointmentReadConfirmed,
  finishState,
  joinState,
  encounterId,
  recorded,
  uncertainSave,
}: EncounterSectionInputs): EncounterSectionView {
  // The Appointment read is fresher than this session's projection, so either one confirming the
  // record is enough to stop offering anything.
  if (recorded || (appointmentReadConfirmed && finishState === "RECORDED")) {
    return view("RECORDED", "Recorded", "Encounter recorded.", encounterId ? ["view-encounter"] : ["view-encounters"]);
  }

  // An unconfirmed save is checked, never replayed, and outranks what a stale read implies.
  if (uncertainSave) {
    return view(
      "UNCERTAIN",
      "Not confirmed",
      uncertainSave === "FINISH" ? unconfirmedFinishMessage : unconfirmedEncounterMessage,
      ["check-again", "view-encounters"],
    );
  }

  // A linked Encounter that is not this Appointment's Counseling record is reported as itself: the
  // session is not documented, and this is not a thing to record over.
  if (encounterId) {
    return view(
      "MISMATCH",
      "Not this Appointment’s record",
      "A Counseling Encounter is linked to this Appointment but is not its Counseling-Appointment record. Review it in My counseling encounters.",
      ["view-encounter"],
    );
  }

  if (!canManageAssigned) {
    return view("READ_ONLY", NOT_RECORDED, "Record the encounter after the counseling conversation.", []);
  }

  // While the access period is open the server refuses to finish, so nothing is offered here that
  // would document the session anyway. join_state only ever explains; it changes no status.
  if (joinState === ECounselingJoinState.OPEN) {
    return view(
      "WINDOW_OPEN",
      NOT_RECORDED,
      "The online access period is still open. Finish counseling becomes available here once it ends.",
      [],
    );
  }

  if (!appointmentReadConfirmed) {
    return view("FALLBACK_RECORD", NOT_RECORDED, "Record the encounter after the counseling conversation.", ["record"]);
  }

  if (finishState === "OFFERED") {
    return view(
      "FINISH",
      NOT_RECORDED,
      "Finish counseling after the conversation. This records the Encounter and completes the Appointment.",
      ["finish"],
    );
  }

  return view(
    "NOT_AVAILABLE",
    NOT_RECORDED,
    "Finish counseling isn’t available for this session yet. Review the Appointment for its latest details.",
    ["view-appointment"],
  );
}

function view(state: EncounterSectionState, status: string, message: string, actions: EncounterSectionAction[]): EncounterSectionView {
  return { state, status, message, actions };
}
