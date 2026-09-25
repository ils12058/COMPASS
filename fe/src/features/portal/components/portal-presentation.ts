import { isRoleCode, roleLabels } from "@/features/accounts/presentation";

export function userDisplayName(user: { email: string; first_name: string; last_name: string }): string {
  const name = `${user.first_name} ${user.last_name}`.trim();
  return name || user.email;
}

export function userRoleLabel(role: string): string {
  return isRoleCode(role) ? roleLabels[role] : "COMPASS user";
}
