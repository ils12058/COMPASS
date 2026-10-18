import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { withNextRouter } from "./support/next-router.mjs";
import { PortalSessionProvider } from "../src/features/portal/components/portal-session.tsx";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { ServiceDetailPage } from "../src/features/services/service-detail-page.tsx";
import {
  ServiceGroupSessionsStaffPanel,
  ServiceGroupSessionsStudentPanel,
} from "../src/features/services/service-group-sessions-panel.tsx";
import { GroupSessionsStaffPage } from "../src/features/group-sessions/group-sessions-staff-page.tsx";
import { GroupSessionsNavigation } from "../src/features/group-sessions/group-sessions-shared.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { GroupSessionsDiscoveryPage } from "../src/features/group-sessions/group-sessions-discovery-page.tsx";
import { GroupSessionDetailPage } from "../src/features/group-sessions/group-session-detail-page.tsx";
import { GroupSessionsHistoryPage } from "../src/features/group-sessions/group-sessions-history-page.tsx";
import {
  getGroupSessionsListStaffQueryKey,
  getGroupSessionsDiscoverQueryKey,
  getGroupSessionsGetMetricsQueryKey,
  getGroupSessionsGetDetailQueryKey,
  getGroupSessionsGetMyRegistrationsQueryKey,
} from "../src/lib/api/generated/group-sessions/group-sessions.ts";
import { getServicesGetQueryKey } from "../src/lib/api/generated/services/services.ts";
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
  capabilities: ["appointments.view_self", "appointments.manage_self"],
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
    schedule_revision: 1,
    facilitators: [
      {
        id: "fac-1",
        kind: "INTERNAL",
        internal_user_id: "counselor-1",
        external_display_name: "",
        display_name: "Dr. Santos",
        is_current: true,
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

function renderWithUser(element, user, seed = () => {}, pathname = "/") {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, retryOnMount: false, staleTime: Infinity, gcTime: Infinity },
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
      { params: { serviceId: SERVICE_ID }, pathname }
    )
  );
}

