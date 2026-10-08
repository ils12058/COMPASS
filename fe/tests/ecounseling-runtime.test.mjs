// The persistent E-Counseling runtime (ADR-094): runtime state, route identity, join availability,
// consent cues, the cross-tab advisory lease, and the call session's terminal cleanup. No test
// reaches Daily or uses browser storage.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { DailyCallSession } from "../src/features/ecounseling/call/daily-call-session.ts";
import {
  CLAIM_WINDOW_MS,
  CrossTabCallCoordinator,
  HEARTBEAT_MS,
  LEASE_MS,
} from "../src/features/ecounseling/runtime/cross-tab-call-coordinator.ts";
import {
  activeCaptureKinds,
  consentEndedNotice,
  isLiveRuntime,
  isSessionRoute,
  joinAvailability,
  pendingConsentCue,
  runtimeState,
  sessionAppointmentFromPath,
  sessionPath,
} from "../src/features/ecounseling/runtime/runtime-model.ts";
import { installFakeDaily } from "./support/fake-daily.mjs";
import { media } from "./support/ui-hierarchy-fixtures.mjs";

test("runtime state is one closed model, separate from what COMPASS records about capture", () => {
  assert.equal(runtimeState({ activated: false, claiming: false, phase: "joined" }), "inactive");
  assert.equal(runtimeState({ activated: true, claiming: true, phase: "idle" }), "activating");
  const expected = { requesting: "joining", joining: "joining", joined: "active", reconnecting: "reconnecting", leaving: "leaving", left: "ended", failed: "failed", idle: "inactive" };
  for (const [phase, state] of Object.entries(expected)) assert.equal(runtimeState({ activated: true, claiming: false, phase }), state, phase);
  assert.deepEqual(["inactive", "activating", "joining", "active", "reconnecting", "leaving", "ended", "failed"].filter(isLiveRuntime), ["activating", "joining", "active", "reconnecting", "leaving"]);
});

test("one helper decides whether a path is the active Appointment's session; call state never enters the URL", () => {
  assert.equal(sessionPath("a b"), "/portal/e-counseling/a%20b");
  assert.equal(sessionAppointmentFromPath("/portal/e-counseling/a%20b"), "a b");
  assert.equal(sessionAppointmentFromPath("/portal/e-counseling/appt-1/"), "appt-1");
  assert.equal(sessionAppointmentFromPath("/portal/e-counseling"), null);
  assert.equal(sessionAppointmentFromPath("/portal/routine-interviews/appt-1"), null);
  assert.equal(isSessionRoute("/portal/e-counseling/appt-1", "appt-1"), true);
  assert.equal(isSessionRoute("/portal/e-counseling/appt-2", "appt-1"), false, "Another Appointment's page is not the active session");
  assert.equal(isSessionRoute("/portal/e-counseling/appt-1", null), false);
  assert.doesNotMatch(sessionPath("appt-1"), /\?|token|room|call/);
});

test("one portal runtime holds at most one call, and another tab's lease blocks a new one", () => {
  const base = { appointmentId: "b", activeAppointmentId: "a", otherTabActive: false };
  assert.equal(joinAvailability({ ...base, state: "active" }), "other-session");
  assert.equal(joinAvailability({ ...base, state: "joining" }), "other-session");
  assert.equal(joinAvailability({ ...base, appointmentId: "a", state: "active" }), "this-session");
  assert.equal(joinAvailability({ ...base, state: "ended" }), "available", "A call that ended frees the runtime");
  assert.equal(joinAvailability({ ...base, state: "failed", otherTabActive: true }), "other-tab");
});

test("the Student's cue and the Counselor's notices come from COMPASS session state", () => {
  const pending = media(); pending.recording.consent_status = "PENDING";
  assert.equal(pendingConsentCue(pending), "Media permission requested");
  const storage = media(); storage.transcription.storage_consent_status = "PENDING";
  assert.equal(pendingConsentCue(storage), "Transcript storage permission requested");
  assert.equal(pendingConsentCue(media()), null);
  const withdrawn = media("STOP_REQUESTED"); withdrawn.recording.consent_status = "WITHDRAWN";
  assert.equal(consentEndedNotice(withdrawn), "The student withdrew media permission.");
  assert.equal(consentEndedNotice(media("READY")), null);
  assert.deepEqual(activeCaptureKinds(media("ACTIVE")), ["recording", "transcription"]);
  assert.deepEqual(activeCaptureKinds(media("START_REQUESTED")), ["recording", "transcription"]);
  assert.deepEqual(activeCaptureKinds(media("STOP_REQUESTED")), []);
});

// An in-memory BroadcastChannel and clock shared by simulated tabs.
function createTabs() {
  let clock = 1_000_000;
  const timers = [];
  const channels = new Set();
  const sent = [];
  const createChannel = () => {
    const listeners = new Set();
    const channel = {
      postMessage(message) {
        sent.push(structuredClone(message));
        for (const other of channels) if (other !== channel) for (const listener of other.listeners) listener({ data: structuredClone(message) });
      },
      addEventListener(_type, listener) { listeners.add(listener); },
      removeEventListener(_type, listener) { listeners.delete(listener); },
      close() { channels.delete(channel); },
      listeners,
    };
    channels.add(channel);
    return channel;
  };
  const setTimer = (callback, ms) => {
    const timer = { at: clock + ms, callback, cleared: false };
    timers.push(timer);
    return timer;
  };
  const clearTimer = (timer) => { if (timer) timer.cleared = true; };
  const advance = (ms) => {
    const target = clock + ms;
    for (;;) {
      const next = timers.filter((timer) => !timer.cleared && timer.at <= target).sort((a, b) => a.at - b.at)[0];
      if (!next) break;
      clock = next.at;
      next.cleared = true;
      next.callback();
    }
    clock = target;
  };
  const tab = (tabId, options = {}) => new CrossTabCallCoordinator({
    tabId,
    createChannel: options.unsupported ? () => null : createChannel,
    now: () => clock,
    setTimer,
    clearTimer,
    wait: async (ms) => { advance(ms); },
  });
  return { tab, advance, sent };
}

