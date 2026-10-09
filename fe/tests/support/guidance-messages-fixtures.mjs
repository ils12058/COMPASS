// A synthetic, in-memory Guidance Messages backend for browser regressions (ADR-102 contract). It
// answers only /api/v1/guidance-messages/* for one viewing account, keeps the same idempotency,
// status and private read-cursor rules as the backend, and records every request. No account,
// record, key or Message is real.
import { user } from "./ui-hierarchy-fixtures.mjs";

export const COLLEGE = { id: "c0000000-0000-4000-8000-000000000001", code: "CCMS", name: "College of Computing" };
export const STUDENT = { id: "student", display_name: "Maria Santos" };
export const OTHER_STUDENT = { id: "student-2", display_name: "John Reyes" };
export const COUNSELOR = { id: "counselor", display_name: "Ana Cruz" };
export const OTHER_STAFF = { id: "staff-2", display_name: "Lea Ramos" };

export const threadIds = {
  office: "a0000000-0000-4000-8000-000000000001",
  counseling: "a0000000-0000-4000-8000-000000000002",
  resolved: "a0000000-0000-4000-8000-000000000003",
  long: "a0000000-0000-4000-8000-000000000004",
  hidden: "a0000000-0000-4000-8000-0000000000ff",
};
export const appointmentId = "b0000000-0000-4000-8000-000000000001";

const STUDENT_CAPABILITIES = ["guidance_messages.view_self", "guidance_messages.manage_self"];
const STAFF_CAPABILITIES = ["guidance_messages.view", "guidance_messages.manage"];

/** A session user with the Messages capabilities its role receives, unless `capabilities` replaces them. */
export function messagesAccount(role, { capabilities, ...fields } = {}) {
  const base = user(role);
  const messages = role === "STUDENT" ? STUDENT_CAPABILITIES : role === "COUNSELOR" || role === "GUIDANCE_SERVICES_STAFF" ? STAFF_CAPABILITIES : [];
  return {
    ...base,
    first_name: role === "STUDENT" ? "Maria" : "Ana",
    last_name: role === "STUDENT" ? "Santos" : "Cruz",
    ...fields,
    capabilities: capabilities ?? [...base.capabilities, ...messages],
  };
}

export const sessionFor = (account) => ({
  authenticated: true,
  user: account,
  session: { id: `session-${account.id}`, expires_at: "2099-10-07T00:00:00Z", is_current: true },
});

const minutesAgo = (minutes) => new Date(Date.now() - minutes * 60_000).toISOString();
const error = (code, message) => ({ error: { code, message } });

