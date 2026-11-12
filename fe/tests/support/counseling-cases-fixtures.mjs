// Synthetic CW-1 wire responses. Browser checks exercise presentation; PostgreSQL tests prove scope.
import assert from "node:assert/strict";
import { user as baseUser } from "./ui-hierarchy-fixtures.mjs";

const uuid = (value) => `c1000000-0000-4000-8000-${String(value).padStart(12, "0")}`;
export const ids = { case: uuid(1), otherCase: uuid(2), openedCase: uuid(3), student: uuid(10), otherStudent: uuid(11), counselor: uuid(20), otherCounselor: uuid(21), appointment: uuid(30), routine: uuid(40), session: uuid(50), inaccessibleSession: uuid(51), candidate: uuid(52), service: uuid(60) };
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
function event(kind, detail_code, encounter = null, number = 1) {
  return { id: uuid(100 + number), kind, occurred_at: "2026-11-01T01:00:00Z", actor: eventPerson(counselor), primary_counselor: eventPerson(counselor), encounter_id: encounter?.encounter_id ?? null, encounter_started_at: encounter?.started_at ?? null, detail_code };
}
export function detail(changes = {}) {
  const first = caseSession();
  const protectedSession = caseSession({ encounter_id: ids.inaccessibleSession, started_at: "2026-01-07T01:00:00Z", ended_at: "2026-01-07T02:00:00Z", entry_mode: "WALK_IN", appointment: null, record_accessible: false, counselor: { ...counselor, id: ids.otherCounselor, display_name: "Synthetic Other Counselor" } });
  return { id: ids.case, reference_code: "CASE-2026-000001", status: "ACTIVE", student, primary_counselor: counselor, origin: "INTAKE", opened_at: "2026-11-01T00:00:00Z", session_count: 2, latest_session_at: protectedSession.started_at, version: 4, source: { appointment: null, encounter_id: null, routine_interview_id: null }, sessions: [first, protectedSession], unlinked_origin_session: null, history: [event("OPENED", "INTAKE"), event("SESSION_LINKED", null, first, 2), event("SESSION_UNLINKED", "LINKED_BY_MISTAKE", candidate(), 3)], can_manage: true, ...changes };
}
export function summary(item) {
  return Object.fromEntries(["id", "reference_code", "status", "student", "primary_counselor", "origin", "opened_at", "session_count", "latest_session_at", "version"].map((key) => [key, item[key]]));
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
    encounters: options.encounters ?? [encounter(), encounter({ id: ids.inaccessibleSession, in_case: true, case: null, appointment: null, entry_mode: "WALK_IN" }), encounter({ id: ids.candidate, in_case: false, case: null, appointment: null, entry_mode: "WALK_IN" })],
    listReads: 0, contextReads: 0, detailReads: 0, candidateReads: 0,
    operations: [],
    listError: options.listError ?? false,
    caseError: options.caseError ?? null,
    openMode: options.openMode ?? "success",
    linkMode: options.linkMode ?? "success",
    unlinkMode: options.unlinkMode ?? "success",
    ...options.state,
  };
  const sourceFor = (origin, source) => ({ appointment: origin === "APPOINTMENT" ? { ...originAppointment, id: source } : null, encounter_id: origin === "ENCOUNTER" ? source : null, routine_interview_id: origin === "ROUTINE_INTERVIEW" ? source : null });
  const sessionFor = (origin) => ["ENCOUNTER", "ROUTINE_INTERVIEW"].includes(origin) ? candidate({ encounter_id: ids.session }) : null;
  const fail = (reply, code, status = 409) => reply({ error: { code, message: "Private diagnostic text must not be displayed" } }, status);
  const operation = (operationId, data = {}) => state.operations.push({ operationId, ...data });
  function addSession(selected) {
    const session = caseSession({ ...selected, counselor });
    state.detail = { ...state.detail, sessions: [...state.detail.sessions, session], session_count: state.detail.session_count + 1, latest_session_at: [state.detail.latest_session_at, selected.started_at].filter(Boolean).sort().at(-1), version: state.detail.version + 1, unlinked_origin_session: null, history: [...state.detail.history, event("SESSION_LINKED", null, session, 10 + state.detail.version)] };
    state.candidates = state.candidates.filter((row) => row.encounter_id !== selected.encounter_id);
    return state.detail;
  }
  state.handler = async ({ reply, route, request, pathname, method, url }) => {
    if (pathname === "/api/v1/auth/session") {
      const account = options.account ?? { ...baseUser(), id: ids.counselor, first_name: "Synthetic", last_name: "Counselor" };
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
      const all = state.list.filter((row) => `${row.student.display_name} ${row.student.institutional_id} ${row.reference_code}`.toLowerCase().includes(search));
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
      const selected = state.candidates.find((row) => row.encounter_id === body.encounter_id) ?? state.detail.unlinked_origin_session;
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
