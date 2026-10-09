// Guidance Messages presentation, send idempotency, history joining, freshness and account safety
// (ADR-102). Pure modules and the app's own QueryClient; no browser, socket, or backend.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { MutationObserver } from "@tanstack/react-query";

import { getGuidanceMessagesAccess } from "../src/features/guidance-messages/guidance-messages-access.ts";
import {
  appendConfirmedMessage,
  cacheConfirmedRead,
  directoryRows,
  guidanceConversationQueryKey,
  guidanceDirectoryQueryKey,
  guidanceThreadQueryKey,
  mergeNewestPage,
  mergeOlderPage,
} from "../src/features/guidance-messages/guidance-messages-cache.ts";
import { describeSendError, describeStatusChangeError } from "../src/features/guidance-messages/guidance-messages-errors.ts";
import {
  changedThreadId,
  MESSAGES_FALLBACK_REFRESH_MS,
  MESSAGES_LIVE_SAFETY_REFRESH_MS,
  reconcileGuidanceMessages,
  startGuidanceMessagesFreshness,
} from "../src/features/guidance-messages/guidance-messages-freshness.ts";
import {
  threadRoutingFacts,
  threadStatusLabel,
  threadSubtitle,
  threadTitle,
  unreadLabel,
} from "../src/features/guidance-messages/guidance-messages-presentation.ts";
import {
  IDLE_SEND,
  isUncertainSendFailure,
  messageBodyProblem,
  messageLength,
  nextSendIntent,
} from "../src/features/guidance-messages/guidance-message-send.ts";
import { messageDayLabel, threadActivityTime } from "../src/features/guidance-messages/guidance-message-time.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { parseServerFrame } from "../src/features/realtime/realtime-protocol.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";
import { AccountChangedError } from "../src/lib/query/account-ownership.ts";
import { createQueryClient } from "../src/lib/query/query-client.ts";

const THREAD = "a0000000-0000-4000-8000-000000000001";
const person = (id, display_name) => ({ id, display_name });
const account = (role, capabilities, extra = {}) => ({
  id: `${role.toLowerCase()}-1`, role, first_name: "Example", last_name: "User", email: "user@example.test",
  student_lifecycle_status: role === "STUDENT" ? "CURRENT" : null, designations: [], capabilities, ...extra,
});
const student = account("STUDENT", ["guidance_messages.view_self", "guidance_messages.manage_self"]);
const counselor = account("COUNSELOR", ["guidance_messages.view", "guidance_messages.manage"]);
const thread = (overrides = {}) => ({
  id: THREAD, kind: "OFFICE", status: "OPEN",
  student: person("student", "Maria Santos"), counselor: null,
  routing_college: { id: "college", code: "CCMS", name: "College of Computing" },
  assigned_to: person("staff", "Lea Ramos"), relationship_appointment_id: null,
  created_at: "2026-10-09T01:00:00Z", last_message_at: "2026-10-09T02:00:00Z",
  last_sequence: 3, own_last_read_sequence: 1, unread_count: 2, ...overrides,
});
const message = (sequence, sender = person("staff", "Lea Ramos")) => ({
  id: `m${sequence}`, sequence, sender, body: `Body ${sequence}`, created_at: "2026-10-09T02:00:00Z",
});
const page = (sequences, has_older) => ({ items: sequences.map((sequence) => message(sequence)), has_older });
const sequences = (history) => history.messages.map((item) => item.sequence);
const apiError = (status, code = "synthetic") => new CompassApiError({ status, body: { error: { code, message: "x" } }, headers: {}, method: "POST", url: "/api/v1/x" });

// ── Access and navigation ─────────────────────────────────────────────────────────────────────

