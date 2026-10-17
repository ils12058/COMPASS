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
    can_view: true,
    can_manage: true,
    can_access_participants: true,
    can_record_attendance: true,
    can_export_roster: true,
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

test("Staff panel offers draft withdrawal instead of deletion", () => {
  const draft = {
    ...sampleSessions[0],
    status: "DRAFT",
    can_manage: true,
    can_access_participants: false,
  };
  const html = renderWithUser(
    h(ServiceGroupSessionsStaffPanel, { service }),
    manager,
    (client) => {
      client.setQueryData(
        getGroupSessionsListStaffQueryKey({ service_id: SERVICE_ID }),
        ok([draft])
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

  assert.match(html, /Withdraw/);
  assert.doesNotMatch(html, /Delete Draft/);
});

test("Facilitator session controls follow resource capabilities", () => {
  const facilitator = {
    ...manager,
    capabilities: ["appointments.manage"],
  };
  const assignedDraft = {
    ...sampleSessions[0],
    status: "DRAFT",
    can_manage: false,
    can_access_participants: true,
    can_record_attendance: true,
    can_export_roster: false,
  };
  const html = renderWithUser(
    h(ServiceGroupSessionsStaffPanel, { service }),
    facilitator,
    (client) => {
      client.setQueryData(
        getGroupSessionsListStaffQueryKey({ service_id: SERVICE_ID }),
        ok([assignedDraft])
      );
      client.setQueryData(
        getGroupSessionsGetMetricsQueryKey({ service_id: SERVICE_ID }),
        ok(sampleMetrics)
      );
    }
  );

  assert.match(html, /Roster &amp; Attendance/);
  assert.doesNotMatch(html, /Publish Draft/);
  assert.doesNotMatch(html, /Withdraw/);
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

import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { NotificationTargetType } from "../src/lib/api/generated/model/index.ts";

test("ServiceDetailPage hides group session panels for IT_ADMIN and INSTITUTIONAL_OFFICER and maps GROUP_SESSION notifications", () => {
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

  for (const nonSchedulingUser of [itAdmin, officer]) {
    const html = renderWithUser(h(ServiceDetailPage), nonSchedulingUser, (client) => {
      client.setQueryData(getServicesGetQueryKey(SERVICE_ID), ok(service));
    });
    assert.doesNotMatch(html, /Schedule Group Session/);
    assert.doesNotMatch(html, /Upcoming Group Sessions &amp; Workshops/);
  }

  const dest = notificationDestination(
    {
      id: "notif-gs-1",
      event_code: "group_session.registered",
      title: "Group Session Registration Confirmed",
      body: "Confirmed",
      target_type: NotificationTargetType.GROUP_SESSION,
      target_id: "gs-1",
      is_read: false,
      read_at: null,
      created_at: "2026-10-17T00:00:00Z",
    },
    "student-1"
  );
  assert.deepEqual(dest, { href: "/portal/services", label: "Open Services" });
});

