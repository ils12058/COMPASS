import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createNotificationHeadsUpState,
  dismissNotificationHeadsUp,
  MAX_KNOWN_NOTIFICATION_IDS,
  reconcileNotificationHeadsUp,
  shouldPresentNotificationHeadsUp,
} from "../src/features/notifications/notification-heads-up-state.ts";

test("initial canonical notifications establish a baseline without a heads-up", () => {
  const initial = createNotificationHeadsUpState();
  const next = reconcileNotificationHeadsUp(initial, ["old-unread", "old-read"], true);

  assert.equal(next.baselineEstablished, true);
  assert.equal(next.notice, null);
  assert.deepEqual([...next.knownIds], ["old-unread", "old-read"]);
});

test("a new ID creates one notice and repeated refetches do not duplicate it", () => {
  const baseline = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["existing"], true);
  const fresh = reconcileNotificationHeadsUp(baseline, ["new", "existing"], true);
  const repeated = reconcileNotificationHeadsUp(fresh, ["new", "existing"], true);

  assert.deepEqual(fresh.notice, { key: 1, count: 1 });
  assert.equal(repeated.notice, fresh.notice);
});

test("read-state-only refetches and dismissal do not create another notice", () => {
  const baseline = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["same-id"], true);
  const afterReadStateChange = reconcileNotificationHeadsUp(baseline, ["same-id"], true);
  assert.equal(afterReadStateChange.notice, null);

  const shown = reconcileNotificationHeadsUp(afterReadStateChange, ["same-id", "new-id"], true);
  const dismissed = dismissNotificationHeadsUp(shown);
  const repeated = reconcileNotificationHeadsUp(dismissed, ["new-id", "same-id"], true);
  assert.equal(repeated.notice, null);
  assert.equal(repeated.knownIds.has("new-id"), true);
});

test("muting suppresses current and muted arrivals while future unmuted arrivals still show", () => {
  const baseline = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["old"], true);
  const whileMuted = reconcileNotificationHeadsUp(baseline, ["old", "muted"], false);
  const afterUnmute = reconcileNotificationHeadsUp(whileMuted, ["old", "muted", "future"], true);

  assert.equal(whileMuted.notice, null);
  assert.deepEqual(afterUnmute.notice, { key: 1, count: 1 });
});

test("active calls, hidden tabs, and blocking dialogs suppress new notices", () => {
  for (const options of [
    { muted: false, activeCall: true, visible: true, blockingDialogOpen: false },
    { muted: false, activeCall: false, visible: false, blockingDialogOpen: false },
    { muted: false, activeCall: false, visible: true, blockingDialogOpen: true },
  ]) {
    assert.equal(shouldPresentNotificationHeadsUp(options), false);
  }
  assert.equal(
    shouldPresentNotificationHeadsUp({
      muted: false,
      activeCall: false,
      visible: true,
      blockingDialogOpen: false,
    }),
    true,
  );
});

test("a burst is represented by one aggregate notice and known IDs stay bounded", () => {
  const baseline = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["old"], true);
  const ids = Array.from({ length: 12 }, (_, index) => `new-${index}`);
  const burst = reconcileNotificationHeadsUp(baseline, ids, true);
  assert.deepEqual(burst.notice, { key: 1, count: 12 });

  const many = Array.from({ length: MAX_KNOWN_NOTIFICATION_IDS + 50 }, (_, index) => `id-${index}`);
  const bounded = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), many, true);
  assert.equal(bounded.knownIds.size, MAX_KNOWN_NOTIFICATION_IDS);
  assert.equal(bounded.notice, null);
});

test("a fresh detector starts isolated for a new authenticated account", () => {
  const firstAccount = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["first"], true);
  const secondAccount = reconcileNotificationHeadsUp(createNotificationHeadsUpState(), ["second"], true);

  assert.equal(firstAccount.knownIds.has("second"), false);
  assert.equal(secondAccount.knownIds.has("first"), false);
  assert.equal(secondAccount.notice, null);
});
