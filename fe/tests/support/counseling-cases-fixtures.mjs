// Synthetic CW-1/CW-2 wire responses. Browser checks exercise presentation; PostgreSQL tests prove scope.
import assert from "node:assert/strict";
import { user as baseUser, appointment as baseAppointment } from "./ui-hierarchy-fixtures.mjs";

const uuid = (value) => `c1000000-0000-4000-8000-${String(value).padStart(12, "0")}`;
export const ids = { case: uuid(1), otherCase: uuid(2), openedCase: uuid(3), student: uuid(10), otherStudent: uuid(11), counselor: uuid(20), otherCounselor: uuid(21), appointment: uuid(30), nextAppointment: uuid(31), routine: uuid(40), session: uuid(50), inaccessibleSession: uuid(51), candidate: uuid(52), service: uuid(60), action: uuid(70), successor: uuid(71), appointmentLink: uuid(80) };
export const root = "/portal/counseling";
export const casePath = `${root}/cases/${ids.case}`;
export const newPath = `${root}/cases/new`;
export const casesAPI = "/api/v1/counseling/cases";
export const student = { id: ids.student, display_name: "Synthetic CW-1 Student", institutional_id: "CW1T-001", profile_photo_url: null, profile_photo_updated_at: null };
export const counselor = { id: ids.counselor, display_name: "Synthetic CW-1 Counselor", profile_photo_url: null, profile_photo_updated_at: null };
export const service = { id: ids.service, code: "COUNSELING", name: "Counseling" };
export const originAppointment = { id: ids.appointment, reference_code: "APT-CW1T-0001", starts_at: "2026-01-06T01:00:00Z", status: "SCHEDULED" };
const emptyPage = (items = [], page = 1, page_size = 20, has_next = false) => ({ items, page, page_size, has_next });
const identity = (person) => ({ id: person.id, display_name: person.display_name, profile_photo_url: person.profile_photo_url, profile_photo_updated_at: person.profile_photo_updated_at });
const eventPerson = (person) => ({ id: person.id, display_name: person.display_name });