export function createMessagesBackend({ viewerId, viewerRole = viewerId === STUDENT.id ? "STUDENT" : "COUNSELOR" }) {
  const state = {
    viewerId,
    viewerRole,
    threads: new Map(),
    messages: new Map(),
    reads: new Map(),
    byClientId: new Map(),
    requests: [],
    // (payload, thread) => undefined to proceed, "network" to abort, "commit-then-network" to
    // store the Message but lose the response, or { status, body } to refuse.
    onSend: null,
    // Delays one send until the test calls the returned release().
    holdSend: null,
    eligibleStudents: [
      { id: STUDENT.id, display_name: STUDENT.display_name, institutional_id: "2026-0001", college: COLLEGE },
      { id: OTHER_STUDENT.id, display_name: OTHER_STUDENT.display_name, institutional_id: "2026-0002", college: COLLEGE },
    ],
    relationships: [{ appointment_id: appointmentId, counselor: COUNSELOR, starts_at: "2026-10-05T02:00:00Z" }],
    nextThread: 100,
  };

  function addThread({ id, kind = "OFFICE", status = "OPEN", student = STUDENT, counselor = null, assigned = COUNSELOR, appointment = null, ownRead = 0, created = 600 }) {
    state.threads.set(id, {
      id, kind, status, student, counselor: kind === "COUNSELING" ? counselor ?? COUNSELOR : null,
      routing_college: kind === "OFFICE" ? COLLEGE : null,
      assigned_to: kind === "OFFICE" ? assigned : null,
      relationship_appointment_id: kind === "COUNSELING" ? appointment ?? appointmentId : null,
      created_at: minutesAgo(created),
    });
    state.messages.set(id, []);
    state.reads.set(id, ownRead);
    return id;
  }

  function addMessage(threadId, sender, body, { at = new Date().toISOString(), clientMessageId = null } = {}) {
    const list = state.messages.get(threadId);
    const message = { id: `m-${threadId.slice(-4)}-${list.length + 1}`, sequence: list.length + 1, sender, body, created_at: at };
    list.push(message);
    if (clientMessageId) state.byClientId.set(`${sender.id}:${clientMessageId}`, { threadId, message });
    return message;
  }

  function threadResponse(thread) {
    const list = state.messages.get(thread.id);
    const read = state.reads.get(thread.id) ?? 0;
    const last = list.at(-1);
    return {
      ...thread,
      routing_college: thread.routing_college && state.viewerRole !== "STUDENT" ? thread.routing_college : null,
      last_message_at: last?.created_at ?? null,
      last_sequence: last?.sequence ?? 0,
      own_last_read_sequence: read,
      unread_count: list.filter((message) => message.sequence > read && message.sender.id !== state.viewerId).length,
    };
  }

  function viewer() {
    return state.viewerId === STUDENT.id ? STUDENT : state.viewerId === COUNSELOR.id ? COUNSELOR : { id: state.viewerId, display_name: "Viewer" };
  }

  function send(thread, payload) {
    const key = `${state.viewerId}:${payload.client_message_id}`;
    const prior = state.byClientId.get(key);
    if (prior) {
      if (prior.threadId !== thread.id) return [409, error("guidance_messages_conflict", "client_message_id has already been used for another thread.")];
      return [200, prior.message];
    }
    if (thread.status !== "OPEN") return [409, error("guidance_messages_conflict", "This Guidance thread is resolved.")];
    if (typeof payload.body !== "string" || !payload.body.trim() || [...payload.body].length > 4000) {
      return [422, error("invalid_guidance_message_input", "Message body must contain 1 to 4000 characters of nonblank text.")];
    }
    return [200, addMessage(thread.id, viewer(), payload.body, { clientMessageId: payload.client_message_id })];
  }

  // Students see only their own threads; staff see every synthetic thread except the concealed one.
  function visible(thread) {
    return Boolean(thread) && thread.id !== threadIds.hidden && (state.viewerRole !== "STUDENT" || thread.student.id === state.viewerId);
  }

  async function finishSend(route, reply, status, body) {
    if (state.holdSend) {
      const hold = state.holdSend;
      state.holdSend = null;
      await hold.promise;
    }
    return reply(body, status);
  }

  async function handler({ route, reply, request, url, pathname, method }) {
    if (!pathname.startsWith("/api/v1/guidance-messages/")) return false;
    const body = request.postData() ? JSON.parse(request.postData()) : null;
    state.requests.push({ method, pathname, search: url.search, body });
    const rest = pathname.slice("/api/v1/guidance-messages/".length).split("/");

    if (method === "GET" && pathname.endsWith("/threads")) {
      const page = Number(url.searchParams.get("page") ?? 1);
      const size = Number(url.searchParams.get("page_size") ?? 20);
      const rows = [...state.threads.values()].filter(visible).map(threadResponse)
        .sort((a, b) => (b.last_message_at ?? "").localeCompare(a.last_message_at ?? "") || b.id.localeCompare(a.id));
      const items = rows.slice((page - 1) * size, page * size);
      await reply({ items, page, page_size: size, has_next: rows.length > page * size });
      return true;
    }
    if (method === "GET" && pathname.endsWith("/recipient-options")) {
      await reply({ office_label: "Guidance Office", counseling_relationships: state.relationships, page: 1, page_size: 10, has_next: false });
      return true;
    }
    if (method === "GET" && pathname.endsWith("/eligible-students")) {
      const search = (url.searchParams.get("search") ?? "").toLowerCase();
      const items = state.eligibleStudents.filter((student) => !search || student.display_name.toLowerCase().includes(search));
      await reply({ items, page: 1, page_size: 10, has_next: false });
      return true;
    }
    const open = (thread, payload) => {
      const [status, result] = send(thread, payload);
      return status === 200 ? [200, { thread: threadResponse(thread), message: result }] : [status, result];
    };
    if (method === "POST" && pathname.endsWith("/office-thread")) {
      const studentId = rest[0] === "students" ? rest[1] : STUDENT.id;
      const student = studentId === STUDENT.id ? STUDENT : state.eligibleStudents.find((item) => item.id === studentId);
      if (!student) { await reply(error("guidance_thread_not_found", "The requested Guidance thread was not found."), 404); return true; }
      let thread = [...state.threads.values()].find((item) => item.kind === "OFFICE" && item.status === "OPEN" && item.student.id === student.id);
      if (!thread && !state.byClientId.has(`${state.viewerId}:${body.client_message_id}`)) {
        const id = `a0000000-0000-4000-8000-${String(state.nextThread++).padStart(12, "0")}`;
        addThread({ id, kind: "OFFICE", student: { id: student.id, display_name: student.display_name }, created: 0 });
        thread = state.threads.get(id);
      }
      thread ??= state.threads.get(state.byClientId.get(`${state.viewerId}:${body.client_message_id}`).threadId);
      const [status, result] = open(thread, body);
      await reply(result, status);
      return true;
    }
    if (method === "POST" && rest[0] === "appointments") {
      if (rest[1] !== appointmentId) { await reply(error("guidance_thread_not_found", "Not found."), 404); return true; }
      let thread = [...state.threads.values()].find((item) => item.relationship_appointment_id === rest[1]);
      if (!thread) {
        const id = `a0000000-0000-4000-8000-${String(state.nextThread++).padStart(12, "0")}`;
        addThread({ id, kind: "COUNSELING", counselor: COUNSELOR, appointment: rest[1], created: 0 });
        thread = state.threads.get(id);
      }
      const [status, result] = open(thread, body);
      await reply(result, status);
      return true;
    }
    if (rest[0] === "threads" && rest[1]) {
      const thread = state.threads.get(rest[1]);
      if (!visible(thread)) { await reply(error("guidance_thread_not_found", "The requested Guidance thread was not found."), 404); return true; }
      const action = rest[2];
      if (method === "GET" && !action) { await reply(threadResponse(thread)); return true; }
      if (method === "GET" && action === "messages") {
        const before = url.searchParams.get("before_sequence");
        const size = Number(url.searchParams.get("page_size") ?? 20);
        const list = state.messages.get(thread.id).filter((message) => !before || message.sequence < Number(before));
        const items = list.slice(-size);
        await reply({ items, has_older: list.length > items.length });
        return true;
      }
      if (method === "POST" && action === "messages") {
        const outcome = state.onSend?.(body, thread);
        if (outcome === "network") { await route.abort("failed"); return true; }
        const [status, result] = outcome && typeof outcome === "object" ? [outcome.status, outcome.body] : send(thread, body);
        if (outcome === "commit-then-network") { await route.abort("failed"); return true; }
        await finishSend(route, reply, status, result);
        return true;
      }
      if (method === "PATCH" && action === "read") {
        const current = state.reads.get(thread.id) ?? 0;
        if (body.sequence > current) state.reads.set(thread.id, body.sequence);
        await reply({ own_last_read_sequence: state.reads.get(thread.id) });
        return true;
      }
      if (method === "POST" && (action === "resolve" || action === "reopen")) {
        if (state.viewerId === STUDENT.id) { await reply(error("guidance_thread_not_found", "Not found."), 404); return true; }
        if (action === "reopen" && thread.kind === "OFFICE" && [...state.threads.values()].some((item) => item.id !== thread.id && item.kind === "OFFICE" && item.status === "OPEN" && item.student.id === thread.student.id)) {
          await reply(error("guidance_messages_conflict", "This Student already has an open Guidance Office thread."), 409);
          return true;
        }
        thread.status = action === "resolve" ? "RESOLVED" : "OPEN";
        await reply(threadResponse(thread));
        return true;
      }
    }
    await reply(error("synthetic_unavailable", "No synthetic Messages route"), 404);
    return true;
  }

  return {
    state,
    handler,
    addThread,
    addMessage,
    minutesAgo,
    /** Holds the next send's response until release() is called. */
    holdNextSend() {
      let release;
      const promise = new Promise((resolve) => { release = resolve; });
      state.holdSend = { promise };
      return release;
    },
    requests: (predicate = () => true) => state.requests.filter(predicate),
    sends: () => state.requests.filter((request) => request.method === "POST" && /\/threads\/[^/]+\/messages$/.test(request.pathname)),
    reads: () => state.requests.filter((request) => request.method === "PATCH"),
  };
}

