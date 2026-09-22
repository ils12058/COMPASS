import type { UserSummary } from "@/lib/api/generated/model";

function cleanPart(value: string | null | undefined) {
  const normalized = value?.trim();
  return normalized || undefined;
}

export function getPortalAccountName(user: UserSummary) {
  return (
    [cleanPart(user.first_name), cleanPart(user.last_name)]
      .filter(Boolean)
      .join(" ") || user.email
  );
}

export function getPortalInitials(user: UserSummary) {
  const parts = [cleanPart(user.first_name), cleanPart(user.last_name)].filter(
    (part): part is string => Boolean(part),
  );
  const initials = parts.map((part) => part.charAt(0)).join("").slice(0, 2);

  return (initials || user.email.slice(0, 2)).toUpperCase();
}

export function getPortalRoleLabel(role: string) {
  const normalized = role.trim().toLowerCase().replace(/[_-]+/g, " ");
  const knownLabels: Record<string, string> = {
    dpo: "Data Protection Officer",
    gss: "GCO Services Staff",
    "head guidance": "Head Guidance Counselor",
    "head guidance counselor": "Head Guidance Counselor",
    "it admin": "IT Admin",
    student: "Student",
  };

  return (
    knownLabels[normalized] ??
    normalized.replace(/\b\w/g, (character) => character.toUpperCase())
  );
}

export function getPortalRoleLine(user: UserSummary) {
  const designation = user.designations.find((item) => item.trim());
  return designation ? getPortalRoleLabel(designation) : getPortalRoleLabel(user.role);
}
