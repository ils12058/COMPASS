import { CompassApiError } from "@/lib/api/errors";
import type { AssignmentBasis, CounselorAboutResponse } from "@/lib/api/generated/model";

// Counselor About (CW-6): where a Counselor is assigned in the Guidance Office. It is not case
// responsibility, availability or a biography, so nothing here describes those.

export const ABOUT_ASSIGNMENTS_HEADING = "Assigned Colleges";
export const ABOUT_EMPTY_COPY = "No current College assignment is recorded for this Counselor.";

const BASIS_NOTES: Record<AssignmentBasis, string | null> = {
  ASSIGNED: null,
  // The unique Head handles a College only while no valid Counselor is assigned to it.
  HEAD_FALLBACK: "Covered while no Counselor is assigned",
};

export function assignmentBasisNote(basis: AssignmentBasis): string | null {
  return BASIS_NOTES[basis];
}

export type AboutCampusRow = {
  id: string;
  name: string;
  colleges: { id: string; name: string; note: string | null }[];
};

function label(name: string, code: string): string {
  return name.trim() || code.trim() || "Unnamed";
}

/** Campuses in the backend's order, each with its Colleges; empty Campuses are dropped. */
export function aboutCampusRows(about: CounselorAboutResponse): AboutCampusRow[] {
  return about.campuses
    .map((campus) => ({
      id: campus.id,
      name: label(campus.name, campus.code),
      colleges: campus.colleges.map((college) => ({
        id: college.id,
        name: label(college.name, college.code),
        note: assignmentBasisNote(college.basis),
      })),
    }))
    .filter((campus) => campus.colleges.length > 0);
}

/** The refusal is final for 403/404; anything else may succeed on retry. */
export function aboutError(error: unknown): { message: string; retryable: boolean } {
  const status = error instanceof CompassApiError ? error.status : null;
  if (status === 404) return { message: "This Counselor's details aren't available.", retryable: false };
  if (status === 403 || status === 401) {
    return { message: "Your account can't view Counselor details.", retryable: false };
  }
  return { message: "Couldn't load this Counselor's details. Try again.", retryable: true };
}
