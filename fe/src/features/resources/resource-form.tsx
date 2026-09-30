"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  publicationAudienceLabels,
  publicationAudienceReaders,
  type PublicationAudience,
} from "@/features/content/content-presentation";
import {
  AudienceField,
  ContentConfirmDialog,
  contentSecondaryLinkClass,
  contentSelectClass,
} from "@/features/content/content-shared";
import { MarkdownEditor } from "@/features/content/markdown-editor/markdown-editor";
import { useMarkdownValue } from "@/features/content/markdown-editor/use-markdown-value";
import { useUnsavedChangesGuard } from "@/features/content/use-unsaved-changes-guard";
import { resourceCategoryLabels, resourceKindLabels } from "@/features/public/shared/presentation";
import { refreshResourceQueries, storeManagedResource } from "@/features/resources/resource-cache";
import {
  isUncertainResourceMutation,
  resourceErrorCode,
  resourceErrorMessage,
} from "@/features/resources/resource-errors";
import { isHttpUrl, resourceBodyHints, resourceKindDescriptions } from "@/features/resources/resource-presentation";
import {
  getResourcesListManagedQueryKey,
  useResourcesCreateDraft,
  useResourcesUpdate,
} from "@/lib/api/generated/resources/resources";
import {
  ResourceAudienceValue,
  ResourceCategoryValue,
  ResourceKindValue,
  ResourceStatusValue,
  type ResourceManagementResponse,
  type ResourceUpdateRequest,
} from "@/lib/api/generated/model";

type ResourceFields = {
  title: string;
  kind: ResourceKindValue | null;
  category: ResourceCategoryValue | null;
  audience: PublicationAudience | null;
  externalUrl: string;
  displayOrder: string;
};

type FieldName = keyof ResourceFields | "body";

const fieldTargets: Record<FieldName, string> = {
  title: "resource-title",
  kind: "resource-kind-article",
  externalUrl: "resource-external-url",
  category: "resource-category",
  audience: "resource-audience-public",
  displayOrder: "resource-display-order",
  body: "resource-body",
};

const INT32_MIN = -(2 ** 31);
const INT32_MAX = 2 ** 31 - 1;

function fieldsFrom(item: ResourceManagementResponse | null): ResourceFields {
  return item
    ? {
        title: item.title,
        kind: item.kind,
        category: item.category,
        audience: item.audience,
        externalUrl: item.external_url ?? "",
        displayOrder: String(item.display_order),
      }
    : { title: "", kind: null, category: null, audience: null, externalUrl: "", displayOrder: "0" };
}

function parseDisplayOrder(value: string): number | null {
  const trimmed = value.trim();
  if (!/^-?\d+$/.test(trimmed)) return null;
  const parsed = Number(trimmed);
  return parsed >= INT32_MIN && parsed <= INT32_MAX ? parsed : null;
}

// Only External link Resources keep a link address.
function effectiveUrl(fields: ResourceFields): string {
  return fields.kind === ResourceKindValue.EXTERNAL_LINK ? fields.externalUrl.trim() : "";
}

function reviewUrl(value: string | null | undefined): string {
  const normalized = (value ?? "").trim();
  if (normalized.length <= 96) return normalized || "No destination";
  return `${normalized.slice(0, 58)}…${normalized.slice(-28)}`;
}

