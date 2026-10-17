import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { ServiceDetailPage } from "../src/features/services/service-detail-page.tsx";
import {
  ServiceGroupSessionsStaffPanel,
  ServiceGroupSessionsStudentPanel,
} from "../src/features/services/service-group-sessions-panel.tsx";
import {
  getGroupSessionsListStaffQueryKey,
  getGroupSessionsDiscoverQueryKey,
  getGroupSessionsGetMetricsQueryKey,
} from "../src/lib/api/generated/group-sessions/group-sessions.ts";
import {
  getServicesGetQueryKey,
  getServicesGetProvidersQueryKey,
} from "../src/lib/api/generated/services/services.ts";
import { UnsavedChangesProvider } from "../src/features/form-safety/unsaved-changes-provider.tsx";

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

const SERVICE_ID = "svc-group-1";
const service = {
  id: SERVICE_ID,
  code: "CAREER_WORKSHOP",
  name: "Career Planning Workshop",
  description: "Workshops and group sessions for students.",
  appointment_booking_enabled: false,
  booking_pathways: ["GROUP_SESSION"],
  default_appointment_duration_minutes: 60,
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

const sampleSessions = [
  {
    id: "gs-1",
    service_id: SERVICE_ID,
    service_name: "Career Planning Workshop",
    title: "Resume & Interview Masterclass",
    description: "Learn resume optimization and technical interview tips.",
    delivery_mode: "IN_PERSON",
    venue_or_meeting_url: "Conference Room B",
    starts_at: "2026-11-10T14:00:00Z",
    ends_at: "2026-11-10T16:00:00Z",
    reg_opens_at: "2026-11-01T00:00:00Z",
    reg_closes_at: "2026-11-10T12:00:00Z",
    capacity: 25,
    active_registrations_count: 10,
    status: "PUBLISHED",
    organizer_id: "counselor-1",
    organizer_name: "Dr. Santos",
    cancellation_reason: "",
    cancelled_at: null,
    version: 1,
    facilitators: [
      {
        id: "fac-1",
        counselor_id: "counselor-1",
        counselor_name: "Dr. Santos",
        is_lead: true,
      },
    ],
    created_at: "2026-10-17T00:00:00Z",
    updated_at: "2026-10-17T00:00:00Z",
  },
];

const sampleMetrics = {
  total_sessions: 5,
  published_sessions: 3,
  completed_sessions: 2,
  cancelled_sessions: 0,
  total_capacity: 100,
  total_registrations: 45,
  cancelled_registrations: 5,
  capacity_utilization_percent: 45,
  attended_count: 38,
  absent_count: 2,
  attendance_rate_percent: 95,
};

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

test("Staff panel renders group sessions, metrics, and management controls", () => {
  const html = renderWithUser(
    h(ServiceGroupSessionsStaffPanel, { service }),
    manager,
    (client) => {
      client.setQueryData(
        getGroupSessionsListStaffQueryKey({ service_id: SERVICE_ID }),
        ok(sampleSessions)
      );
      client.setQueryData(
        getGroupSessionsGetMetricsQueryKey({ service_id: SERVICE_ID }),
        ok(sampleMetrics)
      );
      client.setQueryData(
        getServicesGetProvidersQueryKey(SERVICE_ID),
        ok({ service_id: SERVICE_ID, provider_coverage: "ALL_COUNSELORS", counselors: [] })
      );
    }
  );

  assert.match(html, /Group Sessions &amp; Events/);
  assert.match(html, /Resume &amp; Interview Masterclass/);
  assert.match(html, /Schedule Group Session/);
  assert.match(html, /PUBLISHED/);
  assert.match(html, /Total Sessions/);
  assert.match(html, /95%/);
  assert.match(html, /Roster &amp; Attendance/);
});

test("Student panel renders discoverable group sessions with registration action", () => {
  const discoverableSessions = [
    {
      id: "gs-1",
      service_id: SERVICE_ID,
      service_name: "Career Planning Workshop",
      title: "Resume & Interview Masterclass",
      description: "Learn resume optimization and technical interview tips.",
      delivery_mode: "IN_PERSON",
      venue_or_meeting_url: "Conference Room B",
      starts_at: "2026-11-10T14:00:00Z",
      ends_at: "2026-11-10T16:00:00Z",
      reg_opens_at: "2026-11-01T00:00:00Z",
      reg_closes_at: "2026-11-10T12:00:00Z",
      capacity: 25,
      seats_remaining: 15,
      is_full: false,
      is_registered_by_me: false,
      facilitators: [
        {
          id: "fac-1",
          counselor_id: "counselor-1",
          counselor_name: "Dr. Santos",
          is_lead: true,
        },
      ],
    },
  ];

  const html = renderWithUser(
    h(ServiceGroupSessionsStudentPanel, { service }),
    student,
    (client) => {
      client.setQueryData(
        getGroupSessionsDiscoverQueryKey({ service_id: SERVICE_ID }),
        ok(discoverableSessions)
      );
    }
  );

  assert.match(html, /Upcoming Group Sessions &amp; Workshops/);
  assert.match(html, /Resume &amp; Interview Masterclass/);
  assert.match(html, /15 of 25 seats remaining/);
  assert.match(html, /Register/);
});

test("ServiceDetailPage integrates group sessions staff panel when pathway is configured", () => {
  const html = renderWithUser(h(ServiceDetailPage), manager, (client) => {
    client.setQueryData(getServicesGetQueryKey(SERVICE_ID), ok(service));
    client.setQueryData(
      getGroupSessionsListStaffQueryKey({ service_id: SERVICE_ID }),
      ok(sampleSessions)
    );
    client.setQueryData(
      getGroupSessionsGetMetricsQueryKey({ service_id: SERVICE_ID }),
      ok(sampleMetrics)
    );
    client.setQueryData(
      getServicesGetProvidersQueryKey(SERVICE_ID),
      ok({ service_id: SERVICE_ID, provider_coverage: "ALL_COUNSELORS", counselors: [] })
    );
  });

  assert.match(html, /Group Sessions &amp; Events/);
  assert.match(html, /Resume &amp; Interview Masterclass/);
});
