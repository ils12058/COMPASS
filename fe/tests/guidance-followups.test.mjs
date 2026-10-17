import assert from "node:assert/strict";
import test from "node:test";
import { followupAccess } from "../src/features/guidance-followups/followups-access.ts";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";

import { AttentionPriority, rankAttention } from "../src/features/portal/home/overview-attention-ranking.ts";

test("Follow-Up workspace requires a canonical staff role and its own capability", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_SERVICES_STAFF"]) {
    assert.deepEqual(followupAccess({ role, capabilities: ["guidance_followups.view", "guidance_followups.manage"] }), { view: true, manage: true });
    assert.deepEqual(followupAccess({ role, capabilities: [] }), { view: false, manage: false });
  }
  for (const role of ["STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER", "GSS"]) {
    assert.deepEqual(followupAccess({ role, capabilities: ["guidance_followups.view", "guidance_followups.manage"] }), { view: false, manage: false });
  }
});
test("Follow-Up work uses the queue's confirmed time for overdue language and its own destination", () => {
  const item = { id: "guidance-follow-up:synthetic", kind: "GUIDANCE_FOLLOW_UP", source_id: "synthetic", due_at: "2026-10-01T00:00:00Z" };
  assert.match(presentWork(item, "2026-10-17T00:00:00Z").detail, /^Overdue/);
  assert.doesNotMatch(presentWork(item, "2026-09-17T00:00:00Z").detail, /^Overdue/);
  assert.equal(presentWork(item).href, "/portal/follow-ups/synthetic");
  assert.deepEqual(notificationDestination({ target_type: "GUIDANCE_FOLLOW_UP", target_id: "synthetic" }, "staff"), { href: "/portal/follow-ups/synthetic", label: "Open follow-up" });
});
test("Work queue ranking preserves priority class and does not let non-urgent due dates jump the queue", () => {
  const timeSensitive = { id: "urgent", rank: { priority: AttentionPriority.TIME_SENSITIVE, dueAt: "2026-10-18T00:00:00Z", waitingSince: "2026-10-16T00:00:00Z", stableKey: "urgent" } };
  const olderWaiting = { id: "older-action", rank: { priority: AttentionPriority.ACTION_REQUIRED, dueAt: null, waitingSince: "2026-10-10T00:00:00Z", stableKey: "older-action" } };
  const futureFollowup = { id: "future-followup", rank: { priority: AttentionPriority.ACTION_REQUIRED, dueAt: null, waitingSince: "2026-10-15T00:00:00Z", stableKey: "future-followup" } };

  const ranked = rankAttention([futureFollowup, olderWaiting, timeSensitive]);
  assert.deepEqual(ranked.map(i => i.id), ["urgent", "older-action", "future-followup"]);
});
