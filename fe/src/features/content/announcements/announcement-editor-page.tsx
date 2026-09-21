"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AudienceField } from "@/features/content/components/audience-field";
import { CapabilityGate } from "@/features/content/components/capability-gate";
import { ConfirmationDialog } from "@/features/content/components/confirmation-dialog";
import { PreviewDialog } from "@/features/content/components/preview-dialog";
import { PublicationStatusBadge } from "@/features/content/components/publication-status-badge";
import { RichMarkdownEditor } from "@/features/content/components/rich-markdown-editor";
import { useUnsavedChanges } from "@/features/content/hooks/use-unsaved-changes";
import {
  audienceLabel,
  contentMutationError,
  formatContentDateTime,
  fromDateTimeLocal,
  isExpired,
  toDateTimeLocal,
} from "@/features/content/presentation";
import { isUuid } from "@/features/public/utils";
import {
  getAnnouncementsGetManagedQueryKey,
  getAnnouncementsGetPublicQueryKey,
  getAnnouncementsGetVisibleQueryKey,
  getAnnouncementsListManagedQueryKey,
  getAnnouncementsListPublicQueryKey,
  getAnnouncementsListVisibleQueryKey,
  useAnnouncementsArchive,
  useAnnouncementsGetManaged,
  useAnnouncementsPublish,
  useAnnouncementsUpdate,
} from "@/lib/api/generated/announcements/announcements";
import type {
  AnnouncementAudienceValue,
  AnnouncementManagementResponse,
} from "@/lib/api/generated/model";

export function AnnouncementEditorPage({ announcementId }: { announcementId: string }) {
  return (
    <CapabilityGate capability="announcements.manage">
      <AnnouncementEditorLoader announcementId={announcementId} />
    </CapabilityGate>
  );
}

function AnnouncementEditorLoader({ announcementId }: { announcementId: string }) {
  const validId = isUuid(announcementId);
  const query = useAnnouncementsGetManaged(announcementId, {
    query: {
      enabled: validId,
      retry: false,
    },
  });

  if (!validId) {
    return <UnavailableAnnouncement />;
  }

  if (query.isPending) {
    return <p role="status" className="text-sm text-muted-foreground">Loading announcement…</p>;
  }

  if (query.isError || !query.data?.data) {
    return (
      <section className="rounded-xl border bg-card p-6">
        <h1 className="font-heading text-2xl font-bold">Announcement unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This announcement could not be loaded or is no longer available to manage.
        </p>
        <Button className="mt-4" variant="outline" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </section>
    );
  }

  return (
    <AnnouncementEditor
      key={`${query.data.data.id}:${query.data.data.updated_at}`}
      item={query.data.data}
    />
  );
}

function UnavailableAnnouncement() {
  return (
    <section className="rounded-xl border bg-card p-6">
      <h1 className="font-heading text-2xl font-bold">Announcement unavailable</h1>
      <p className="mt-2 text-sm text-muted-foreground">This announcement could not be found.</p>
      <Link href="/portal/content/announcements" className="mt-4 inline-block font-semibold no-underline">
        Back to Announcements
      </Link>
    </section>
  );
}

