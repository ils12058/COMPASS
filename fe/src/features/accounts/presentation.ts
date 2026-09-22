import {
  DesignationCode,
  RoleCode,
  StudentLifecycleCode,
} from "@/lib/api/generated/model";
import type {
  AccountDetailResponse,
  AccountSummaryResponse,
} from "@/lib/api/generated/model";

export const roleLabels: Record<RoleCode, string> = {
  [RoleCode.IT_ADMIN]: "IT Administrator",
  [RoleCode.COUNSELOR]: "Counselor",
  [RoleCode.GUIDANCE_SERVICES_STAFF]: "Guidance Services Staff",
  [RoleCode.STUDENT]: "Student",
  [RoleCode.INSTITUTIONAL_OFFICER]: "Institutional Officer",
};

export const designationLabels: Record<DesignationCode, string> = {
  [DesignationCode.HEAD_GUIDANCE_COUNSELOR]: "Head Guidance Counselor",
  [DesignationCode.DPO]: "Data Protection Officer",
};

export const lifecycleLabels: Record<StudentLifecycleCode, string> = {
  [StudentLifecycleCode.CURRENT]: "Current",
  [StudentLifecycleCode.GRADUATED]: "Graduated",
  [StudentLifecycleCode.FORMER]: "Former",
};

export const roles = Object.values(RoleCode);
export const designations = Object.values(DesignationCode);
export const lifecycles = Object.values(StudentLifecycleCode);

export function isRoleCode(value: string): value is RoleCode {
  return roles.some((role) => role === value);
}

export function isDesignationCode(value: string): value is DesignationCode {
  return designations.some((designation) => designation === value);
}

export function accountName(
  account: AccountSummaryResponse | AccountDetailResponse,
): string {
  return account.full_name.trim() || account.email;
}

export function formatAccountDate(value: string | null): string {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function compatibleDesignation(role: RoleCode): DesignationCode | null {
  if (role === RoleCode.COUNSELOR)
    return DesignationCode.HEAD_GUIDANCE_COUNSELOR;
  if (role === RoleCode.INSTITUTIONAL_OFFICER) return DesignationCode.DPO;
  return null;
}
