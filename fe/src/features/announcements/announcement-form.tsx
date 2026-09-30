"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { refreshAnnouncementQueries, storeManagedAnnouncement } from "@/features/announcements/announcement-cache";
import {
  announcementErrorCode,
  announcementErrorMessage,
  isUncertainAnnouncementMutation,
} from "@/features/announcements/announcement-errors";
import {
  publicationAudienceLabels,
  publicationAudienceReaders,
  type PublicationAudience,
} from "@/features/content/content-presentation";
import {
  AudienceField,
  ContentConfirmDialog,
  contentSecondaryLinkClass,
} from "@/features/content/content-shared";
import { MarkdownEditor } from "@/features/content/markdown-editor/markdown-editor";
import { useMarkdownValue } from "@/features/content/markdown-editor/use-markdown-value";
import { useUnsavedChangesGuard } from "@/features/content/use-unsaved-changes-guard";
import {
  getAnnouncementsListManagedQueryKey,
  useAnnouncementsCreateDraft,
  useAnnouncementsUpdate,
} from "@/lib/api/generated/announcements/announcements";
import {
  AnnouncementAudienceValue,
  AnnouncementStatusValue,
  type AnnouncementManagementResponse,
  type AnnouncementUpdateRequest,
} from "@/lib/api/generated/model";
import {
  formatInstitutionalDateTime,
  INSTITUTION_TIME_ZONE_LABEL,
  institutionalDateTimeInputToISO,
  isFutureInstitutionalDateTimeInput,
  isoToInstitutionalDateTimeInput,
} from "@/lib/institutional-time";

type AnnouncementFields = {
  title: string;
  audience: PublicationAudience | null;
  isPinned: boolean;
  expiresAt: string;
};

type FieldName = keyof AnnouncementFields | "body";

const fieldTargets: Record<FieldName, string> = {
  title: "announcement-title",
  audience: "announcement-audience-public",
  isPinned: "announcement-pinned",
  expiresAt: "announcement-expires",
  body: "announcement-body",
};

function fieldsFrom(item: AnnouncementManagementResponse | null): AnnouncementFields {
  return item
    ? {
        title: item.title,
        audience: item.audience,
        isPinned: item.is_pinned,
        expiresAt: isoToInstitutionalDateTimeInput(item.expires_at),
      }
    : { title: "", audience: null, isPinned: false, expiresAt: "" };
}

