// EC-WS-1/2: Counseling and E-Counseling workspaces show clinical records read-only and link to the
// pages that own their editing. Pure helpers and source checks; no browser, backend or network.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  contextEncounterPreset,
  encounterReturnPath,
  encounterReturnTarget,
  recordEncounterPath,
} from "../src/features/counseling/encounter-origin.ts";

const source = (path) => readFileSync(new URL(`../src/features/${path}`, import.meta.url), "utf8");
const student = { id: "student-1", display_name: "Maria Santos", institutional_id: "TEST-01" };

test("the Record Counseling Encounter page is addressed by anchor, with a closed return choice", () => {
  assert.equal(recordEncounterPath("APPOINTMENT", "a/1"), "/portal/counseling/encounters/new/appointment/a%2F1");
  assert.equal(recordEncounterPath("APPOINTMENT", "a1", "ecounseling"), "/portal/counseling/encounters/new/appointment/a1?from=ecounseling");
  assert.equal(recordEncounterPath("ROUTINE_INTERVIEW", "r1"), "/portal/counseling/encounters/new/routine-interview/r1");
  assert.deepEqual(encounterReturnPath("APPOINTMENT", "a1", "ecounseling"), { href: "/portal/e-counseling/a1", label: "Back to session" });
  assert.deepEqual(encounterReturnPath("APPOINTMENT", "a1", "workspace"), { href: "/portal/counseling/workspace/appointment/a1", label: "Back to Counseling workspace" });
  assert.equal(encounterReturnPath("ROUTINE_INTERVIEW", "r1", "ecounseling").href, "/portal/counseling/workspace/routine-interview/r1", "A Routine Interview never returns to a call");
  for (const value of [undefined, "https://evil.test", "/portal/admin", ["ecounseling"], "ECOUNSELING"]) {
    assert.equal(encounterReturnTarget(value), "workspace", String(value));
  }
  assert.equal(encounterReturnTarget("ecounseling"), "ecounseling");
});

test("the origin comes from the server-checked context, never from the address", () => {
  const appointment = contextEncounterPreset("APPOINTMENT", "a1", { student, entry_mode: "APPOINTMENT", delivery_mode: "ONLINE" });
  assert.deepEqual(appointment, { entryMode: "APPOINTMENT", appointmentId: "a1", studentName: "Maria Santos", institutionalId: "TEST-01", deliveryMode: "ONLINE" });
  const direct = contextEncounterPreset("ROUTINE_INTERVIEW", "r1", { student, entry_mode: "WALK_IN", delivery_mode: "IN_PERSON" });
  assert.equal(direct.routineInterviewId, "r1");
  assert.equal(direct.studentId, "student-1");
  assert.equal(contextEncounterPreset("ROUTINE_INTERVIEW", "r1", { student, entry_mode: "APPOINTMENT", delivery_mode: "IN_PERSON" }), undefined);
  assert.equal(contextEncounterPreset("APPOINTMENT", "a1", { student, entry_mode: "APPOINTMENT", delivery_mode: "UNKNOWN" }), undefined);
});

test("workspaces embed no Encounter, Intake or Evaluation editor", () => {
  for (const path of ["counseling/counseling-workspace.tsx", "ecounseling/ecounseling-workspace.tsx"]) {
    const text = source(path);
    assert.doesNotMatch(text, /RecordEncounterDialog|RecordEncounterForm|RoutineCounselorEvaluationWorkspace|RoutineStudentIntakeForm|StudentSessionSummarySection/, path);
    assert.match(text, /recordEncounterPath\(/, path);
  }
  assert.match(source("counseling/counseling-workspace.tsx"), /Open Routine Interview/);
  // The Routine Interview detail page stays the editor, with its unsaved-changes guard.
  assert.match(source("routine-interviews/routine-counselor-evaluation.tsx"), /useUnsavedChangesGuard\(/);
});

test("the dedicated page guards unsaved times and never claims a recording documents the session", () => {
  const page = source("counseling/record-encounter-page.tsx");
  assert.match(page, /useUnsavedChangesGuard\(/);
  assert.match(page, /Recording audio or video during a session doesn’t record the encounter/);
  assert.match(page, /router\.push\(`\/portal\/counseling\/encounters\/\$\{encodeURIComponent\(encounterId\)\}`\)/);
});
