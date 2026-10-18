import type { UserSummary } from "@/lib/api/generated/model";

type Account = Pick<UserSummary, "role" | "capabilities">;

export function canBrowseGroupSessions(user: Account) {
  return user.role === "STUDENT" && user.capabilities.includes("appointments.view_self");
}

// Only an entry-point hint. The server checks current GSS supervision and each session's scope.
export function canManageGroupSessions(user: Account) {
  return (user.role === "COUNSELOR" || user.role === "GUIDANCE_SERVICES_STAFF") &&
    user.capabilities.includes("appointments.manage");
}

export function hasGroupSessionsWorkspace(user: Account) {
  return canBrowseGroupSessions(user) || canManageGroupSessions(user);
}
