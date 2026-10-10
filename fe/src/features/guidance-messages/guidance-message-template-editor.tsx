"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { MESSAGE_BODY_LIMIT, messageBodyProblem, messageLength } from "@/features/guidance-messages/guidance-message-send";
import { templatesQueryFamily } from "@/features/guidance-messages/guidance-message-templates";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  guidanceMessagesCreateTemplate,
  guidanceMessagesUpdateTemplate,
} from "@/lib/api/generated/guidance-messages/guidance-messages";
import type { GuidanceTemplateResponse } from "@/lib/api/generated/model";
import { AccountChangedError } from "@/lib/query/account-ownership";
import { cn } from "@/lib/utils/cn";

export const TEMPLATE_NAME_LIMIT = 120;
const COUNTER_FROM = MESSAGE_BODY_LIMIT - 500;

/** The browser's own check, matching the backend: one trimmed line of at most 120 characters. */
export function templateNameProblem(name: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return "Enter a template name.";
  if ([...trimmed].length > TEMPLATE_NAME_LIMIT) return `Template names can be up to ${TEMPLATE_NAME_LIMIT} characters.`;
  if (/[\u0000-\u001f\u007f-\u009f]/.test(trimmed)) return "Template names must be one line without special characters.";
  return null;
}

export function templateBodyProblem(body: string): string | null {
  const problem = messageBodyProblem(body);
  if (problem === "empty") return "Write the template text.";
  if (problem === "too_long") return `Templates can be up to ${MESSAGE_BODY_LIMIT.toLocaleString("en-PH")} characters.`;
  if (problem === "unsupported") return "This text contains a character COMPASS cannot save. Remove it and try again.";
  return null;
}

type SaveError = { field: "name" | null; text: string };

function describeSaveError(error: unknown): SaveError {
  if (error instanceof AccountChangedError) return { field: null, text: "The signed-in account changed, so this template was not saved here." };
  const status = error instanceof CompassApiError ? error.status : null;
  if (status === 409 && error instanceof CompassApiError && readApiErrorCode(error.body) === "guidance_message_template_name_taken") {
    return { field: "name", text: "Another template already uses this name. Choose a different name." };
  }
  if (status === 409) {
    return { field: null, text: "This template changed after you opened it. Close it and open it again to see the current version." };
  }
  if (status === 404) return { field: null, text: "This template no longer exists." };
  if (status === 403) return { field: null, text: "Your account can no longer manage Message templates." };
  if (status === 401) return { field: null, text: "Your session needs to be checked again. Your changes are still here." };
  if (status === 422) return { field: null, text: "Check the name and text, then save again." };
  return { field: null, text: "The template could not be saved. Try again." };
}

/**
 * Creates a template, or edits an active one. The edit carries the version it opened, so a newer
 * save by someone else is refused instead of overwritten. Unsaved text guards navigation, and
 * closing the dialog with unsaved text asks first.
 */
