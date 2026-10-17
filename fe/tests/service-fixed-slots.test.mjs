import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { ServiceDetailPage } from "../src/features/services/service-detail-page.tsx";
import {
  ServiceFixedSlotsStaffPanel,
  ServiceFixedSlotsStudentPanel,
} from "../src/features/services/service-fixed-slots-panel.tsx";
import {
  getServicesGetQueryKey,
  getServicesListSlotsQueryKey,
  getServicesListBookableSlotsQueryKey,
  getServicesGetProvidersQueryKey,
} from "../src/lib/api/generated/services/services.ts";

const ok = (data) => ({ data, status: 200, headers: {} });

const manager = {
  id: "counselor-1",
  role: "COUNSELOR",
  student_lifecycle_status: null,
  designations: [],
  first_name: "Staff",
  last_name: "Member",
  email: "staff@example.test",
  capabilities: ["services.manage", "appointments.manage"],
};

const student = {
  id: "student-1",
  role: "STUDENT",
  student_lifecycle_status: null,
  designations: [],
  first_name: "Student",
  last_name: "User",
  email: "student@example.test",
  capabilities: ["appointments.create"],
};

const SERVICE_ID = "svc-fixed-1";
const service = {
  id: SERVICE_ID,
  code: "SCHOLARSHIP_REVIEW",
  name: "Scholarship Consultation",
  description: "Fixed date consultations for applicants.",
  appointment_booking_enabled: false,
  booking_pathways: ["FIXED_DATE_SLOT"],
  default_appointment_duration_minutes: 30,
  cancellation_cutoff_minutes: 60,
  requires_current_inventory: false,
  delivery_modes: ["IN_PERSON"],
  provider_coverage: "ALL_COUNSELORS",
  is_active: true,
  is_system_required: false,
  activation_blockers: [],
  created_at: "2026-10-17T00:00:00Z",
  updated_at: "2026-10-17T00:00:00Z",
};

const sampleSlots = [
  {
    id: "slot-1",
    service_id: SERVICE_ID,
    provider_id: "counselor-1",
    provider_name: "Dr. Santos",
    delivery_mode: "IN_PERSON",
    starts_at: "2026-11-01T09:00:00Z",
    ends_at: "2026-11-01T09:30:00Z",
    is_published: true,
    withdrawn_at: null,
    has_booking_history: false,
    is_booked: false,
    appointment_id: null,
    appointment_reference_code: null,
    created_at: "2026-10-17T00:00:00Z",
    updated_at: "2026-10-17T00:00:00Z",
  },
  {
    id: "slot-2",
    service_id: SERVICE_ID,
    provider_id: "counselor-1",
    provider_name: "Dr. Santos",
    delivery_mode: "IN_PERSON",
    starts_at: "2026-11-01T10:00:00Z",
    ends_at: "2026-11-01T10:30:00Z",
    is_published: false,
    withdrawn_at: null,
    has_booking_history: false,
    is_booked: false,
    appointment_id: null,
    appointment_reference_code: null,
    created_at: "2026-10-17T00:00:00Z",
    updated_at: "2026-10-17T00:00:00Z",
  },
];

import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";

function renderWithUser(element, user, seed = () => {}) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: Infinity, gcTime: Infinity },
    },
  });
  seed(client);
  return renderToStaticMarkup(
    withNextRouter(
      h(
        QueryClientProvider,
        { client },
        h(
          PortalSessionProvider,
          { value: { user } },
          h(UnsavedChangesProvider, null, element)
        )
      ),
      { params: { serviceId: SERVICE_ID } }
    )
  );
}

test("Staff panel renders published and unpublished fixed slots with controls", () => {
  const html = renderWithUser(
    h(ServiceFixedSlotsStaffPanel, { service }),
    manager,
    (client) => {
      client.setQueryData(getServicesListSlotsQueryKey(SERVICE_ID), ok(sampleSlots));
      client.setQueryData(
        getServicesGetProvidersQueryKey(SERVICE_ID),
        ok({ service_id: SERVICE_ID, provider_coverage: "ALL_COUNSELORS", counselors: [] })
      );
    }
  );

  assert.match(html, /Fixed-date appointment slots/);
  assert.match(html, /Publish slot/);
  assert.match(html, /Dr\. Santos/);
  assert.match(html, /Available/);
  assert.match(html, /Unpublished/);
  assert.match(html, /Withdraw/);
  assert.doesNotMatch(html, /Delete slot/);
});

test("Student panel renders available bookable slots with Book action", () => {
  const bookableSlots = [
    {
      id: "slot-1",
      service_id: SERVICE_ID,
      service_name: service.name,
      provider_id: "counselor-1",
      provider_name: "Dr. Santos",
      delivery_mode: "IN_PERSON",
      starts_at: "2026-11-01T09:00:00Z",
      ends_at: "2026-11-01T09:30:00Z",
    },
  ];

  const html = renderWithUser(
    h(ServiceFixedSlotsStudentPanel, { service }),
    student,
    (client) => {
      client.setQueryData(
        getServicesListBookableSlotsQueryKey(SERVICE_ID),
        ok(bookableSlots)
      );
    }
  );

  assert.match(html, /Available appointment slots/);
  assert.match(html, /Dr\. Santos/);
  assert.match(html, /Book this slot/);
});

test("ServiceDetailPage integrates fixed slots staff panel when pathway is configured", () => {
  const html = renderWithUser(h(ServiceDetailPage), manager, (client) => {
    client.setQueryData(getServicesGetQueryKey(SERVICE_ID), ok(service));
    client.setQueryData(getServicesListSlotsQueryKey(SERVICE_ID), ok(sampleSlots));
    client.setQueryData(
      getServicesGetProvidersQueryKey(SERVICE_ID),
      ok({ service_id: SERVICE_ID, provider_coverage: "ALL_COUNSELORS", counselors: [] })
    );
  });

  assert.match(html, /Fixed-date appointment slots/);
  assert.match(html, /Dr\. Santos/);
});

test("ServiceDetailPage hides fixed slots panels for IT_ADMIN and INSTITUTIONAL_OFFICER and supports non-Head Counselor without services.manage", () => {
  const itAdmin = {
    ...manager,
    id: "admin-1",
    role: "IT_ADMIN",
    capabilities: ["services.catalog.view", "services.manage"],
  };
  const officer = {
    ...manager,
    id: "officer-1",
    role: "INSTITUTIONAL_OFFICER",
    capabilities: ["services.catalog.view"],
  };
  const regularCounselor = {
    ...manager,
    id: "counselor-regular",
    role: "COUNSELOR",
    capabilities: ["services.catalog.view", "appointments.manage"],
  };

  for (const nonSchedulingUser of [itAdmin, officer]) {
    const html = renderWithUser(h(ServiceDetailPage), nonSchedulingUser, (client) => {
      client.setQueryData(getServicesGetQueryKey(SERVICE_ID), ok(service));
    });
    assert.doesNotMatch(html, /Publish slot/);
    assert.doesNotMatch(html, /Available appointment slots/);
  }

  const counselorHtml = renderWithUser(h(ServiceDetailPage), regularCounselor, (client) => {
    client.setQueryData(getServicesGetQueryKey(SERVICE_ID), ok(service));
    client.setQueryData(getServicesListSlotsQueryKey(SERVICE_ID), ok(sampleSlots));
  });
  assert.match(counselorHtml, /Publish slot/);
  assert.match(counselorHtml, /Dr\. Santos/);
});

