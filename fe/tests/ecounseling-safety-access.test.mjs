import assert from "node:assert/strict";
import { test } from "node:test";
import { MutationObserver, QueryObserver } from "@tanstack/react-query";

import { captureIndicators } from "../src/features/ecounseling/call/capture-indicators.tsx";
import { activeCaptureKinds, captureCessationWarning, captureSafetyState } from "../src/features/ecounseling/runtime/runtime-model.ts";
import { sessionRefreshInterval } from "../src/features/ecounseling/ecounseling-shared.ts";
import { sessionFileRows } from "../src/features/ecounseling/session-files.tsx";
import { ecounselingResourceAccess } from "../src/features/ecounseling/ecounseling-resource-access.ts";
import { safeQueryData } from "../src/features/freshness/query-freshness.ts";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { getECounselingGetAssignedWorkspaceQueryKey, getECounselingGetMyWorkspaceQueryKey, getECounselingListAssignedConsentsQueryKey, getECounselingAccessAssignedMediaQueryKey } from "../src/lib/api/generated/e-counseling/e-counseling.ts";
import { getCounselingContextGetOverviewQueryKey, getCounselingContextGetInventoryQueryKey, getCounselingGetEncounterQueryKey } from "../src/lib/api/generated/counseling/counseling.ts";
import { getRoutineInterviewsGetAssignedQueryKey } from "../src/lib/api/generated/routine-interviews/routine-interviews.ts";
import { getGuidanceMessagesGetAppointmentContextQueryKey, getGuidanceMessagesGetThreadQueryKey, getGuidanceMessagesListMessagesQueryKey } from "../src/lib/api/generated/guidance-messages/guidance-messages.ts";
import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";
import { createQueryClient } from "../src/lib/query/query-client.ts";
import { appointmentId, media, workspace } from "./support/ui-hierarchy-fixtures.mjs";

