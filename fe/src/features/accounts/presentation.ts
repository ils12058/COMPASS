import {
  AccountOrdering,
  DesignationCode,
  RoleCode,
  StudentLifecycleCode,
} from "@/lib/api/generated/model";
import type { SortOption } from "@/components/ui/sort-field";
import type {
  AccountDetailResponse,
  AccountSummaryResponse,
} from "@/lib/api/generated/model";
import { formatInstitutionalDateTime } from "@/lib/institutional-time";

export const roleLabels: Record<RoleCode, string> = {
  [RoleCode.FACULTY]: "Faculty",
  [RoleCode.IT_ADMIN]: "IT Administrator",
  [RoleCode.COUNSELOR]: "Counselor",
  [RoleCode.GUIDANCE_OFFICE_ASSISTANT]: "Guidance Office Assistant",
  [RoleCode.STUDENT]: "Student",
  [RoleCode.INSTITUTIONAL_OFFICER]: "Institutional Officer",
};

export const designationLabels: Record<DesignationCode, string> = {
  [DesignationCode.HEAD_GUIDANCE_COUNSELOR]: "Head Guidance Counselor",
  [DesignationCode.GENERAL_GUIDANCE_INTAKE]: "General Guidance Intake",
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

// The account list is a directory, so it reads by last name (ADR-090); creation and update
// chronology stay available for operational review.
export const accountOrderingOptions: readonly SortOption<AccountOrdering>[] = [
  { value: AccountOrdering.NAME_ASC, label: "Last name A–Z" },
  { value: AccountOrdering.NAME_DESC, label: "Last name Z–A" },
  { value: AccountOrdering.NEWEST_CREATED, label: "Newest accounts first" },
  { value: AccountOrdering.OLDEST_CREATED, label: "Oldest accounts first" },
  { value: AccountOrdering.RECENTLY_UPDATED, label: "Recently updated first" },
];

export function accountName(
  account: AccountSummaryResponse | AccountDetailResponse,
): string {
  return account.full_name.trim() || account.email;
}

export function formatAccountDate(value: string | null): string {
  if (!value) return "Not available";
  const formatted = formatInstitutionalDateTime(value);
  return formatted === value ? "Not available" : formatted;
}

/** Every institutional designation this role may hold, in the order the account UI offers them. */
export function compatibleDesignations(role: RoleCode): DesignationCode[] {
  if (role === RoleCode.COUNSELOR) {
    return [DesignationCode.HEAD_GUIDANCE_COUNSELOR, DesignationCode.GENERAL_GUIDANCE_INTAKE];
  }
  if (role === RoleCode.GUIDANCE_OFFICE_ASSISTANT) return [DesignationCode.GENERAL_GUIDANCE_INTAKE];
  return [];
}
