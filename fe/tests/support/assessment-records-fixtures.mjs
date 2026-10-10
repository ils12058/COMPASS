import { user } from "./ui-hierarchy-fixtures.mjs";

export const recordId = "d0000000-0000-4000-8000-000000000001";
export const typeId = "e0000000-0000-4000-8000-000000000001";
export const studentId = "f0000000-0000-4000-8000-000000000001";
export const timestamp = "2020-01-01T01:00:00Z";
export const content = { score: "CONFIDENTIAL-SCORE-88/100", result: "CONFIDENTIAL-RESULT", interpretation: "CONFIDENTIAL-INTERPRETATION", remarks: "CONFIDENTIAL-REMARKS" };
export const head = () => ({ ...user(), id: "assessment-head", designations: ["HEAD_GUIDANCE_COUNSELOR"], capabilities: ["assessment_records.view", "assessment_records.manage"] });
export const person = { id: studentId, display_name: "Maria Assessment Student", institutional_id: "AS-STUDENT-01", college: { id: "college", name: "College A" } };
export const type = { id: typeId, name: "Career Aptitude Test", description: "Institutional source result", is_active: true, created_at: timestamp, updated_at: timestamp };
export const record = { id: recordId, student: person, assessment_type: type, administered_on: "2020-01-01", recorded_by: { id: "head", display_name: "Head Guidance", institutional_id: "HEAD-01" }, created_at: timestamp, updated_at: timestamp, ...content };
export function structural(item) {
  const { id, student, assessment_type, administered_on, recorded_by, created_at, updated_at } = item;
  return { id, student, assessment_type, administered_on, recorded_by, created_at, updated_at };
}

export function assessmentWorld(changes = {}) {
  const state = { account: head(), types: [{ ...type }], records: [{ ...record }], students: [{ ...person }], mutations: [], listFailure: null, detailFailure: null, typeFailure: null, saveFailure: null, waitForSave: null, ...changes };
  state.handler = async ({ pathname, method, url, request, reply }) => {
    const fail = (failure) => reply({ error: { code: failure.code ?? "synthetic_failure", message: "PRIVATE-ERROR-SENTINEL" } }, failure.status);
    if (pathname === "/api/v1/auth/session") { await reply({ user: state.account, session: { id: state.account.id + "-session", expires_at: "2099-01-01T00:00:00Z", is_current: true } }); return true; }
    if (!pathname.startsWith("/api/v1/assessment-records")) return false;
    if (method !== "GET") {
      const body = request.postDataJSON(); state.mutations.push({ pathname, method, body });
      if (state.waitForSave) await state.waitForSave;
      if (state.saveFailure) { await fail(state.saveFailure); return true; }
      if (pathname.endsWith("/types")) {
        const next = { ...type, id: "e0000000-0000-4000-8000-000000000002", ...body }; state.types.push(next); await reply(next, 201);
      } else if (pathname.includes("/types/")) {
        const next = state.types.find((item) => item.id === pathname.split("/").at(-1)); Object.assign(next, body); await reply(next);
      } else if (method === "POST") {
        const next = { ...record, id: "d0000000-0000-4000-8000-000000000002", student: state.students.find((item) => item.id === body.student_id), assessment_type: state.types.find((item) => item.id === body.assessment_type_id), ...body }; state.records.push(next); await reply(next, 201);
      } else {
        const next = state.records.find((item) => item.id === pathname.split("/").at(-1)); Object.assign(next, body, { assessment_type: state.types.find((item) => item.id === body.assessment_type_id) ?? next.assessment_type }); await reply(next);
      }
    } else if (pathname.endsWith("/types")) {
      if (state.typeFailure) await fail(state.typeFailure); else await reply(state.types);
    } else if (pathname.endsWith("/students")) {
      const search = (url.searchParams.get("search") ?? "").toLowerCase(); await reply({ items: state.students.filter((item) => `${item.display_name} ${item.institutional_id}`.toLowerCase().includes(search)), page: 1, page_size: 20, has_next: false });
    } else if (pathname === "/api/v1/assessment-records") {
      if (state.listFailure) await fail(state.listFailure);
      else {
        const page = Number(url.searchParams.get("page") ?? 1); const search = (url.searchParams.get("search") ?? "").toLowerCase();
        let items = state.records.filter((item) => `${item.student.display_name} ${item.student.institutional_id} ${item.assessment_type.name}`.toLowerCase().includes(search));
        if (url.searchParams.get("assessment_type_id")) items = items.filter((item) => item.assessment_type.id === url.searchParams.get("assessment_type_id"));
        await reply({ items: items.slice((page - 1) * 20, page * 20).map(structural), page, page_size: 20, has_next: items.length > page * 20, ordering: url.searchParams.get("ordering") ?? "NEWEST_ADMINISTERED" });
      }
    } else {
      const item = state.records.find((value) => value.id === pathname.split("/").at(-1));
      if (state.detailFailure) await fail(state.detailFailure); else if (item) await reply(item); else await fail({ status: 404 });
    }
    return true;
  };
  state.options = (extra = {}) => ({ handler: state.handler, ...extra });
  return state;
}