export function AnnouncementForm({ announcement }: { announcement: AnnouncementManagementResponse | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const create = useAnnouncementsCreateDraft();
  const update = useAnnouncementsUpdate();
  const [saved, setSaved] = useState(() => fieldsFrom(announcement));
  const [values, setValues] = useState(() => fieldsFrom(announcement));
  const body = useMarkdownValue(announcement?.body_markdown ?? "");
  const [errors, setErrors] = useState<Partial<Record<FieldName, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewPayload, setReviewPayload] = useState<AnnouncementUpdateRequest | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);

  const isPublished = announcement?.status === AnnouncementStatusValue.PUBLISHED;
  const saving = create.isPending || update.isPending;
  const dirty =
    values.title.trim() !== saved.title.trim() ||
    values.audience !== saved.audience ||
    values.isPinned !== saved.isPinned ||
    values.expiresAt !== saved.expiresAt ||
    body.changed;

  useUnsavedChangesGuard(dirty, "Discard your unsaved Announcement changes?");

  function setField<K extends keyof AnnouncementFields>(key: K, value: AnnouncementFields[K]) {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
    setNotice(null);
  }

  function validate(currentBody: string) {
    const next: Partial<Record<FieldName, string>> = {};
    if (!values.title.trim()) next.title = "Enter a title.";
    if (!values.audience) next.audience = "Choose who can see this Announcement.";
    if (values.expiresAt && !institutionalDateTimeInputToISO(values.expiresAt)) {
      next.expiresAt = "Enter a valid date and time, or remove the expiry.";
    } else if (
      isPublished &&
      values.expiresAt &&
      !isFutureInstitutionalDateTimeInput(values.expiresAt)
    ) {
      next.expiresAt =
        "Choose a future expiry. Use Archive Announcement if it should disappear immediately.";
    }
    if (isPublished && !currentBody.trim()) next.body = "A published Announcement needs body text.";
    return next;
  }

  async function saveExisting(
    payload: AnnouncementUpdateRequest,
    acknowledgePublicationConsequences = false,
  ) {
    if (!announcement) return;
    try {
      const data: AnnouncementUpdateRequest = acknowledgePublicationConsequences
        ? { ...payload, acknowledge_publication_consequences: true }
        : payload;
      const response = await update.mutateAsync({
        announcementId: announcement.id,
        data,
      });
      const published = response.data.status === AnnouncementStatusValue.PUBLISHED;
      storeManagedAnnouncement(queryClient, response);
      void refreshAnnouncementQueries(queryClient, announcement.id, { readers: published });
      setSaved(fieldsFrom(response.data));
      if (payload.body_markdown !== undefined) body.markSaved(response.data.body_markdown);
      setReviewOpen(false);
      setReviewPayload(null);
      setReviewError(null);
      setNotice(published ? "Changes saved. Readers now see the updated Announcement." : "Draft saved.");
    } catch (caught) {
      if (
        !acknowledgePublicationConsequences &&
        announcementErrorCode(caught) === "publication_consequence_review_required"
      ) {
        setReviewPayload(payload);
        setReviewError(null);
        setReviewOpen(true);
        return;
      }
      const message = isUncertainAnnouncementMutation(caught)
        ? "The changes could not be confirmed as saved. Save again to make sure they are kept."
        : announcementErrorMessage(caught, "The changes could not be saved.");
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
    if (firstInvalid || !values.audience) {
      if (firstInvalid) document.getElementById(fieldTargets[firstInvalid])?.focus();
      return;
    }
    const expiresAt = values.expiresAt
      ? institutionalDateTimeInputToISO(values.expiresAt)
      : null;

    if (!announcement) {
      try {
        const response = await create.mutateAsync({
          data: {
            title: values.title.trim(),
            body_markdown: currentBody,
            audience: values.audience,
            is_pinned: values.isPinned,
            expires_at: expiresAt,
          },
        });
        void queryClient.invalidateQueries({ queryKey: getAnnouncementsListManagedQueryKey() });
        router.replace(`/portal/announcements/${response.data.id}?notice=created`);
      } catch (caught) {
        setFormError(
          isUncertainAnnouncementMutation(caught)
            ? "The draft could not be confirmed as saved. Check the Announcements list before saving again."
            : announcementErrorMessage(caught, "The draft could not be saved."),
        );
      }
      return;
    }

    // PATCH applies only the fields sent, so unchanged values stay untouched.
    const payload: AnnouncementUpdateRequest = {};
    if (values.title.trim() !== saved.title.trim()) payload.title = values.title.trim();
    const changedBody = body.readChanged();
    if (changedBody !== null) payload.body_markdown = changedBody;
    if (values.audience !== saved.audience) payload.audience = values.audience;
    if (values.isPinned !== saved.isPinned) payload.is_pinned = values.isPinned;
    if (values.expiresAt !== saved.expiresAt) payload.expires_at = expiresAt;
    if (Object.keys(payload).length === 0) return;

    const consequenceReviewNeeded =
      isPublished &&
      (payload.audience !== undefined ||
        Object.prototype.hasOwnProperty.call(payload, "expires_at"));
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

  const reviewedAudience = reviewPayload?.audience;
  const reviewedExpiryChanged =
    reviewPayload !== null &&
    Object.prototype.hasOwnProperty.call(reviewPayload, "expires_at");

  return (
    <>
    <form className="mt-8 space-y-8" onSubmit={(event) => void submit(event)} noValidate>
      <div className="grid gap-2">
        <Label htmlFor="announcement-title">Title</Label>
        <Input
          id="announcement-title"
          value={values.title}
          maxLength={200}
          aria-invalid={errors.title ? true : undefined}
          aria-describedby={errors.title ? "announcement-title-error" : undefined}
          onChange={(event) => setField("title", event.target.value)}
        />
        {errors.title ? (
          <p id="announcement-title-error" className="text-sm text-danger">{errors.title}</p>
        ) : null}
      </div>

      <AudienceField
        name="announcement-audience"
        value={values.audience}
        error={errors.audience}
        onChange={(audience) => setField("audience", audience)}
      />

      <div className="grid gap-6 border-t border-border pt-7 md:grid-cols-2">
        <div>
          <label htmlFor="announcement-pinned" className="flex min-h-10 cursor-pointer items-start gap-3">
            <input
              id="announcement-pinned"
              type="checkbox"
              className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
              checked={values.isPinned}
              onChange={(event) => setField("isPinned", event.target.checked)}
            />
            <span>
              <span className="block text-sm font-semibold text-ink">Pin this Announcement</span>
              <span className="mt-0.5 block text-xs leading-5 text-muted">
                Pinned Announcements are listed before other Announcements.
              </span>
            </span>
          </label>
        </div>
        <div className="grid content-start gap-2">
          <Label htmlFor="announcement-expires">Stop showing after</Label>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              id="announcement-expires"
              type="datetime-local"
              className="w-auto"
              value={values.expiresAt}
              aria-invalid={errors.expiresAt ? true : undefined}
              aria-describedby={`announcement-expires-hint${errors.expiresAt ? " announcement-expires-error" : ""}`}
              onChange={(event) => setField("expiresAt", event.target.value)}
            />
            {values.expiresAt ? (
              <Button variant="quiet" onClick={() => setField("expiresAt", "")}>
                Remove expiry
              </Button>
            ) : null}
          </div>
          <p id="announcement-expires-hint" className="text-xs leading-5 text-muted">
            Optional. Times use {INSTITUTION_TIME_ZONE_LABEL}. Without an
            expiry, the Announcement stays visible until it is archived.
          </p>
          {errors.expiresAt ? (
            <p id="announcement-expires-error" className="text-sm text-danger">{errors.expiresAt}</p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-2 border-t border-border pt-7">
        <p id="announcement-body-label" className="text-sm font-semibold text-ink">Body</p>
        <p id="announcement-body-hint" className="text-xs leading-5 text-muted">
          Readers see this text on the Announcement page.
        </p>
        <MarkdownEditor
          id="announcement-body"
          labelId="announcement-body-label"
          describedBy={`announcement-body-hint${errors.body ? " announcement-body-error" : ""}`}
          invalid={Boolean(errors.body)}
          initialValue={body.editorProps.initialValue}
          onChange={(markdown) => {
            body.editorProps.onChange(markdown);
            setErrors((current) => ({ ...current, body: undefined }));
            setNotice(null);
          }}
          onReady={body.editorProps.onReady}
        />
        {errors.body ? (
          <p id="announcement-body-error" className="text-sm text-danger">{errors.body}</p>
        ) : null}
      </div>

      <div className="border-t border-border pt-6">
        {formError ? (
          <p role="alert" className="mb-4 text-sm leading-6 text-danger">{formError}</p>
        ) : null}
        {notice ? (
          <p role="status" className="mb-4 text-sm text-success">{notice}</p>
        ) : null}
        <div className="flex flex-wrap items-center justify-end gap-3">
          {!announcement ? (
            <Link href="/portal/announcements" className={contentSecondaryLinkClass}>
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
      title="Review published Announcement changes?"
      description={
        <>
          {reviewedAudience !== undefined && saved.audience ? (
            <p>
              The audience will change from {publicationAudienceLabels[saved.audience]} to{" "}
              {publicationAudienceLabels[reviewedAudience]}.
            </p>
          ) : null}
          {reviewedAudience !== undefined ? (
            reviewedAudience === AnnouncementAudienceValue.PUBLIC ? (
              <p>
                Anyone who can access the public COMPASS site will be able to read this
                Announcement without signing in.
              </p>
            ) : (
              <p>
                After this change, it will be available to{" "}
                {publicationAudienceReaders[reviewedAudience]}.
              </p>
            )
          ) : null}
          {reviewedExpiryChanged ? (
            reviewPayload?.expires_at ? (
              <p>
                This Announcement will stop being shown after{" "}
                {formatInstitutionalDateTime(reviewPayload.expires_at)}{" "}
                {INSTITUTION_TIME_ZONE_LABEL}.
              </p>
            ) : (
              <p>
                This Announcement will no longer expire automatically and will remain
                visible until it is archived.
              </p>
            )
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