export function ResourceForm({ resource }: { resource: ResourceManagementResponse | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = useResourcesCreateDraft();
  const update = useResourcesUpdate();
  const [saved, setSaved] = useState(() => fieldsFrom(resource));
  const [values, setValues] = useState(() => fieldsFrom(resource));
  const body = useMarkdownValue(resource?.body_markdown ?? "");
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewPayload, setReviewPayload] = useState<ResourceUpdateRequest | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const isPublished = resource?.status === ResourceStatusValue.PUBLISHED;
  const kindLockedReason = isPublished
    ? "The type cannot be changed after the Resource is published."
    : resource?.has_file
      ? "Remove the attached file before changing the type."
      : null;
  const saving = create.isPending || update.isPending;
  const dirty =
    values.title.trim() !== saved.title.trim() ||
    values.kind !== saved.kind ||
    values.category !== saved.category ||
    values.audience !== saved.audience ||
    effectiveUrl(values) !== effectiveUrl(saved) ||
    values.displayOrder.trim() !== saved.displayOrder.trim() ||
    body.changed;

  useUnsavedChangesGuard(dirty, "Discard your unsaved Resource changes?");

  function setField<K extends keyof ResourceFields>(key: K, value: ResourceFields[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setNotice(null);
  }

  function validate(currentBody: string) {
    const next: Partial<Record<FieldName, string>> = {};
    if (!values.title.trim()) next.title = "Enter a title.";
    if (!values.kind) next.kind = "Choose a Resource type.";
    const url = effectiveUrl(values);
    if (values.kind === ResourceKindValue.EXTERNAL_LINK) {
      if (url && !isHttpUrl(url)) next.externalUrl = "Enter a link address that starts with https:// or http://.";
      else if (!url && isPublished) next.externalUrl = "A published External link Resource needs a link address.";
    }
    if (!values.category) next.category = "Choose a category.";
    if (!values.audience) next.audience = "Choose who can see this Resource.";
    if (parseDisplayOrder(values.displayOrder) === null) next.displayOrder = "Enter a whole number, such as 0 or 10.";
    if (isPublished && !currentBody.trim()) next.body = "A published Resource needs body text.";
    return next;
  }

  async function saveExisting(
    payload: ResourceUpdateRequest,
    acknowledgePublicationConsequences = false,
  ) {
    if (!resource) return;
    try {
      const data: ResourceUpdateRequest = acknowledgePublicationConsequences
        ? { ...payload, acknowledge_publication_consequences: true }
        : payload;
      const response = await update.mutateAsync({
        resourceId: resource.id,
        data,
      });
      const published = response.data.status === ResourceStatusValue.PUBLISHED;
      storeManagedResource(queryClient, response);
      void refreshResourceQueries(queryClient, resource.id, { readers: published });
      setSaved(fieldsFrom(response.data));
      if (payload.body_markdown !== undefined) body.markSaved(response.data.body_markdown);
      setReviewOpen(false);
      setReviewPayload(null);
      setReviewError(null);
      setNotice(published ? "Changes saved. Readers now see the updated Resource." : "Draft saved.");
    } catch (caught) {
      if (
        !acknowledgePublicationConsequences &&
        resourceErrorCode(caught) === "publication_consequence_review_required"
      ) {
        setReviewPayload(payload);
        setReviewError(null);
        setReviewOpen(true);
        return;
      }
      const message = isUncertainResourceMutation(caught)
        ? "The changes could not be confirmed as saved. Save again to make sure they are kept."
        : resourceErrorMessage(caught, "The changes could not be saved.");
      if (acknowledgePublicationConsequences) setReviewError(message);
      else setFormError(message);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setFormError(null);
    setNotice(null);
    const currentBody = body.readCurrent();
    const found = validate(currentBody);
    setErrors(found);
    const firstInvalid = (Object.keys(fieldTargets) as FieldName[]).find((name) => found[name]);
    const displayOrder = parseDisplayOrder(values.displayOrder);
    if (firstInvalid || !values.kind || !values.category || !values.audience || displayOrder === null) {
      if (firstInvalid) document.getElementById(fieldTargets[firstInvalid])?.focus();
      return;
    }
    const url = effectiveUrl(values);

    if (!resource) {
      try {
        const response = await create.mutateAsync({
          data: {
            title: values.title.trim(),
            body_markdown: currentBody,
            kind: values.kind,
            category: values.category,
            audience: values.audience,
            external_url: url || null,
            display_order: displayOrder,
          },
        });
        void queryClient.invalidateQueries({ queryKey: getResourcesListManagedQueryKey() });
        router.replace(`/portal/resources/${response.data.id}?notice=created`);
      } catch (caught) {
        setFormError(
          isUncertainResourceMutation(caught)
            ? "The draft could not be confirmed as saved. Check the Resources list before saving again."
            : resourceErrorMessage(caught, "The draft could not be saved."),
        );
      }
      return;
    }

    // PATCH applies only the fields sent. A link address is cleared when the
    // type changes away from External link, as the backend requires.
    const payload: ResourceUpdateRequest = {};
    if (values.title.trim() !== saved.title.trim()) payload.title = values.title.trim();
    const changedBody = body.readChanged();
    if (changedBody !== null) payload.body_markdown = changedBody;
    if (values.kind !== saved.kind) payload.kind = values.kind;
    if (values.category !== saved.category) payload.category = values.category;
    if (values.audience !== saved.audience) payload.audience = values.audience;
    if (url !== effectiveUrl(saved)) payload.external_url = url || null;
    if (displayOrder !== parseDisplayOrder(saved.displayOrder)) payload.display_order = displayOrder;
    if (Object.keys(payload).length === 0) return;

    const consequenceReviewNeeded =
      isPublished &&
      (payload.audience !== undefined ||
        (resource.kind === ResourceKindValue.EXTERNAL_LINK &&
          payload.external_url !== undefined));
    if (consequenceReviewNeeded) {
      setReviewPayload(payload);
      setReviewError(null);
      setReviewOpen(true);
      return;
    }
    await saveExisting(payload);
  }

  const submitLabel = isPublished ? "Save changes" : "Save draft";
  const pendingLabel = isPublished ? "Saving changes…" : "Saving draft…";
  const kindHintId = kindLockedReason ? "resource-kind-locked" : undefined;

  const reviewedAudience = reviewPayload?.audience;
  const reviewedDestinationChanged =
    resource?.kind === ResourceKindValue.EXTERNAL_LINK &&
    reviewPayload?.external_url !== undefined;

  return (
    <>
    <form className="mt-8 space-y-8" onSubmit={(event) => void submit(event)} noValidate>
      <div className="grid gap-2">
        <Label htmlFor="resource-title">Title</Label>
        <Input
          id="resource-title"
          value={values.title}
          maxLength={200}
          aria-invalid={errors.title ? true : undefined}
          aria-describedby={errors.title ? "resource-title-error" : undefined}
          onChange={(event) => setField("title", event.target.value)}
        />
        {errors.title ? <p id="resource-title-error" className="text-sm text-danger">{errors.title}</p> : null}
      </div>

      <fieldset aria-describedby={[kindHintId, errors.kind ? "resource-kind-error" : undefined].filter(Boolean).join(" ") || undefined}>
        <legend className="text-sm font-semibold text-ink">Type</legend>
        {kindLockedReason ? (
          <p id="resource-kind-locked" className="mt-1 text-xs leading-5 text-muted">{kindLockedReason}</p>
        ) : null}
        {errors.kind ? <p id="resource-kind-error" className="mt-1 text-sm text-danger">{errors.kind}</p> : null}
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {Object.values(ResourceKindValue).map((kind) => {
            const id = `resource-kind-${kind.toLowerCase().replace("_", "-")}`;
            const disabled = kindLockedReason !== null && kind !== saved.kind;
            return (
              <label
                key={kind}
                htmlFor={id}
                className={
                  "flex gap-3 rounded-md border border-border bg-surface-raised px-3 py-3 has-[:checked]:border-brand has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-focus " +
                  (disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer")
                }
              >
                <input
                  id={id}
                  type="radio"
                  name="resource-kind"
                  value={kind}
                  checked={values.kind === kind}
                  disabled={disabled}
                  aria-labelledby={`${id}-label`}
                  aria-describedby={`${id}-description`}
                  onChange={() => setField("kind", kind)}
                  className="mt-1 h-4 w-4 shrink-0 accent-brand focus-visible:outline-none"
                />
                <span>
                  <span id={`${id}-label`} className="block text-sm font-semibold text-ink">{resourceKindLabels[kind]}</span>
                  <span id={`${id}-description`} className="mt-0.5 block text-xs leading-5 text-muted">{resourceKindDescriptions[kind]}</span>
                </span>
              </label>
            );
          })}
        </div>
        {values.kind === ResourceKindValue.FILE && !resource ? (
          <p className="mt-3 text-xs leading-5 text-muted">Attach the PDF after you save the draft.</p>
        ) : null}
      </fieldset>

      {values.kind === ResourceKindValue.EXTERNAL_LINK ? (
        <div className="grid gap-2">
          <Label htmlFor="resource-external-url">Link address</Label>
          <Input
            id="resource-external-url"
            type="url"
            inputMode="url"
            value={values.externalUrl}
            maxLength={2048}
            placeholder="https://"
            aria-invalid={errors.externalUrl ? true : undefined}
            aria-describedby={`resource-external-url-hint${errors.externalUrl ? " resource-external-url-error" : ""}`}
            onChange={(event) => setField("externalUrl", event.target.value)}
          />
          <p id="resource-external-url-hint" className="text-xs leading-5 text-muted">
            Readers open this address in a new tab. It is required before publishing.
          </p>
          {errors.externalUrl ? (
            <p id="resource-external-url-error" className="text-sm text-danger">{errors.externalUrl}</p>
          ) : null}
        </div>
      ) : null}

      <div className="grid gap-6 border-t border-border pt-7 md:grid-cols-2">
        <div className="grid content-start gap-2">
          <Label htmlFor="resource-category">Category</Label>
          <select
            id="resource-category"
            className={contentSelectClass}
            value={values.category ?? ""}
            aria-invalid={errors.category ? true : undefined}
            aria-describedby={errors.category ? "resource-category-error" : undefined}
            onChange={(event) => {
              const next = Object.values(ResourceCategoryValue).find((value) => value === event.target.value);
              setField("category", next ?? null);
            }}
          >
            <option value="" disabled>Choose a category</option>
            {Object.values(ResourceCategoryValue).map((value) => (
              <option key={value} value={value}>{resourceCategoryLabels[value]}</option>
            ))}
          </select>
          {errors.category ? <p id="resource-category-error" className="text-sm text-danger">{errors.category}</p> : null}
        </div>
        <div className="grid content-start gap-2">
          <Label htmlFor="resource-display-order">Display order</Label>
          <Input
            id="resource-display-order"
            type="number"
            inputMode="numeric"
            step={1}
            className="max-w-40"
            value={values.displayOrder}
            aria-invalid={errors.displayOrder ? true : undefined}
            aria-describedby={`resource-display-order-hint${errors.displayOrder ? " resource-display-order-error" : ""}`}
            onChange={(event) => setField("displayOrder", event.target.value)}
          />
          <p id="resource-display-order-hint" className="text-xs leading-5 text-muted">
            Lower numbers are listed first. Resources with the same number are listed newest first.
          </p>
          {errors.displayOrder ? (
            <p id="resource-display-order-error" className="text-sm text-danger">{errors.displayOrder}</p>
          ) : null}
        </div>
      </div>

      <AudienceField
        name="resource-audience"
        value={values.audience}
        error={errors.audience}
        onChange={(audience) => setField("audience", audience)}
      />

      <div className="grid gap-2 border-t border-border pt-7">
        <p id="resource-body-label" className="text-sm font-semibold text-ink">Body</p>
        <p id="resource-body-hint" className="text-xs leading-5 text-muted">
          {values.kind ? resourceBodyHints[values.kind] : "Readers see this text on the Resource page."}
        </p>
        <MarkdownEditor
          id="resource-body"
          labelId="resource-body-label"
          describedBy={`resource-body-hint${errors.body ? " resource-body-error" : ""}`}
          invalid={Boolean(errors.body)}
          initialValue={body.editorProps.initialValue}
          onChange={(markdown) => {
            body.editorProps.onChange(markdown);
            setErrors((current) => ({ ...current, body: undefined }));
            setNotice(null);
          }}
          onReady={body.editorProps.onReady}
        />
        {errors.body ? <p id="resource-body-error" className="text-sm text-danger">{errors.body}</p> : null}
      </div>

      <div className="border-t border-border pt-6">
        {formError ? <p role="alert" className="mb-4 text-sm leading-6 text-danger">{formError}</p> : null}
        {notice ? <p role="status" className="mb-4 text-sm text-success">{notice}</p> : null}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {!resource ? (
            <Link href="/portal/resources" className={contentSecondaryLinkClass}>
              Cancel
            </Link>
          ) : null}
          <Button type="submit" disabled={saving || !dirty}>
            {saving ? pendingLabel : submitLabel}
          </Button>
        </div>
      </div>
    </form>
    <ContentConfirmDialog
      open={reviewOpen}
      title="Review published Resource changes?"
      description={
        <>
          {reviewedAudience !== undefined && saved.audience ? (
            <p>
              The audience will change from {publicationAudienceLabels[saved.audience]} to{" "}
              {publicationAudienceLabels[reviewedAudience]}.
            </p>
          ) : null}
          {reviewedAudience !== undefined ? (
            reviewedAudience === ResourceAudienceValue.PUBLIC ? (
              <p>
                Anyone who can access the public COMPASS site will be able to open this
                Resource without signing in.
              </p>
            ) : (
              <p>
                After this change, it will be available to{" "}
                {publicationAudienceReaders[reviewedAudience]}.
              </p>
            )
          ) : null}
          {reviewedDestinationChanged ? (
            <>
              <p>
                Readers of this published Resource will be sent to a different external
                destination.
              </p>
              <dl className="grid gap-2">
                <div>
                  <dt className="font-semibold text-ink">Current destination</dt>
                  <dd className="break-all">{reviewUrl(resource?.external_url)}</dd>
                </div>
                <div>
                  <dt className="font-semibold text-ink">New destination</dt>
                  <dd className="break-all">{reviewUrl(reviewPayload?.external_url)}</dd>
                </div>
              </dl>
            </>
          ) : null}
        </>
      }
      confirmLabel="Save reviewed changes"
      pendingLabel="Saving changes…"
      pending={update.isPending}
      error={reviewError}
      onOpenChange={(open) => {
        setReviewOpen(open);
        if (!open) {
          setReviewPayload(null);
          setReviewError(null);
        }
      }}
      onConfirm={() => {
        if (reviewPayload) void saveExisting(reviewPayload, true);
      }}
    />
    </>
  );
}
