const ROLE_LABELS: Record<string, string> = {
  STUDENT: "Student",
  COUNSELOR: "Counselor",
  GUIDANCE_SERVICES_STAFF: "Guidance Services Staff",
  IT_ADMIN: "IT Admin",
  INSTITUTIONAL_OFFICER: "Institutional Officer",
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role.replaceAll("_", " ").toLowerCase().replace(
    /\b\w/g,
    (letter) => letter.toUpperCase(),
  );
}

export function userDisplayName(user: {
  first_name: string;
  last_name: string;
  email: string;
}): string {
  const fullName = `${user.first_name} ${user.last_name}`.trim();
  return fullName || user.email;
}