const response = (data) => ({ data, status: 200, headers: {} });
const canonical = getECounselingGetAssignedWorkspaceQueryKey(appointmentId);
const error = (status, url = canonical[0], code = "permission_denied") => new CompassApiError({ status, url, method: "GET", headers: {}, body: { error: { code, message: "Synthetic private reason" } } });
const tick = () => new Promise((resolve) => setImmediate(resolve));
function deferred() {
  let resolve; let reject;
  const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

for (const kind of ["recording", "transcription"]) {
  for (const [status, safety] of [["ACTIVE", "active"], ["START_REQUESTED", "starting"], ["STOP_REQUESTED", "stopping"], ["ERROR", "uncertain"]]) {
    test(`${kind} ${status} is safety-relevant with truthful Leave and sign-out copy`, () => {
      const value = media(); value[kind].capture_status = status;
      assert.equal(captureSafetyState(kind, status), safety);
      assert.deepEqual(activeCaptureKinds(value), [kind]);
      assert.equal(captureIndicators(value).length, 1);
      assert.match(captureIndicators(value)[0].label.toLowerCase(), new RegExp(kind));
      for (const action of ["leave", "sign-out", "access-loss"]) {
        const text = captureCessationWarning([kind], action);
        assert.match(text, /not been confirmed as stopped/);
        assert.match(text, /may not stop/);
        assert.doesNotMatch(text, /STOP_REQUESTED|ERROR|HTTP|webhook|provider|still active/);
      }
      assert.equal(sessionRefreshInterval(false, value), 7000, "Uncertainty continues to refresh outside the call");
    });
  }
}

test("terminal capture has no warning; legacy transcription STOPPED remains uncertain", () => {
  for (const status of ["NOT_STARTED", "READY"]) {
    assert.deepEqual(activeCaptureKinds(media(status)), []);
    assert.deepEqual(captureIndicators(media(status)), []);
  }
  assert.deepEqual(activeCaptureKinds(media("STOPPED")), ["transcription"]);
  assert.equal(captureCessationWarning([], "leave"), null);
  const stopped = media("STOPPED"); stopped.media_policy_version = 2;
  assert.match(sessionFileRows(stopped).find((row) => row.kind === "TRANSCRIPTION").outcome.text, /stop has not been confirmed/);
  assert.match(captureCessationWarning(activeCaptureKinds(media("ERROR")), "leave"), /Recording and transcription have/);
});

function seeded() {
  const client = createQueryClient();
  client.setQueryData(getAuthGetSessionQueryKey(), response({ user: { id: "synthetic-account" }, session: { id: "session" } }));
  const value = workspace("STOP_REQUESTED");
  value.routine_interview = { id: "routine-related" };
  value.counseling_encounter = { id: "encounter-related" };
  client.setQueryData(canonical, response(value));
  const context = getCounselingContextGetOverviewQueryKey("APPOINTMENT", appointmentId);
  const messages = getGuidanceMessagesGetAppointmentContextQueryKey(appointmentId);
  client.setQueryData(messages, response({ thread: { id: "thread-related" } }));
  const dependencies = [context, getCounselingContextGetInventoryQueryKey("APPOINTMENT", appointmentId), getECounselingListAssignedConsentsQueryKey(appointmentId), getECounselingAccessAssignedMediaQueryKey(appointmentId, "RECORDING"), getRoutineInterviewsGetAssignedQueryKey("routine-related"), getCounselingGetEncounterQueryKey("encounter-related"), messages, getGuidanceMessagesGetThreadQueryKey("thread-related"), [...getGuidanceMessagesListMessagesQueryKey("thread-related"), "conversation"]];
  for (const key of dependencies.filter((key) => key !== messages)) client.setQueryData(key, response({ private: "Synthetic protected context" }));
  const unrelated = getRoutineInterviewsGetAssignedQueryKey("routine-unrelated");
  client.setQueryData(unrelated, response({ private: "Independent resource" }));
  return { client, access: ecounselingResourceAccess(client), dependencies, unrelated };
}

for (const key of [canonical, getECounselingGetMyWorkspaceQueryKey(appointmentId)]) test(`403 at ${key[0]} conceals the resource and dependencies while the session stays valid`, async () => {
  const { client, access, dependencies, unrelated } = seeded();
  const observer = new QueryObserver(client, { queryKey: dependencies[0], enabled: false });
  const unsubscribe = observer.subscribe(() => {});
  try {
    await assert.rejects(client.fetchQuery({ queryKey: key, queryFn: async () => { throw error(403, key[0]); }, retry: false, staleTime: 0 }));
    assert.ok(access.getDenial(appointmentId));
    assert.deepEqual(access.getDenial(appointmentId).captureKinds, ["recording", "transcription"]);
    assert.equal(client.getQueryData(canonical), undefined);
    for (const dependency of dependencies) assert.equal(client.getQueryData(dependency), undefined);
    assert.equal(observer.getCurrentResult().data, undefined, "Already mounted observers are also concealed");
    assert.equal(observer.getCurrentResult().isError, true);
    assert.ok(client.getQueryData(getAuthGetSessionQueryKey()).data.session, "Account session remains valid");
    assert.ok(client.getQueryData(unrelated), "No unrelated record is cleared");
    assert.doesNotMatch(access.getDenial(appointmentId).error.message, /private reason/);
  } finally { unsubscribe(); client.clear(); }
});

for (const failure of [error(503), new TypeError("Failed to fetch"), error(408)]) test(`temporary ${failure.name}/${failure.status ?? "network"} retains data and warning`, async () => {
  const { client, access } = seeded();
  try {
    await assert.rejects(client.fetchQuery({ queryKey: canonical, queryFn: async () => { throw failure; }, retry: false, staleTime: 0 }));
    assert.equal(access.getDenial(appointmentId), null);
    const query = client.getQueryCache().find({ queryKey: canonical });
    const data = safeQueryData({ data: query.state.data, error: query.state.error, isError: true });
    assert.deepEqual(activeCaptureKinds(data.data.media), ["recording", "transcription"]);
  } finally { client.clear(); }
});

test("delayed reads and manual cache updates cannot authorize a denied resource; fresh canonical GET restores it", async () => {
  const { client, access, dependencies } = seeded();
  const pending = deferred(); let signal;
  const late = client.fetchQuery({ queryKey: dependencies[0], queryFn: (context) => { signal = context.signal; return pending.promise; }, staleTime: 0 }).catch(() => {});
  await tick(); access.deny(appointmentId);
  pending.resolve(response({ private: "late" })); await late;
  assert.equal(signal.aborted, true);
  assert.equal(client.getQueryData(dependencies[0]), undefined);
  client.setQueryData(canonical, response(workspace()));
  client.setQueryData(dependencies[0], response({ private: "late callback" }));
  assert.equal(client.getQueryData(canonical), undefined);
  assert.equal(client.getQueryData(dependencies[0]), undefined);
  const initialKey = [...dependencies[0], "late-initial-data"];
  const initial = new QueryObserver(client, { queryKey: initialKey, enabled: false, initialData: response({ private: "old mounted initial data" }) });
  assert.equal(initial.getCurrentResult().data, undefined, "A new observer's pre-denial initial data is concealed too");
  await client.fetchQuery({ queryKey: dependencies[0], queryFn: async () => response({ private: "independent child success" }), retry: false });
  assert.ok(access.getDenial(appointmentId), "Child success cannot restore access");
  assert.equal(client.getQueryData(dependencies[0]), undefined);
  await client.fetchQuery({ queryKey: canonical, queryFn: async () => response(workspace()), retry: false });
  assert.equal(access.getDenial(appointmentId), null);
  assert.ok(client.getQueryData(canonical));
  assert.equal(client.getQueryData(dependencies[0]), undefined, "Pre-denial children are never restored from memory");
  await client.fetchQuery({ queryKey: dependencies[0], queryFn: async () => response({ private: "new authorized context" }), retry: false });
  assert.equal(client.getQueryData(dependencies[0]).data.private, "new authorized context");
  client.clear();
});

test("a canonical read started before denial cannot recover access, even if it ignores abort", async () => {
  const { client, access } = seeded(); const held = deferred();
  const late = client.fetchQuery({ queryKey: canonical, queryFn: () => held.promise, staleTime: 0 }).catch(() => {});
  await tick(); access.deny(appointmentId); held.resolve(response(workspace())); await late;
  assert.ok(access.getDenial(appointmentId)); assert.equal(client.getQueryData(canonical), undefined);
  client.clear();
});

test("resource mutations cannot start or report success across a denial, even after recovery", async () => {
  const { client, access } = seeded(); const held = deferred(); let invoked = 0; let succeeded = 0;
  const observer = new MutationObserver(client, { mutationKey: ["eCounselingStartAssignedRecording"], mutationFn: () => { invoked++; return held.promise; }, onSuccess: () => { succeeded++; } });
  const outcome = observer.mutate({ appointmentId }).catch((caught) => caught);
  while (!invoked) await tick(); access.deny(appointmentId);
  await assert.rejects(observer.mutate({ appointmentId }));
  assert.equal(invoked, 1, "No second resource operation");
  await client.fetchQuery({ queryKey: canonical, queryFn: async () => response(workspace()) });
  held.resolve(response({})); assert.ok(await outcome instanceof CompassApiError);
  assert.equal(succeeded, 0, "A stale success callback never runs");
  client.clear();
});

test("related Routine and contextual Message mutations are also fenced", async () => {
  const { client, access } = seeded(); access.deny(appointmentId); let invoked = 0;
  for (const options of [{ mutationKey: ["routineInterviewsReplaceAssignedEvaluation"] }, { meta: { ecounselingAppointmentId: appointmentId } }]) {
    const observer = new MutationObserver(client, { ...options, mutationFn: async () => { invoked++; } });
    await assert.rejects(observer.mutate({ routineInterviewId: "routine-related" }));
  }
  assert.equal(invoked, 0); client.clear();
});

test("request-scoped CSRF refusal does not revoke the resource; authoritative join denial does", () => {
  const { client, access } = seeded();
  access.requestFailed(error(403, `${canonical[0]}/join`, "csrf_failed"));
  assert.equal(access.getDenial(appointmentId), null);
  access.requestFailed(error(403, `${canonical[0]}/join`));
  assert.ok(access.getDenial(appointmentId));
  assert.throws(() => access.assertAuthorized(appointmentId)); client.clear();
});
