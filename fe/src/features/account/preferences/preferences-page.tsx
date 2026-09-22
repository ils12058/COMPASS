"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { accountErrorMessage } from "@/features/account/components/account-errors";
import {
  getNotificationsGetPreferencesQueryKey,
  useNotificationsGetPreferences,
  useNotificationsUpdatePreferences,
} from "@/lib/api/generated/notifications/notifications";

export function PreferencesPage() {
  const queryClient = useQueryClient();
  const preferences = useNotificationsGetPreferences({ query: { retry: false } });
  const update = useNotificationsUpdatePreferences();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function setOptionalEmail(enabled: boolean) {
    setError(null);
    setSaved(false);
    try {
      const response = await update.mutateAsync({ data: { optional_email_enabled: enabled } });
      queryClient.setQueryData(getNotificationsGetPreferencesQueryKey(), response);
      setSaved(true);
    } catch (caught) {
      setError(accountErrorMessage(caught, "The email preference could not be saved. Please try again."));
    }
  }

  return (
    <section aria-labelledby="preferences-heading">
      <h1 id="preferences-heading" className="font-heading text-3xl font-bold text-ink">Preferences</h1>
      {preferences.isPending ? <p role="status" className="mt-7 text-sm text-muted">Loading preferences…</p> : null}
      {preferences.isError ? (
        <div className="mt-7" role="alert">
          <p className="text-sm text-danger">Your preferences could not be loaded.</p>
          <Button variant="secondary" className="mt-3" onClick={() => void preferences.refetch()}>Retry</Button>
        </div>
      ) : null}
      {preferences.isSuccess ? (
        <div className="mt-7 border-t border-border py-6">
          <label className="flex items-start gap-4">
            <input
              type="checkbox"
              className="mt-1 size-5 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              checked={preferences.data.data.optional_email_enabled}
              disabled={update.isPending}
              onChange={(event) => void setOptionalEmail(event.target.checked)}
            />
            <span>
              <span className="block font-heading text-lg font-semibold text-ink">Optional informational email</span>
              <span className="mt-1 block text-sm leading-6 text-muted">Receive optional informational COMPASS emails.</span>
              <span className="mt-1 block text-sm leading-6 text-muted">Security and required operational emails are not disabled by this setting.</span>
            </span>
          </label>
          {update.isPending ? <p role="status" className="mt-4 text-sm text-muted">Saving preference…</p> : null}
          {saved ? <p role="status" className="mt-4 text-sm text-success">Preference saved.</p> : null}
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
