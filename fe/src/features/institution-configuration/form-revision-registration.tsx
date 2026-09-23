"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { InstitutionActionFeedback } from "@/features/institution-configuration/institution-shared";
import { useInstitutionConfigurationAction } from "@/features/institution-configuration/institution-action";
import {
  getInstitutionalFormsRevisionsListQueryKey,
  useInstitutionalFormsRevisionsRegister,
} from "@/lib/api/generated/institutional-forms/institutional-forms";

type RevisionDraft = {
  officialCode: string;
  officialRevision: string;
  internalSchemaVersion: string;
};

const emptyDraft: RevisionDraft = {
  officialCode: "",
  officialRevision: "",
  internalSchemaVersion: "",
};

export function FormRevisionRegistration({
  familyKey,
  familyTitle,
}: {
  familyKey: string;
  familyTitle: string;
}) {
  const queryClient = useQueryClient();
  const registerRevision = useInstitutionalFormsRevisionsRegister();
  const action = useInstitutionConfigurationAction();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<RevisionDraft>(emptyDraft);
  const [localError, setLocalError] = useState<string | null>(null);
  const [successNotice, setSuccessNotice] = useState<string | null>(null);

  function openDialog() {
    setSuccessNotice(null);
    setLocalError(null);
    action.resetFeedback();
    setOpen(true);
  }

  function cancelDialog() {
    setOpen(false);
    setLocalError(null);
    action.resetFeedback();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const schemaVersion = Number(draft.internalSchemaVersion);
    if (
      !Number.isSafeInteger(schemaVersion) ||
      schemaVersion < 1
    ) {
      setLocalError("Internal schema version must be a positive whole number.");
      return;
    }

    const registered = await action.run(
      () =>
        registerRevision.mutateAsync({
          familyKey,
          data: {
            official_code: draft.officialCode,
            official_revision: draft.officialRevision,
            internal_schema_version: schemaVersion,
          },
        }),
      "The Form Revision could not be registered.",
      {
        onStepUpRequired: () => setOpen(false),
        onStepUpVerified: () => setOpen(true),
      },
    );
    if (!registered) return;

    setOpen(false);
    setDraft(emptyDraft);
    setSuccessNotice(
      `${registered.data.official_code ?? familyTitle}, official revision ${registered.data.official_revision ?? "not recorded"}, was registered as Inactive.`,
    );
    await queryClient.invalidateQueries({
      queryKey: getInstitutionalFormsRevisionsListQueryKey(familyKey),
    });
  }

  return (
    <div className="shrink-0">
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (registerRevision.isPending) return;
          if (next) openDialog();
          else cancelDialog();
        }}
      >
        <>
          <DialogTrigger asChild>
            <Button>Register revision</Button>
          </DialogTrigger>
          {successNotice ? (
            <p role="status" className="mt-3 text-sm leading-6 text-success">
              {successNotice}
            </p>
          ) : null}
        <DialogContent
          onEscapeKeyDown={(event) => {
            if (registerRevision.isPending) event.preventDefault();
          }}
          onPointerDownOutside={(event) => {
            if (registerRevision.isPending) event.preventDefault();
          }}
        >
          <DialogTitle>Register Form Revision</DialogTitle>
          <DialogDescription>
            Record the official QMS identity and COMPASS schema version for {familyTitle}. Registration creates an Inactive revision; activation is a separate action.
          </DialogDescription>
          <form className="mt-6 space-y-5" onSubmit={submit}>
            <div className="grid gap-2">
              <Label htmlFor="form-revision-official-code">Official code</Label>
              <Input
                id="form-revision-official-code"
                autoComplete="off"
                required
                value={draft.officialCode}
                onChange={(event) => {
                  setLocalError(null);
                  setDraft((current) => ({
                    ...current,
                    officialCode: event.target.value,
                  }));
                }}
                disabled={registerRevision.isPending}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="form-revision-official-revision">
                Official revision
              </Label>
              <Input
                id="form-revision-official-revision"
                autoComplete="off"
                required
                value={draft.officialRevision}
                onChange={(event) => {
                  setLocalError(null);
                  setDraft((current) => ({
                    ...current,
                    officialRevision: event.target.value,
                  }));
                }}
                disabled={registerRevision.isPending}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="form-revision-schema-version">
                Internal schema version
              </Label>
              <Input
                id="form-revision-schema-version"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                required
                value={draft.internalSchemaVersion}
                onChange={(event) => {
                  setLocalError(null);
                  setDraft((current) => ({
                    ...current,
                    internalSchemaVersion: event.target.value,
                  }));
                }}
                aria-invalid={localError ? true : undefined}
                aria-describedby={
                  localError
                    ? "form-revision-schema-version-help form-revision-schema-version-error"
                    : "form-revision-schema-version-help"
                }
                disabled={registerRevision.isPending}
              />
              <p
                id="form-revision-schema-version-help"
                className="text-sm leading-6 text-muted"
              >
                Identifies the COMPASS data/schema version associated with this official form revision.
              </p>
            </div>
            {localError ? (
              <p
                id="form-revision-schema-version-error"
                role="alert"
                className="text-sm leading-6 text-danger"
              >
                {localError}
              </p>
            ) : null}
            <InstitutionActionFeedback
              error={action.error}
              notice={action.notice}
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="secondary"
                disabled={registerRevision.isPending}
                onClick={cancelDialog}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={registerRevision.isPending}>
                {registerRevision.isPending ? "Registering…" : "Register revision"}
              </Button>
            </div>
          </form>
        </DialogContent>
        </>
      </Dialog>

      {action.stepUpDialog}
    </div>
  );
}
