import assert from "node:assert/strict";
import { test } from "node:test";

import {
  NOTIFICATION_HEADS_UP_PREFERENCE_PREFIX,
  notificationHeadsUpPreferenceStorageKey,
  parseNotificationHeadsUpPreference,
} from "../src/features/notifications/notification-heads-up-preference.ts";

test("pop-up alerts default to enabled unless this account explicitly turned them off", () => {
  assert.equal(parseNotificationHeadsUpPreference(null), true);
  assert.equal(parseNotificationHeadsUpPreference("true"), true);
  assert.equal(parseNotificationHeadsUpPreference("invalid"), true);
  assert.equal(parseNotificationHeadsUpPreference("false"), false);
});

test("browser preference keys are distinct and account scoped", () => {
  assert.equal(notificationHeadsUpPreferenceStorageKey("account A"), `${NOTIFICATION_HEADS_UP_PREFERENCE_PREFIX}account%20A`);
  assert.notEqual(notificationHeadsUpPreferenceStorageKey("account-A"), notificationHeadsUpPreferenceStorageKey("account-B"));
});
