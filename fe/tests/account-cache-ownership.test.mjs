// Protected client state belongs to one confirmed account at a time (frontend audit FE-001). These
// tests drive the app's own QueryClient: a session read that confirms another account discards the
// previous account's queries and mutations, while the same account or a failed check keeps them.
import assert from "node:assert/strict";
import { test } from "node:test";

import { MutationObserver } from "@tanstack/react-query";

import { getAuthGetSessionQueryKey } from "../src/lib/api/generated/auth/auth.ts";
import { AccountChangedError, confirmedAccountId } from "../src/lib/query/account-ownership.ts";
import { createQueryClient } from "../src/lib/query/query-client.ts";

const sessionKey = getAuthGetSessionQueryKey();
const profileKey = ["/api/v1/me/profile"];
const recordKey = ["/api/v1/referrals/referral-a"];

const session = (account, sessionId = `session-${account}`) => ({
  status: 200,
  headers: {},
  data: { authenticated: true, user: { id: `account-${account}` }, session: { id: sessionId } },
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

function signedInAs(account) {
  const client = createQueryClient();
  client.setQueryData(sessionKey, session(account));
  client.setQueryData(profileKey, { data: { full_name: `Profile ${account}` } });
  client.setQueryData(recordKey, { data: { status_note: `Record ${account}` } });
  return client;
}

test("a session read confirms an account only with a session and a user", () => {
  assert.equal(confirmedAccountId(session("a")), "account-a");
  assert.equal(confirmedAccountId({ data: { authenticated: false, user: { id: "account-a" }, session: null } }), null);
  assert.equal(confirmedAccountId({ data: { session: { id: "s" }, user: null } }), null);
  assert.equal(confirmedAccountId(undefined), null);
});

test("confirming another account discards the previous account's queries and mutations", () => {
  const client = signedInAs("a");
  client.getMutationCache().build(client, { mutationKey: ["previous"], mutationFn: async () => null });

  client.setQueryData(sessionKey, session("b"));

  assert.equal(client.getQueryData(profileKey), undefined, "Account A's profile is gone");
  assert.equal(client.getQueryData(recordKey), undefined, "Account A's records are gone");
  assert.deepEqual(client.getQueryData(sessionKey), session("b"), "Account B's confirmed session is kept");
  assert.equal(client.getMutationCache().getAll().length, 0, "Account A's mutation state is gone");
});

test("a refreshed session for the same account keeps the cache", () => {
  const client = signedInAs("a");
  client.setQueryData(sessionKey, session("a", "rotated-session"));
  assert.deepEqual(client.getQueryData(profileKey), { data: { full_name: "Profile a" } });
  assert.deepEqual(client.getQueryData(recordKey), { data: { status_note: "Record a" } });
});

test("a session check that fails or confirms nobody is not an account change", async () => {
  const client = signedInAs("a");
  await assert.rejects(
    client.fetchQuery({ queryKey: sessionKey, queryFn: async () => { throw new TypeError("Failed to fetch"); }, staleTime: 0, retry: false }),
  );
  client.setQueryData(sessionKey, { status: 200, headers: {}, data: { authenticated: false, user: null, session: null } });
  assert.deepEqual(client.getQueryData(profileKey), { data: { full_name: "Profile a" } }, "Failures leave Account A's cache alone");

  // Account A is still the owner: a later change to Account B is still detected.
  client.setQueryData(sessionKey, session("b"));
  assert.equal(client.getQueryData(profileKey), undefined);
});

test("a read Account A started cannot fill the cache after Account B is confirmed", async () => {
  const client = signedInAs("a");
  client.removeQueries({ queryKey: profileKey });
  const response = deferred();
  let signal;
  const lateRead = client
    .fetchQuery({
      queryKey: profileKey,
      queryFn: (context) => {
        signal = context.signal;
        return response.promise;
      },
    })
    .catch((error) => error);
  await tick();

  client.setQueryData(sessionKey, session("b"));
  response.resolve({ data: { full_name: "Profile a" } });
  await lateRead;

  assert.equal(signal.aborted, true, "The previous account's request is cancelled");
  assert.equal(client.getQueryData(profileKey), undefined, "Its late response never reaches the cache");

  // Account B reads its own data normally.
  await client.fetchQuery({ queryKey: profileKey, queryFn: async () => ({ data: { full_name: "Profile b" } }) });
  assert.deepEqual(client.getQueryData(profileKey), { data: { full_name: "Profile b" } });
});

test("a mutation Account A started does not succeed after Account B is confirmed", async () => {
  const client = signedInAs("a");
  const response = deferred();
  let started = false;
  let succeeded = false;
  const observer = new MutationObserver(client, {
    mutationFn: () => {
      started = true;
      return response.promise;
    },
    onSuccess: () => {
      succeeded = true;
      // A component would write the previous account's response into the cache here.
      client.setQueryData(recordKey, { data: { status_note: "Record a (late)" } });
    },
  });
  const outcome = observer.mutate({ status_note: "late" }).then(() => null, (error) => error);
  while (!started) await tick();

  client.setQueryData(sessionKey, session("b"));
  response.resolve({ data: { status_note: "Record a (late)" } });

  assert.ok((await outcome) instanceof AccountChangedError, "The caller sees the account change, not a success");
  assert.equal(succeeded, false, "The mutation's success handling does not run");
  assert.equal(client.getQueryData(recordKey), undefined);

  // A mutation started under Account B succeeds.
  const next = new MutationObserver(client, { mutationFn: async () => ({ data: { status_note: "Record b" } }) });
  assert.deepEqual(await next.mutate({}), { data: { status_note: "Record b" } });
});
