// Synthetic records for rendering/browser regression tests. No production account or Daily room.
export const appointmentId = "appointment-density-test";
export const serviceId = "service-density-test";
export const user = (role = "COUNSELOR") => ({
  id: role === "STUDENT" ? "student" : "counselor",
  first_name: "Example", last_name: "User", middle_name: "", email: "example@example.test",
  role, student_lifecycle_status: role === "STUDENT" ? "CURRENT" : null,
  designations: [], institutional_id: "TEST-01",
  capabilities: role === "STUDENT"
    ? ["ecounseling.view_self", "ecounseling.join_self", "ecounseling.consent_self", "appointments.view_self", "call_slips.view_self"]
    : ["ecounseling.view_assigned", "ecounseling.join_assigned", "ecounseling.manage_media_assigned", "appointments.view_self", "appointments.manage", "counseling.view_assigned", "counseling.manage_assigned", "call_slips.view", "call_slips.manage", "organization.manage", "organization.structure.view", "institutional_forms.view", "services.catalog.view", "services.manage", "platform_operations.view", "platform_operations.manage"],
});
export const appointment = {
  id: appointmentId, reference_code: "APT-TEST-1024", student_id: "student",
  student: { id: "student", institutional_id: "TEST-01", display_name: "Maria Santos" },
  service: { id: serviceId, code: "COUNSELING", name: "Counseling" },
  provider: { id: "counselor", display_name: "Maria Reyes" },
  delivery_mode: "ONLINE", status: "SCHEDULED",
  starts_at: "2026-10-08T02:00:00Z", ends_at: "2026-10-08T03:00:00Z",
  cancellation_cutoff_minutes: 30, cancelled_at: null, completed_at: null, no_show_at: null,
  created_at: "2026-10-07T00:00:00Z", counseling_context_available: false,
  actions: Object.fromEntries(["cancel", "reschedule", "reassign", "complete", "mark_no_show"].map((name) => [name, { allowed: true, blocker: null, consequences: [] }])),
};
export const media = (capture = "NOT_STARTED") => ({
  recording: { artifact_disposed_at: null, capture_status: capture, consent_status: "APPROVED" },
  transcription: { artifact_disposed_at: null, capture_status: capture, consent_status: "APPROVED", storage_consent_status: "NOT_REQUESTED", storage_enabled: false },
});
export const consents = (decision = "APPROVED") => ["AUDIO_VIDEO_RECORDING", "LIVE_TRANSCRIPTION"].map((scope, index) => ({
  id: `consent-${index}`, scope, decision, effective: decision === "APPROVED", withdrawn_at: null,
  requested_at: "2026-10-07T00:00:00Z", decided_at: decision === "PENDING" ? null : "2026-10-07T00:01:00Z",
}));
export const workspace = (capture = "NOT_STARTED") => ({
  appointment, media: media(capture), student: appointment.student,
  counselor: appointment.provider, counseling_context_available: false,
  counseling_encounter: null, routine_interview: null,
  provider_readiness: { daily_enabled: true, room_provisioned: true, join_allowed: true, join_state: "OPEN", join_available_from: "2026-10-07T00:00:00Z", join_available_until: "2099-10-07T00:00:00Z" },
});
export const service = {
  id: serviceId, code: "COUNSELING", name: "Counseling", description: "",
  appointment_booking_enabled: true, default_appointment_duration_minutes: 60,
  cancellation_cutoff_minutes: 30, requires_current_inventory: false,
  delivery_modes: ["IN_PERSON", "ONLINE"], provider_coverage: "ALL_COUNSELORS",
  is_active: true, is_system_required: true, activation_blockers: [],
  created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-07T00:00:00Z",
};
export const slip = {
  id: "slip-density-test", student: appointment.student, student_name_snapshot: "Maria Santos",
  course_year_snapshot: "BSIT / 4", report_at: appointment.starts_at,
  destination_type: "GUIDANCE_OFFICE", other_destination: "", state: "ACTIVE",
  issued_by_name_snapshot: "Maria Reyes", issued_by: appointment.provider,
  created_at: "2026-10-07T00:00:00Z", interview_ended_at: null, referral: null,
  issuance_mode: "LIVE", void_notifies_student: true,
  form_revision: { official_code: "TEST-CS", official_revision: "1", effective_on: "2026-10-01" },
};
