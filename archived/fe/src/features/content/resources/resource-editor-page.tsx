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
  RESOURCE_CATEGORY_OPTIONS,
  RESOURCE_KIND_OPTIONS,
  audienceLabel,
  contentMutationError,
  formatContentDateTime,
  formatFileSize,
  isSafeExternalHttpUrl,
  resourceCategoryLabel,
  resourceKindLabel,
} from "@/features/content/presentation";
import { ResourceFilePanel } from "@/features/content/resources/resource-file-panel";
import { isUuid } from "@/features/public/utils";
import {
  getResourcesGetManagedQueryKey,
  getResourcesGetPublicQueryKey,
  getResourcesGetVisibleQueryKey,
  getResourcesListManagedQueryKey,
  getResourcesListPublicQueryKey,
  getResourcesListVisibleQueryKey,
  useResourcesArchive,
  useResourcesGetManaged,
  useResourcesPublish,
  useResourcesUpdate,
} from "@/lib/api/generated/resources/resources";
import type {
  ResourceAudienceValue,
  ResourceCategoryValue,
  ResourceKindValue,
  ResourceManagementResponse,
} from "@/lib/api/generated/model";

export function ResourceEditorPage({ resourceId }: { resourceId: string }) {
  return (
    <CapabilityGate capability="resources.manage">
      <ResourceEditorLoader resourceId={resourceId} />
    </CapabilityGate>
  );
}

function ResourceEditorLoader({ resourceId }: { resourceId: string }) {
  const validId = isUuid(resourceId);
  const query = useResourcesGetManaged(resourceId, {
    query: { enabled: validId, retry: false },
  });

  if (!validId) {
    return <UnavailableResource />;
  }

  if (query.isPending) {
    return <p role="status" className="text-sm text-muted-foreground">Loading resource…</p>;
  }

  if (query.isError || !query.data?.data) {
    return (
      <section className="rounded-xl border bg-card p-6">
        <h1 className="font-heading text-2xl font-bold">Resource unavailable</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          This resource could not be loaded or is no longer available to manage.
        </p>
        <Button className="mt-4" variant="outline" onClick={() => void query.refetch()}>
          Try again
        </Button>
      </section>
    );
  }

  return (
    <ResourceEditor
      key={`${query.data.data.id}:${query.data.data.updated_at}`}
      item={query.data.data}
    />
  );
}

function UnavailableResource() {
  return (
    <section className="rounded-xl border bg-card p-6">
      <h1 className="font-heading text-2xl font-bold">Resource unavailable</h1>
      <p className="mt-2 text-sm text-muted-foreground">This resource could not be found.</p>
      <Link href="/portal/content/resources" className="mt-4 inline-block font-semibold no-underline">
        Back to Resources
      </Link>
    </section>
  );
}

