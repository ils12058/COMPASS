// Case-coordination Guidance Messages (GMSG-5): grant-scoped access, contextual entry, the exact
// ended copy and refusal wording. Pure modules, the app's QueryClient and source guards; no
// browser, socket or backend.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  canWriteThread,
  getGuidanceMessagesAccess,
} from "../src/features/guidance-messages/guidance-messages-access.ts";
import {
  cacheOpenedCaseCoordinationThread,
  caseCoordinationContextQueryKey,
  reconcileCaseCoordinationMessages,
} from "../src/features/guidance-messages/guidance-case-coordination-context.ts";
import {
  guidanceConversationQueryKey,
  guidanceThreadQueryKey,
} from "../src/features/guidance-messages/guidance-messages-cache.ts";
import { describeSendError } from "../src/features/guidance-messages/guidance-messages-errors.ts";
import {
  CASE_COORDINATION_ENDED_COPY,
  CASE_COORDINATION_ENTRY_COPY,
  CASE_COORDINATION_UNAVAILABLE_COPY,
  threadRoutingFacts,
  threadSubtitle,
  threadTitle,
} from "../src/features/guidance-messages/guidance-messages-presentation.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { createQueryClient } from "../src/lib/query/query-client.ts";

const THREAD = "c0000000-0000-4000-8000-000000000001";
const GRANT = "d0000000-0000-4000-8000-000000000001";
const person = (id, display_name) => ({ id, display_name });
const account = (role, capabilities) => ({
  id: `${role.toLowerCase()}-1`, role, first_name: "Example", last_name: "User",
  email: "user@example.test", student_lifecycle_status: null, designations: [], capabilities,
});
const student = account("STUDENT", ["guidance_messages.view_self", "guidance_messages.manage_self"]);
const thread = (overrides = {}) => ({
  id: THREAD, kind: "COUNSELOR_CASE_COORDINATION", status: "OPEN",
  student: null, counselor: null, requester: null,
  direct_first_user: null, direct_second_user: null,
  student_subject: person("subject", "Maria Santos"),
  routing_college: null, assigned_to: null,
  relationship_appointment_id: null, relationship_referral_id: null,
  relationship_referral_reference: null, relationship_referral_voided: null,
  relationship_case_grant_id: GRANT,
  created_at: "2026-11-07T01:00:00Z", last_message_at: "2026-11-07T02:00:00Z",
  last_sequence: 1, own_last_read_sequence: 0, unread_count: 1, ...overrides,
});
const message = (sequence, sender = person("other-counselor", "Ana Cruz")) => ({
  id: `m${sequence}`, sequence, sender, body: `Body ${sequence}`, created_at: "2026-11-07T02:00:00Z",
});
const apiError = (status, code = "synthetic") =>
  new CompassApiError({ status, body: { error: { code, message: "x" } }, headers: {}, method: "POST", url: "/api/v1/x" });
const source = (name) =>
  readFileSync(new URL(`../src/features/guidance-messages/${name}`, import.meta.url), "utf8");

const CASE_CAPS = ["guidance_messages.view", "guidance_messages.manage"];
const VIEW = "guidance_messages.case_coordination.view";
const MANAGE = "guidance_messages.case_coordination.manage";

// ── Access ───────────────────────────────────────────────────────────────────────────────────

test("case coordination needs the narrow capability on top of broad view and never starts generically", () => {
  const contextualWriter = getGuidanceMessagesAccess(
    account("COUNSELOR", ["guidance_messages.view", VIEW, MANAGE]),
  );
  assert.deepEqual(
    [
      contextualWriter.canViewCaseCoordination,
      contextualWriter.canManageCaseCoordination,
      contextualWriter.hasWorkspace,
      contextualWriter.canWrite,
      contextualWriter.canStart,
    ],
    [true, true, true, true, false],
    "Case coordination opens its grant's panel without enabling the generic start chooser",
  );
  const writer = getGuidanceMessagesAccess(account("COUNSELOR", [...CASE_CAPS, VIEW, MANAGE]));
  assert.deepEqual(
    [writer.canViewCaseCoordination, writer.canManageCaseCoordination, writer.hasWorkspace, writer.canWrite],
    [true, true, true, true],
    "Broad manage writes Office conversations; case manage writes only its own kind",
  );
  const reader = getGuidanceMessagesAccess(account("COUNSELOR", ["guidance_messages.view", VIEW]));
  assert.deepEqual(
    [reader.canViewCaseCoordination, reader.canManageCaseCoordination, reader.hasWorkspace, reader.canWrite, reader.canStart],
    [true, false, true, false, false],
    "Narrow view opens the grant's panel; writing needs narrow manage",
  );
  for (const partial of [
    account("COUNSELOR", [VIEW, MANAGE]),
    account("COUNSELOR", ["guidance_messages.view", MANAGE]),
    account("GUIDANCE_SERVICES_STAFF", [...CASE_CAPS, VIEW, MANAGE]),
    account("IT_ADMIN", [...CASE_CAPS, VIEW, MANAGE]),
    student,
  ]) {
    assert.deepEqual(
      [getGuidanceMessagesAccess(partial).canViewCaseCoordination, getGuidanceMessagesAccess(partial).canManageCaseCoordination],
      [false, false],
      `${partial.role} without the exact dependency holds no case coordination`,
    );
  }
});

