import assert from "node:assert/strict";
import { test } from "node:test";

import { CompassApiError } from "../src/lib/api/errors.ts";
import {
  caseSessionNotice,
  pendingReassignmentNotice,
  reassignmentError,
  reassignmentStale,
  reassignmentStateLabel,
} from "../src/features/counseling/reassignment/reassignment-presentation.ts";
import { presentWork } from "../src/features/work-queue/work-queue-presentation.ts";

const apiError = (code, message = "Server message") =>
  Object.assign(Object.create(CompassApiError.prototype), { body: { error: { code, message } } });

test("plain words for state, pending and case-session notices", () => {
  assert.equal(reassignmentStateLabel("PENDING"), "Waiting for Head approval");
  assert.equal(reassignmentStateLabel("EXPIRED"), "No longer current");
  assert.equal(
    pendingReassignmentNotice({ to_provider: { display_name: "Ana Cruz" }, from_provider: { display_name: "Maria Reyes" } }),
    "Reassignment to Ana Cruz is waiting for Head approval. The Appointment stays with Maria Reyes until then.",
  );
  assert.equal(caseSessionNotice("Lea Santos"), "Part of Lea Santos's counseling case. Case records stay with Lea Santos.");
});

test("known refusals map to plain words and stale ones reload the request", () => {
  assert.equal(reassignmentError(apiError("case_continuity_reassignment_pending"), "fallback"), "A reassignment for this Appointment is already waiting for the Head.");
  assert.equal(reassignmentError(apiError("unknown_code", "Raw server text"), "fallback"), "fallback", "raw server text is never shown");
  assert.equal(reassignmentError(new Error("network"), "fallback"), "fallback");
  assert.equal(reassignmentStale(apiError("case_continuity_reassignment_expired")), true);
  assert.equal(reassignmentStale(apiError("case_continuity_reassignment_approval_denied")), false);
});

test("the Head's Work Queue row opens the review page before the session starts", () => {
  const row = presentWork({
    id: "case-reassignment:1", kind: "CASE_REASSIGNMENT_APPROVAL", priority: "TIME_SENSITIVE",
    source_id: "e1", student: { id: "s", display_name: "Maria Santos" }, conversation_kind: null,
    due_at: "2026-10-08T02:00:00Z", waiting_since: "2026-10-07T00:00:00Z", case_reference_code: "CASE-2026-000001",
  });
  assert.equal(row.href, "/portal/counseling/reassignments/e1");
  assert.equal(row.actionLabel, "Review reassignment");
  assert.match(row.title, /^Approve session reassignment · CASE-2026-000001$/);
});
