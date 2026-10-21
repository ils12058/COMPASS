"use client";

import { studentActionsQueryFamily } from "@/features/student-actions/student-actions-data";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { Skeleton } from "@/components/ui/skeleton";
import { FormErrorSummary, FormSaveStatus, FormSectionLinks } from "@/components/ui/form-experience";
import { Panel, PanelHeader, PanelSection, PanelFooter, PanelMessage } from "@/components/ui/panel";
import { GraduateTracerEducationSection, GraduateTracerGeneralSection, GraduateTracerTrainingSection } from "@/features/graduate-tracer/graduate-tracer-form-sections";
import { GraduateTracerCurriculumSection, GraduateTracerEmploymentSection } from "@/features/graduate-tracer/graduate-tracer-employment-section";
import { FORM_SECTIONS, graduateTracerDraftFromDetail, graduateTracerPayloadFromDraft, getGraduateTracerDraftRowIssues, getGraduateTracerSubmissionIssues, normalizeGraduateTracerDraft, type GraduateTracerFormDraft, type SubmissionIssue } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { graduateTracerErrorMessage, isUncertainGraduateTracerMutation } from "@/features/graduate-tracer/graduate-tracer-shared";
import { graduateTracerGetMyResponse, getGraduateTracerGetMyResponseQueryKey, graduateTracerReplaceMyDraft, graduateTracerSubmitMyResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { CompassApiError } from "@/lib/api/errors";
import type { GraduateTracerDetailResponse, GraduateTracerDraftPayload } from "@/lib/api/generated/model";

function focusIssue(issue: SubmissionIssue | undefined) {
  if (!issue) return;
  const target = document.getElementById(issue.targetId);
  if (target) {
    target.scrollIntoView({ block: "center" });
    const focusTarget = target.matches("input, select, textarea, button")
      ? target
      : target.querySelector<HTMLElement>("input, select, textarea, button");
    (focusTarget as HTMLElement | null)?.focus({ preventScroll: true });
    return;
  }

  const section = document.getElementById(issue.section);
  section?.scrollIntoView({ block: "start" });
  section?.querySelector<HTMLElement>("input, select, textarea, button")?.focus({ preventScroll: true });
}

function isValidOptionalEmail(value: string | undefined): boolean {
  return !value?.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

export function GraduateTracerForm({ detail }: { detail: GraduateTracerDetailResponse }) {
  const queryClient = useQueryClient();
  const canonicalDraft = useMemo(() => graduateTracerDraftFromDetail(detail), [detail]);
  const [editedDraft, setEditedDraft] = useState<GraduateTracerFormDraft | null>(null);
  const draft = editedDraft && JSON.stringify(editedDraft) !== JSON.stringify(canonicalDraft) ? editedDraft : canonicalDraft;
  const dirty = draft !== canonicalDraft;
  const [saveError, setSaveError] = useState<string>();
  const [saveMessage, setSaveMessage] = useState<string>();
  const [submitError, setSubmitError] = useState<string>();
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [needsSubmissionCheck, setNeedsSubmissionCheck] = useState(false);
  const [localIssue, setLocalIssue] = useState<string>();
  const [draftValidationVisible, setDraftValidationVisible] = useState(false);
  const [submissionValidationVisible, setSubmissionValidationVisible] = useState(false);
  const save = useMutation({
    mutationFn: ({ data }: { data: GraduateTracerDraftPayload }) => graduateTracerReplaceMyDraft(data),
    retry: false,
  });
  const submit = useMutation({ mutationFn: () => graduateTracerSubmitMyResponse(), retry: false });
  const pending = save.isPending || submit.isPending;
  const draftRowIssues = getGraduateTracerDraftRowIssues(draft);
  const draftEmailIssue: SubmissionIssue | undefined = isValidOptionalEmail(draft.email)
    ? undefined
    : {
        section: "graduate-tracer-general",
        targetId: "gts-email",
        message: "Enter a valid email address or leave the field blank.",
      };
  const draftIssues = draftEmailIssue ? [...draftRowIssues, draftEmailIssue] : draftRowIssues;
  const submissionIssues = getGraduateTracerSubmissionIssues(draft);
  const visibleIssues = [
    ...(draftValidationVisible ? draftIssues : []),
    ...(submissionValidationVisible ? submissionIssues : []),
  ].filter((issue, index, issues) => issues.findIndex((other) => other.targetId === issue.targetId) === index);
  const errorFor = (targetId: string) =>
    visibleIssues.find((issue) => issue.targetId === targetId)?.message;

  useUnsavedChangesGuard({
    dirty,
    message: "Discard your unsaved Graduate Tracer changes?",
  });


  function updateDraft<K extends keyof GraduateTracerFormDraft>(
    field: K,
    value: GraduateTracerFormDraft[K],
  ) {
    setEditedDraft((current) => {
      const base = current && JSON.stringify(current) !== JSON.stringify(canonicalDraft) ? current : canonicalDraft;
      return normalizeGraduateTracerDraft({ ...base, [field]: value });
    });
    setSaveError(undefined);
    setSaveMessage(undefined);
    setSubmitError(undefined);
    setLocalIssue(undefined);
  }

  async function saveDraft() {
    setSaveError(undefined);
    setSaveMessage(undefined);
    setSubmitError(undefined);
    setDraftValidationVisible(true);
    const draftIssue = draftIssues[0];
    if (draftIssue) {
      setLocalIssue(draftIssue.message);
      focusIssue(draftIssue);
      return;
    }
    try {
      const result = await save.mutateAsync({ data: graduateTracerPayloadFromDraft(draft) });
      queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), result);
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
      setEditedDraft(null);
      setLocalIssue(undefined);
      setDraftValidationVisible(false);
      setSaveMessage("Draft saved.");
    } catch (error) {
      setSaveError(graduateTracerErrorMessage(error, "The Graduate Tracer draft could not be saved."));
      if (error instanceof CompassApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: getGraduateTracerGetMyResponseQueryKey() });
      }
    }
  }

  function openSubmitConfirmation() {
    setSubmitError(undefined);
    setNeedsSubmissionCheck(false);
    if (dirty) {
      setLocalIssue("Save your draft before submitting. The submitted response uses the last saved version.");
      return;
    }
    const rowIssue = draftRowIssues[0];
    if (rowIssue) {
      setDraftValidationVisible(true);
      setLocalIssue(rowIssue.message);
      focusIssue(rowIssue);
      return;
    }
    const issue = submissionIssues[0];
    if (issue) {
      setSubmissionValidationVisible(true);
      setLocalIssue(issue.message);
      focusIssue(issue);
      return;
    }
    setLocalIssue(undefined);
    setConfirmSubmit(true);
  }

  async function checkCanonicalSubmission() {
    setNeedsSubmissionCheck(false);
    try {
      const canonical = await queryClient.fetchQuery({
        queryKey: getGraduateTracerGetMyResponseQueryKey(),
        queryFn: () => graduateTracerGetMyResponse(),
        staleTime: 0,
      });
      queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), canonical);
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
      if (canonical.data.status === "SUBMITTED") {
        setConfirmSubmit(false);
        setSubmitError(undefined);
        return;
      }
      setSubmitError("The saved response is still a draft. Review its status, then submit again only when you are ready.");
    } catch {
      setNeedsSubmissionCheck(true);
      setSubmitError("We could not verify whether submission completed. Check the response status before deliberately trying again.");
    }
  }

  async function submitDraft() {
    setSubmitError(undefined);
    try {
      const result = await submit.mutateAsync();
      queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), result);
      void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
      setConfirmSubmit(false);
    } catch (error) {
      if (isUncertainGraduateTracerMutation(error)) {
        try {
          const canonical = await queryClient.fetchQuery({
            queryKey: getGraduateTracerGetMyResponseQueryKey(),
            queryFn: () => graduateTracerGetMyResponse(),
            staleTime: 0,
          });
          queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), canonical);
          void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
          if (canonical.data.status === "SUBMITTED") {
            setConfirmSubmit(false);
            return;
          }
          setSubmitError("The response is still a draft. Your answers remain saved; submit again only after reviewing its current status.");
          return;
        } catch {
          setNeedsSubmissionCheck(true);
          setSubmitError("We could not verify whether submission completed. Check the response status before deliberately trying again.");
          return;
        }
      }
      setSubmitError(graduateTracerErrorMessage(error, "The Graduate Tracer response could not be submitted."));
      if (error instanceof CompassApiError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: getGraduateTracerGetMyResponseQueryKey() });
      }
    }
  }

  return (
    <section aria-labelledby="graduate-tracer-form-heading">
      <form onSubmit={(event) => event.preventDefault()} aria-busy={pending} className="@container/tracer min-w-0 [overflow-wrap:anywhere]">
        <Panel as="div">
          <PanelHeader
            title="Graduate Tracer Survey"
            titleId="graduate-tracer-form-heading"
            description="Your draft remains private until you submit it."
          />
          <div className="border-b border-brand-line px-4 py-4 sm:px-5">
            <FormSectionLinks id="graduate-tracer-section-links" label="Survey sections" sections={FORM_SECTIONS} onSelect={(id) => {
              const target = document.getElementById(id);
              target?.scrollIntoView({ block: "start" });
              target?.focus({ preventScroll: true });
            }} />
          </div>

          <fieldset disabled={pending} className="min-w-0">
            <GraduateTracerGeneralSection draft={draft} onChange={updateDraft} errorFor={errorFor} />
            <GraduateTracerEducationSection draft={draft} onChange={updateDraft} errorFor={errorFor} />
            <GraduateTracerTrainingSection draft={draft} onChange={updateDraft} errorFor={errorFor} />
            <GraduateTracerEmploymentSection draft={draft} onChange={updateDraft} errorFor={errorFor} />
            <GraduateTracerCurriculumSection draft={draft} onChange={updateDraft} />
          </fieldset>

          <PanelSection title="Review and submit" titleId="graduate-tracer-review-heading">
            <p className="max-w-3xl text-sm leading-6 text-muted">
              You can save a partial draft. Save your changes before submitting; submission uses your saved answers and makes this response read-only.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1">
              <Button type="button" variant="quiet" className="px-0" disabled={pending} onClick={() => {
                setDraftValidationVisible(true);
                setSubmissionValidationVisible(true);
                setLocalIssue(undefined);
              }}>Review answers</Button>
              <a href="#graduate-tracer-section-links" className="inline-flex min-h-11 items-center text-sm font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" onClick={(event) => {
                event.preventDefault();
                const target = document.getElementById("graduate-tracer-section-links");
                target?.scrollIntoView({ block: "start" });
                target?.focus({ preventScroll: true });
              }}>Back to sections</a>
            </div>
            {visibleIssues.length ? (
              <div className="mt-4">
                <FormErrorSummary id="graduate-tracer-error-summary" issues={visibleIssues} onSelect={focusIssue}
                  title={submissionValidationVisible ? "Check these answers before submitting" : "Check these answers before saving"}
                  instruction={submissionValidationVisible ? "Select an item to return to its question. You can still save a partial draft." : "Correct these draft values, then save again. Other incomplete answers can remain in your draft."} />
              </div>
            ) : submissionValidationVisible ? <p className="mt-2 text-sm text-muted">The required answers are ready for review. Check your responses before submitting.</p> : null}
          </PanelSection>
          {localIssue && !visibleIssues.length ? <PanelMessage role="alert">{localIssue}</PanelMessage> : null}
          {saveError ? <PanelMessage role="alert" tone="danger">{saveError}</PanelMessage> : null}
          <PanelFooter className="items-start justify-between">
            <FormSaveStatus dirty={dirty} saving={save.isPending} savedMessage={submit.isPending ? "Submitting…" : needsSubmissionCheck ? "Submission status could not be confirmed" : saveMessage} />
            <div className="flex min-w-0 max-w-full flex-wrap gap-3">
              <Button type="button" variant="secondary" className="whitespace-normal" disabled={!dirty || pending} onClick={() => void saveDraft()}>
                {save.isPending ? "Saving…" : "Save draft"}
              </Button>
              <Button type="button" className="whitespace-normal" disabled={pending || dirty} onClick={openSubmitConfirmation}>Submit Graduate Tracer Survey</Button>
              <ConsequentialActionDialog
                open={confirmSubmit}
                title="Submit Graduate Tracer Survey?"
                confirmLabel="Submit Graduate Tracer Survey"
                pendingLabel="Submitting…"
                pending={submit.isPending}
                confirmDisabled={needsSubmissionCheck}
                error={submitError ?? null}
                onOpenChange={setConfirmSubmit}
                onConfirm={() => void submitDraft()}
              >
                <p>
                  Your response will be finalized and made available only to
                  authorized Guidance and Counseling Office reviewers. You will
                  not be able to edit it after submission.
                </p>
                {needsSubmissionCheck ? (
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => void checkCanonicalSubmission()}
                    disabled={submit.isPending}
                  >
                    Check response status
                  </Button>
                ) : null}
              </ConsequentialActionDialog>
            </div>
          </PanelFooter>
        </Panel>
      </form>
    </section>
  );
}

export function GraduateTracerFormSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true"><span className="sr-only">Loading Graduate Tracer draft…</span>
      <Skeleton className="h-9 w-60" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
