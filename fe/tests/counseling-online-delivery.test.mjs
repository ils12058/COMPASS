import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { EditServicePage } from "../src/features/services/service-editor-page.tsx";
import { ServiceDetailPage } from "../src/features/services/service-detail-page.tsx";
import { HelpSections } from "../src/components/ui/context-help.tsx";
import { serviceHelpSections } from "../src/features/services/service-help.tsx";
import { ServiceConsequenceSummary } from "../src/features/services/services-shared.tsx";
import { counselingOnlineStatus } from "../src/features/services/counseling-delivery.tsx";
import { BookingDeliveryModeChoice } from "../src/features/appointments/appointment-booking-page.tsx";
import { AppointmentDetailPage } from "../src/features/appointments/appointment-detail-page.tsx";
import {
  getServicesGetProvidersQueryKey,
  getServicesGetQueryKey,
} from "../src/lib/api/generated/services/services.ts";
import { getAppointmentsGetQueryKey } from "../src/lib/api/generated/appointments/appointments.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const person = (overrides) => ({
  student_lifecycle_status: null,
  designations: [],
  first_name: "Example",
  last_name: "User",
  email: "user@example.test",
  ...overrides,
});
// A Head Guidance Counselor manages Services but has no Platform Operations access.
const serviceManager = person({
  id: "head",
  role: "COUNSELOR",
  capabilities: ["services.catalog.view", "services.manage"],
});
const platformAdmin = person({
  id: "admin",
  role: "IT_ADMIN",
  capabilities: ["services.catalog.view", "services.manage", "platform_operations.view"],
});
const student = person({
  id: "student",
  role: "STUDENT",
  student_lifecycle_status: "CURRENT",
  capabilities: ["appointments.view_self", "ecounseling.view_self"],
});

const SERVICE = "service-1";
function serviceResponse(overrides = {}) {
  return {
    id: SERVICE,
    code: "COUNSELING",
    name: "Counseling",
    description: "",
    appointment_booking_enabled: true,
    default_appointment_duration_minutes: 60,
    cancellation_cutoff_minutes: 30,
    requires_current_inventory: false,
    delivery_modes: ["IN_PERSON"],
    provider_coverage: "ALL_COUNSELORS",
    is_active: true,
    is_system_required: true,
    activation_blockers: [],
    created_at: "2026-10-07T00:00:00Z",
    updated_at: "2026-10-07T00:00:00Z",
    ...overrides,
  };
}
const ordinaryOnline = serviceResponse({
  code: "CAREER_GUIDANCE",
  name: "Career Guidance",
  delivery_modes: ["IN_PERSON", "ONLINE"],
  is_system_required: false,
});

function render(element, { user = serviceManager, seed = () => {}, params = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(
    withNextRouter(
      h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user } }, h(UnsavedChangesProvider, null, element))),
      { params },
    ),
  );
  client.clear();
  return html;
}

function seedService(service) {
  return (client) => {
    client.setQueryData(getServicesGetQueryKey(SERVICE), ok(service));
    client.setQueryData(getServicesGetProvidersQueryKey(SERVICE), ok({ provider_coverage: "ALL_COUNSELORS", counselors: [] }));
  };
}
const editor = (service) => render(h(EditServicePage), { params: { serviceId: SERVICE }, seed: seedService(service) });
const detail = (service, user) => render(h(ServiceDetailPage), { user, params: { serviceId: SERVICE }, seed: seedService(service) });
const E_COUNSELING = /E-Counseling|Online counseling|Online Counseling|video|Platform Health/;

test("the Counseling editor names modes, shows current state and offers configuration Help", () => {
  const html = editor(serviceResponse());
  assert.match(html, /<legend class="sr-only">Counseling delivery modes<\/legend>/);
  assert.match(html, /<input[^>]*id="counseling-delivery-inPerson"[^>]*checked=""/);
  assert.doesNotMatch(html, /<input[^>]*id="counseling-delivery-online"[^>]*checked=""/);
  assert.match(html, /<label[^>]*for="counseling-delivery-online"[^>]*>Online counseling<\/label>/);
  assert.match(html, /role="status"[^>]*>Online counseling off/);
  assert.match(html, /aria-label="Help: About Service configuration"/);
  assert.match(html, /aria-describedby="counseling-delivery-help counseling-delivery-status"/);
});

