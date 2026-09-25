import type { UserSummary } from "@/lib/api/generated/model";

export type GraduateTracerAccess = {
  isStudent: boolean;
  isGraduatedStudent: boolean;
  canViewSelf: boolean;
  canManageSelf: boolean;
  canViewOperational: boolean;
  hasStudentWorkspace: boolean;
  hasOperationalWorkspace: boolean;
  hasWorkspace: boolean;
};

export function getGraduateTracerAccess(user: UserSummary): GraduateTracerAccess {
  const isStudent = user.role === "STUDENT";
  const isGraduatedStudent = user.student_lifecycle_status === "GRADUATED";
  const canViewSelf =
    isStudent && user.capabilities.includes("graduate_tracer.view_self");
  const canManageSelf =
    isStudent &&
    isGraduatedStudent &&
    user.capabilities.includes("graduate_tracer.manage_self");
  const canViewOperational = user.capabilities.includes("graduate_tracer.view");
  const hasStudentWorkspace = canViewSelf || canManageSelf;
  const hasOperationalWorkspace = canViewOperational;

  return {
    isStudent,
    isGraduatedStudent,
    canViewSelf,
    canManageSelf,
    canViewOperational,
    hasStudentWorkspace,
    hasOperationalWorkspace,
    hasWorkspace: hasStudentWorkspace || hasOperationalWorkspace,
  };
}