export function candidate(changes = {}) {
  return { encounter_id: ids.candidate, started_at: "2026-01-08T01:00:00Z", ended_at: "2026-01-08T02:00:00Z", entry_mode: "WALK_IN", delivery_mode: "IN_PERSON", appointment: null, ...changes };
}
export function caseSession(changes = {}) {
  return { ...candidate({ encounter_id: ids.session, started_at: "2026-01-06T01:00:00Z", ended_at: "2026-01-06T02:00:00Z", entry_mode: "APPOINTMENT", appointment: { id: ids.appointment, reference_code: originAppointment.reference_code } }), counselor, linked_at: "2026-11-01T01:00:00Z", record_accessible: true, ...changes };
}
export function appointmentCandidate(changes = {}) {
  return { id: ids.nextAppointment, reference_code: "APT-CW2T-0002", starts_at: "2099-01-08T01:00:00Z", ends_at: "2099-01-08T02:00:00Z", status: "SCHEDULED", delivery_mode: "IN_PERSON", provider: eventPerson(counselor), ...changes };
}
export function caseAppointment(changes = {}) {
  return { id: ids.appointmentLink, appointment_id: ids.nextAppointment, appointment: appointmentCandidate(), linked_at: "2026-11-13T01:00:00Z", linked_by: eventPerson(counselor), removed_at: null, removed_by: null, removal_reason: null, ...changes };
}
export function followup(changes = {}) {
  return { id: ids.action, title: "Check progress with Student", student_id: ids.student, student_name: student.display_name, student_profile_photo_url: null, student_profile_photo_updated_at: null, assigned_to_id: ids.counselor, assigned_to_name: counselor.display_name, assigned_to_profile_photo_url: null, assigned_to_profile_photo_updated_at: null, category: "COUNSELING", visibility: "COUNSELOR_CONFIDENTIAL", due_at: "2099-01-07T02:00:00Z", status: "PENDING", overdue: false, version: 1, post_closure_designated_at: null, created_at: "2026-11-13T01:00:00Z", updated_at: "2026-11-13T01:00:00Z", case: { id: ids.case, reference_code: "CASE-2026-000001", status: "ACTIVE" }, predecessor_id: null, source: null, source_unavailable: false, can_create_next_action: true, description: "Protected synthetic task detail", outcome: null, completed_at: null, completed_by_name: null, cancelled_at: null, cancelled_by_name: null, events: [], events_has_next: false, ...changes };
}
function event(kind, detail_code, encounter = null, number = 1) {
  return { id: uuid(100 + number), kind, occurred_at: "2026-11-01T01:00:00Z", actor: eventPerson(counselor), primary_counselor: eventPerson(counselor), encounter_id: encounter?.encounter_id ?? null, encounter_started_at: encounter?.started_at ?? null, detail_code };
}
export function detail(changes = {}) {
  const first = caseSession();
  const protectedSession = caseSession({ encounter_id: ids.inaccessibleSession, started_at: "2026-01-07T01:00:00Z", ended_at: "2026-01-07T02:00:00Z", entry_mode: "WALK_IN", appointment: null, record_accessible: false, counselor: { ...counselor, id: ids.otherCounselor, display_name: "Synthetic Other Counselor" } });
  const managed = changes.can_manage ?? changes.status !== "CLOSED";
  return { id: ids.case, reference_code: "CASE-2026-000001", status: "ACTIVE", student, primary_counselor: counselor, origin: "INTAKE", opened_at: "2026-11-01T00:00:00Z", session_count: 2, latest_session_at: protectedSession.started_at, version: 4, source: { appointment: null, encounter_id: null, routine_interview_id: null }, sessions: [first, protectedSession], unlinked_origin_session: null, appointments: [], next_appointment: null, unlinked_appointment_sessions: [], next_action: null, next_actions: [], next_actions_has_more: false, next_actions_available: true, can_add_next_action: managed, can_link_appointments: managed, history: [event("OPENED", "INTAKE"), event("SESSION_LINKED", null, first, 2), event("SESSION_UNLINKED", "LINKED_BY_MISTAKE", candidate(), 3)], continuity: { transfers: [], responsibility: [{ counselor: eventPerson(counselor), started_at: "2026-11-01T00:00:00Z", ended_at: null, transfer_id: null, derived_opening: true }], history: [], can_transfer: managed }, can_manage: managed, can_close: managed && changes.status !== "CLOSED", can_reopen: changes.status === "CLOSED" && managed, closure: null, closures: [], closed_at: null, closure_reason: null, ...changes };
}
export function summary(item) {
  return Object.fromEntries(["id", "reference_code", "status", "student", "primary_counselor", "origin", "opened_at", "session_count", "latest_session_at", "version", "closed_at", "closure_reason"].map((key) => [key, item[key]]));
}
export function encounter(changes = {}) {
  return { id: ids.session, student: identity(student), counselor, service, appointment: { id: ids.appointment, reference_code: originAppointment.reference_code }, entry_mode: "APPOINTMENT", delivery_mode: "IN_PERSON", started_at: "2026-01-06T01:00:00Z", ended_at: "2026-01-06T02:00:00Z", created_at: "2026-01-06T02:05:00Z", updated_at: "2026-01-06T02:05:00Z", in_case: true, case: { id: ids.case, reference_code: "CASE-2026-000001", status: "ACTIVE" }, ...changes };
}