test("a tab with a call announces it, a new tab learns of it, and joining there is blocked", async () => {
  const { tab, sent } = createTabs();
  const first = tab("tab-a");
  first.start();
  assert.equal(await first.acquire(), true);
  const second = tab("tab-b");
  second.start();
  assert.equal(second.getSnapshot(), true, "The new tab asked and the owner answered");
  assert.equal(await second.acquire(), false);
  const payloads = JSON.stringify(sent);
  assert.doesNotMatch(payloads, /token|room|appointment|daily\.co|Maria|https?:/i, "Only tab IDs, message types and claim times cross tabs");
  for (const message of sent) assert.deepEqual(Object.keys(message).sort(), message.type === "owner" ? ["since", "tab", "type", "v"] : ["tab", "type", "v"]);
});

test("releasing the lease lets another tab join, and a crashed tab's lease expires on its own", async () => {
  const { tab, advance } = createTabs();
  const first = tab("tab-a");
  const second = tab("tab-b");
  first.start();
  second.start();
  await first.acquire();
  assert.equal(second.getSnapshot(), true);
  first.release();
  assert.equal(second.getSnapshot(), false);
  assert.equal(await second.acquire(), true);

  const third = tab("tab-c");
  third.start();
  assert.equal(third.getSnapshot(), true);
  // tab-b keeps renewing while its call lasts…
  advance(HEARTBEAT_MS * 5);
  assert.equal(third.getSnapshot(), true);
  // …then crashes: it stops sending anything, including a release, and its lease runs out.
  second.post = () => {};
  advance(LEASE_MS + HEARTBEAT_MS);
  assert.equal(third.getSnapshot(), false, "A stale owner stops blocking");
  assert.equal(await third.acquire(), true);
});

test("simultaneous claims settle on one owner", async () => {
  const { tab } = createTabs();
  const a = tab("tab-a");
  const b = tab("tab-b");
  a.start();
  b.start();
  const results = await Promise.all([a.acquire(), b.acquire()]);
  assert.equal(results.filter(Boolean).length, 1, `exactly one owner: ${results}`);
  assert.ok(CLAIM_WINDOW_MS > 0);
});

test("without BroadcastChannel the coordinator stays out of the way", async () => {
  const { tab } = createTabs();
  const lonely = tab("tab-a", { unsupported: true });
  lonely.start();
  assert.equal(lonely.getSnapshot(), false);
  assert.equal(await lonely.acquire(), true);
  lonely.release();
  lonely.stop();
});

test("terminal cleanup leaves and destroys the call and resolves when destruction finishes", async () => {
  const daily = installFakeDaily({});
  const session = new DailyCallSession({ loadFactory: async () => daily, supportsSpeakerSelection: () => false });
  await session.join({
    fetchCredential: async () => ({ roomUrl: "https://example.daily.co/r", token: "t", expiresAt: new Date(Date.now() + 60_000).toISOString() }),
    describeCredentialError: () => "x",
  });
  assert.equal(session.getSnapshot().phase, "joined");
  await session.dispose();
  assert.equal(daily.instances[0].isDestroyed(), true);
  assert.deepEqual(daily.log.map(([method]) => method).filter((method) => method === "leave" || method === "destroy"), ["leave", "destroy"]);
  assert.equal(session.getSnapshot().phase, "idle");
});

test("the call is owned by the portal runtime, not by a page", () => {
  const source = (path) => readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8");
  const workspace = source("features/ecounseling/ecounseling-workspace.tsx");
  const stage = source("features/ecounseling/call/call-stage.tsx");
  for (const file of [workspace, stage]) {
    assert.doesNotMatch(file, /new DailyCallSession|\.dispose\(/, "Pages and the stage never create or end the call object");
  }
  assert.doesNotMatch(stage, /<audio|useRemoteAudioPlayback/, "The stage never plays the remote audio itself");
  const runtime = source("features/ecounseling/runtime/active-call-runtime.tsx");
  assert.equal((runtime.match(/new DailyCallSession\(/g) ?? []).length, 1);
  assert.equal((runtime.match(/<audio /g) ?? []).length, 1, "One remote-audio owner");
  const boundary = source("features/portal/components/portal-boundary.tsx");
  assert.match(boundary, /<ActiveECounselingRuntimeProvider[\s\S]*\{content\}[\s\S]*<\/ActiveECounselingRuntimeProvider>/, "The runtime wraps the loading, verification and maintenance presentations");
  for (const path of ["features/ecounseling/runtime/active-call-runtime.tsx", "features/ecounseling/runtime/cross-tab-call-coordinator.ts", "features/ecounseling/runtime/global-call-dock.tsx"]) {
    assert.doesNotMatch(source(path), /localStorage|sessionStorage|indexedDB|startRecording|startTranscription|transcription-message/, path);
  }
});