test("enabled Online counseling shows scheduling state without claiming video readiness", () => {
  const html = editor(serviceResponse({ delivery_modes: ["IN_PERSON", "ONLINE"] }));
  assert.match(html, /<input[^>]*id="counseling-delivery-online"[^>]*checked=""/);
  assert.match(html, /role="status"[^>]*>Online counseling on/);
  assert.doesNotMatch(html, /provider is (ready|healthy)|E-Counseling: Enabled/);
  const help = renderToStaticMarkup(h(HelpSections, { sections: serviceHelpSections }));
  assert.match(help, /Scheduled Online Counseling appointments use E-Counseling/);
  assert.match(help, /video availability still depends on separate video-service settings/);
});

test("the Online status follows each delivery and booking state", () => {
  assert.match(counselingOnlineStatus({ inPerson: true, online: false, bookingEnabled: true }), /Online counseling off.*In-person Counseling remains available/);
  assert.doesNotMatch(counselingOnlineStatus({ inPerson: false, online: false, bookingEnabled: true }), /In-person/);
  assert.match(counselingOnlineStatus({ inPerson: true, online: true, bookingEnabled: true }), /Online counseling on.*booking is available/);
  assert.match(counselingOnlineStatus({ inPerson: false, online: true, bookingEnabled: false }), /booking is off/);
});

test("ordinary Services keep generic delivery wording in the editor and detail", () => {
  const form = editor(ordinaryOnline);
  assert.match(form, /<legend[^>]*>Supported delivery modes<\/legend>/);
  assert.match(form, /aria-label="Help: About Service configuration"/);
  assert.doesNotMatch(form, E_COUNSELING);
  const page = detail(ordinaryOnline, platformAdmin);
  assert.match(page, /In person, Online/);
  assert.doesNotMatch(page, E_COUNSELING);
});

test("Counseling detail keeps delivery and E-Counseling unavailability visible", () => {
  const html = detail(serviceResponse(), serviceManager);
  assert.match(html, /Counseling delivery/);
  assert.match(html, />In person<\/dt><dd[^>]*>Available</);
  assert.match(html, />Online counseling<\/dt><dd[^>]*>Not enabled</);
  assert.match(html, />New E-Counseling appointments<\/dt><dd[^>]*>Unavailable</);
  assert.match(html, /aria-label="Help: About Service configuration"/);
  assert.doesNotMatch(html, /Video-session provider/);
});

test("Counseling detail shows scheduling state and discloses configuration semantics in Help", () => {
  const html = detail(serviceResponse({ delivery_modes: ["IN_PERSON", "ONLINE"] }), serviceManager);
  assert.match(html, />Online counseling<\/dt><dd[^>]*>Available</);
  assert.match(html, />New E-Counseling appointments<\/dt><dd[^>]*>Available for scheduling</);
  assert.doesNotMatch(html, /provider is (ready|healthy)/);
  const onlineOnly = detail(serviceResponse({ delivery_modes: ["ONLINE"] }), serviceManager);
  assert.match(onlineOnly, />In person<\/dt><dd[^>]*>Not enabled</);
  const bookingOff = detail(serviceResponse({ delivery_modes: ["ONLINE"], appointment_booking_enabled: false, default_appointment_duration_minutes: null, cancellation_cutoff_minutes: null }), serviceManager);
  assert.match(bookingOff, />New E-Counseling appointments<\/dt><dd[^>]*>Unavailable</);
});

test("the Platform Health link appears only for viewers who already have Platform Operations", () => {
  const online = serviceResponse({ delivery_modes: ["IN_PERSON", "ONLINE"] });
  assert.doesNotMatch(detail(online, serviceManager), /View Platform Health|\/portal\/platform/);
  assert.match(detail(online, platformAdmin), /<a[^>]*href="\/portal\/platform\/health"[^>]*>View Platform Health<\/a>/);
});

