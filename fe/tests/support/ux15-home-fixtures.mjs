import { messagesAccount, sessionFor } from "./guidance-messages-fixtures.mjs";

export const homeInstant = "2026-10-22T01:30:00Z";
const source = (n) => `a0000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export function homeAction(kind, priority = "ACTION_REQUIRED", n = 1, extra = {}) {
  return { id: `${kind.toLowerCase()}:${source(n)}`, kind, priority, source_id: source(n),
    due_at: null, waiting_since: "2026-10-21T01:30:00Z", conversation_kind: null, pending_count: null, ...extra };
}
export const pendingHomeActions = [
  homeAction("CALL_SLIP_ACTIVE", "TIME_SENSITIVE", 1, { due_at: homeInstant }),
  homeAction("ROUTINE_INTAKE", "ACTION_REQUIRED", 2),
  homeAction("GUIDANCE_MESSAGE_UNREAD", "ACTION_REQUIRED", 3, { conversation_kind: "OFFICE", pending_count: 2 }),
  homeAction("EXIT_INTERVIEW_CONTINUE", "ACTION_REQUIRED", 4),
  homeAction("INVENTORY_CONTINUE", "INCOMPLETE_SELF_SERVICE", 5),
  homeAction("ECOUNSELING_CONSENT", "ACTION_REQUIRED", 6),
];
export const homeCapabilities = ["appointments.view_self", "appointments.manage_self",
  "inventory.view_self", "inventory.manage_self", "good_moral.view_self", "good_moral.request_self",
  "guidance_messages.view_self", "guidance_messages.manage_self", "graduate_tracer.view_self",
  "graduate_tracer.manage_self", "routine_interviews.view_self", "routine_interviews.manage_self",
  "exit_interviews.view_self", "exit_interviews.manage_self", "ecounseling.view_self",
  "ecounseling.join_self", "ecounseling.consent_self", "call_slips.view_self"];

export function homeWorld({ role = "STUDENT", lifecycle = "CURRENT", capabilities, items = pendingHomeActions, designations = [] } = {}) {
  const state = {
    account: messagesAccount(role, { first_name: "Alex", last_name: "Rivera", designations,
      student_lifecycle_status: role === "STUDENT" ? lifecycle : null,
      ...(capabilities ? { capabilities } : role === "STUDENT" ? { capabilities: homeCapabilities }
        : ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role) ? { capabilities: [
          ...messagesAccount(role).capabilities, "good_moral.view", "good_moral.prepare",
          ...(role === "COUNSELOR" ? ["routine_interviews.view_assigned", "routine_interviews.manage_assigned", "good_moral.issue"] : []),
        ] } : {}) }),
    items: structuredClone(items), actionsStatus: 200, summaryStatus: 200, announcementsStatus: 200, sessionStatus: 200,
    actionsHold: null, summaryHold: null, announcementsHold: null,
    summary: { generated_at: homeInstant, student: role === "STUDENT" ? {
      upcoming_appointments_count: 2, routine_intake_draft_count: lifecycle === "CURRENT" ? 1 : null, good_moral_requested_count: 1, active_call_slip_count: 1,
    } : null, guidance: ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role) ? {
      upcoming_self_appointments_count: role === "COUNSELOR" ? 2 : null,
      upcoming_managed_appointments_count: role === "GUIDANCE_SERVICES_STAFF" ? 3 : null,
      routine_evaluation_pending_count: role === "COUNSELOR" ? 2 : null,
      good_moral_requested_count: 1, good_moral_ready_count: 2, active_call_slip_count: 1,
    } : null, platform: role === "IT_ADMIN" ? {
      email_failed_count: 2, email_pending_count: 3, email_due_pending_count: 1, email_sent_today_count: 4,
    } : null },
    announcements: [
      { id: source(101), title: "Guidance Office schedule for October", is_pinned: true, published_at: "2026-10-21T01:00:00Z", audience: "STUDENTS" },
      { id: source(102), title: "Preparing for your Guidance appointment", is_pinned: false, published_at: "2026-10-20T01:00:00Z", audience: "AUTHENTICATED" },
      { id: source(103), title: "Career conversations this semester", is_pinned: false, published_at: "2026-10-19T01:00:00Z", audience: "PUBLIC" },
    ],
    work: [{ id: "routine-evaluation:synthetic", kind: "ROUTINE_EVALUATION", priority: "ACTION_REQUIRED",
      source_id: source(201), student: { id: "synthetic-student", display_name: "Synthetic Student" },
      waiting_since: homeInstant, due_at: null, conversation_kind: null }],
    reads: [],
  };
  const pageReply = (rows, url) => {
    const page = Number(url.searchParams.get("page") ?? 1);
    const size = Number(url.searchParams.get("page_size") ?? 20);
    return { items: rows.slice((page - 1) * size, page * size), page, page_size: size, has_next: rows.length > page * size, generated_at: homeInstant };
  };
  state.handler = async ({ pathname, reply, url }) => {
    state.reads.push(pathname + url.search);
    if (pathname === "/api/v1/auth/session") {
      await reply(state.sessionStatus === 200 ? sessionFor(state.account) : { error: { code: "authentication_required", message: "Synthetic session ended" } }, state.sessionStatus);
      return true;
    }
    if (pathname === "/api/v1/me/profile") { await reply({ full_name: "Alex Rivera", photo: null }); return true; }
    const sources = {
      "/api/v1/student-actions": ["actions", () => pageReply(state.items, url)],
      "/api/v1/overview": ["summary", () => state.summary],
      "/api/v1/announcements": ["announcements", () => ({ ...pageReply(state.announcements, url), ordering: "RECOMMENDED" })],
    };
    if (sources[pathname]) {
      const [key, data] = sources[pathname];
      if (state[`${key}Hold`]) await state[`${key}Hold`];
      const status = state[`${key}Status`];
      await reply(status === 200 ? data() : { error: { code: status === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, status);
      return true;
    }
    if (pathname === "/api/v1/work") { await reply(pageReply(state.work, url)); return true; }
    return false;
  };
  state.options = (extra = {}) => ({ handler: state.handler, timezoneId: "America/Los_Angeles",
    beforeNavigate: async ({ page }) => page.clock.install({ time: new Date(homeInstant) }), ...extra });
  return state;
}