test("Messages access pairs each identity with its own capability", () => {
  assert.deepEqual(
    { ...getGuidanceMessagesAccess(student) },
    { isStudent: true, isStaff: false, canViewSelf: true, canManageSelf: true, canViewStaff: false, canManageStaff: false, hasWorkspace: true, canWrite: true },
  );
  assert.equal(getGuidanceMessagesAccess(counselor).canManageStaff, true);
  assert.equal(getGuidanceMessagesAccess(account("GUIDANCE_SERVICES_STAFF", ["guidance_messages.view"])).canWrite, false, "View without manage reads only");
  assert.equal(getGuidanceMessagesAccess(account("STUDENT", ["guidance_messages.view"])).hasWorkspace, false, "A Student needs view_self");
  assert.equal(getGuidanceMessagesAccess(account("COUNSELOR", ["guidance_messages.view_self"])).hasWorkspace, false, "Staff need view");
  for (const other of [
    account("IT_ADMIN", ["accounts.manage", "platform_operations.view"]),
    account("IT_ADMIN", ["privacy.governance.view"], { designations: ["DPO"] }),
    account("INSTITUTIONAL_OFFICER", ["reports.view"]),
    account("COUNSELOR", ["appointments.manage"], { designations: ["HEAD_GUIDANCE_COUNSELOR"] }),
  ]) {
    assert.equal(getGuidanceMessagesAccess(other).hasWorkspace, false, `${other.role} ${other.designations} has no Messages`);
    assert.ok(!portalWorkspaceGroups(other).some((group) => group.links.some((link) => link.href === "/portal/messages")));
  }
});

test("Messages is a daily workspace placed before administration", () => {
  const labels = (user) => portalWorkspaceGroups(user).map((group) => group.label);
  const groups = portalWorkspaceGroups({ ...counselor, capabilities: [...counselor.capabilities, "organization.manage", "accounts.manage"] });
  const order = groups.map((group) => group.label);
  assert.ok(order.indexOf("Communication") < order.indexOf("Institution"));
  assert.ok(order.indexOf("Communication") < order.indexOf("Identity & Access"));
  assert.deepEqual(groups.find((group) => group.label === "Communication").links.map((link) => link.href), ["/portal/messages"]);
  assert.ok(labels(student).includes("Communication"));
  const commands = (user) => portalCommandDestinations(user).map((destination) => destination.href);
  assert.ok(commands(student).includes("/portal/messages/new"));
  assert.ok(!commands(account("GUIDANCE_SERVICES_STAFF", ["guidance_messages.view"])).includes("/portal/messages/new"));
  assert.ok(commands(account("GUIDANCE_SERVICES_STAFF", ["guidance_messages.view"])).includes("/portal/messages"));
});

// ── Presentation ──────────────────────────────────────────────────────────────────────────────

test("conversation labels use human wording from each reader's side", () => {
  const office = thread();
  const counseling = thread({ kind: "COUNSELING", counselor: person("counselor", "Ana Cruz"), routing_college: null, assigned_to: null });
  assert.equal(threadTitle(office, "student"), "Guidance Office");
  assert.equal(threadSubtitle(office, "student"), null);
  assert.equal(threadTitle(counseling, "student"), "Ana Cruz");
  assert.equal(threadSubtitle(counseling, "student"), "Counseling");
  assert.equal(threadTitle(office, "staff"), "Maria Santos");
  assert.equal(threadSubtitle(office, "staff"), "Guidance Office");
  assert.equal(threadTitle(counseling, "staff"), "Maria Santos");
  assert.equal(threadSubtitle(counseling, "staff"), "Counseling");
  assert.deepEqual(threadRoutingFacts(office, "staff"), { college: "College of Computing", assignedTo: "Lea Ramos" });
  assert.deepEqual(threadRoutingFacts(office, "student"), { college: null, assignedTo: null });
  assert.deepEqual(threadRoutingFacts(counseling, "staff"), { college: null, assignedTo: null });
  assert.equal(threadStatusLabel("RESOLVED"), "Resolved");
  assert.equal(unreadLabel(0), null);
  assert.equal(unreadLabel(2), "2 unread");
  assert.equal(threadTitle(thread({ student: person("s", "  ") }), "staff"), "Student");
});

test("times follow the institution's calendar", () => {
  const now = new Date("2026-10-09T08:00:00Z"); // 4:00 PM in Manila
  assert.match(threadActivityTime("2026-10-09T01:30:00Z", now), /^9:30\s?AM$/i);
  assert.match(threadActivityTime("2026-10-08T20:00:00Z", now), /^4:00\s?AM$/i, "Oct 8 in UTC is already Oct 9 in Manila");
  assert.equal(threadActivityTime("2026-10-08T15:00:00Z", now), "Yesterday");
  assert.match(threadActivityTime("2026-09-01T03:00:00Z", now), /Sep\s+1/);
  assert.match(threadActivityTime("2025-09-01T03:00:00Z", now), /2025/);
  assert.equal(threadActivityTime(null, now), "");
  assert.equal(messageDayLabel("2026-10-09T00:30:00Z", now), "Today");
  assert.match(messageDayLabel("2026-10-01T00:30:00Z", now), /Thursday, October 1, 2026/);
});

