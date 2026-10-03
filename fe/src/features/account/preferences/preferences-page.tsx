"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { RowsSkeleton } from "@/components/ui/rows-skeleton";
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
      <PageHeader title="Preferences" headingId="preferences-heading" />
      {preferences.isPending ? <RowsSkeleton label="Loading preferences…" rows={1} framed /> : null}
      {preferences.isError ? (
        <Notice
          role="alert"
          tone="danger"
          action={<Button variant="secondary" onClick={() => void preferences.refetch()}>Retry</Button>}
        >
          Your preferences could not be loaded.
        </Notice>
      ) : null}
      {preferences.isSuccess ? (
        <Panel aria-labelledby="preferences-email-heading">
          <PanelHeader title="Email" titleId="preferences-email-heading" />
          <PanelBody>
          <label className="flex items-start gap-4">
            <input
              type="checkbox"
              className="mt-1 size-5 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
              checked={preferences.data.data.optional_email_enabled}
              disabled={update.isPending}
              onChange={(event) => void setOptionalEmail(event.target.checked)}
            />
            <span>
              <span className="block font-semibold text-ink">Optional informational email</span>
              <span className="mt-1 block text-sm leading-6 text-muted">Receive optional informational COMPASS emails.</span>
              <span className="mt-1 block text-sm leading-6 text-muted">Security and required operational emails are not disabled by this setting.</span>
            </span>
          </label>
          {update.isPending ? <p role="status" className="mt-4 text-sm text-muted">Saving preference…</p> : null}
          {saved ? <p role="status" className="mt-4 text-sm text-success">Preference saved.</p> : null}
          {error ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
          </PanelBody>
        </Panel>
      ) : null}
    </section>
  );
}
