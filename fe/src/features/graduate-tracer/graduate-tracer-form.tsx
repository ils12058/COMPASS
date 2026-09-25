"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GraduateTracerEducationSection, GraduateTracerGeneralSection, GraduateTracerTrainingSection } from "@/features/graduate-tracer/graduate-tracer-form-sections";
import { GraduateTracerCurriculumSection, GraduateTracerEmploymentSection } from "@/features/graduate-tracer/graduate-tracer-employment-section";
import { FORM_SECTIONS, graduateTracerDraftFromDetail, graduateTracerPayloadFromDraft, getGraduateTracerDraftRowIssues, getGraduateTracerSubmissionIssues, normalizeGraduateTracerDraft, type GraduateTracerFormDraft, type SubmissionIssue } from "@/features/graduate-tracer/graduate-tracer-presentation";
import { graduateTracerErrorMessage, isUncertainGraduateTracerMutation } from "@/features/graduate-tracer/graduate-tracer-shared";
import { graduateTracerGetMyResponse, getGraduateTracerGetMyResponseQueryKey, graduateTracerReplaceMyDraft, graduateTracerSubmitMyResponse } from "@/lib/api/generated/graduate-tracer/graduate-tracer";
import { CompassApiError } from "@/lib/api/errors";
import type { GraduateTracerDetailResponse, GraduateTracerDraftPayload } from "@/lib/api/generated/model";