// ── Body rules and send idempotency ───────────────────────────────────────────────────────────

test("body rules match the backend: nonblank, 4,000 code points, no NUL or lone surrogate", () => {
  assert.equal(messageBodyProblem(""), "empty");
  assert.equal(messageBodyProblem(" \n\t "), "empty");
  assert.equal(messageBodyProblem("a".repeat(4000)), null);
  assert.equal(messageBodyProblem("a".repeat(4001)), "too_long");
  assert.equal(messageLength("😀".repeat(4000)), 4000, "Emoji count once each, like the backend");
  assert.equal(messageBodyProblem("😀".repeat(4000)), null);
  assert.equal(messageBodyProblem("bad\u0000byte"), "unsupported");
  assert.equal(messageBodyProblem("lone \ud800 surrogate"), "unsupported");
  assert.equal(messageBodyProblem("  Line one\n\nLine three  "), null, "Whitespace and line breaks are kept");
});

test("one intended Message keeps one client_message_id until confirmed", () => {
  let ids = 0;
  const createId = () => `id-${++ids}`;
  const first = nextSendIntent(IDLE_SEND, "thread:a", "Hello", createId);
  assert.deepEqual(first, { target: "thread:a", clientMessageId: "id-1", body: "Hello" });
  assert.equal(nextSendIntent({ kind: "sending", intent: first }, "thread:a", "Hello", createId), null, "No second send while one is in flight");
  const uncertain = { kind: "uncertain", intent: first };
  assert.equal(nextSendIntent(uncertain, "thread:a", "Hello", createId), first, "A retry reuses the same ID and body");
  assert.equal(nextSendIntent(uncertain, "thread:a", "Hello!", createId), null, "Edited text never reuses the unconfirmed ID");
  assert.equal(nextSendIntent(uncertain, "thread:b", "Hello", createId), null, "Another recipient never reuses it");
  assert.deepEqual(nextSendIntent(IDLE_SEND, "thread:a", "Hello", createId).clientMessageId, "id-2", "After confirmation the next Message gets a new ID");
});

test("only outcomes that may follow a stored Message keep the intent for retry", () => {
  for (const uncertain of [new TypeError("Failed to fetch"), new DOMException("aborted", "AbortError"), apiError(500), apiError(502), apiError(503, "guidance_message_content_unavailable"), apiError(504), apiError(408)]) {
    assert.equal(isUncertainSendFailure(uncertain), true, String(uncertain));
  }
  for (const refused of [apiError(401), apiError(403), apiError(404), apiError(409), apiError(422), apiError(429)]) {
    assert.equal(isUncertainSendFailure(refused), false, `${refused.status}`);
  }
});

test("send and status errors say what happened without backend jargon", () => {
  assert.match(describeSendError(new TypeError("x"), "thread"), /could not be confirmed/);
  assert.match(describeSendError(apiError(409), "thread"), /resolved, so your message was not sent/);
  assert.match(describeSendError(apiError(409), "staff-office"), /no available Guidance Office routing/);
  assert.match(describeSendError(apiError(404), "student-counseling"), /choose another recipient/);
  assert.match(describeSendError(apiError(422), "thread"), /4,000 characters/);
  assert.match(describeSendError(new AccountChangedError(), "thread"), /account changed/);
  assert.match(describeStatusChangeError(apiError(409), "reopen"), /already has an open Guidance Office conversation/);
  for (const text of [describeSendError(apiError(409), "thread"), describeSendError(apiError(404), "thread")]) {
    assert.ok(!/thread|client_message_id|OFFICE/.test(text), text);
  }
});

// ── Directory and history ─────────────────────────────────────────────────────────────────────

test("directory rows keep backend order and show a thread that moved between pages once", () => {
  const rows = directoryRows({
    pages: [
      { data: { items: [thread({ id: "1" }), thread({ id: "2" })], page: 1, page_size: 2, has_next: true } },
      { data: { items: [thread({ id: "2" }), thread({ id: "3" })], page: 2, page_size: 2, has_next: false } },
    ],
    pageParams: [1, 2],
  });
  assert.deepEqual(rows.map((row) => row.id), ["1", "2", "3"]);
});

