import assert from "node:assert/strict";
import { test } from "node:test";

import { callSlipStateLabel } from "../src/features/call-slips/call-slips-shared.tsx";
import { publicationStatusLabels } from "../src/features/content/content-presentation.ts";
import { getCounselingAccess } from "../src/features/counseling/counseling-access.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { getGoaHomeDestinations } from "../src/features/portal/home/goa-home-presentation.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";
import { messagesAccount } from "./support/guidance-messages-fixtures.mjs";

test("GOA is excluded from counseling continuity access, navigation, and home destinations", () => {
  const goa = messagesAccount("GUIDANCE_OFFICE_ASSISTANT", {
    capabilities: [
      "counseling.continuity.view",
      "counseling.continuity.request",
      "appointments.manage",
      "call_slips.view",
      "call_slips.manage",
      "announcements.manage",
      "resources.manage",
    ],
  });
  const access = getCounselingAccess(goa);
  assert.equal(access.canViewCoverage, false);
  assert.equal(access.hasWorkspace, false);

  const navHrefs = portalWorkspaceGroups(goa).flatMap((group) => group.links.map((link) => link.href));
  assert.equal(navHrefs.some((href) => href.includes("continuity") || href.includes("coverage")), false);

  const goaHomeHrefs = getGoaHomeDestinations(goa).map((item) => item.href);
  assert.equal(goaHomeHrefs.some((href) => href.includes("continuity") || href.includes("coverage")), false);
});

test("work queue approval items use plain-language titles and source routes", () => {
  const callSlip = presentWork({
    kind: "CALL_SLIP_APPROVAL",
    source_id: "cs-1",
    due_at: "2026-10-10T02:00:00Z",
    waiting_since: "2026-10-09T02:00:00Z",
  });
  assert.equal(callSlip.title, "Approve Call Slip");
  assert.equal(callSlip.href, "/portal/call-slips/cs-1");

  const announcement = presentWork({
    kind: "ANNOUNCEMENT_APPROVAL",
    source_id: "ann-1",
    due_at: null,
    waiting_since: "2026-10-09T02:00:00Z",
  });
  assert.equal(announcement.title, "Approve Announcement");
  assert.equal(announcement.href, "/portal/announcements/ann-1");

  const resource = presentWork({
    kind: "RESOURCE_APPROVAL",
    source_id: "res-1",
    due_at: null,
    waiting_since: "2026-10-09T02:00:00Z",
  });
  assert.equal(resource.title, "Approve Resource");
  assert.equal(resource.href, "/portal/resources/res-1");
});

test("Call Slip and publication approval statuses use plain-language labels", () => {
  assert.equal(callSlipStateLabel("PENDING_APPROVAL"), "Waiting for approval");
  assert.equal(callSlipStateLabel("RETURNED"), "Returned for changes");
  assert.equal(publicationStatusLabels.PENDING_APPROVAL, "Waiting for approval");
  assert.doesNotMatch(callSlipStateLabel("PENDING_APPROVAL"), /PENDING_APPROVAL/);
  assert.doesNotMatch(publicationStatusLabels.PENDING_APPROVAL, /PENDING_APPROVAL/);
});

test("notification targets route announcement and resource approval notices to management pages", () => {
  assert.deepEqual(
    notificationDestination(
      {
        target_type: "ANNOUNCEMENT",
        target_id: "12345678-1234-4234-8234-123456789abc",
      },
      "user-1",
    ),
    {
      href: "/portal/announcements/12345678-1234-4234-8234-123456789abc",
      label: "Open Announcement",
    },
  );
  assert.deepEqual(
    notificationDestination(
      {
        target_type: "RESOURCE",
        target_id: "12345678-1234-4234-8234-123456789abc",
      },
      "user-1",
    ),
    {
      href: "/portal/resources/12345678-1234-4234-8234-123456789abc",
      label: "Open Resource",
    },
  );
});