test("booking offers only current modes and explains Online only for canonical Counseling", () => {
  const booking = (service) =>
    render(h(BookingDeliveryModeChoice, { service, value: "", onChange: () => {} }), { user: student });
  const summary = (overrides) => ({
    id: SERVICE,
    code: "COUNSELING",
    name: "Counseling",
    description: "",
    delivery_modes: ["IN_PERSON"],
    default_appointment_duration_minutes: 60,
    cancellation_cutoff_minutes: 30,
    requires_current_inventory: false,
    ...overrides,
  });

  const inPersonOnly = booking(summary());
  assert.match(inPersonOnly, /value="IN_PERSON"/);
  assert.doesNotMatch(inPersonOnly, /value="ONLINE"|E-Counseling/);

  const both = booking(summary({ delivery_modes: ["IN_PERSON", "ONLINE"] }));
  assert.match(both, /<input(?=[^>]*value="ONLINE")(?=[^>]*aria-describedby="booking-online-help")[^>]*>/);
  assert.match(both, /id="booking-online-help"[^>]*>Online appointments use the E-Counseling workspace\./);

  const ordinary = booking(summary({ code: "CAREER_GUIDANCE", delivery_modes: ["IN_PERSON", "ONLINE"] }));
  assert.match(ordinary, /value="ONLINE"/);
  assert.doesNotMatch(ordinary, /E-Counseling|aria-describedby/);
});

test("a saved Online Counseling Appointment opens E-Counseling from its own provenance", () => {
  const blocked = { allowed: false, blocker: null, consequences: [] };
  const appointment = (service) => ({
    id: "appointment-1",
    reference_code: "APT-2026-000123",
    student_id: "student",
    student: { id: "student", institutional_id: "2026-0001", display_name: "Student Example" },
    service,
    provider: { id: "counselor", display_name: "Counselor Example" },
    delivery_mode: "ONLINE",
    starts_at: "2026-10-08T01:00:00Z",
    ends_at: "2026-10-08T02:00:00Z",
    status: "SCHEDULED",
    cancellation_cutoff_minutes: 30,
    cancelled_at: null,
    completed_at: null,
    no_show_at: null,
    created_at: "2026-10-01T00:00:00Z",
    actions: { cancel: blocked, reschedule: blocked, reassign: blocked, complete: blocked, mark_no_show: blocked },
    counseling_context_available: false,
  });
  // No Service Catalog data is loaded: removing ONLINE from the live Service cannot hide the link.
  const page = (service) =>
    render(h(AppointmentDetailPage, { appointmentId: "appointment-1" }), {
      user: student,
      seed: (client) => client.setQueryData(getAppointmentsGetQueryKey("appointment-1"), ok(appointment(service))),
    });

  const counseling = page({ id: SERVICE, code: "COUNSELING", name: "Counseling" });
  assert.match(counseling, />Delivery<\/dt><dd[^>]*>Online</);
  assert.match(counseling, /<a[^>]*href="\/portal\/e-counseling\/appointment-1"[^>]*>(?:(?!<\/a>)[\s\S])*data-page-action-label[^>]*>Open E-Counseling<\/span><\/a>/);

  const ordinary = page({ id: "other", code: "CAREER_GUIDANCE", name: "Career Guidance" });
  assert.match(ordinary, />Delivery<\/dt><dd[^>]*>Online</);
  assert.doesNotMatch(ordinary, /Open E-Counseling/);
});

test("consequence review explains enabling and removing Online counseling without converting Appointments", () => {
  const details = (overrides) => ({
    existingAppointmentDependencyDetected: false,
    providerDependencyDetected: false,
    counselingOnlineEnabled: false,
    ...overrides,
  });

  const enabled = renderToStaticMarkup(h(ServiceConsequenceSummary, { details: details({ counselingOnlineEnabled: true }) }));
  assert.match(enabled, /allows new Online Counseling appointments to be scheduled/);
  assert.match(enabled, /use E-Counseling/);
  assert.match(enabled, /does not confirm that the\s+video-session provider is configured or available/);

  const removed = renderToStaticMarkup(
    h(ServiceConsequenceSummary, {
      details: details({ existingAppointmentDependencyDetected: true }),
      change: { counselingOnlineRemoved: true, bookingTurnedOff: false },
    }),
  );
  assert.match(removed, /New Online Counseling work will no longer be available\./);
  assert.match(removed, /remain scheduled and keep their saved Online delivery mode; they are not\s+changed to in person/);
  assert.match(removed, /cannot be rescheduled or\s+reassigned/);
  assert.doesNotMatch(removed, /Some upcoming Appointments use a setting/);

  const generic = renderToStaticMarkup(
    h(ServiceConsequenceSummary, {
      details: details({ existingAppointmentDependencyDetected: true }),
      change: { counselingOnlineRemoved: false, bookingTurnedOff: true },
    }),
  );
  assert.match(generic, /Some upcoming Appointments use a setting this change removes/);
  assert.doesNotMatch(generic, /Online Counseling/);
});
