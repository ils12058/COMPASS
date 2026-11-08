import assert from "node:assert/strict";
import test from "node:test";
import { followupAccess } from "../src/features/guidance-followups/followups-access.ts";
import { nextFollowupHref } from "../src/features/guidance-followups/followups-shared.tsx";
import { notificationDestination } from "../src/features/notifications/notification-targets.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";

import { AttentionPriority, rankAttention } from "../src/features/portal/home/overview-attention-ranking.ts";

test("Follow-Up workspace requires a canonical staff role and its own capability", () => {
  for (const role of ["COUNSELOR", "GUIDANCE_OFFICE_ASSISTANT"]) {
    assert.deepEqual(followupAccess({ role, capabilities: ["guidance_followups.view", "guidance_followups.manage"] }), { view: true, manage: true });
    assert.deepEqual(followupAccess({ role, capabilities: [] }), { view: false, manage: false });
  }
  for (const role of ["STUDENT", "IT_ADMIN", "INSTITUTIONAL_OFFICER", "GOA"]) {
    assert.deepEqual(followupAccess({ role, capabilities: ["guidance_followups.view", "guidance_followups.manage"] }), { view: false, manage: false });
  }
});
test("Create next follow-up links only the readable source or the standalone Student identity", () => {
  const studentId = "22222222-2222-4222-8222-222222222222";
  const studentName = "Synthetic Student & Co.";
  const sourceId = "33333333-3333-4333-8333-333333333333";
  const sourceHref = nextFollowupHref({ student_id: studentId, student_name: studentName, source: { kind: "REFERRAL", id: sourceId } });
  assert.equal(sourceHref, `/portal/follow-ups/new?source_kind=REFERRAL&source_id=${encodeURIComponent(sourceId)}`);
  assert.deepEqual([...new URLSearchParams(sourceHref.split("?")[1]).keys()], ["source_kind", "source_id"]);

  for (const item of [
    { student_id: studentId, student_name: studentName, source: null },
    { student_id: studentId, student_name: studentName, source: null, source_unavailable: true },
  ]) {
    const href = nextFollowupHref(item);
    assert.equal(href, `/portal/follow-ups/new?student_id=${encodeURIComponent(studentId)}&student_name=${encodeURIComponent(studentName)}`);
    assert.deepEqual([...new URLSearchParams(href.split("?")[1]).keys()], ["student_id", "student_name"]);
  }

  const encoded = nextFollowupHref({ student_id: studentId, student_name: "A/B? C&D#E", source: { kind: "REFERRAL", id: "source/../&id" } });
  for (const forbidden of ["category", "visibility", "assigned_to_id", "due_at", "description", "outcome", "status", "version", "predecessor", "successor"]) {
    assert.equal(new URLSearchParams(encoded.split("?")[1]).has(forbidden), false, `${forbidden} is never copied into the create link`);
  }
  assert.equal(new URLSearchParams(encoded.split("?")[1]).get("source_id"), "source/../&id");
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
