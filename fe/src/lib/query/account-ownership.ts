import type { Mutation, Query, QueryClient } from "@tanstack/react-query";

// Protected client state belongs to exactly one confirmed account at a time. The root QueryClient
// outlives page navigation, and another tab can sign in as a different account, so a session check
// may confirm account B in a tab that still holds account A's records. When that happens, A's
// queries and mutations are discarded before B's session reaches any component, and responses to
// requests A started can no longer reach the cache. A refreshed session for the same account, or a
// session check that fails, changes nothing.

export class AccountChangedError extends Error {
  constructor() {
    super("The signed-in account changed before this request completed.");
    this.name = "AccountChangedError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// The account a successful session read confirms: a session row and its user, or nothing.
export function confirmedAccountId(sessionResponse: unknown): string | null {
  if (!isRecord(sessionResponse) || !isRecord(sessionResponse.data)) return null;
  const { session, user } = sessionResponse.data;
  return isRecord(session) && isRecord(user) && typeof user.id === "string" ? user.id : null;
}

export type AccountOwnership = {
  /** Watches session reads in `client` and discards the previous account's state on a change. */
  attach: (client: QueryClient) => () => void;
  /** Records which account a mutation started under (MutationCache `onMutate`). */
  mutationStarted: (mutation: Mutation<unknown, unknown, unknown>) => void;
  /** Refuses a result that belongs to an account that is no longer signed in (MutationCache `onSuccess`). */
  assertMutationOwner: (mutation: Mutation<unknown, unknown, unknown>) => void;
};

export function createAccountOwnership({
  isSessionQuery,
}: {
  isSessionQuery: (query: Query) => boolean;
}): AccountOwnership {
  let owner: string | null = null;
  // Increases each time protected state is discarded for a different account.
  let generation = 0;
  const mutationGenerations = new WeakMap<object, number>();

  function discardPreviousAccount(client: QueryClient, session: Query) {
    generation += 1;
    const queries = client.getQueryCache();
    // Removing a query cancels its fetch, so a late response for the previous account lands in a
    // detached query rather than the cache. Components fetch again for the new account.
    for (const query of queries.getAll()) {
      if (query !== session) queries.remove(query);
    }
    client.getMutationCache().clear();
  }

  return {
    attach(client) {
      return client.getQueryCache().subscribe((event) => {
        if (event.type !== "updated" || event.action.type !== "success") return;
        if (!isSessionQuery(event.query)) return;
        const account = confirmedAccountId(event.query.state.data);
        // Signed-out and unreadable sessions never establish an owner; sign-out clears the cache.
        if (account === null) return;
        if (owner !== null && owner !== account) discardPreviousAccount(client, event.query);
        owner = account;
      });
    },
    mutationStarted(mutation) {
      mutationGenerations.set(mutation, generation);
    },
    assertMutationOwner(mutation) {
      const started = mutationGenerations.get(mutation);
      if (started !== undefined && started !== generation) throw new AccountChangedError();
    },
  };
}
