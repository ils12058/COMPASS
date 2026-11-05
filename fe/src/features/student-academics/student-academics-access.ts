import type { CapabilityCode, RoleCode } from "@/lib/api/generated/model";

type CapabilityUser = { capabilities: readonly CapabilityCode[]; role?: RoleCode };

function hasCapability(user: CapabilityUser, capability: CapabilityCode): boolean {
  return user.capabilities.includes(capability);
}

export function canViewStudentAcademics(user: CapabilityUser): boolean {
  return hasCapability(user, "student_academics.view");
}

export function canManageStudentAcademics(user: CapabilityUser): boolean {
  return hasCapability(user, "student_academics.manage");
}

export function canImportStudentAcademics(user: CapabilityUser): boolean {
  return hasCapability(user, "student_academics.import");
}

export function canViewOwnAcademicRecord(user: CapabilityUser): boolean {
  return user.role === "STUDENT" && hasCapability(user, "student_academics.view_self");
}
