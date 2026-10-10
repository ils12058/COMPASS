// Synthetic Appointment, Counseling context and E-Counseling records for contextual Guidance
// Messages (ADR-103), all on one UUID Appointment so the Messages context can be resolved.
import { appointmentId } from "./guidance-messages-fixtures.mjs";
import { appointment as baseAppointment, consents, workspace } from "./ui-hierarchy-fixtures.mjs";

export { appointmentId };
export const appointmentPath = `/portal/appointments/${appointmentId}`;
export const counselingPath = `/portal/counseling/workspace/appointment/${appointmentId}`;
export const ecounselingPath = `/portal/e-counseling/${appointmentId}`;
export const routineInterviewId = "c0000000-0000-4000-8000-000000000001";
export const routineCounselingPath = `/portal/counseling/workspace/routine-interview/${routineInterviewId}`;

export function contextualAppointment({ serviceCode = "COUNSELING", studentName = "Maria Santos", counselorName = "Ana Cruz" } = {}) {
  return {
    ...baseAppointment,
    id: appointmentId,
    reference_code: "APT-CTX-0001",
    service: { ...baseAppointment.service, code: serviceCode, name: serviceCode === "COUNSELING" ? "Counseling" : "Career Guidance" },
    student: { id: "student", institutional_id: "2026-0001", display_name: studentName },
    provider: { id: "counselor", display_name: counselorName },
    counseling_context_available: true,
  };
}

export function counselingOverview({ anchorType = "APPOINTMENT", anchorId = appointmentId, validUntil = "2099-01-01T00:00:00Z" } = {}) {
  return {
    source_type: anchorType, source_id: anchorId, entry_mode: anchorType === "APPOINTMENT" ? "APPOINTMENT" : "WALK_IN", delivery_mode: "IN_PERSON",
    valid_from: "2026-01-01T00:00:00Z", valid_until: validUntil,
    student: { id: "student", institutional_id: "2026-0001", display_name: "Maria Santos", campus: null, college: null, program: null, year_level: 4 },
    matching_encounter: null, routine_interview: null, available_sections: ["OVERVIEW"],
  };
}

/** Appointment, Counseling context and E-Counseling routes for the one UUID Appointment. */
export function contextualRoutes({ serviceCode = "COUNSELING", validUntil, joins = { count: 0 } } = {}) {
  const appointment = contextualAppointment({ serviceCode });
  const session = () => {
    const value = workspace();
    value.appointment = { ...value.appointment, ...appointment };
    value.student = { id: "student", institutional_id: "2026-0001", display_name: "Maria Santos" };
    value.counselor = { id: "counselor", display_name: "Ana Cruz" };
    value.media.media_policy_version = 2;
    value.routine_interview = null;
    return value;
  };
  return async ({ reply, pathname, method }) => {
    if (pathname === `/api/v1/appointments/${appointmentId}`) { await reply(appointment); return true; }
    if (pathname === `/api/v1/appointments/${appointmentId}/history`) { await reply({ items: [] }); return true; }
    if (pathname === `/api/v1/counseling/context/APPOINTMENT/${appointmentId}`) { await reply(counselingOverview({ validUntil })); return true; }
    if (pathname === `/api/v1/counseling/context/ROUTINE_INTERVIEW/${routineInterviewId}`) { await reply(counselingOverview({ anchorType: "ROUTINE_INTERVIEW", anchorId: routineInterviewId })); return true; }
    if (/^\/api\/v1\/e-counseling\/(?:me\/)?appointments\/[^/]+\/consents$/.test(pathname)) {
      await reply({ items: [{ ...consents("APPROVED")[0], id: "v2-media", scope: "SESSION_MEDIA_CAPTURE" }] });
      return true;
    }
    if (method === "POST" && pathname === `/api/v1/e-counseling/appointments/${appointmentId}/join`) {
      joins.count += 1;
      await reply({ appointment_id: appointmentId, workspace_id: "w", provider: "DAILY", room_url: "https://synthetic.daily.co/room", meeting_token: `synthetic-meeting-token-${joins.count}`, token_expires_at: new Date(Date.now() + 900_000).toISOString() });
      return true;
    }
    if (new RegExp(`^/api/v1/e-counseling/(?:me/)?appointments/${appointmentId}$`).test(pathname)) { await reply(session()); return true; }
    return false;
  };
}