export function TemplateEditorDialog({
  open,
  template,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  /** The template to edit; null creates one. */
  template: GuidanceTemplateResponse | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (template: GuidanceTemplateResponse, created: boolean) => void;
}) {
  const [dirty, setDirty] = useState(false);
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  const [pending, setPending] = useState(false);
  useUnsavedChangesGuard({ dirty: open && dirty, message: "Discard your unsaved template changes?" });

  function requestClose(next: boolean) {
    if (next) return onOpenChange(true);
    if (pending) return;
    if (dirty) {
      setConfirmingDiscard(true);
      return;
    }
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={requestClose}>
      <DialogContent
        closeLabel="Close template editor"
        dismissible={!pending}
        aria-describedby={undefined}
        className="flex max-h-[calc(100dvh-2rem)] max-w-2xl flex-col overflow-hidden p-0"
      >
        <EditorForm
          // A new key per opened template restarts the form from the saved version.
          key={template ? `${template.id}:${template.updated_at}` : "new"}
          template={template}
          confirmingDiscard={confirmingDiscard}
          onDirtyChange={setDirty}
          onPendingChange={setPending}
          onKeepEditing={() => setConfirmingDiscard(false)}
          onDiscard={() => {
            setConfirmingDiscard(false);
            setDirty(false);
            onOpenChange(false);
          }}
          onCancel={() => requestClose(false)}
          onSaved={(saved) => {
            setDirty(false);
            onSaved(saved, template === null);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}

function EditorForm({
  template,
  confirmingDiscard,
  onDirtyChange,
  onPendingChange,
  onKeepEditing,
  onDiscard,
  onCancel,
  onSaved,
}: {
  template: GuidanceTemplateResponse | null;
  confirmingDiscard: boolean;
  onDirtyChange: (dirty: boolean) => void;
  onPendingChange: (pending: boolean) => void;
  onKeepEditing: () => void;
  onDiscard: () => void;
  onCancel: () => void;
  onSaved: (template: GuidanceTemplateResponse) => void;
}) {
  const queryClient = useQueryClient();
  const nameId = useId();
  const bodyId = useId();
  const nameErrorId = useId();
  const bodyErrorId = useId();
  const counterId = useId();
  const privacyId = useId();
  const [name, setName] = useState(template?.name ?? "");
  const [body, setBody] = useState(template?.body ?? "");
  const [nameError, setNameError] = useState<string | null>(null);
  const [bodyError, setBodyError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: async (): Promise<GuidanceTemplateResponse> => {
      if (!template) return (await guidanceMessagesCreateTemplate({ name: name.trim(), body })).data;
      const changes = {
        ...(name.trim() !== template.name ? { name: name.trim() } : {}),
        ...(body !== template.body ? { body } : {}),
        expected_updated_at: template.updated_at,
      };
      return (await guidanceMessagesUpdateTemplate(template.id, changes)).data;
    },
    onMutate: () => onPendingChange(true),
    onSettled: () => {
      onPendingChange(false);
      void queryClient.invalidateQueries({ queryKey: templatesQueryFamily() });
    },
  });

  function changed(nextName: string, nextBody: string) {
    onDirtyChange(template ? nextName.trim() !== template.name || nextBody !== template.body : nextName.trim() !== "" || nextBody.trim() !== "");
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problems = { name: templateNameProblem(name), body: templateBodyProblem(body) };
    setNameError(problems.name);
    setBodyError(problems.body);
    setFormError(null);
    if (problems.name || problems.body) {
      document.getElementById(problems.name ? nameId : bodyId)?.focus();
      return;
    }
    if (template && name.trim() === template.name && body === template.body) {
      onSaved(template);
      return;
    }
    save.mutate(undefined, {
      onSuccess: onSaved,
      onError: (error) => {
        const described = describeSaveError(error);
        if (described.field === "name") {
          setNameError(described.text);
          document.getElementById(nameId)?.focus();
        } else {
          setFormError(described.text);
        }
      },
    });
  }

  const length = messageLength(body);
  const tooLong = length > MESSAGE_BODY_LIMIT;
  const showCounter = length >= COUNTER_FROM;
  return (
    <form noValidate onSubmit={submit} className="flex min-h-0 flex-1 flex-col" aria-busy={save.isPending}>
      <div className="border-b border-brand-line px-5 pt-5 pb-4">
        <DialogTitle className="text-lg">{template ? "Edit template" : "Create template"}</DialogTitle>
        <p id={privacyId} className="mt-1 text-sm text-muted">
          Templates are shared with Guidance staff. Use general wording only, never a Student&rsquo;s name or details.
        </p>
      </div>
      {/* Read-only rather than disabled while saving, so focus can return to a field it refused. */}
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {formError ? (
          <p role="alert" className="text-sm text-danger">
            {formError}
          </p>
        ) : null}
        <div className="grid gap-1.5">
          <Label htmlFor={nameId}>Name</Label>
          <Input
            id={nameId}
            autoComplete="off"
            maxLength={TEMPLATE_NAME_LIMIT + 20}
            readOnly={save.isPending}
            value={name}
            aria-invalid={nameError ? true : undefined}
            aria-describedby={nameError ? nameErrorId : undefined}
            onChange={(event) => {
              setName(event.target.value);
              setNameError(null);
              changed(event.target.value, body);
            }}
          />
          {nameError ? (
            <p id={nameErrorId} className="text-sm text-danger">
              {nameError}
            </p>
          ) : null}
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={bodyId}>Text</Label>
          <Textarea
            id={bodyId}
            rows={8}
            readOnly={save.isPending}
            value={body}
            aria-invalid={bodyError || tooLong ? true : undefined}
            aria-describedby={[bodyError ? bodyErrorId : null, privacyId, showCounter ? counterId : null].filter(Boolean).join(" ")}
            onChange={(event) => {
              setBody(event.target.value);
              setBodyError(null);
              changed(name, event.target.value);
            }}
            className="max-h-[50dvh] min-h-40 resize-y"
          />
          <div className="flex flex-wrap justify-between gap-x-3 text-xs text-muted">
            {bodyError ? (
              <p id={bodyErrorId} className="text-sm text-danger">
                {bodyError}
              </p>
            ) : (
              <span />
            )}
            {showCounter ? (
              <span id={counterId} className={cn(tooLong && "font-semibold text-danger")}>
                {length.toLocaleString("en-PH")} of {MESSAGE_BODY_LIMIT.toLocaleString("en-PH")} characters
              </span>
            ) : null}
          </div>
        </div>
      </div>
      {confirmingDiscard ? (
        <div role="alert" className="flex flex-col gap-3 border-t border-brand-line bg-surface px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold text-ink">Discard your changes to this template?</p>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="secondary" onClick={onKeepEditing}>
              Keep editing
            </Button>
            <Button variant="danger" onClick={onDiscard}>
              Discard changes
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col-reverse gap-2 border-t border-brand-line px-5 py-4 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={onCancel} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {save.isPending ? "Saving…" : template ? "Save changes" : "Create template"}
          </Button>
        </div>
      )}
    </form>
  );
}
