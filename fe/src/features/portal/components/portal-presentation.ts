const roleLabels: Record<string, string> = {
  COUNSELOR: "Counselor",
  GUIDANCE_SERVICES_STAFF: "Guidance Services Staff",
  INSTITUTIONAL_OFFICER: "Institutional Officer",
  IT_ADMIN: "IT Administrator",
  STUDENT: "Student",
};

export function userDisplayName(user: { email: string; first_name: string; last_name: string }): string {
  const name = `${user.first_name} ${user.last_name}`.trim();
  return name || user.email;
}

export function userRoleLabel(role: string): string {
  return roleLabels[role] ?? "COMPASS user";
}
