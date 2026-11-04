import type {
  AcademicTerm,
  EnrollmentStatus,
  StudentLifecycleStatus,
} from "@/lib/api/generated/model";

const termLabels: Record<AcademicTerm, string> = {
  FIRST_SEMESTER: "First Semester",
  SECOND_SEMESTER: "Second Semester",
};

export function academicTermLabel(term: AcademicTerm): string {
  return termLabels[term] ?? term;
}

const enrollmentLabels: Record<EnrollmentStatus, string> = {
  UNKNOWN: "Unknown",
  ENROLLED: "Enrolled",
  NOT_ENROLLED: "Not enrolled",
};

export function enrollmentStatusLabel(status: EnrollmentStatus): string {
  return enrollmentLabels[status] ?? status;
}

const lifecycleLabels: Record<StudentLifecycleStatus, string> = {
  CURRENT: "Current",
  GRADUATED: "Graduated",
  FORMER: "Former",
};

export function lifecycleStatusLabel(
  status: StudentLifecycleStatus | null,
): string {
  return status ? (lifecycleLabels[status] ?? status) : "Not set";
}

export function yearLevelLabel(yearLevel: number | null): string {
  return yearLevel === null ? "—" : String(yearLevel);
}