test("Staff panel renders group sessions, metrics, and management controls", () => {
  const sessionsWithHistory = [
    {
      ...sampleSessions[0],
      facilitators: [
        ...sampleSessions[0].facilitators,
        {
          id: "fac-former",
          kind: "INTERNAL",
          internal_user_id: "former-counselor",
          external_display_name: "",
          display_name: "Former Counselor",
          is_current: false,
          counselor_id: "former-counselor",
          counselor_name: "Former Counselor",
          is_lead: false,
        },
      ],
    },
  ];
  const html = renderWithUser(
    h(ServiceGroupSessionsStaffPanel, { service }),
    manager,
    (client) => {
      client.setQueryData(
        getGroupSessionsListStaffQueryKey({ service_id: SERVICE_ID }),
        ok(sessionsWithHistory)
      );
      client.setQueryData(
        getGroupSessionsGetMetricsQueryKey({ service_id: SERVICE_ID }),
        ok(sampleMetrics)
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
  assert.match(html, /Former facilitators: Former Counselor/);
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
      can_register: true,
      registration_block_reason: null,
      facilitators: [
        {
          id: "fac-1",
          kind: "INTERNAL",
          internal_user_id: "counselor-1",
          external_display_name: "",
          display_name: "Dr. Santos",
          is_current: true,
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

test("Student Group Session discovery is available outside the staff-only Services workspace", () => {
  const studentWithSchedulingView = {
    ...student,
    capabilities: ["appointments.view_self"],
  };
  const html = renderWithUser(
    h(GroupSessionsDiscoveryPage),
    studentWithSchedulingView,
    (client) => {
      client.setQueryData(getGroupSessionsDiscoverQueryKey(), ok(sampleSessions));
    }
  );

  assert.match(html, /Group Sessions &amp; Workshops/);
  assert.match(html, /Resume &amp; Interview Masterclass/);
  assert.match(html, /My Registrations/);
  assert.doesNotMatch(html, /Services unavailable/);
});

test("Group Session discovery stays unavailable outside Student scheduling scope", () => {
  const html = renderWithUser(
    h(GroupSessionsDiscoveryPage),
    { ...student, role: "IT_ADMIN", capabilities: ["appointments.view_self"] }
  );

  assert.match(html, /Group Sessions unavailable/);
  assert.doesNotMatch(html, /Upcoming Group Sessions/);
});

test("Student registration action follows server-derived overlap eligibility", () => {
  const unavailable = {
    ...sampleSessions[0],
    seats_remaining: 10,
    is_full: false,
    is_registered_by_me: false,
    can_register: false,
    registration_block_reason: "This session overlaps another Appointment or registered Group Session.",
  };
  const html = renderWithUser(
    h(ServiceGroupSessionsStudentPanel, { service }),
    student,
    (client) => {
      client.setQueryData(
        getGroupSessionsDiscoverQueryKey({ service_id: SERVICE_ID }),
        ok([unavailable])
      );
    }
  );

  assert.match(html, /Registration unavailable/);
  assert.match(html, /overlaps another Appointment or registered Group Session/);
  assert.doesNotMatch(html, />Register<\/button>/);
});

test("Student history and direct event details remain reachable outside the Service page", () => {
  const registration = {
    id: "registration-1",
    session_id: "gs-1",
    session_title: "Resume & Interview Masterclass",
    service_id: SERVICE_ID,
    starts_at: "2026-11-10T14:00:00Z",
    ends_at: "2026-11-10T16:00:00Z",
    student_id: "student-1",
    student_name: "Student User",
    student_email: "student@example.test",
    status: "CANCELLED",
    registered_at: "2026-10-17T00:00:00Z",
    cancelled_at: "2026-10-18T00:00:00Z",
    cancellation_reason: "Facilitator illness",
    attended: null,
    attendance_notes: null,
  };
  const history = renderWithUser(h(GroupSessionsHistoryPage), student, (client) => {
    client.setQueryData(getGroupSessionsGetMyRegistrationsQueryKey(), ok([registration]));
  });
  assert.match(history, /My Registrations/);
  assert.match(history, /Cancelled/);
  assert.match(history, /Facilitator illness/);
  assert.match(history, /href="\/portal\/group-sessions\/gs-1"/);

  const detailSession = {
    ...sampleSessions[0],
    status: "CANCELLED",
    cancellation_reason: "Facilitator illness",
    venue_or_meeting_url: "",
    facilitators: [
      {
        id: "fac-external",
        kind: "EXTERNAL",
        internal_user_id: null,
        external_display_name: "Community Speaker",
        display_name: "Community Speaker",
        is_current: true,
        is_lead: true,
        counselor_id: null,
        counselor_name: null,
      },
      {
        id: "fac-former",
        kind: "INTERNAL",
        internal_user_id: "former-counselor",
        external_display_name: "",
        display_name: "Former Counselor",
        is_current: false,
        is_lead: false,
        counselor_id: "former-counselor",
        counselor_name: "Former Counselor",
      },
    ],
  };
  const detail = renderWithUser(
    h(GroupSessionDetailPage, { sessionId: "gs-1" }),
    student,
    (client) => {
      client.setQueryData(getGroupSessionsGetDetailQueryKey("gs-1"), ok(detailSession));
    }
  );
  assert.match(detail, /Community Speaker/);
  assert.match(detail, /Guest speaker/);
  assert.match(detail, /Former Counselor/);
  assert.match(detail, /Former facilitator/);
  assert.match(detail, /Facilitator illness/);
  assert.doesNotMatch(detail, /secret-group-room/);
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
      is_current: true,
      is_read: false,
      read_at: null,
      created_at: "2026-10-17T00:00:00Z",
    },
    "student-1"
  );
  assert.deepEqual(dest, {
    href: "/portal/group-sessions/gs-1",
    label: "Open Group Session",
  });

  const staleDest = notificationDestination(
    {
      target_type: NotificationTargetType.GROUP_SESSION,
      target_id: "gs-1",
      is_current: false,
    },
    "student-1"
  );
  assert.deepEqual(staleDest, {
    href: "/portal/group-sessions/gs-1",
    label: "Review current event",
  });

  const noTargetDest = notificationDestination(
    { target_type: NotificationTargetType.GROUP_SESSION, target_id: null },
    "student-1"
  );
  assert.deepEqual(noTargetDest, {
    href: "/portal/group-sessions/my",
    label: "My group sessions",
  });

  const studentWithSchedulingView = {
    ...student,
    capabilities: ["appointments.view_self", "appointments.manage_self"],
  };
  const studentLinks = portalWorkspaceGroups(studentWithSchedulingView)
    .flatMap((group) => group.links)
    .map((link) => link.href);
  assert.equal(studentLinks.filter((href) => href.startsWith("/portal/group-sessions")).length, 1);
  assert.ok(studentLinks.includes("/portal/group-sessions"));
  assert.ok(!portalWorkspaceGroups(manager).some((group) =>
    group.links.some((link) => link.href === "/portal/group-sessions/my")
  ));
});



test("one Group Sessions sidebar entry follows scheduling role and capability, independently of Services management", () => {
  for (const role of ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF", "IT_ADMIN", "INSTITUTIONAL_OFFICER"]) {
    const account = { ...manager, role, capabilities: ["appointments.manage", "appointments.view_self"] };
    const entries = portalWorkspaceGroups(account).flatMap(group => group.links).filter(link => link.href.startsWith("/portal/group-sessions"));
    assert.equal(entries.length, ["STUDENT", "COUNSELOR", "GUIDANCE_SERVICES_STAFF"].includes(role) ? 1 : 0);
    if (entries.length) assert.equal(entries[0].href, "/portal/group-sessions");
  }
  assert.equal(portalWorkspaceGroups({ ...manager, capabilities: ["services.manage"] }).flatMap(group => group.links).some(link => link.href === "/portal/group-sessions"), false);
});

test("Student and staff workspace tabs mark the current route", () => {
  const html = renderWithUser(h(GroupSessionsNavigation), student, () => {}, "/portal/group-sessions/my");
  assert.match(html, /aria-current="page"[^>]*href="\/portal\/group-sessions\/my"/);
  assert.match(html, /Browse Sessions/);
  assert.match(html, /My Registrations/);
  const staff = renderWithUser(h(GroupSessionsNavigation), manager, () => {}, "/portal/group-sessions/attendance");
  assert.match(staff, /aria-current="page"[^>]*href="\/portal\/group-sessions\/attendance"/);
  assert.match(staff, /Manage Sessions/);
  assert.doesNotMatch(staff, /Browse Sessions/);
});

test("centralized management reuses scoped session projections without Services management", () => {
  const html = renderWithUser(h(GroupSessionsStaffPage), { ...manager, capabilities: ["appointments.manage", "services.catalog.view"] }, client => {
    client.setQueryData(getGroupSessionsListStaffQueryKey(), ok(sampleSessions));
    client.setQueryData(getGroupSessionsGetMetricsQueryKey(), ok(sampleMetrics));
  });
  assert.match(html, /Resume &amp; Interview Masterclass/);
  assert.match(html, /Schedule Group Session/);
  assert.match(html, /Help: Group Sessions/);
  assert.doesNotMatch(html, /Services unavailable/);
});

test("attendance entry shows only participant-authorized summaries and no lifecycle controls", () => {
  const html = renderWithUser(h(GroupSessionsStaffPage, { attendance: true }), manager, client => {
    client.setQueryData(getGroupSessionsListStaffQueryKey(), ok([sampleSessions[0], { ...sampleSessions[0], id: "hidden", title: "No participant authority", can_access_participants: false }]));
    client.setQueryData(getGroupSessionsGetMetricsQueryKey(), ok(sampleMetrics));
  });
  assert.match(html, /Roster &amp; Attendance/);
  assert.doesNotMatch(html, /No participant authority|Schedule Group Session|>Edit<|>Cancel<|>Publish</);
  const denied = renderWithUser(h(GroupSessionsStaffPage), { ...manager, role: "IT_ADMIN" });
  assert.match(denied, /Group Sessions unavailable/);
  assert.doesNotMatch(denied, /Participant Roster|Manage Sessions/);
});

test("discovery failures never become empty sessions, and distinguish access denial", () => {
  for (const status of [403, 500, 503]) {
    const html = renderWithUser(h(ServiceGroupSessionsStudentPanel), student, client => {
      client.getQueryCache().build(client, { queryKey: getGroupSessionsDiscoverQueryKey() }).setState({ status: "error", fetchStatus: "idle", error: new CompassApiError({ status, body: { error: { code: "test_error", message: "Internal details" } }, headers: {}, method: "GET", url: "/api/v1/group-sessions/discover" }) });
    });
    assert.match(html, /role="alert"/);
    assert.match(html, /Retry/);
    assert.doesNotMatch(html, /No upcoming group sessions|Internal details/);
    if (status === 403) assert.match(html, /access to this Group Sessions view/);
  }
});
