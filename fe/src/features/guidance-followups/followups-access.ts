import type { UserSummary } from "@/lib/api/generated/model";
export function followupAccess(user: Pick<UserSummary, "role" | "capabilities">) {
  const staff = user.role === "COUNSELOR" || user.role === "GUIDANCE_OFFICE_ASSISTANT";
  return { view: staff && user.capabilities.includes("guidance_followups.view"), manage: staff && user.capabilities.includes("guidance_followups.manage") };
}