test("canWriteThread keeps every narrow kind on its own capability", () => {
  const office = thread({ kind: "OFFICE", student_subject: null, relationship_case_grant_id: null });
  const direct = thread({ kind: "COUNSELOR_DIRECT", student_subject: null, relationship_case_grant_id: null });
  const caseThread = thread();
  const broadManager = getGuidanceMessagesAccess(account("COUNSELOR", CASE_CAPS));
  const caseReader = getGuidanceMessagesAccess(account("COUNSELOR", [...CASE_CAPS, VIEW]));
  const caseWriter = getGuidanceMessagesAccess(account("COUNSELOR", [...CASE_CAPS, VIEW, MANAGE]));
  const directWriter = getGuidanceMessagesAccess(
    account("COUNSELOR", [...CASE_CAPS, "guidance_messages.counselor_direct.view", "guidance_messages.counselor_direct.manage"]),
  );
  assert.equal(canWriteThread(office, broadManager), true, "Broad manage still writes an Office thread");
  assert.equal(canWriteThread(caseThread, broadManager), false, "Broad manage alone never writes a case conversation");
  assert.equal(canWriteThread(caseThread, caseReader), false, "A live grant is still read-only without narrow manage");
  assert.equal(canWriteThread(caseThread, caseWriter), true);
  assert.equal(canWriteThread(direct, caseWriter), false, "Case manage never grants direct authority");
  assert.equal(canWriteThread(caseThread, directWriter), false, "Direct manage never grants case authority");
  assert.equal(canWriteThread(caseThread, getGuidanceMessagesAccess(student)), false);
});

// ── Presentation ─────────────────────────────────────────────────────────────────────────────

test("case titles name the Student subject and subtitles name the kind", () => {
  assert.equal(threadTitle(thread(), "staff"), "Maria Santos");
  assert.equal(threadTitle(thread({ student_subject: null }), "staff"), "Case coordination");
  assert.equal(threadTitle(thread({ student_subject: person("subject", "   ") }), "staff"), "Case coordination");
  assert.equal(threadSubtitle(thread(), "staff"), "Case coordination");
  assert.equal(threadSubtitle(thread(), "student"), "Case coordination");
  assert.deepEqual(threadRoutingFacts(thread(), "staff"), { college: null, assignedTo: null });
});