test("a refresh reads only the newest page and joins it to the loaded run", () => {
  const first = mergeNewestPage(undefined, page([51, 52, 53], true));
  assert.deepEqual(sequences(first), [51, 52, 53]);
  const older = mergeOlderPage(first, page([49, 50], true), 51);
  assert.deepEqual(sequences(older), [49, 50, 51, 52, 53]);
  assert.equal(older.hasOlder, true);

  const joined = mergeNewestPage(older, page([52, 53, 54, 55], true));
  assert.deepEqual(sequences(joined), [49, 50, 51, 52, 53, 54, 55], "Older loaded Messages stay");
  assert.equal(joined.hasOlder, true);

  const restarted = mergeNewestPage(joined, page([70, 71], true));
  assert.deepEqual(sequences(restarted), [70, 71], "A gap restarts from the newest page instead of hiding it");

  const complete = mergeNewestPage(joined, page([1, 2, 3], false));
  assert.deepEqual(sequences(complete), [1, 2, 3]);
  assert.equal(complete.hasOlder, false);
});

test("an older page joins only at the anchor it was requested for", () => {
  const current = mergeNewestPage(undefined, page([10, 11], true));
  assert.equal(mergeOlderPage(current, page([8, 9], true), 12), current, "A stale anchor changes nothing");
  assert.equal(mergeOlderPage(undefined, page([8, 9], true), 10), undefined);
  assert.equal(mergeOlderPage(current, page([8, 9], false), 10).hasOlder, false);
});

test("a confirmed send appears once and only next to the loaded run", () => {
  const current = mergeNewestPage(undefined, page([1, 2], false));
  assert.deepEqual(sequences(appendConfirmedMessage(current, message(3))), [1, 2, 3]);
  assert.equal(appendConfirmedMessage(current, message(2)), current, "A replayed Message is not duplicated");
  assert.equal(appendConfirmedMessage(current, message(5)), current, "A gap waits for the refresh");
  assert.equal(appendConfirmedMessage(undefined, message(1)), undefined);
});

test("a confirmed private read cursor updates only the reader's cached rows", () => {
  const client = createQueryClient();
  client.setQueryData(guidanceDirectoryQueryKey(), { pages: [{ data: { items: [thread(), thread({ id: "other" })], page: 1, page_size: 20, has_next: false } }], pageParams: [1] });
  client.setQueryData(guidanceThreadQueryKey(THREAD), { data: thread(), status: 200, headers: {} });
  cacheConfirmedRead(client, THREAD, 3);
  const [read, other] = client.getQueryData(guidanceDirectoryQueryKey()).pages[0].data.items;
  assert.equal(read.unread_count, 0);
  assert.equal(read.own_last_read_sequence, 3);
  assert.equal(other.unread_count, 2, "Other threads stay unread");
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)).data.unread_count, 0);
  cacheConfirmedRead(client, THREAD, 2);
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)).data.own_last_read_sequence, 3, "The cursor never moves back");
});

// ── Realtime hints and freshness ──────────────────────────────────────────────────────────────

test("the protocol accepts only the closed messages.thread_changed shape", () => {
  const frame = (value) => parseServerFrame(JSON.stringify(value));
  assert.equal(frame({ v: 1, type: "messages.thread_changed", thread_id: THREAD }).event.thread_id, THREAD);
  assert.equal(frame({ v: 1, type: "messages.thread_changed" }), null);
  assert.equal(frame({ v: 1, type: "messages.thread_changed", thread_id: "not-a-uuid" }), null);
  assert.equal(frame({ v: 1, type: "messages.thread_changed", thread_id: THREAD, body: THREAD }), null, "No extra field, however shaped");
  assert.equal(frame({ v: 1, type: "messages.thread_changed", message_id: THREAD }), null);
  assert.equal(changedThreadId({ v: 1, type: "notifications.changed" }), null);
});

function freshnessFixture(reconcile = () => Promise.resolve(), initialGeneration = 0) {
  const document = new EventTarget();
  document.visibilityState = "visible";
  const window = new EventTarget();
  const timers = new Map();
  let timerId = 0;
  window.setInterval = (callback, ms) => { timers.set(++timerId, { callback, ms }); return timerId; };
  window.clearInterval = (id) => timers.delete(id);
  const navigator = { onLine: true };
  const scopes = [];
  const consumer = startGuidanceMessagesFreshness((scope) => { scopes.push(scope.activeThread); return reconcile(); }, { document, window, navigator }, initialGeneration);
  return {
    document, window, navigator, timers, scopes, consumer,
    tick: () => [...timers.values()][0]?.callback(),
    delay: () => [...timers.values()][0]?.ms,
  };
}
const settle = () => new Promise((resolve) => setImmediate(resolve));

