import { messagesAccount } from "./guidance-messages-fixtures.mjs";

export const operationsInstant = "2026-10-10T00:00:00Z";

export function operationsData(role = "COUNSELOR") {
  const waiting = (count) => ({ count, oldest_waiting_since: count ? operationsInstant : null });
  return {
    generated_at: operationsInstant,
    backlog: {
      guidance_messages: waiting(7),
      routine_evaluations: role === "COUNSELOR" ? waiting(4) : null,
      good_moral_preparation: waiting(12),
      good_moral_issuance: role === "COUNSELOR" ? waiting(5) : null,
      call_slips_due: { count: 3, oldest_due_at: operationsInstant },
    },
    schedule: {
      upcoming_self_appointments_count: role === "COUNSELOR" ? 6 : null,
      upcoming_managed_appointments_count: role === "GUIDANCE_SERVICES_STAFF" ? 14 : null,
      active_call_slips_count: 9,
    },
  };
}

export function operationsAccount(role = "COUNSELOR", fields = {}) {
  const user = messagesAccount(role, fields);
  if (!["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role) || fields.capabilities) return user;
  return { ...user, capabilities: [...new Set([...user.capabilities,
    "good_moral.view", "good_moral.prepare", "call_slips.view", "call_slips.manage",
    "appointments.manage", ...(role === "COUNSELOR" ? ["appointments.view_self",
      "routine_interviews.view_assigned", "routine_interviews.manage_assigned", "good_moral.issue"] : []),
  ])] };
}