function ResourceEditor({ item }: { item: ResourceManagementResponse }) {
  const queryClient = useQueryClient();
  const update = useResourcesUpdate();
  const publish = useResourcesPublish();
  const archive = useResourcesArchive();

  const [title, setTitle] = useState(item.title);
  const [body, setBody] = useState(item.body_markdown);
  const [category, setCategory] = useState<ResourceCategoryValue>(item.category);
  const [kind, setKind] = useState<ResourceKindValue>(item.kind);
  const [audience, setAudience] = useState<ResourceAudienceValue>(item.audience);
  const [externalUrl, setExternalUrl] = useState(item.external_url ?? "");
  const [displayOrder, setDisplayOrder] = useState(String(item.display_order));
  const [error, setError] = useState<string | null>(null);

  const readOnly = item.status === "ARCHIVED";
  const kindLocked = item.status === "PUBLISHED" || item.has_file;
  const pending = update.isPending || publish.isPending || archive.isPending;
  const order = Number(displayOrder);
  const normalizedExternalUrl = externalUrl.trim();
  const dirty =
    title !== item.title ||
    body !== item.body_markdown ||
    category !== item.category ||
    kind !== item.kind ||
    audience !== item.audience ||
    (kind === "EXTERNAL_LINK" ? normalizedExternalUrl : "") !== (item.external_url ?? "") ||
    (Number.isInteger(order) ? order : displayOrder) !== item.display_order;

  useUnsavedChanges(dirty && !pending);

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getResourcesListManagedQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getResourcesGetManagedQueryKey(item.id) }),
      queryClient.invalidateQueries({ queryKey: getResourcesListVisibleQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getResourcesGetVisibleQueryKey(item.id) }),
      queryClient.invalidateQueries({ queryKey: getResourcesListPublicQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getResourcesGetPublicQueryKey(item.id) }),
    ]);
  }

  function localProblem(forPublish: boolean): string | null {
    if (!Number.isInteger(order)) {
      return "Display order must be a whole number.";
    }
    if (kind === "EXTERNAL_LINK") {
      if (forPublish && !normalizedExternalUrl) {
        return "Add an external URL before publishing.";
      }
      if (normalizedExternalUrl && !isSafeExternalHttpUrl(normalizedExternalUrl)) {
        return "External URL must be a valid http or https address without embedded credentials.";
      }
    }
    if (forPublish && !title.trim()) {
      return "Add a title before publishing.";
    }
    if (forPublish && !body.trim()) {
      return "Add resource content before publishing.";
    }
    if (forPublish && kind === "FILE" && !item.has_file) {
      return "Attach a PDF before publishing this resource.";
    }
    return null;
  }

  function updatePayload() {
    return {
      title,
      body_markdown: body,
      category,
      kind,
      audience,
      external_url: kind === "EXTERNAL_LINK" ? normalizedExternalUrl || null : null,
      display_order: order,
    };
  }

  async function save() {
    setError(null);
    const problem = localProblem(item.status === "PUBLISHED");
    if (problem) {
      setError(problem);
      return false;
    }

    try {
      await update.mutateAsync({
        resourceId: item.id,
        data: updatePayload(),
      });
      await invalidate();
      return true;
    } catch (caught) {
      setError(contentMutationError(caught, "resource"));
      return false;
    }
  }

  function publicationProblem(): string | null {
    return localProblem(true);
  }

  async function publishResource() {
    setError(null);
    const problem = publicationProblem();
    if (problem) {
      setError(problem);
      return;
    }

    try {
      if (dirty) {
        await update.mutateAsync({
          resourceId: item.id,
          data: updatePayload(),
        });
      }
      await publish.mutateAsync({ resourceId: item.id });
      await invalidate();
    } catch (caught) {
      setError(contentMutationError(caught, "resource"));
      throw caught;
    }
  }

  async function archiveResource() {
    setError(null);
    try {
      await archive.mutateAsync({ resourceId: item.id });
      await invalidate();
    } catch (caught) {
      setError(contentMutationError(caught, "resource"));
      throw caught;
    }
  }

  const publicLink = item.status === "PUBLISHED" && item.audience === "PUBLIC";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Link href="/portal/content/resources" className="text-sm font-semibold no-underline">
            ← Resources
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-heading text-3xl font-bold tracking-tight">
              {item.title.trim() || "Untitled draft"}
            </h1>
            <PublicationStatusBadge status={item.status} />
          </div>
        </div>
        {publicLink ? (
          <Link
            href={`/resources/${item.id}`}
            className="inline-flex min-h-10 items-center rounded-lg border bg-card px-4 py-2 text-sm font-semibold no-underline hover:bg-muted"
          >
            View public page
          </Link>
        ) : null}
      </header>

      {item.status === "PUBLISHED" ? (
        <p className="rounded-lg border border-[var(--compass-support)]/25 bg-accent/50 p-3 text-sm">
          Changes to a published resource are visible to its audience as soon as you save them.
        </p>
      ) : null}

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
              ariaLabel="Resource content"
            />
          </div>
        </section>

        <aside className="space-y-5">
          <section className="space-y-5 rounded-xl border bg-card p-5">
            <div className="space-y-2">
              <Label htmlFor="resource-kind">Resource type</Label>
              <select
                id="resource-kind"
                value={kind}
                disabled={readOnly || pending || kindLocked}
                onChange={(event) => {
                  const next = event.target.value as ResourceKindValue;
                  setKind(next);
                  if (next !== "EXTERNAL_LINK") {
                    setExternalUrl("");
                  }
                }}
                className="min-h-10 w-full rounded-lg border bg-card px-3 py-2 text-sm disabled:opacity-70"
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
              {item.status === "DRAFT" && item.has_file ? (
                <p className="text-xs leading-5 text-muted-foreground">
                  The resource type is locked because a PDF is already attached.
                </p>
              ) : null}
              {item.status === "PUBLISHED" ? (
                <p className="text-xs text-muted-foreground">
                  Published resource type cannot be changed.
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor="resource-category">Category</Label>
              <select
                id="resource-category"
                value={category}
                disabled={readOnly || pending}
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
              onChange={(value) => setAudience(value as ResourceAudienceValue)}
              disabled={readOnly || pending}
            />

            {kind === "EXTERNAL_LINK" ? (
              <div className="space-y-2">
                <Label htmlFor="resource-external-url">External URL</Label>
                <Input
                  id="resource-external-url"
                  type="url"
                  value={externalUrl}
                  disabled={readOnly || pending}
                  onChange={(event) => setExternalUrl(event.target.value)}
                />
              </div>
            ) : null}

            {item.status === "DRAFT" && kind === "FILE" && item.kind !== "FILE" ? (
              <p className="rounded-lg bg-muted p-3 text-xs leading-5 text-muted-foreground">
                Save the draft as a PDF file resource before attaching the document.
              </p>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="resource-display-order">Display order</Label>
              <Input
                id="resource-display-order"
                type="number"
                step="1"
                value={displayOrder}
                disabled={readOnly || pending}
                onChange={(event) => setDisplayOrder(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Lower numbers appear earlier in Resource listings.
              </p>
            </div>
          </section>

          <ResourceFilePanel item={item} disabled={pending || readOnly} />
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
            title="Publish resource?"
            confirmLabel="Publish"
            pendingLabel="Publishing…"
            isPending={publish.isPending || update.isPending}
            disabled={pending || Boolean(publicationProblem())}
            onConfirm={publishResource}
          >
            <p><strong>Title:</strong> {title.trim() || "Untitled"}</p>
            <p><strong>Type:</strong> {resourceKindLabel(kind)}</p>
            <p><strong>Category:</strong> {resourceCategoryLabel(category)}</p>
            <p><strong>Audience:</strong> {audienceLabel(audience)}</p>
            {kind === "FILE" && item.has_file ? (
              <>
                <p><strong>Filename:</strong> {item.original_filename || "Attached PDF"}</p>
                <p><strong>File size:</strong> {formatFileSize(item.size_bytes)}</p>
              </>
            ) : null}
            {kind === "EXTERNAL_LINK" && normalizedExternalUrl ? (
              <p><strong>External destination:</strong> {normalizedExternalUrl}</p>
            ) : null}
            {audience === "PUBLIC" ? (
              <p>This resource will be visible to anyone visiting the public COMPASS site.</p>
            ) : null}
            <p>Publishing is immediate and the item cannot return to Draft.</p>
            {kind === "FILE" ? (
              <p>
                The PDF cannot be replaced after publishing. Archive this resource and create a
                new one if the document itself must be replaced later.
              </p>
            ) : null}
          </ConfirmationDialog>
        ) : null}

        {!readOnly ? (
          <ConfirmationDialog
            triggerLabel="Archive"
            title="Archive resource?"
            confirmLabel="Archive"
            confirmVariant="destructive"
            pendingLabel="Archiving…"
            isPending={archive.isPending}
            disabled={pending}
            onConfirm={archiveResource}
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

function MetadataPanel({ item }: { item: ResourceManagementResponse }) {
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