test("not live polls about every 8 seconds; live keeps a 60-second safety poll", async () => {
  const f = freshnessFixture();
  try {
    assert.equal(f.delay(), MESSAGES_FALLBACK_REFRESH_MS);
    f.tick();
    await settle();
    assert.deepEqual(f.scopes, [true], "A poll reconciles the directory and the open thread");
    f.consumer.setRealtimeStatus({ state: "live", generation: 1 });
    assert.equal(f.delay(), MESSAGES_LIVE_SAFETY_REFRESH_MS);
    assert.equal(f.timers.size, 1);
    await settle();
    assert.deepEqual(f.scopes, [true, true], "A fresh ready reconciles everything");
    f.consumer.setRealtimeStatus({ state: "reconnecting", generation: 1 });
    assert.equal(f.delay(), MESSAGES_FALLBACK_REFRESH_MS);
  } finally { f.consumer.stop(); }
});

test("the generation the workspace opened under does not refetch; a later ready does, once", async () => {
  const f = freshnessFixture(undefined, 3);
  try {
    f.consumer.setRealtimeStatus({ state: "live", generation: 3 });
    await settle();
    assert.deepEqual(f.scopes, []);
    for (let index = 0; index < 4; index += 1) f.consumer.setRealtimeStatus({ state: "live", generation: 4 });
    await settle();
    assert.deepEqual(f.scopes, [true]);
  } finally { f.consumer.stop(); }
});

test("a burst of hints collapses into one trailing reconciliation covering every scope asked for", async () => {
  const pending = [];
  const f = freshnessFixture(() => new Promise((resolve) => pending.push(resolve)));
  try {
    f.consumer.requestRefresh({ activeThread: false });
    for (let index = 0; index < 20; index += 1) f.consumer.requestRefresh({ activeThread: index === 7 });
    assert.deepEqual(f.scopes, [false], "One reconciliation at a time");
    pending.shift()();
    await settle();
    assert.deepEqual(f.scopes, [false, true], "One trailing reconciliation, including the open thread");
    pending.shift()();
    await settle();
    assert.deepEqual(f.scopes, [false, true], "Nothing more without a new signal");
  } finally { f.consumer.stop(); }
});

test("hidden or offline tabs do not poll; returning reconciles promptly", async () => {
  const f = freshnessFixture();
  try {
    f.document.visibilityState = "hidden";
    f.tick();
    f.consumer.requestRefresh({ activeThread: false });
    await settle();
    assert.deepEqual(f.scopes, []);
    f.document.visibilityState = "visible";
    f.document.dispatchEvent(new Event("visibilitychange"));
    await settle();
    assert.deepEqual(f.scopes, [true]);
    f.navigator.onLine = false;
    f.tick();
    await settle();
    assert.equal(f.scopes.length, 1);
    f.navigator.onLine = true;
    f.window.dispatchEvent(new Event("online"));
    await settle();
    assert.equal(f.scopes.length, 2);
    f.window.dispatchEvent(new Event("focus"));
    await settle();
    assert.equal(f.scopes.length, 3);
  } finally { f.consumer.stop(); }
});

test("stopping ends polling and listeners", async () => {
  const f = freshnessFixture();
  f.consumer.stop();
  assert.equal(f.timers.size, 0);
  f.consumer.requestRefresh();
  f.document.dispatchEvent(new Event("visibilitychange"));
  await settle();
  assert.deepEqual(f.scopes, []);
});

test("reconciliation reads the directory always and the open thread only when asked", async () => {
  const keys = [];
  const client = { invalidateQueries: ({ queryKey, exact }) => { keys.push([queryKey, Boolean(exact)]); return Promise.resolve(); } };
  await reconcileGuidanceMessages(client, THREAD, { activeThread: false });
  assert.deepEqual(keys, [[["/api/v1/guidance-messages/threads"], false]]);
  keys.length = 0;
  await reconcileGuidanceMessages(client, THREAD, { activeThread: true });
  assert.deepEqual(keys, [
    [["/api/v1/guidance-messages/threads"], false],
    [guidanceThreadQueryKey(THREAD), true],
    [guidanceConversationQueryKey(THREAD), true],
  ]);
  keys.length = 0;
  await reconcileGuidanceMessages(client, null, { activeThread: true });
  assert.equal(keys.length, 1, "No open thread, only the directory");
});

