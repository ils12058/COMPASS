// EC-FIX-1: a Stop that COMPASS accepted shows "Stopping…" until completion; a Stop request that
// itself failed says it is not confirmed and can be sent again. Neither ever shows completion.
import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { GovernedCaptureControls } from "../src/features/ecounseling/counselor-media.tsx";
import { settleCaptureStop, stopControlState } from "../src/features/ecounseling/runtime/runtime-model.ts";

test("stop control state follows COMPASS Stop intent and only this person's failed request", () => {
  const idle = { stopping: false, failed: false };
  assert.equal(stopControlState("STOP_REQUESTED", idle), "stopping");
  assert.equal(stopControlState("STOP_REQUESTED", { stopping: false, failed: true }), "not-confirmed");
  // A request in flight always reads as Stopping, even after an earlier failure.
  assert.equal(stopControlState("STOP_REQUESTED", { stopping: true, failed: true }), "stopping");
  assert.equal(stopControlState("ACTIVE", { stopping: true, failed: false }), "stopping");
  // A failure never overrides other canonical states, including confirmed completion.
  for (const status of ["ACTIVE", "START_REQUESTED", "READY", "STOPPED", "ERROR", "NOT_STARTED", undefined]) {
    assert.equal(stopControlState(status, { stopping: false, failed: true }), null, String(status));
    assert.equal(stopControlState(status, idle), null, String(status));
  }
});

test("a Stop is sent once, a failure is reported before the re-read, and a failed re-read never leaves it pending", async () => {
  const events = [];
  await settleCaptureStop(
    async () => { events.push("send"); },
    async () => { events.push("refresh"); },
    () => events.push("failed"),
  );
  assert.deepEqual(events, ["send", "refresh"]);

  events.length = 0;
  const rejection = new Error("synthetic provider rejection");
  let reported;
  await settleCaptureStop(
    async () => { events.push("send"); throw rejection; },
    async () => { events.push("refresh"); },
    (caught) => { reported = caught; events.push("failed"); },
  );
  assert.deepEqual(events, ["send", "failed", "refresh"]);
  assert.equal(reported, rejection);

  events.length = 0;
  await assert.doesNotReject(settleCaptureStop(
    async () => { events.push("send"); throw rejection; },
    async () => { events.push("refresh"); throw new Error("synthetic refresh failure"); },
    () => events.push("failed"),
  ));
  assert.deepEqual(events, ["send", "failed", "refresh"]);
});

function tray(status, { stopping = false, failed = false } = {}) {
  const both = (value) => ({ recording: value, transcription: value });
  const media = {
    access: { canManageMediaAssigned: true },
    status: both(status),
    stopping: both(stopping),
    stopFailed: both(failed),
    canStop: both(["START_REQUESTED", "ACTIVE", "STOP_REQUESTED"].includes(status)),
    canStart: both(false),
    starting: false,
    stop: async () => {},
    openStart: () => {},
  };
  return renderToStaticMarkup(h(GovernedCaptureControls, { media }));
}

test("the call tray distinguishes pending confirmation, a failed Stop request and completion", () => {
  const pending = tray("STOP_REQUESTED");
  assert.equal((pending.match(/Stopping…/g) ?? []).length, 2);
  assert.doesNotMatch(pending, /Stop not confirmed/);
  assert.equal((pending.match(/disabled=""/g) ?? []).length, 2, "an accepted Stop cannot be re-sent");

  const failed = tray("STOP_REQUESTED", { failed: true });
  assert.match(failed, /aria-label="Recording stop not confirmed\. Stop recording again"/);
  assert.match(failed, /aria-label="Transcription stop not confirmed\. Stop transcription again"/);
  assert.equal((failed.match(/>Stop not confirmed</g) ?? []).length, 2);
  assert.doesNotMatch(failed, /Stopping…|Recorded|Transcribed/);
  assert.doesNotMatch(failed, /disabled=""/, "the not-confirmed Stop can be sent again");

  const retrying = tray("STOP_REQUESTED", { stopping: true, failed: true });
  assert.equal((retrying.match(/Stopping…/g) ?? []).length, 2);

  const completed = tray("READY", { failed: true });
  assert.match(completed, /Recorded/);
  assert.match(completed, /Transcribed/);
  assert.doesNotMatch(completed, /Stop not confirmed|Stopping…/);
});