function AnnouncementEditor({ item }: { item: AnnouncementManagementResponse }) {
  const queryClient = useQueryClient();
  const update = useAnnouncementsUpdate();
  const publish = useAnnouncementsPublish();
  const archive = useAnnouncementsArchive();

  const [title, setTitle] = useState(item.title);
  const [body, setBody] = useState(item.body_markdown);
  const [audience, setAudience] = useState<AnnouncementAudienceValue>(item.audience);
  const [pinned, setPinned] = useState(item.is_pinned);
  const [expiresAt, setExpiresAt] = useState(toDateTimeLocal(item.expires_at));
  const [error, setError] = useState<string | null>(null);

  const readOnly = item.status === "ARCHIVED";
  const pending = update.isPending || publish.isPending || archive.isPending;
  const expiryIso = fromDateTimeLocal(expiresAt);
  const dirty =
    title !== item.title ||
    body !== item.body_markdown ||
    audience !== item.audience ||
    pinned !== item.is_pinned ||
    expiryIso !== item.expires_at;

  useUnsavedChanges(dirty && !pending);

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getAnnouncementsListManagedQueryKey() }),
      queryClient.invalidateQueries({
        queryKey: getAnnouncementsGetManagedQueryKey(item.id),
      }),
      queryClient.invalidateQueries({ queryKey: getAnnouncementsListVisibleQueryKey() }),
      queryClient.invalidateQueries({
        queryKey: getAnnouncementsGetVisibleQueryKey(item.id),
      }),
      queryClient.invalidateQueries({ queryKey: getAnnouncementsListPublicQueryKey() }),
      queryClient.invalidateQueries({
        queryKey: getAnnouncementsGetPublicQueryKey(item.id),
      }),
    ]);
  }

  function updatePayload() {
    return {
      title,
      body_markdown: body,
      audience,
      is_pinned: pinned,
      expires_at: expiryIso,
    };
  }

  async function save() {
    setError(null);
    if (expiresAt && !expiryIso) {
      setError("Enter a valid expiry date and time.");
      return false;
    }

    try {
      await update.mutateAsync({
        announcementId: item.id,
        data: updatePayload(),
      });
      await invalidate();
      return true;
    } catch (caught) {
      setError(contentMutationError(caught, "announcement"));
      return false;
    }
  }

  function publicationProblem(): string | null {
    if (!title.trim()) {
      return "Add a title before publishing.";
    }
    if (!body.trim()) {
      return "Add announcement content before publishing.";
    }
    if (!audience) {
      return "Choose an audience before publishing.";
    }
    if (expiresAt && (!expiryIso || Date.parse(expiryIso) <= Date.now())) {
      return "Choose a future expiry date and time before publishing.";
    }
    return null;
  }

  async function publishAnnouncement() {
    setError(null);
    const problem = publicationProblem();
    if (problem) {
      setError(problem);
      return;
    }

    try {
      if (dirty) {
        await update.mutateAsync({
          announcementId: item.id,
          data: updatePayload(),
        });
      }
      await publish.mutateAsync({ announcementId: item.id });
      await invalidate();
    } catch (caught) {
      setError(contentMutationError(caught, "announcement"));
      throw caught;
    }
  }

  async function archiveAnnouncement() {
    setError(null);
    try {
      await archive.mutateAsync({ announcementId: item.id });
      await invalidate();
    } catch (caught) {
      setError(contentMutationError(caught, "announcement"));
      throw caught;
    }
  }

  const publishedPublicly =
    item.status === "PUBLISHED" &&
    item.audience === "PUBLIC" &&
    !isExpired(item.expires_at);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Link href="/portal/content/announcements" className="text-sm font-semibold no-underline">
            ← Announcements
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-heading text-3xl font-bold tracking-tight">
              {item.title.trim() || "Untitled draft"}
            </h1>
            <PublicationStatusBadge status={item.status} expiresAt={item.expires_at} />
          </div>
        </div>
        {publishedPublicly ? (
          <Link
            href={`/announcements/${item.id}`}
            className="inline-flex min-h-10 items-center rounded-lg border bg-card px-4 py-2 text-sm font-semibold no-underline hover:bg-muted"
          >
            View public page
          </Link>
        ) : null}
      </header>

      {item.status === "PUBLISHED" ? (
        <p className="rounded-lg border border-[var(--compass-support)]/25 bg-accent/50 p-3 text-sm">
          Changes to a published announcement are visible to its audience as soon as you save them.
        </p>
      ) : null}

      {error ? (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <section className="space-y-5 rounded-xl border bg-card p-5 sm:p-6">
          <div className="space-y-2">
            <Label htmlFor="announcement-title">Title</Label>
            <Input
              id="announcement-title"
              value={title}
              maxLength={200}
              disabled={readOnly || pending}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Content</Label>
            <RichMarkdownEditor
              initialValue={item.body_markdown}
              onChange={setBody}
              disabled={readOnly || pending}
              ariaLabel="Announcement content"
            />
          </div>
        </section>

        <aside className="space-y-5">
          <section className="space-y-5 rounded-xl border bg-card p-5">
            <AudienceField
              id="announcement-audience"
              value={audience}
              onChange={(value) => setAudience(value as AnnouncementAudienceValue)}
              disabled={readOnly || pending}
            />
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1 size-4"
                checked={pinned}
                disabled={readOnly || pending}
                onChange={(event) => setPinned(event.target.checked)}
              />
              <span className="font-semibold">Pin this announcement</span>
            </label>
            <div className="space-y-2">
              <Label htmlFor="announcement-expiry">Expires at (optional)</Label>
              <Input
                id="announcement-expiry"
                type="datetime-local"
                value={expiresAt}
                disabled={readOnly || pending}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
              <p className="text-xs leading-5 text-muted-foreground">
                Expiry changes visibility; it does not archive the announcement.
              </p>
              {item.status === "PUBLISHED" &&
              expiresAt &&
              expiryIso &&
              Date.parse(expiryIso) <= Date.now() ? (
                <p className="text-xs font-semibold text-[var(--compass-warning)]">
                  Once saved, this announcement will no longer be visible to readers.
                </p>
              ) : null}
            </div>
          </section>

          <MetadataPanel item={item} />
        </aside>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {!readOnly ? (
          <Button onClick={() => void save()} disabled={pending || !dirty}>
            {update.isPending ? "Saving…" : item.status === "PUBLISHED" ? "Save changes" : "Save draft"}
          </Button>
        ) : null}
        <PreviewDialog title={title} markdown={body} />

        {item.status === "DRAFT" ? (
          <ConfirmationDialog
            triggerLabel="Publish"
            title="Publish announcement?"
            confirmLabel="Publish"
            pendingLabel="Publishing…"
            isPending={publish.isPending || update.isPending}
            disabled={pending || Boolean(publicationProblem())}
            onConfirm={publishAnnouncement}
          >
            <p><strong>Title:</strong> {title.trim() || "Untitled"}</p>
            <p><strong>Audience:</strong> {audienceLabel(audience)}</p>
            <p><strong>Pinned:</strong> {pinned ? "Yes" : "No"}</p>
            {expiryIso ? <p><strong>Expiry:</strong> {formatContentDateTime(expiryIso)}</p> : null}
            {audience === "PUBLIC" ? (
              <p>This announcement will be visible to anyone visiting the public COMPASS site.</p>
            ) : null}
            <p>
              Publishing is immediate. The announcement cannot return to Draft, but published
              content may still be corrected until it is archived.
            </p>
          </ConfirmationDialog>
        ) : null}

        {!readOnly ? (
          <ConfirmationDialog
            triggerLabel="Archive"
            title="Archive announcement?"
            confirmLabel="Archive"
            confirmVariant="destructive"
            pendingLabel="Archiving…"
            isPending={archive.isPending}
            disabled={pending}
            onConfirm={archiveAnnouncement}
          >
            <p>Archived items cannot be edited or published again.</p>
            {dirty ? <p>Your unsaved changes will not be saved before archiving.</p> : null}
          </ConfirmationDialog>
        ) : null}

        {dirty && !readOnly ? (
          <span className="text-sm font-medium text-[var(--compass-warning)]">Unsaved changes</span>
        ) : null}
      </div>
    </div>
  );
}

function MetadataPanel({ item }: { item: AnnouncementManagementResponse }) {
  return (
    <section className="rounded-xl border bg-card p-5">
      <h2 className="font-heading text-lg font-bold">Details</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <MetadataRow label="Created by" value={item.created_by.display_name} />
        <MetadataRow label="Created" value={formatContentDateTime(item.created_at)} />
        <MetadataRow label="Last updated by" value={item.updated_by.display_name} />
        <MetadataRow label="Last updated" value={formatContentDateTime(item.updated_at)} />
        {item.published_by ? (
          <MetadataRow label="Published by" value={item.published_by.display_name} />
        ) : null}
        {item.published_at ? (
          <MetadataRow label="Published at" value={formatContentDateTime(item.published_at)} />
        ) : null}
      </dl>
    </section>
  );
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}