// ── Account ownership ─────────────────────────────────────────────────────────────────────────

const session = (id) => ({ status: 200, headers: {}, data: { authenticated: true, user: { id }, session: { id: `session-${id}` } } });

test("another account's confirmation removes the previous account's conversations and Message bodies", () => {
  const client = createQueryClient();
  client.setQueryData(getAuthGetSessionQueryKey(), session("account-a"));
  client.setQueryData(guidanceDirectoryQueryKey(), { pages: [{ data: { items: [thread()], page: 1, page_size: 20, has_next: false } }], pageParams: [1] });
  client.setQueryData(guidanceThreadQueryKey(THREAD), { data: thread(), status: 200, headers: {} });
  client.setQueryData(guidanceConversationQueryKey(THREAD), mergeNewestPage(undefined, page([1, 2, 3], false)));

  client.setQueryData(getAuthGetSessionQueryKey(), session("account-b"));

  assert.equal(client.getQueryData(guidanceDirectoryQueryKey()), undefined);
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)), undefined);
  assert.equal(client.getQueryData(guidanceConversationQueryKey(THREAD)), undefined, "Account A's Message bodies are gone");
});

test("a send Account A started cannot add its Message after Account B is confirmed", async () => {
  const client = createQueryClient();
  client.setQueryData(getAuthGetSessionQueryKey(), session("account-a"));
  let release;
  let started = false;
  const observer = new MutationObserver(client, {
    mutationFn: () => { started = true; return new Promise((resolve) => { release = resolve; }); },
    // As useSendThreadMessage does: the canonical Message joins the conversation on success.
    onSuccess: (response) => client.setQueryData(guidanceConversationQueryKey(THREAD), (current) => appendConfirmedMessage(current, response.data) ?? { messages: [response.data], hasOlder: false }),
  });
  const outcome = observer.mutate({}).then(() => null, (error) => error);
  while (!started) await settle();
  client.setQueryData(getAuthGetSessionQueryKey(), session("account-b"));
  release({ data: message(1, person("account-a", "Account A")), status: 200, headers: {} });
  assert.ok((await outcome) instanceof AccountChangedError);
  assert.equal(client.getQueryData(guidanceConversationQueryKey(THREAD)), undefined);
});

// ── Source guards ─────────────────────────────────────────────────────────────────────────────

test("Messages code renders plain text and never persists, logs or opens a socket", () => {
  const directory = new URL("../src/features/guidance-messages/", import.meta.url).pathname;
  const sources = readdirSync(directory).map((name) => [name, readFileSync(join(directory, name), "utf8")]);
  assert.ok(sources.length >= 10);
  for (const [name, source] of sources) {
    for (const forbidden of [/dangerouslySetInnerHTML/, /ReactMarkdown|react-markdown/, /localStorage|sessionStorage|indexedDB/, /console\./, /new\s+WebSocket/, /persistQueryClient|createSyncStoragePersister/]) {
      assert.ok(!forbidden.test(source), `${name} must not use ${forbidden}`);
    }
  }
  const routes = new URL("../src/app/(portal)/portal/messages/", import.meta.url).pathname;
  assert.ok(!/searchParams/.test(readFileSync(join(routes, "page.tsx"), "utf8")), "No Message content travels in the URL");
});

// ── Contextual Messages (ADR-103) ─────────────────────────────────────────────────────────────

import {
  appointmentContextQueryKey,
  cacheOpenedCounselingThread,
  contextualHintScope,
  reconcileAppointmentMessages,
} from "../src/features/guidance-messages/guidance-appointment-context.ts";

const APPOINTMENT = "b0000000-0000-4000-8000-000000000001";
const counselingThread = (overrides = {}) => thread({
  kind: "COUNSELING", counselor: person("counselor", "Ana Cruz"), routing_college: null, assigned_to: null,
  relationship_appointment_id: APPOINTMENT, ...overrides,
});

