import { homeInstant, homeWorld } from "./ux15-home-fixtures.mjs";
import { messagesAccount } from "./guidance-messages-fixtures.mjs";
import { appointment as baseAppointment } from "./ui-hierarchy-fixtures.mjs";
import { workItem } from "./ux15-counselor-home-fixtures.mjs";

export const gssHomeDate = "2026-10-22";
export const gssAppointmentId = "d0000000-0000-4000-8000-000000000501";

const gssCapabilities = [
  ...messagesAccount("GUIDANCE_SERVICES_STAFF").capabilities,
  "appointments.manage",
  "good_moral.view",
  "good_moral.prepare",
  "call_slips.view",
  "guidance_followups.view",
  "referrals.view",
];

export const gssHomeWork = [
  workItem("GUIDANCE_FOLLOW_UP", 1, "TIME_SENSITIVE", { due_at: "2026-10-22T10:00:00+08:00" }),
  workItem("GUIDANCE_MESSAGE_REPLY", 2),
  workItem("GOOD_MORAL_PREPARATION", 3),
  workItem("CALL_SLIP_DUE", 4, "TIME_SENSITIVE", { due_at: "2026-10-22T10:30:00+08:00" }),
  workItem("GUIDANCE_FOLLOW_UP", 5),
  workItem("GUIDANCE_MESSAGE_REPLY", 6),
];

export function managedAppointment(n, {
  hour = 9 + n,
  studentName = `Synthetic GSS Student ${n}`,
  status = "SCHEDULED",
  startsAt,
  endsAt,
} = {}) {
  const start = startsAt ?? `2026-10-22T${String(hour).padStart(2, "0")}:00:00+08:00`;
  const end = endsAt ?? `2026-10-22T${String(hour + 1).padStart(2, "0")}:00:00+08:00`;
  return {
    ...baseAppointment,
    id: n === 1 ? gssAppointmentId : `d0000000-0000-4000-8000-${String(500 + n).padStart(12, "0")}`,
    reference_code: `APT-GSS-SYN-${n}`,
    student_id: `synthetic-gss-student-${n}`,
    student: { ...baseAppointment.student, id: `synthetic-gss-student-${n}`, display_name: studentName },
    provider: { ...baseAppointment.provider, id: `synthetic-counselor-${n}`, display_name: `Sam Counselor ${n}` },
    service: { ...baseAppointment.service, name: "Career Guidance" },
    starts_at: start,
    ends_at: end,
    status,
    // This is intentionally outside AppointmentResponse's managed-list contract and must never be rendered.
    private_purpose: "Synthetic confidential counseling narrative",
  };
}

function pageReply(rows, url, extra = {}) {
  const page = Number(url.searchParams.get("page") ?? 1);
  const pageSize = Number(url.searchParams.get("page_size") ?? 20);
  const start = (page - 1) * pageSize;
  return {
    items: rows.slice(start, start + pageSize),
    page,
    page_size: pageSize,
    has_next: rows.length > start + pageSize,
    ...extra,
  };
}

function dateInManila(value) {
  const parts = new Intl.DateTimeFormat("en-CA-u-ca-gregory-nu-latn", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const fields = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${fields.year}-${fields.month}-${fields.day}`;
}

export function gssWorld({
  capabilities = gssCapabilities,
  work = gssHomeWork,
  appointments = [
    managedAppointment(1, { studentName: "Alexandria Maria Catherine Johnson Williams" }),
    managedAppointment(2, { hour: 11 }),
    managedAppointment(3, { hour: 12 }),
    managedAppointment(4, { hour: 13, status: "CANCELLED" }),
    managedAppointment(5, { hour: 9, startsAt: "2026-10-23T09:00:00+08:00", endsAt: "2026-10-23T10:00:00+08:00" }),
    managedAppointment(6, { hour: 14 }),
    managedAppointment(7, { hour: 15 }),
    managedAppointment(8, { hour: 16 }),
  ],
  operations,
} = {}) {
  const state = homeWorld({ role: "GUIDANCE_SERVICES_STAFF", capabilities, items: [] });
  state.work = structuredClone(work);
  state.workStatus = 200;
  state.appointments = structuredClone(appointments);
  state.appointmentsStatus = 200;
  state.operationsStatus = 200;
  state.operations = structuredClone(operations ?? {
    generated_at: homeInstant,
    backlog: {
      guidance_messages: { count: 2, oldest_waiting_since: "2026-10-21T08:00:00+08:00" },
      routine_evaluations: null,
      good_moral_preparation: { count: 3, oldest_waiting_since: "2026-10-20T09:00:00+08:00" },
      good_moral_issuance: { count: 1, oldest_waiting_since: "2026-10-21T09:00:00+08:00" },
      call_slips_due: { count: 4, oldest_due_at: "2026-10-22T08:30:00+08:00" },
    },
    schedule: {
      upcoming_self_appointments_count: null,
      upcoming_managed_appointments_count: 6,
      active_call_slips_count: 5,
    },
  });
  state.workStatus = 200;
  state.appointmentsStatus = 200;
  state.operationsStatus = 200;

  const originalHandler = state.handler;
  state.handler = async (context) => {
    const { pathname, reply, url, method } = context;
    if (pathname === "/api/v1/work" && method === "GET") {
      state.reads.push(pathname + url.search);
      if (state.workStatus !== 200) {
        await reply({ error: { code: state.workStatus === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, state.workStatus);
      } else {
        await reply({ ...pageReply(state.work, url), generated_at: homeInstant });
      }
      return true;
    }
    if (pathname === "/api/v1/appointments" && method === "GET") {
      state.reads.push(pathname + url.search);
      if (state.appointmentsStatus !== 200) {
        await reply({ error: { code: state.appointmentsStatus === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, state.appointmentsStatus);
      } else {
        const status = url.searchParams.get("status");
        const from = url.searchParams.get("from_date");
        const to = url.searchParams.get("to_date");
        const items = state.appointments
          .filter((item) => (!status || item.status === status) && (!from || dateInManila(item.starts_at) >= from) && (!to || dateInManila(item.starts_at) <= to))
          .sort((left, right) => left.starts_at.localeCompare(right.starts_at));
        await reply(pageReply(items, url, { ordering: url.searchParams.get("ordering") ?? "EARLIEST_START" }));
      }
      return true;
    }
    if (pathname === "/api/v1/guidance-operations" && method === "GET") {
      state.reads.push(pathname + url.search);
      await reply(state.operationsStatus === 200 ? state.operations : { error: { code: state.operationsStatus === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, state.operationsStatus);
      return true;
    }
    return originalHandler(context);
  };

  return state;
}
