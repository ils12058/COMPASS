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
  RESOURCE_CATEGORY_OPTIONS,
  RESOURCE_KIND_OPTIONS,
  contentMutationError,
  isSafeExternalHttpUrl,
} from "@/features/content/presentation";
import { useResourcesCreateDraft } from "@/lib/api/generated/resources/resources";
import type {
  ResourceAudienceValue,
  ResourceCategoryValue,
  ResourceKindValue,
} from "@/lib/api/generated/model";

export function ResourceCreatePage() {
  return (
    <CapabilityGate capability="resources.manage">
      <ResourceCreatePageInner />
    </CapabilityGate>
  );
}

function ResourceCreatePageInner() {
  const router = useRouter();
  const createDraft = useResourcesCreateDraft();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState<ResourceCategoryValue>("GENERAL");
  const [kind, setKind] = useState<ResourceKindValue>("ARTICLE");
  const [audience, setAudience] = useState<ResourceAudienceValue | "">("");
  const [externalUrl, setExternalUrl] = useState("");
  const [displayOrder, setDisplayOrder] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const isDirty =
    Boolean(title || body || audience || externalUrl) ||
    category !== "GENERAL" ||
    kind !== "ARTICLE" ||
    displayOrder !== "0";
  useUnsavedChanges(isDirty && !createDraft.isPending);

  async function saveDraft() {
    setError(null);
    if (!audience) {
      setError("Choose who can read this resource before saving the draft.");
      return;
    }

    const order = Number(displayOrder);
    if (!Number.isInteger(order)) {
      setError("Display order must be a whole number.");
      return;
    }

    const normalizedUrl = externalUrl.trim();
    if (kind === "EXTERNAL_LINK" && normalizedUrl && !isSafeExternalHttpUrl(normalizedUrl)) {
      setError("External URL must be a valid http or https address without embedded credentials.");
      return;
    }

    try {
      const result = await createDraft.mutateAsync({
        data: {
          title,
          body_markdown: body,
          category,
          kind,
          audience,
          external_url: kind === "EXTERNAL_LINK" ? normalizedUrl || null : null,
          display_order: order,
        },
      });
      router.replace(`/portal/content/resources/${result.data.id}`);
    } catch (caught) {
      setError(contentMutationError(caught, "resource"));
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link href="/portal/content/resources" className="text-sm font-semibold no-underline">
          ← Resources
        </Link>
        <h1 className="font-heading text-3xl font-bold tracking-tight">New resource</h1>
        <p className="max-w-2xl text-muted-foreground">
          Create the draft first. PDF files are attached from the edit page after COMPASS creates
          the resource record.
        </p>
      </header>

      {error ? (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="space-y-5 rounded-xl border bg-card p-5 sm:p-6">
          <div className="space-y-2">
            <Label htmlFor="resource-title">Title</Label>
            <Input
              id="resource-title"
              value={title}
              maxLength={200}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Resource title"
              disabled={createDraft.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label>Content</Label>
            <RichMarkdownEditor
              initialValue=""
              onChange={setBody}
              disabled={createDraft.isPending}
              ariaLabel="Resource content"
            />
          </div>
        </section>

        <aside className="space-y-5 rounded-xl border bg-card p-5">
          <div className="space-y-2">
            <Label htmlFor="resource-kind">Resource type</Label>
            <select
              id="resource-kind"
              value={kind}
              disabled={createDraft.isPending}
              onChange={(event) => {
                const next = event.target.value as ResourceKindValue;
                setKind(next);
                if (next !== "EXTERNAL_LINK") {
                  setExternalUrl("");
                }
              }}
              className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 text-sm"
            >
              {RESOURCE_KIND_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="text-xs leading-5 text-muted-foreground">
              {RESOURCE_KIND_OPTIONS.find((option) => option.value === kind)?.description}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="resource-category">Category</Label>
            <select
              id="resource-category"
              value={category}
              disabled={createDraft.isPending}
              onChange={(event) => setCategory(event.target.value as ResourceCategoryValue)}
              className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 text-sm"
            >
              {RESOURCE_CATEGORY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <AudienceField
            id="resource-audience"
            value={audience}
            onChange={(value) => setAudience(value as ResourceAudienceValue | "")}
            disabled={createDraft.isPending}
          />

          {kind === "EXTERNAL_LINK" ? (
            <div className="space-y-2">
              <Label htmlFor="resource-external-url">External URL</Label>
              <Input
                id="resource-external-url"
                type="url"
                value={externalUrl}
                placeholder="https://example.org/guide"
                disabled={createDraft.isPending}
                onChange={(event) => setExternalUrl(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                A valid http or https address is required before publication.
              </p>
            </div>
          ) : null}

          {kind === "FILE" ? (
            <p className="rounded-lg bg-muted p-3 text-xs leading-5 text-muted-foreground">
              Save this draft first. You can attach the PDF on the resource edit page.
            </p>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="resource-display-order">Display order</Label>
            <Input
              id="resource-display-order"
              type="number"
              step="1"
              value={displayOrder}
              disabled={createDraft.isPending}
              onChange={(event) => setDisplayOrder(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Lower numbers appear earlier in Resource listings.
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