test("an open panel asks again on any hint until its thread exists, then only for that thread", () => {
  assert.deepEqual(contextualHintScope(null, THREAD), { activeThread: true });
  assert.deepEqual(contextualHintScope(THREAD, THREAD), { activeThread: true });
  assert.equal(contextualHintScope(THREAD, "a0000000-0000-4000-8000-000000000009"), null);
});

test("contextual reconciliation reads the context, then the thread and its newest page once known", async () => {
  const keys = [];
  const client = { invalidateQueries: ({ queryKey, exact }) => { keys.push([queryKey[0], Boolean(exact)]); return Promise.resolve(); } };
  await reconcileAppointmentMessages(client, APPOINTMENT, null);
  assert.deepEqual(keys, [[appointmentContextQueryKey(APPOINTMENT)[0], true]]);
  keys.length = 0;
  await reconcileAppointmentMessages(client, APPOINTMENT, THREAD);
  assert.deepEqual(keys.map(([key]) => key), [
    appointmentContextQueryKey(APPOINTMENT)[0],
    guidanceThreadQueryKey(THREAD)[0],
    guidanceConversationQueryKey(THREAD)[0],
  ]);
  assert.ok(keys.every(([, exact]) => exact), "Exact keys only; no directory scan");
});

test("a confirmed first Message switches the context to its thread and seeds only a new history", () => {
  const client = createQueryClient();
  client.setQueryData(appointmentContextQueryKey(APPOINTMENT), { data: { thread: null, can_start: true }, status: 200, headers: {} });
  const first = message(1, person("student", "Maria Santos"));
  cacheOpenedCounselingThread(client, APPOINTMENT, { thread: counselingThread({ last_sequence: 1 }), message: first });
  assert.deepEqual(client.getQueryData(appointmentContextQueryKey(APPOINTMENT)).data, { thread: counselingThread({ last_sequence: 1 }), can_start: false });
  assert.deepEqual(sequences(client.getQueryData(guidanceConversationQueryKey(THREAD))), [1]);
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)).data.id, THREAD);

  const later = createQueryClient();
  cacheOpenedCounselingThread(later, APPOINTMENT, { thread: counselingThread(), message: message(7) });
  assert.equal(later.getQueryData(guidanceConversationQueryKey(THREAD)), undefined, "A later Message never invents a history");
  assert.equal(later.getQueryData(appointmentContextQueryKey(APPOINTMENT)), undefined, "No context is invented either");
});

test("a contextual send Account A started cannot reach Account B's panel", async () => {
  const client = createQueryClient();
  client.setQueryData(getAuthGetSessionQueryKey(), session("account-a"));
  let release;
  let started = false;
  const observer = new MutationObserver(client, {
    mutationFn: () => { started = true; return new Promise((resolve) => { release = resolve; }); },
    onSuccess: (response) => cacheOpenedCounselingThread(client, APPOINTMENT, response.data),
  });
  const outcome = observer.mutate({}).then(() => null, (error) => error);
  while (!started) await settle();
  client.setQueryData(getAuthGetSessionQueryKey(), session("account-b"));
  release({ data: { thread: counselingThread({ last_sequence: 1 }), message: message(1) }, status: 200, headers: {} });
  assert.ok((await outcome) instanceof AccountChangedError);
  assert.equal(client.getQueryData(guidanceConversationQueryKey(THREAD)), undefined);
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)), undefined);
});

test("contextual Messages never uses call chat, transcripts or a second socket", () => {
  const sources = ["guidance-contextual-messages.tsx", "guidance-appointment-context.ts", "guidance-conversation-surface.tsx"]
    .map((name) => [name, readFileSync(new URL(`../src/features/guidance-messages/${name}`, import.meta.url), "utf8")]);
  for (const [name, source] of sources) {
    for (const forbidden of [/sendAppMessage|app-message|transcription-message/, /features\/ecounseling\/(?:call|runtime)/, /daily-js|DailyIframe/, /new\s+WebSocket/]) {
      assert.ok(!forbidden.test(source), `${name} must not use ${forbidden}`);
    }
  }
  const ecounseling = readFileSync(new URL("../src/features/ecounseling/ecounseling-workspace.tsx", import.meta.url), "utf8");
  assert.ok(!/useMessageComposer|guidanceMessages[A-Z]/.test(ecounseling), "E-Counseling only mounts the shared contextual surface");
});