test("the exact ended copy is reserved for an ended access; every other refusal keeps its wording", () => {
  assert.equal(CASE_COORDINATION_ENTRY_COPY, "Coordinate on this authorized case.");
  assert.equal(CASE_COORDINATION_ENDED_COPY, "Your case coordination access has ended.");
  assert.equal(CASE_COORDINATION_UNAVAILABLE_COPY, "This conversation is no longer available for new messages.");
  assert.equal(
    describeSendError(apiError(403, "guidance_messages_case_coordination_ended"), "case-coordination"),
    CASE_COORDINATION_ENDED_COPY,
  );
  assert.equal(describeSendError(apiError(404), "case-coordination"), CASE_COORDINATION_UNAVAILABLE_COPY);
  assert.equal(
    describeSendError(apiError(403), "case-coordination"),
    "Your account can no longer send this message. It was not sent.",
    "A generic refusal never claims access ended",
  );
  assert.equal(
    describeSendError(apiError(403, "guidance_messages_case_coordination_ended"), "thread"),
    "Your account can no longer send this message. It was not sent.",
    "The ended copy is scoped to case coordination",
  );
  const context = source("guidance-case-coordination-context.ts");
  assert.match(context, /accessEnded: Boolean\(context\?\.access_ended\)/, "Ended is read from the server, never inferred");
  const host = source("guidance-contextual-messages.tsx");
  const panel = host.slice(host.indexOf("function ContextualPanel"));
  assert.match(panel, /const ended = target\.accessEnded;/);
  assert.match(panel, /\{ended \? \(/);
  assert.match(panel, /\{target\.endedMessage\}/);
  const wrapper = host.slice(host.indexOf("function CaseCoordinationContextualHost"));
  assert.match(wrapper, /emptyMessage: CASE_COORDINATION_ENTRY_COPY/);
  assert.match(wrapper, /endedMessage: CASE_COORDINATION_ENDED_COPY/);
});

// ── Context and cache ────────────────────────────────────────────────────────────────────────

test("case reconciliation reads the grant's context, then the thread and its newest page once known", async () => {
  const keys = [];
  const client = {
    invalidateQueries: ({ queryKey, exact }) => {
      keys.push([queryKey[0], Boolean(exact)]);
      return Promise.resolve();
    },
  };
  await reconcileCaseCoordinationMessages(client, GRANT, null);
  assert.deepEqual(keys, [[caseCoordinationContextQueryKey(GRANT)[0], true]]);
  keys.length = 0;
  await reconcileCaseCoordinationMessages(client, GRANT, THREAD);
  assert.deepEqual(keys.map(([key]) => key), [
    caseCoordinationContextQueryKey(GRANT)[0],
    guidanceThreadQueryKey(THREAD)[0],
    guidanceConversationQueryKey(THREAD)[0],
  ]);
  assert.ok(keys.every(([, exact]) => exact), "Exact keys only; no directory scan");
});

test("a confirmed case Message joins the grant's context and seeds only a new history", () => {
  const client = createQueryClient();
  client.setQueryData(caseCoordinationContextQueryKey(GRANT), {
    data: { thread: null, counterpart: null, can_start: true, access_ended: false }, status: 200, headers: {},
  });
  const first = message(1);
  cacheOpenedCaseCoordinationThread(client, GRANT, { thread: thread(), message: first });
  assert.deepEqual(client.getQueryData(caseCoordinationContextQueryKey(GRANT)).data, {
    thread: thread(), counterpart: null, can_start: false, access_ended: false,
  });
  assert.deepEqual(
    client.getQueryData(guidanceConversationQueryKey(THREAD)).messages.map((item) => item.sequence),
    [1],
  );
  assert.equal(client.getQueryData(guidanceThreadQueryKey(THREAD)).data.id, THREAD);

  const later = createQueryClient();
  cacheOpenedCaseCoordinationThread(later, GRANT, { thread: thread(), message: message(7) });
  assert.equal(
    later.getQueryData(guidanceConversationQueryKey(THREAD)),
    undefined,
    "A later Message never invents a history",
  );
  assert.equal(
    later.getQueryData(caseCoordinationContextQueryKey(GRANT)),
    undefined,
    "No context is invented either",
  );
});

// ── Entry points ────────────────────────────────────────────────────────────────────────────

test("nothing renders or opens while the grant offers no conversation or an ended one", () => {
  const context = source("guidance-case-coordination-context.ts");
  assert.match(context, /available: Boolean\(context && \(context\.thread \|\| context\.can_start\)\)/);
  const host = source("guidance-contextual-messages.tsx");
  const trigger = host.slice(host.indexOf("function MessagesTriggerButton"), host.indexOf("function ContextualPanel"));
  assert.match(trigger, /if \(!available\) return null;/, "The trigger appears only when the backend offers Messages");
  assert.match(host, /const open = requestedOpen && \(target\.available \|\| target\.accessEnded\);/);
  const coverage = readFileSync(
    new URL("../src/features/counseling/coverage/coverage-detail.tsx", import.meta.url),
    "utf8",
  );
  assert.match(
    coverage,
    /grant\.communication_purpose === "CASE_COORDINATION"[\s\S]*guidance_messages\.case_coordination\.view/,
    "The grant page mounts the case surface only for an ACTIVE case-purpose grant the reader can view",
  );
});

test("the generic start chooser never offers a case conversation", () => {
  const chooser = source("guidance-new-message.tsx");
  assert.ok(!/CaseCoordination|case-grant|case_coordination/.test(chooser), "Case coordination starts only from its grant page");
  const access = source("guidance-messages-access.ts");
  assert.match(access, /canStart: canManageSelf \|\| canManageStaff \|\| canManageInquirySelf \|\| canManageDirect/);
  assert.ok(!/canStart:[^;]*canManageCaseCoordination/.test(access));
});
