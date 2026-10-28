import { appointment as baseAppointment } from "./ui-hierarchy-fixtures.mjs";
import { homeInstant, homeWorld } from "./ux15-home-fixtures.mjs";

const uuid = (n) => `c0000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export function counselorAppointment(n, {
  hour = 10 + n,
  studentName = `Synthetic Student ${n}`,
  status = "SCHEDULED",
  startsAt,
  endsAt,
} = {}) {
  const start = startsAt ?? `2026-10-22T${String(hour).padStart(2, "0")}:00:00+08:00`;
  const end = endsAt ?? `2026-10-22T${String(hour + 1).padStart(2, "0")}:00:00+08:00`;
  return {
    ...baseAppointment,
    id: uuid(500 + n),
    reference_code: `APT-SYN-${n}`,
    student_id: `synthetic-student-${n}`,
    student: { ...baseAppointment.student, id: `synthetic-student-${n}`, display_name: studentName },
    service: { ...baseAppointment.service, name: "Counseling service" },
    starts_at: start,
    ends_at: end,
    status,
  };
}

export function workItem(kind, n, priority = "ACTION_REQUIRED", extra = {}) {
  return {
    id: `${kind.toLowerCase()}:${uuid(700 + n)}`,
    kind,
    priority,
    source_id: uuid(700 + n),
    student: { id: `work-student-${n}`, display_name: `Synthetic Work Student ${n}` },
    waiting_since: "2026-10-21T01:30:00+08:00",
    due_at: null,
    conversation_kind: null,
    ...extra,
  };
}

function pageReply(rows, url) {
  const page = Number(url.searchParams.get("page") ?? 1);
  const size = Number(url.searchParams.get("page_size") ?? 20);
  const start = (page - 1) * size;
  return {
    items: rows.slice(start, start + size),
    page,
    page_size: size,
    has_next: rows.length > start + size,
    ordering: url.searchParams.get("ordering") ?? "EARLIEST_START",
  };
}

function appointmentDateInManila(value) {
  const parts = new Intl.DateTimeFormat("en-CA-u-ca-gregory-nu-latn", {
    timeZone: "Asia/Manila",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const values = Object.fromEntries(parts.filter((part) => part.type !== "literal").map(({ type, value: part }) => [type, part]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function counselorWorld({
  head = false,
  capabilities,
  appointments = [counselorAppointment(1, { hour: 10 }), counselorAppointment(2, { hour: 11 })],
  work = [workItem("ROUTINE_EVALUATION", 1)],
} = {}) {
  const state = homeWorld({
    role: "COUNSELOR",
    designations: head ? ["HEAD_GUIDANCE_COUNSELOR"] : [],
    ...(capabilities ? { capabilities } : {}),
    items: [],
  });
  state.appointments = structuredClone(appointments);
  state.appointmentsStatus = 200;
  state.appointmentsHold = null;
  state.work = structuredClone(work);
  state.workStatus = 200;

  const previousHandler = state.handler;
  state.handler = async (context) => {
    const { pathname, reply, url } = context;
    if (pathname === "/api/v1/appointments/me") {
      if (state.appointmentsHold) await state.appointmentsHold;
      if (state.appointmentsStatus !== 200) {
        const status = state.appointmentsStatus;
        await reply({ error: { code: status === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, status);
        return true;
      }
      const from = url.searchParams.get("from_date");
      const to = url.searchParams.get("to_date");
      const status = url.searchParams.get("status");
      const rows = state.appointments.filter((item) =>
        (!status || item.status === status) &&
        (!from || appointmentDateInManila(item.starts_at) >= from) &&
        (!to || appointmentDateInManila(item.starts_at) <= to));
      await reply(pageReply(rows, url));
      return true;
    }
    if (pathname === "/api/v1/work") {
      if (state.workStatus !== 200) {
        const status = state.workStatus;
        await reply({ error: { code: status === 403 ? "permission_denied" : "synthetic_unavailable", message: "Synthetic" } }, status);
        return true;
      }
      await reply(pageReply(state.work, url));
      return true;
    }
    return previousHandler(context);
  };

  state.options = (extra = {}) => ({
    handler: state.handler,
    timezoneId: "America/Los_Angeles",
    beforeNavigate: async ({ page }) => page.clock.install({ time: new Date(homeInstant) }),
    ...extra,
  });
  return state;
}

export const counselorDate = "2026-10-22";
export const counselorSyntheticUuid = uuid;
