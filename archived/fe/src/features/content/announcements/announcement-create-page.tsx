"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AudienceField } from "@/features/content/components/audience-field";
import { CapabilityGate } from "@/features/content/components/capability-gate";
import { PreviewDialog } from "@/features/content/components/preview-dialog";
import { RichMarkdownEditor } from "@/features/content/components/rich-markdown-editor";
import { useUnsavedChanges } from "@/features/content/hooks/use-unsaved-changes";
import {
  contentMutationError,
  fromDateTimeLocal,
} from "@/features/content/presentation";
import { useAnnouncementsCreateDraft } from "@/lib/api/generated/announcements/announcements";
import type { AnnouncementAudienceValue } from "@/lib/api/generated/model";

export function AnnouncementCreatePage() {
  return (
    <CapabilityGate capability="announcements.manage">
      <AnnouncementCreatePageInner />
    </CapabilityGate>
  );
}

function AnnouncementCreatePageInner() {
  const router = useRouter();
  const createDraft = useAnnouncementsCreateDraft();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState<AnnouncementAudienceValue | "">("");
  const [pinned, setPinned] = useState(false);
  const [expiresAt, setExpiresAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const isDirty = Boolean(title || body || audience || pinned || expiresAt);
  useUnsavedChanges(isDirty && !createDraft.isPending);

  async function saveDraft() {
    setError(null);
    if (!audience) {
      setError("Choose who can read this announcement before saving the draft.");
      return;
    }

    const expiry = fromDateTimeLocal(expiresAt);
    if (expiresAt && !expiry) {
      setError("Enter a valid expiry date and time.");
      return;
    }

    try {
      const result = await createDraft.mutateAsync({
        data: {
          title,
          body_markdown: body,
          audience,
          is_pinned: pinned,
          expires_at: expiry,
        },
      });
      router.replace(`/portal/content/announcements/${result.data.id}`);
    } catch (caught) {
      setError(contentMutationError(caught, "announcement"));
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link href="/portal/content/announcements" className="text-sm font-semibold no-underline">
          ← Announcements
        </Link>
        <h1 className="font-heading text-3xl font-bold tracking-tight">New announcement</h1>
        <p className="max-w-2xl text-muted-foreground">
          Start a draft now. You can complete and publish it from the edit page after it is saved.
        </p>
      </header>

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
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Announcement title"
              disabled={createDraft.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label>Content</Label>
            <RichMarkdownEditor
              initialValue=""
              onChange={setBody}
              disabled={createDraft.isPending}
              ariaLabel="Announcement content"
            />
          </div>
        </section>

        <aside className="space-y-5 rounded-xl border bg-card p-5">
          <AudienceField
            id="announcement-audience"
            value={audience}
            onChange={(value) => setAudience(value as AnnouncementAudienceValue | "")}
            disabled={createDraft.isPending}
          />

          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className="mt-1 size-4"
              checked={pinned}
              disabled={createDraft.isPending}
              onChange={(event) => setPinned(event.target.checked)}
            />
            <span>
              <span className="block font-semibold">Pin this announcement</span>
              <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                Pinned announcements appear first in reader lists.
              </span>
            </span>
          </label>

          <div className="space-y-2">
            <Label htmlFor="announcement-expiry">Expires at (optional)</Label>
            <Input
              id="announcement-expiry"
              type="datetime-local"
              value={expiresAt}
              disabled={createDraft.isPending}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
            <p className="text-xs leading-5 text-muted-foreground">
              Expiry controls reader visibility. It does not schedule publication.
            </p>
          </div>
        </aside>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => void saveDraft()} disabled={createDraft.isPending}>
          {createDraft.isPending ? "Saving…" : "Save draft"}
        </Button>
        <PreviewDialog title={title} markdown={body} />
        {isDirty ? (
          <span className="text-sm font-medium text-[var(--compass-warning)]">Unsaved changes</span>
        ) : null}
      </div>
    </div>
  );
}