function focusSection(issue: SubmissionIssue | undefined) {
  if (!issue) return;
  const section = document.getElementById(issue.section);
  section?.scrollIntoView({ block: "start" });
  section?.focus({ preventScroll: true });
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
  const save = useMutation({
    mutationFn: ({ data }: { data: GraduateTracerDraftPayload }) => graduateTracerReplaceMyDraft(data),
    retry: false,
  });
  const submit = useMutation({ mutationFn: () => graduateTracerSubmitMyResponse(), retry: false });
  const pending = save.isPending || submit.isPending;
  const draftRowIssues = getGraduateTracerDraftRowIssues(draft);

  useEffect(() => {
    if (!dirty) return;
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const confirmLinkNavigation = (event: globalThis.MouseEvent) => {
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if (anchor.origin === window.location.origin && anchor.pathname === window.location.pathname) return;
      if (!window.confirm("Discard your unsaved Graduate Tracer changes?")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", warnBeforeLeave);
    document.addEventListener("click", confirmLinkNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeLeave);
      document.removeEventListener("click", confirmLinkNavigation, true);
    };
  }, [dirty]);

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
    const rowIssue = draftRowIssues[0];
    if (rowIssue) {
      setLocalIssue(rowIssue);
      focusSection({ section: rowIssue.startsWith("Degree") ? "graduate-tracer-education" : rowIssue.startsWith("Training") ? "graduate-tracer-training" : "graduate-tracer-education", message: rowIssue });
      return;
    }
    if (!isValidOptionalEmail(draft.email)) {
      setLocalIssue("Enter a valid email address or leave the field blank.");
      focusSection({ section: "graduate-tracer-general", message: "Email format is invalid." });
      return;
    }
    try {
      const result = await save.mutateAsync({ data: graduateTracerPayloadFromDraft(draft) });
      queryClient.setQueryData(getGraduateTracerGetMyResponseQueryKey(), result);
      setEditedDraft(null);
      setLocalIssue(undefined);
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
      setLocalIssue(rowIssue);
      focusSection({ section: rowIssue.startsWith("Degree") ? "graduate-tracer-education" : rowIssue.startsWith("Training") ? "graduate-tracer-training" : "graduate-tracer-education", message: rowIssue });
      return;
    }
    const issue = getGraduateTracerSubmissionIssues(draft)[0];
    if (issue) {
      setLocalIssue(issue.message);
      focusSection(issue);
      return;
    }
    if (!isValidOptionalEmail(draft.email)) {
      setLocalIssue("Enter a valid email address or leave the field blank.");
      focusSection({ section: "graduate-tracer-general", message: "Email format is invalid." });
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
    <section className="space-y-6" aria-labelledby="graduate-tracer-form-heading">
      <header className="border-b border-border pb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="graduate-tracer-form-heading" className="font-heading text-xl font-semibold text-ink">Graduate Tracer Survey</h2>
          <span className="text-xs text-muted">Schema version {detail.instrument_schema_version}</span>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">This survey collects information about your education and employment experiences to support graduate employability research and curriculum improvement. Your draft is private to you until you submit it.</p>
      </header>

      <div className="lg:grid lg:grid-cols-[14rem_minmax(0,1fr)] lg:gap-10">
        <nav aria-label="Survey sections" className="mb-6 overflow-x-auto lg:mb-0">
          <div className="flex min-w-max gap-2 border-b border-border pb-3 lg:sticky lg:top-5 lg:min-w-0 lg:flex-col lg:gap-1 lg:border-b-0 lg:border-l lg:pb-0 lg:pl-3">
            {FORM_SECTIONS.map((section) => (
              <a key={section.id} href={`#${section.id}`} className="inline-flex min-h-10 items-center rounded-md px-3 text-sm font-medium text-muted hover:bg-surface-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                {section.label}
              </a>
            ))}
          </div>
        </nav>

        <form onSubmit={(event) => event.preventDefault()} aria-busy={pending} className="min-w-0">
          {localIssue ? <p role="alert" className="mb-5 border-l-4 border-warning bg-warning/5 px-4 py-3 text-sm leading-6 text-ink">{localIssue}</p> : null}
          {saveError ? <p role="alert" className="mb-5 border-l-4 border-danger bg-danger/5 px-4 py-3 text-sm leading-6 text-ink">{saveError}</p> : null}
          {saveMessage ? <p role="status" className="mb-5 border-l-4 border-success bg-success/5 px-4 py-3 text-sm text-ink">{saveMessage}</p> : null}

          <fieldset disabled={pending} className="min-w-0">
            <GraduateTracerGeneralSection draft={draft} onChange={updateDraft} />
            <GraduateTracerEducationSection draft={draft} onChange={updateDraft} />
            <GraduateTracerTrainingSection draft={draft} onChange={updateDraft} />
            <GraduateTracerEmploymentSection draft={draft} onChange={updateDraft} />
            <GraduateTracerCurriculumSection draft={draft} onChange={updateDraft} />
          </fieldset>

          <div className="border-t border-border py-6">
            {dirty ? <p className="mb-3 text-sm text-warning">Unsaved changes. Save the draft before submitting.</p> : null}
            {draftRowIssues.length ? <p className="mb-3 text-sm text-warning">{draftRowIssues[0]}</p> : null}
            <div className="flex flex-wrap gap-3">
              <Button type="button" variant="secondary" disabled={!dirty || pending || draftRowIssues.length > 0} onClick={() => void saveDraft()}>
                {save.isPending ? "Saving…" : "Save draft"}
              </Button>
              <Button type="button" disabled={pending || dirty || draftRowIssues.length > 0} onClick={openSubmitConfirmation}>Submit Graduate Tracer Survey</Button>
              <AlertDialog open={confirmSubmit} onOpenChange={(open) => { if (!submit.isPending) setConfirmSubmit(open); }}>
                <AlertDialogContent>
                  <AlertDialogTitle>Submit Graduate Tracer Survey?</AlertDialogTitle>
                  <AlertDialogDescription>
                    Your response will be finalized and made available to authorized Guidance and Counseling Office reviewers. You will not be able to edit it after submission.
                  </AlertDialogDescription>
                  {submitError ? <p role="alert" className="mt-4 text-sm leading-6 text-danger">{submitError}</p> : null}
                  {needsSubmissionCheck ? (
                    <Button type="button" variant="secondary" className="mt-3" onClick={() => void checkCanonicalSubmission()} disabled={submit.isPending}>Check response status</Button>
                  ) : null}
                  <div className="mt-6 flex flex-wrap justify-end gap-3">
                    <AlertDialogCancel asChild>
                      <Button type="button" variant="secondary" disabled={submit.isPending}>Cancel</Button>
                    </AlertDialogCancel>
                    <AlertDialogAction asChild>
                      <Button type="button" onClick={(event) => { event.preventDefault(); void submitDraft(); }} disabled={submit.isPending} aria-busy={submit.isPending}>
                        {submit.isPending ? "Submitting…" : "Submit Graduate Tracer Survey"}
                      </Button>
                    </AlertDialogAction>
                  </div>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </form>
      </div>
    </section>
  );
}

export function GraduateTracerFormSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading Graduate Tracer draft">
      <Skeleton className="h-9 w-60" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}
