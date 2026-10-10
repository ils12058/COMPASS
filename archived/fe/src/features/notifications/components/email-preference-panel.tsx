"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Mail } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useCurrentAuth } from "@/features/auth/hooks/use-current-auth";
import {
  getNotificationsGetPreferencesQueryKey,
  useNotificationsGetPreferences,
  useNotificationsUpdatePreferences,
} from "@/lib/api/generated/notifications/notifications";

export function EmailPreferencePanel() {
  const { session } = useCurrentAuth();
  const queryClient = useQueryClient();
  const preferences = useNotificationsGetPreferences();
  const update = useNotificationsUpdatePreferences();
  const [error, setError] = useState<string | null>(null);

  async function save(nextValue: boolean) {
    setError(null);

    try {
      const result = await update.mutateAsync({
        data: { optional_email_enabled: nextValue },
      });
      queryClient.setQueryData(getNotificationsGetPreferencesQueryKey(), result);
    } catch {
      setError("Your optional email preference could not be saved. Please try again.");
    }
  }

  if (preferences.isPending) {
    return (
      <section aria-busy="true" className="rounded-xl border bg-card p-5 sm:p-6">
        <p role="status" className="text-sm text-muted-foreground">
          Loading email preferences…
        </p>
      </section>
    );
  }

  if (preferences.isError || !preferences.data?.data) {
    return (
      <section className="rounded-xl border bg-card p-5 sm:p-6">
        <h2 className="font-heading text-xl font-bold">Email preferences</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Email preferences are unavailable right now.
        </p>
        <Button className="mt-4" variant="outline" onClick={() => void preferences.refetch()}>
          Try again
        </Button>
      </section>
    );
  }

  const enabled = preferences.data.data.optional_email_enabled;

  return (
    <section className="rounded-xl border bg-card p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="rounded-lg bg-accent p-2 text-accent-foreground">
          <Mail aria-hidden="true" className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-heading text-xl font-bold">Optional email updates</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Receive optional informational emails from COMPASS, such as feedback invitations.
          </p>
        </div>
      </div>

      <label className="mt-5 flex items-start justify-between gap-4 rounded-lg border p-4">
        <span>
          <span className="block text-sm font-semibold">Receive optional email updates</span>
          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
            Important service and account-security emails may still be sent even when this setting is off.
          </span>
        </span>
        <input
          type="checkbox"
          role="switch"
          checked={enabled}
          disabled={update.isPending}
          onChange={(event) => void save(event.target.checked)}
          className="mt-1 size-5 shrink-0 accent-[var(--compass-brand-maroon)]"
        />
      </label>

      {session.user.email ? (
        <p className="mt-4 break-words text-xs text-muted-foreground">
          COMPASS sends email to your account address:{" "}
          <span className="font-medium text-foreground">{session.user.email}</span>
        </p>
      ) : null}

      {update.isPending ? (
        <p role="status" className="mt-3 text-xs text-muted-foreground">
          Saving preference…
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </section>
  );
}
