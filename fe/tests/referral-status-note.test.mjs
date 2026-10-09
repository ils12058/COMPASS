// The Referral status note editor across reloads (frontend audit FE-003): a reload never replaces
// text the person changed, a newer saved note replaces unchanged text, and only the person's own
// review, Cancel, or a confirmed save moves the baseline.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  keepStatusNoteText,
  reconcileStatusNote,
  startStatusNoteDraft,
  statusNoteConflict,
  statusNoteDirty,
} from "../src/features/referrals/referral-status-note.ts";

const editing = (saved, value) => ({ ...startStatusNoteDraft(saved), editing: true, value });

test("a reload with the same saved note changes nothing, even while text is unsaved", () => {
  const draft = editing("Existing note", "My unsaved text");
  assert.equal(reconcileStatusNote(draft, "Existing note"), draft, "The same draft object, so no re-render loop");
  assert.equal(statusNoteConflict(draft, "Existing note"), false);
  assert.equal(statusNoteDirty(draft), true);
});

test("a newer saved note replaces unchanged text", () => {
  const closed = startStatusNoteDraft("Existing note");
  assert.deepEqual(reconcileStatusNote(closed, "Newer note"), { editing: false, value: "Newer note", baseline: "Newer note" });

  const openUnchanged = editing("Existing note", "Existing note");
  assert.deepEqual(reconcileStatusNote(openUnchanged, "Newer note"), { editing: true, value: "Newer note", baseline: "Newer note" });
});

test("a newer saved note never replaces changed text; it is reported until reviewed", () => {
  const draft = editing("Existing note", "My unsaved text");
  const reconciled = reconcileStatusNote(draft, "Newer note");
  assert.equal(reconciled, draft, "The unsaved text is kept");
  assert.equal(statusNoteConflict(reconciled, "Newer note"), true);

  const kept = keepStatusNoteText(reconciled, "Newer note");
  assert.deepEqual(kept, { editing: true, value: "My unsaved text", baseline: "Newer note" });
  assert.equal(statusNoteConflict(kept, "Newer note"), false, "After review, saving replaces the newer note");
  assert.equal(statusNoteDirty(kept), true);
});

test("Cancel and a confirmed save start again from the saved note", () => {
  assert.deepEqual(startStatusNoteDraft("Newer note"), { editing: false, value: "Newer note", baseline: "Newer note" });
  const afterSave = startStatusNoteDraft("Saved text");
  assert.equal(reconcileStatusNote(afterSave, "Saved text"), afterSave, "The reload after saving is not a change");
});

test("the editor is keyed by the Referral, never by its timestamp", () => {
  const source = readFileSync(new URL("../src/features/referrals/referral-detail-page.tsx", import.meta.url), "utf8");
  assert.match(source, /<StatusNoteEditor key=\{item\.id\}/);
  assert.doesNotMatch(source, /key=\{`\$\{item\.id\}-\$\{item\.updated_at\}`\}/);
});
