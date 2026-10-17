import assert from "node:assert/strict";
import { test } from "node:test";

import { QueryClient } from "@tanstack/react-query";

import {
  getNotificationsListMineQueryKey,
} from "../src/lib/api/generated/notifications/notifications.ts";
import {
  cacheConfirmedAllRead,
  cacheConfirmedRead,
} from "../src/features/notifications/notification-cache.ts";

const params = { page: 1, page_size: 20 };
const keyFor = (accountId) => [...getNotificationsListMineQueryKey(params), accountId];
const item = (id, is_read = false) => ({
  id,
  event_code: "appointment.scheduled",
  policy: "MANDATORY_OPERATIONAL",
  title: "Appointment Scheduled",
  message: "Sign in to review details.",
  target_type: null,
  target_id: null,
  created_at: "2026-10-17T00:00:00Z",
  read_at: is_read ? "2026-10-17T01:00:00Z" : null,
  is_read,
});

test("notification read-state cache updates stay within the authenticated account", () => {
  const client = new QueryClient();
  client.setQueryData(keyFor("account-a"), { data: { items: [item("notice-a")] } });
  client.setQueryData(keyFor("account-b"), { data: { items: [item("notice-b")] } });

  cacheConfirmedRead(client, item("notice-a", true), "account-a");
  assert.equal(client.getQueryData(keyFor("account-a")).data.items[0].is_read, true);
  assert.equal(client.getQueryData(keyFor("account-b")).data.items[0].is_read, false);

  cacheConfirmedAllRead(client, "account-a");
  assert.equal(client.getQueryData(keyFor("account-a")).data.items[0].is_read, true);
  assert.equal(client.getQueryData(keyFor("account-b")).data.items[0].is_read, false);
  client.clear();
});
