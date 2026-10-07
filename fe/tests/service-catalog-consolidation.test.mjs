import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import * as model from "../src/lib/api/generated/model/index.ts";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { CreateServicePage } from "../src/features/services/service-editor-page.tsx";
import { ServiceDetailPage } from "../src/features/services/service-detail-page.tsx";
import { ServiceProviderPicker } from "../src/features/services/service-provider-picker.tsx";
import {
  ServiceConsequenceSummary,
  activationBlockerLabels,
} from "../src/features/services/services-shared.tsx";
import {
  getServicesGetProvidersQueryKey,
  getServicesGetQueryKey,
  getServicesListProviderCandidatesQueryKey,
} from "../src/lib/api/generated/services/services.ts";

const ok = (data) => ({ data, status: 200, headers: {} });
const manager = {
  id: "admin",
  role: "IT_ADMIN",
  student_lifecycle_status: null,
  designations: [],
  first_name: "Admin",
  last_name: "Example",
  email: "admin@example.test",
  capabilities: ["services.catalog.view", "services.manage"],
};
const SERVICE = "service-1";
const service = {
  id: SERVICE,
  code: "PSYCH_TESTING",
  name: "Psychological Testing",
  description: "",
  appointment_booking_enabled: true,
  default_appointment_duration_minutes: null,
  cancellation_cutoff_minutes: null,
  requires_current_inventory: false,
  delivery_modes: ["IN_PERSON"],
  provider_coverage: "SELECTED_COUNSELORS",
  is_active: false,
  is_system_required: false,
  activation_blockers: ["APPOINTMENT_DURATION_MISSING", "SELECTED_COUNSELORS_MISSING"],
  created_at: "2026-10-07T00:00:00Z",
  updated_at: "2026-10-07T00:00:00Z",
};

function render(element, { seed = () => {}, params = {} } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } });
  seed(client);
  const html = renderToStaticMarkup(
    withNextRouter(
      h(QueryClientProvider, { client }, h(PortalSessionProvider, { value: { user: manager } }, element)),
      { params },
    ),
  );
  client.clear();
  return html;
}

test("generated contracts no longer expose the three-state policy or provider-role configuration", () => {
  for (const retired of ["AppointmentPolicy", "ProviderRoleCode", "ConfigurableProviderRoleCode"]) {
    assert.equal(retired in model, false, retired);
  }
  assert.deepEqual(Object.values(model.ServiceProviderCoverage), ["ALL_COUNSELORS", "SELECTED_COUNSELORS"]);
});

test("the Service form offers two-state booking and Counselor coverage, not policy or role checkboxes", () => {
  const html = render(h(CreateServicePage));
  assert.match(html, />Not available</);
  assert.match(html, />Available</);
  assert.doesNotMatch(html, /Appointment optional|Appointment required|Appointment policy/);
  assert.doesNotMatch(html, /Provider eligibility/);
  assert.match(html, /Provider type/);
  assert.match(html, /Who may provide this Service\?/);
  assert.match(html, /All active Counselors/);
  assert.match(html, /Selected Counselors/);
  // Booking starts unavailable, so its Appointment-only settings are disabled.
  assert.match(html, /<input[^>]*id="service-default-duration"[^>]*disabled=""/);
  assert.match(html, /<input[^>]*id="service-cancellation-cutoff"[^>]*disabled=""/);
});

test("an inactive Service explains exactly what blocks enabling it", () => {
  const html = render(h(ServiceDetailPage), {
    params: { serviceId: SERVICE },
    seed: (client) => {
      client.setQueryData(getServicesGetQueryKey(SERVICE), ok(service));
      client.setQueryData(getServicesGetProvidersQueryKey(SERVICE), ok({ provider_coverage: "SELECTED_COUNSELORS", counselors: [] }));
    },
  });
  assert.match(html, /Needs configuration before it can be enabled/);
  assert.match(html, new RegExp(activationBlockerLabels.APPOINTMENT_DURATION_MISSING));
  assert.match(html, /no active Counselor is selected/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Enable Service<\/button>/);
  assert.match(html, /Provider type/);
  assert.match(html, /Coverage/);
  assert.match(html, /No Counselors are selected\./);
  assert.doesNotMatch(html, /Appointment optional|Appointment required/);
});

test("a booking-off Service shows no Appointment settings", () => {
  const html = render(h(ServiceDetailPage), {
    params: { serviceId: SERVICE },
    seed: (client) => {
      client.setQueryData(
        getServicesGetQueryKey(SERVICE),
        ok({ ...service, appointment_booking_enabled: false, provider_coverage: "ALL_COUNSELORS", is_active: true, activation_blockers: [] }),
      );
    },
  });
  assert.match(html, />Appointment booking<\/dt><dd[^>]*>Not available</);
  assert.doesNotMatch(html, /Default Appointment duration/);
  assert.match(html, /All active Counselors/);
});

test("the provider picker lists active Counselors without any College filter", () => {
  const params = { page: 1, page_size: 10 };
  const html = render(
    h(ServiceProviderPicker, { selected: [{ id: "c1", displayName: "Counselor One", isActive: false }], onChange: () => {} }),
    {
      seed: (client) => {
        client.setQueryData(
          getServicesListProviderCandidatesQueryKey(params),
          ok({ items: [{ id: "c1", display_name: "Counselor One" }, { id: "c2", display_name: "Counselor Two" }], page: 1, page_size: 10, has_next: false }),
        );
      },
    },
  );
  assert.deepEqual(Object.keys(params).sort(), ["page", "page_size"]);
  assert.match(html, /Counselor Two/);
  assert.match(html, />Selected<span class="sr-only"> Counselor One/);
  assert.match(html, />Add<span class="sr-only"> Counselor Two/);
  assert.match(html, /Inactive account · not eligible/);
});

test("consequence review explains that existing Appointments stay as booked", () => {
  const html = renderToStaticMarkup(
    h(ServiceConsequenceSummary, {
      details: { existingAppointmentDependencyDetected: true, providerDependencyDetected: true, counselingOnlineEnabled: false },
    }),
  );
  assert.match(html, /stay scheduled and can still take place as booked/);
  assert.match(html, /will not receive new Appointments for this Service/);
  assert.doesNotMatch(html, /Online Counseling/);
});