/** The standard Student world: an Office thread with unread staff replies, a Counseling thread, and a resolved one. */
export function studentWorld() {
  const backend = createMessagesBackend({ viewerId: STUDENT.id });
  backend.addThread({ id: threadIds.office, kind: "OFFICE" });
  backend.addMessage(threadIds.office, STUDENT, "Good afternoon po. May I ask about my schedule?", { at: minutesAgo(30) });
  backend.addMessage(threadIds.office, COUNSELOR, "Good afternoon, Maria.\nYes, you can come on Monday.", { at: minutesAgo(5) });
  backend.addMessage(threadIds.office, COUNSELOR, "Bring your ID.", { at: minutesAgo(2) });
  backend.state.reads.set(threadIds.office, 1);
  backend.addThread({ id: threadIds.counseling, kind: "COUNSELING", counselor: COUNSELOR });
  backend.addMessage(threadIds.counseling, COUNSELOR, "See you at our next session.", { at: minutesAgo(120) });
  backend.state.reads.set(threadIds.counseling, 1);
  backend.addThread({ id: threadIds.resolved, kind: "OFFICE", status: "RESOLVED" });
  backend.addMessage(threadIds.resolved, STUDENT, "Thank you po.", { at: minutesAgo(60 * 24 * 3) });
  backend.state.reads.set(threadIds.resolved, 1);
  return backend;
}

/** The standard staff world, seen by the Counselor `counselor`. */
export function staffWorld() {
  const backend = createMessagesBackend({ viewerId: COUNSELOR.id });
  backend.addThread({ id: threadIds.office, kind: "OFFICE", assigned: OTHER_STAFF });
  backend.addMessage(threadIds.office, STUDENT, "Good afternoon po.", { at: minutesAgo(3) });
  backend.addThread({ id: threadIds.counseling, kind: "COUNSELING", student: OTHER_STUDENT, counselor: COUNSELOR });
  backend.addMessage(threadIds.counseling, OTHER_STUDENT, "Thank you for today.", { at: minutesAgo(90) });
  backend.state.reads.set(threadIds.counseling, 1);
  return backend;
}