export function casesFixture(options = {}) {
  const item = detail(options.detail);
  const state = {
    detail: item,
    list: options.list ?? [summary(item)],
    active: options.active ?? [],
    candidates: options.candidates ?? [candidate()],
    appointmentCandidates: options.appointmentCandidates ?? [appointmentCandidate()],
    followups: options.followups ?? item.next_actions,
    encounters: options.encounters ?? [encounter(), encounter({ id: ids.inaccessibleSession, in_case: true, case: null, appointment: null, entry_mode: "WALK_IN" }), encounter({ id: ids.candidate, in_case: false, case: null, appointment: null, entry_mode: "WALK_IN" })],
    listReads: 0, contextReads: 0, detailReads: 0, candidateReads: 0,
    operations: [],
    listError: options.listError ?? false,
    caseError: options.caseError ?? null,
    openMode: options.openMode ?? "success",
    linkMode: options.linkMode ?? "success",
    unlinkMode: options.unlinkMode ?? "success",
    appointmentLinkMode: options.appointmentLinkMode ?? "success",
    appointmentUnlinkMode: options.appointmentUnlinkMode ?? "success",
    ...options.state,
  };
  const sourceFor = (origin, source) => ({ appointment: origin === "APPOINTMENT" ? { ...originAppointment, id: source } : null, encounter_id: origin === "ENCOUNTER" ? source : null, routine_interview_id: origin === "ROUTINE_INTERVIEW" ? source : null });
  const sessionFor = (origin) => ["ENCOUNTER", "ROUTINE_INTERVIEW"].includes(origin) ? candidate({ encounter_id: ids.session }) : null;
  const fail = (reply, code, status = 409) => reply({ error: { code, message: "Private diagnostic text must not be displayed" } }, status);
  const operation = (operationId, data = {}) => state.operations.push({ operationId, ...data });
  function addSession(selected) {
    const session = caseSession({ ...selected, counselor });
    state.detail = { ...state.detail, sessions: [...state.detail.sessions, session], session_count: state.detail.session_count + 1, latest_session_at: [state.detail.latest_session_at, selected.started_at].filter(Boolean).sort().at(-1), version: state.detail.version + 1, unlinked_origin_session: null, unlinked_appointment_sessions: state.detail.unlinked_appointment_sessions.filter(row => row.encounter_id !== selected.encounter_id), history: [...state.detail.history, event("SESSION_LINKED", null, session, 10 + state.detail.version)] };
    state.candidates = state.candidates.filter((row) => row.encounter_id !== selected.encounter_id);
    return state.detail;
  }
  function projectActions() {
    const linked = state.followups.filter(row => row.case?.id === state.detail.id);
    const pending = linked.filter(row => row.status === "PENDING").sort((a, b) => a.due_at.localeCompare(b.due_at));
    const recent = linked.filter(row => row.status !== "PENDING").sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    state.detail = { ...state.detail, next_action: pending[0] ?? null, next_actions: [...pending, ...recent] };
  }
  function projectAppointments() {
    const next = state.detail.appointments.filter(row => !row.removed_at && row.appointment?.status === "SCHEDULED" && Date.parse(row.appointment.starts_at) > Date.now()).map(row => row.appointment).sort((a, b) => a.starts_at.localeCompare(b.starts_at))[0] ?? null;
    state.detail = { ...state.detail, next_appointment: next };
  }
  if (options.followups) projectActions();
  state.handler = async ({ reply, route, request, pathname, method, url }) => {
    if (pathname === "/api/v1/auth/session") {
      const base = baseUser();
      const account = options.account ?? { ...base, id: ids.counselor, first_name: "Synthetic", last_name: "Counselor", capabilities: [...base.capabilities, "guidance_followups.view", "guidance_followups.manage"] };
      await reply({ user: account, session: { id: "cw1t-synthetic-session", expires_at: "2099-01-01T00:00:00Z", is_current: true } });
      return true;
    }
    if (pathname === casesAPI && method === "GET") {
      state.listReads++;
      operation("counselingListMyCases", { query: Object.fromEntries(url.searchParams) });
      if (state.listHold) await state.listHold;
      if (state.listError) return await fail(reply, "synthetic_failure", 503), true;
      const ordering = url.searchParams.get("ordering") ?? "LATEST_ACTIVITY";
      const search = (url.searchParams.get("search") ?? "").toLowerCase();
      const status = url.searchParams.get("status");
      const all = state.list.filter((row) => (!status || row.status === status) && `${row.student.display_name} ${row.student.institutional_id} ${row.reference_code}`.toLowerCase().includes(search));
      if (ordering.startsWith("STUDENT_")) all.sort((a, b) => (ordering === "STUDENT_ASC" ? 1 : -1) * a.student.display_name.localeCompare(b.student.display_name));
      if (["OLDEST_OPENED", "LATEST_OPENED"].includes(ordering)) all.sort((a, b) => (ordering === "OLDEST_OPENED" ? 1 : -1) * a.opened_at.localeCompare(b.opened_at));
      const page = Number(url.searchParams.get("page") ?? 1), pageSize = Number(url.searchParams.get("page_size") ?? 20);
      await reply({ ...emptyPage(all.slice((page - 1) * pageSize, page * pageSize), page, pageSize, all.length > page * pageSize), ordering });
      return true;
    }
    if (pathname === casesAPI && method === "POST") {
      const body = JSON.parse(request.postData());
      operation("counselingOpenCase", { body });
      assert.ok(["INTAKE", "APPOINTMENT", "ENCOUNTER", "ROUTINE_INTERVIEW"].includes(body.origin));
      assert.ok(Array.isArray(body.known_active_case_ids), "Opening must carry the reviewed active cases");
      if (state.openHold) await state.openHold;
      if (state.openMode === "network") return await route.abort("failed"), true;
      if (state.openMode === "review") {
        state.active = [summary(detail({ id: ids.otherCase, reference_code: "CASE-2026-000002" }))];
        return await fail(reply, "counseling_case_review_required"), true;
      }
      if (state.openMode === "server") return await fail(reply, "synthetic_failure", 503), true;
      const session = sessionFor(body.origin);
      state.detail = detail({ id: ids.openedCase, reference_code: "CASE-2026-000003", origin: body.origin, source: sourceFor(body.origin, body.source_id), sessions: session ? [caseSession({ ...session })] : [], session_count: session ? 1 : 0, latest_session_at: session?.started_at ?? null, version: session ? 2 : 1, history: [event("OPENED", body.origin)] });
      if (body.origin === "APPOINTMENT") {
        state.detail = { ...state.detail, appointments: [caseAppointment({ appointment_id: body.source_id, appointment: appointmentCandidate({ ...originAppointment, id: body.source_id }) })], version: 2 };
        projectAppointments();
      }
      state.list.push(summary(state.detail));
      await reply(state.detail, 201);
      return true;
    }
    if (pathname === `${casesAPI}/opening-context`) {
      state.contextReads++;
      const query = Object.fromEntries(url.searchParams);
      operation("counselingGetCaseOpeningContext", { query });
      if (state.contextHold) await state.contextHold;
      if (state.contextError) return await fail(reply, state.contextError, 404), true;
      await reply({ origin: query.origin, student, source: sourceFor(query.origin, query.source_id), session: sessionFor(query.origin), active_cases: state.active });
      return true;
    }
    if (pathname === `${casesAPI}/${state.detail.id}` && method === "GET") {
      state.detailReads++;
      operation("counselingGetCase");
      if (state.caseError) return await fail(reply, state.caseError, state.caseErrorStatus ?? 404), true;
      await reply(state.detail);
      return true;
    }
    if (pathname === `${casesAPI}/${state.detail.id}/session-candidates`) {
      state.candidateReads++;
      operation("counselingListCaseSessionCandidates", { query: Object.fromEntries(url.searchParams) });
      if (state.candidateError) return await fail(reply, "synthetic_failure", 503), true;
      const page = Number(url.searchParams.get("page") ?? 1), pageSize = Number(url.searchParams.get("page_size") ?? 10);
      await reply(emptyPage(state.candidates.slice((page - 1) * pageSize, page * pageSize), page, pageSize, state.candidates.length > page * pageSize));
      return true;
    }
    if (pathname === `${casesAPI}/${state.detail.id}/appointment-candidates`) {
      operation("counselingListCaseAppointmentCandidates", { query: Object.fromEntries(url.searchParams) });
      if (state.appointmentCandidateHold) await state.appointmentCandidateHold;
      if (state.appointmentCandidateError) return await fail(reply, "synthetic_failure", 503), true;
      const page = Number(url.searchParams.get("page") ?? 1), pageSize = Number(url.searchParams.get("page_size") ?? 10);
      await reply(emptyPage(state.appointmentCandidates.slice((page - 1) * pageSize, page * pageSize), page, pageSize, state.appointmentCandidates.length > page * pageSize));
      return true;
    }
    if (pathname === `${casesAPI}/${state.detail.id}/appointments` && method === "POST") {
      const body = JSON.parse(request.postData());
      operation("counselingLinkCaseAppointment", { body });
      if (state.appointmentLinkHold) await state.appointmentLinkHold;
      if (state.appointmentLinkMode === "changed") {
        state.detail = { ...state.detail, version: state.detail.version + 1 };
        return await fail(reply, "counseling_case_changed"), true;
      }
      if (state.appointmentLinkMode === "failure") return await fail(reply, "counseling_case_appointment_invalid", 422), true;
      if (state.appointmentLinkMode === "network") return await route.abort("failed"), true;
      assert.equal(body.expected_version, state.detail.version);
      const selected = state.appointmentCandidates.find(row => row.id === body.appointment_id);
      assert.ok(selected, "Only an offered Appointment is linked");
      state.detail = { ...state.detail, version: state.detail.version + 1, appointments: [...state.detail.appointments, caseAppointment({ appointment_id: selected.id, appointment: selected })] };
      state.appointmentCandidates = state.appointmentCandidates.filter(row => row.id !== selected.id);
      projectAppointments();
      await reply(state.detail);
      return true;
    }
    if (pathname.startsWith(`${casesAPI}/${state.detail.id}/appointments/`) && pathname.endsWith("/unlink") && method === "POST") {
      const body = JSON.parse(request.postData());
      const appointmentId = pathname.split("/").at(-2);
      operation("counselingUnlinkCaseAppointment", { body, appointmentId });
      if (state.appointmentUnlinkHold) await state.appointmentUnlinkHold;
      if (state.appointmentUnlinkMode === "changed") {
        state.detail = { ...state.detail, version: state.detail.version + 1 };
        return await fail(reply, "counseling_case_changed"), true;
      }
      if (state.appointmentUnlinkMode === "failure") return await fail(reply, "counseling_case_appointment_not_found", 404), true;
      assert.equal(body.expected_version, state.detail.version);
      assert.ok(["BELONGS_TO_ANOTHER_CASE", "NOT_PART_OF_THIS_CASE", "LINKED_BY_MISTAKE"].includes(body.reason));
      state.detail = { ...state.detail, version: state.detail.version + 1, appointments: state.detail.appointments.map(link => link.appointment_id === appointmentId && !link.removed_at ? { ...link, removed_at: "2026-11-13T02:00:00Z", removed_by: eventPerson(counselor), removal_reason: body.reason } : link) };
      projectAppointments();
      await reply(state.detail);
      return true;
    }
    if (pathname === `${casesAPI}/${state.detail.id}/sessions` && method === "POST") {
      const body = JSON.parse(request.postData());
      operation("counselingLinkCaseSession", { body });
      if (state.linkHold) await state.linkHold;
      if (state.linkMode === "changed") {
        state.detail = { ...state.detail, version: state.detail.version + 1 };
        return await fail(reply, "counseling_case_changed"), true;
      }
      if (state.linkMode === "failure") return await fail(reply, "counseling_case_session_already_linked"), true;
      assert.equal(body.expected_version, state.detail.version);
      const selected = state.candidates.find((row) => row.encounter_id === body.encounter_id) ?? state.detail.unlinked_appointment_sessions.find(row => row.encounter_id === body.encounter_id) ?? state.detail.unlinked_origin_session;
      assert.equal(selected?.encounter_id, body.encounter_id, "Only an offered session is linked");
      await reply(addSession(selected));
      return true;
    }
    if (pathname.startsWith(`${casesAPI}/${state.detail.id}/sessions/`) && pathname.endsWith("/unlink") && method === "POST") {
      const body = JSON.parse(request.postData());
      const encounterId = pathname.split("/").at(-2);
      operation("counselingUnlinkCaseSession", { body, encounterId });
      if (state.unlinkHold) await state.unlinkHold;
      if (state.unlinkMode === "failure") return await fail(reply, "counseling_case_session_not_found", 404), true;
      if (state.unlinkMode === "changed") {
        state.detail = { ...state.detail, version: state.detail.version + 1 };
        return await fail(reply, "counseling_case_changed"), true;
      }
      assert.ok(["BELONGS_TO_ANOTHER_CASE", "NOT_PART_OF_THIS_CASE", "LINKED_BY_MISTAKE"].includes(body.reason));
      assert.equal(body.expected_version, state.detail.version);
      const removed = state.detail.sessions.find((row) => row.encounter_id === encounterId);
      assert.ok(removed);
      const sessions = state.detail.sessions.filter((row) => row.encounter_id !== encounterId);
      state.detail = { ...state.detail, sessions, session_count: sessions.length, latest_session_at: sessions.map((row) => row.started_at).sort().at(-1) ?? null, version: state.detail.version + 1, history: [...state.detail.history, event("SESSION_UNLINKED", body.reason, removed, 10 + state.detail.version)] };
      await reply(state.detail);
      return true;
    }
    if (pathname === "/api/v1/counseling/students") {
      const search = (url.searchParams.get("search") ?? "").toLowerCase();
      await reply(emptyPage(`${student.display_name} ${student.institutional_id}`.toLowerCase().includes(search) ? [student] : [], 1, Number(url.searchParams.get("page_size") ?? 10)));
      return true;
    }
    if (pathname === "/api/v1/counseling/encounter-options") {
      await reply({ service, delivery_modes: ["IN_PERSON"] });
      return true;
    }
    if (pathname === "/api/v1/counseling/appointment-candidates") {
      await reply(emptyPage([{ ...originAppointment, student, delivery_mode: "IN_PERSON", ends_at: "2026-01-06T02:00:00Z" }]));
      return true;
    }
    if (pathname === "/api/v1/counseling/me/encounters") {
      const caseLink = url.searchParams.get("case_link");
      const items = state.encounters.filter((row) => !caseLink || row.in_case === (caseLink === "LINKED"));
      await reply({ ...emptyPage(items), ordering: "LATEST_ENCOUNTER" });
      return true;
    }
    if (pathname === "/api/v1/counseling/documentation-review") {
      await reply(emptyPage([], 1, 5));
      return true;
    }
    if (pathname === "/api/v1/work") {
      operation("workQueueList", { query: Object.fromEntries(url.searchParams) });
      await reply({ ...emptyPage(state.followups.filter(row => row.status === "PENDING").map(row => ({ id: row.id, kind: "GUIDANCE_FOLLOW_UP", source_id: row.id, student: identity(student), due_at: row.due_at, waiting_since: row.created_at })), Number(url.searchParams.get("page") ?? 1)), generated_at: "2026-11-13T00:00:00Z" });
      return true;
    }
    if (pathname === "/api/v1/guidance-followups/context") {
      operation("guidanceFollowupsGetContext", { query: Object.fromEntries(url.searchParams) });
      await reply(state.sourceContext ?? { source_kind: url.searchParams.get("source_kind"), source_id: url.searchParams.get("source_id"), student_id: ids.student, student_name: student.display_name, category: "COUNSELING", visibility: "COUNSELOR_CONFIDENTIAL", can_create: true, case: { id: state.detail.id, reference_code: state.detail.reference_code, status: state.detail.status } });
      return true;
    }
    if (pathname === "/api/v1/guidance-followups/eligible-assignees") {
      operation("guidanceFollowupsEligibleAssignees", { query: Object.fromEntries(url.searchParams) });
      await reply(emptyPage([eventPerson(counselor)]));
      return true;
    }
    if (pathname === "/api/v1/guidance-followups/eligible-students") {
      operation("guidanceFollowupsEligibleStudents");
      await reply(emptyPage([student]));
      return true;
    }
    if (pathname === "/api/v1/guidance-followups/report") {
      await reply({ pending: state.followups.filter(row => row.status === "PENDING").length, completed: state.followups.filter(row => row.status === "COMPLETED").length, cancelled: state.followups.filter(row => row.status === "CANCELLED").length, overdue: 0, due_soon: 0, completed_in_period: 0, period_start: "2026-10-13T00:00:00Z", period_end: "2026-11-13T00:00:00Z", generated_at: "2026-11-13T00:00:00Z", horizon_days: 7, categories: [] });
      return true;
    }
    if (pathname === "/api/v1/guidance-followups" && method === "GET") {
      operation("guidanceFollowupsList", { query: Object.fromEntries(url.searchParams) });
      const status = url.searchParams.get("status"), caseId = url.searchParams.get("case_id");
      const rows = state.followups.filter(row => (!status || status === row.status) && (!caseId || row.case?.id === caseId));
      const page = Number(url.searchParams.get("page") ?? 1), pageSize = Number(url.searchParams.get("page_size") ?? 20);
      await reply({ ...emptyPage(rows.slice((page - 1) * pageSize, page * pageSize), page, pageSize, rows.length > page * pageSize), ordering: url.searchParams.get("ordering") ?? "EARLIEST_DUE" });
      return true;
    }
    if (pathname === "/api/v1/guidance-followups" && method === "POST") {
      const body = JSON.parse(request.postData());
      operation("guidanceFollowupsCreate", { body, key: request.headers()["idempotency-key"] });
      assert.ok(body.title?.trim(), "The create form requires an action title");
      const row = followup({ ...body, id: state.followups.length ? ids.successor : ids.action, source: body.source_id ? { kind: body.source_kind, id: body.source_id } : null, case: body.case_id ? { id: body.case_id, reference_code: state.detail.reference_code, status: state.detail.status } : null });
      state.followups.push(row);
      projectActions();
      await reply(row, 201);
      return true;
    }
    if (pathname.startsWith("/api/v1/guidance-followups/") && method === "GET") {
      const followupId = pathname.split("/")[4];
      const row = state.followups.find(row => row.id === followupId);
      if (!row) return await fail(reply, "followup_not_found", 404), true;
      operation("guidanceFollowupsGet", { id: followupId });
      await reply(pathname.endsWith("/history") ? emptyPage(row.events) : row);
      return true;
    }
    if (pathname.startsWith("/api/v1/appointments/")) {
      const appointmentId = pathname.split("/")[4];
      const source = state.detail.appointments.find(link => link.appointment_id === appointmentId)?.appointment;
      if (source) {
        await reply(pathname.endsWith("/history") || pathname.endsWith("/reminders") ? { items: [] } : { ...baseAppointment, ...source, student_id: ids.student, student, provider: counselor, service, counseling_context_available: false });
        return true;
      }
    }
    if (pathname.endsWith("/context") && pathname.startsWith("/api/v1/guidance-messages/appointments/")) {
      await reply({ thread: null, can_start: false });
      return true;
    }
    if (pathname === "/api/v1/counseling/encounters" && method === "POST") {
      const body = JSON.parse(request.postData());
      operation("counselingCreateEncounter", { body });
      assert.equal(body.case_id, state.detail.id);
      if (body.entry_mode !== "APPOINTMENT") assert.equal(body.student_id, student.id);
      const selected = candidate({ started_at: body.started_at, ended_at: body.ended_at, entry_mode: body.entry_mode, appointment: body.appointment_id ? { id: body.appointment_id, reference_code: originAppointment.reference_code } : null });
      addSession(selected);
      await reply(encounter({ id: selected.encounter_id, started_at: body.started_at, ended_at: body.ended_at, entry_mode: body.entry_mode, appointment: selected.appointment, case: { id: state.detail.id, reference_code: state.detail.reference_code, status: state.detail.status } }), 201);
      return true;
    }
    return false;
  };
  return state;
}
