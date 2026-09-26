"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent, type MouseEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ExitInterviewDetailResponse } from "@/lib/api/generated/model";
import {
  CareerModeValue,
  DelayReasonValue,
  ProgramCompletionValue,
  SignificantLearningValue,
} from "@/lib/api/generated/model";
import {
  exitInterviewFormFromDetail,
  exitInterviewDraftPayload,
  answeredCount,
  COLLEGE_FEEDBACK_CATEGORIES,
  SELF_ASSESSMENT_ITEMS,
} from "@/features/exit-interviews/exit-interview-presentation";
import {
  ExitInterviewFormSections,
  type ExitInterviewTextFieldKey,
} from "@/features/exit-interviews/exit-interview-form-sections";
import {
  ExitInterviewError,
  ExitInterviewHeading,
  exitInterviewErrorMessage,
  isUncertainExitInterviewMutation,
} from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewCorrectionHistory } from "@/features/exit-interviews/exit-interview-correction-history";
import {
  exitInterviewsSubmitMine,
  exitInterviewsUpdateMine,
  getExitInterviewsGetMineQueryKey,
  getExitInterviewsGetMyCurrentQueryKey,
  getExitInterviewsListMineQueryKey,
} from "@/lib/api/generated/exit-interviews/exit-interviews";

function toggle<T extends string>(values: readonly T[], value: T): T[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

export function ExitInterviewForm({
  detail,
  onRefreshRecord,
}: {
  detail: ExitInterviewDetailResponse;
  onRefreshRecord: () => Promise<ExitInterviewDetailResponse | undefined>;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(() => exitInterviewFormFromDetail(detail));
  const [savedForm, setSavedForm] = useState(() => exitInterviewFormFromDetail(detail));
  const [saveError, setSaveError] = useState<unknown>();
  const [submitError, setSubmitError] = useState<unknown>();
  const [saveMessage, setSaveMessage] = useState("");
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submissionUncertain, setSubmissionUncertain] = useState(false);
  const [refreshError, setRefreshError] = useState(false);
  const isDirty = JSON.stringify(form) !== JSON.stringify(savedForm);

  const save = useMutation({
    mutationFn: (payload: ReturnType<typeof exitInterviewDraftPayload>) =>
      exitInterviewsUpdateMine(detail.id, payload),
    retry: false,
  });
  const submit = useMutation({
    mutationFn: () => exitInterviewsSubmitMine(detail.id),
    retry: false,
  });

  useEffect(() => {
    if (!isDirty) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => window.removeEventListener("beforeunload", warnBeforeUnload);
  }, [isDirty]);

  function updateText(field: ExitInterviewTextFieldKey, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setSaveMessage("");
  }

  function updateRating(
    section: "selfRatings" | "collegeRatings",
    code: string,
    value: string,
  ) {
    setForm((current) => ({
      ...current,
      [section]: { ...current[section], [code]: value },
    }));
    setSaveMessage("");
  }

  function toggleDelayReason(value: DelayReasonValue) {
    setForm((current) => {
      const delayReasons = toggle(current.delayReasons, value);
      return {
        ...current,
        delayReasons,
        delayOther: delayReasons.includes(DelayReasonValue.OTHER)
          ? current.delayOther
          : "",
      };
    });
    setSaveMessage("");
  }

  function toggleLearning(value: SignificantLearningValue) {
    setForm((current) => {
      const significantLearningExperiences = toggle(
        current.significantLearningExperiences,
        value,
      );
      return {
        ...current,
        significantLearningExperiences,
        significantLearningOther: significantLearningExperiences.includes(
          SignificantLearningValue.OTHER,
        )
          ? current.significantLearningOther
          : "",
      };
    });
    setSaveMessage("");
  }

  function changeCompletion(value: "" | ProgramCompletionValue) {
    setForm((current) => ({
      ...current,
      programCompletion: value,
      ...(value === ProgramCompletionValue.ACCORDING_TO_SCHEDULE
        ? { extraTermsCount: "", delayReasons: [], delayOther: "" }
        : {}),
    }));
    setSaveMessage("");
  }

  function toggleCareerMode(value: CareerModeValue) {
    setForm((current) => {
      const careerModes = toggle(current.careerModes, value);
      return {
        ...current,
        careerModes,
        workChoices: careerModes.includes(CareerModeValue.WORK)
          ? current.workChoices
          : [],
        studyChoices: careerModes.includes(CareerModeValue.STUDY)
          ? current.studyChoices
          : [],
      };
    });
    setSaveMessage("");
  }

  async function saveDraft() {
    setSaveError(undefined);
    setSaveMessage("");
    try {
      const result = await save.mutateAsync(exitInterviewDraftPayload(form));
      queryClient.setQueryData(getExitInterviewsGetMineQueryKey(detail.id), result);
      const canonical = exitInterviewFormFromDetail(result.data);
      setForm(canonical);
      setSavedForm(canonical);
      setSaveMessage("Draft saved.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyCurrentQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsListMineQueryKey() }),
      ]);
    } catch (error) {
      setSaveError(error);
    }
  }

  async function submitDraft() {
    setSubmitError(undefined);
    try {
      const result = await submit.mutateAsync();
      queryClient.setQueryData(getExitInterviewsGetMineQueryKey(detail.id), result);
      setConfirmSubmit(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyCurrentQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsListMineQueryKey() }),
      ]);
    } catch (error) {
      setSubmitError(error);
      const outcomeIsUncertain = isUncertainExitInterviewMutation(error);
      setSubmissionUncertain(outcomeIsUncertain);
      if (outcomeIsUncertain) setConfirmSubmit(false);
    }
  }

  async function refreshCanonicalRecord() {
    setRefreshError(false);
    const canonical = await onRefreshRecord();
    if (!canonical) {
      setRefreshError(true);
      return;
    }
    const nextForm = exitInterviewFormFromDetail(canonical);
    setForm(nextForm);
    setSavedForm(nextForm);
    setSubmissionUncertain(false);
    setSubmitError(undefined);
    setSaveError(undefined);
    setSaveMessage("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isDirty || submissionUncertain || !allRatingsComplete) return;
    setSubmitError(undefined);
    setConfirmSubmit(true);
  }

  const selfAnswered = answeredCount(SELF_ASSESSMENT_ITEMS, form.selfRatings);
  const collegeItems = COLLEGE_FEEDBACK_CATEGORIES.flatMap((category) => category.items);
  const collegeAnswered = answeredCount(collegeItems, form.collegeRatings);
  const allRatingsComplete =
    selfAnswered === SELF_ASSESSMENT_ITEMS.length &&
    collegeAnswered === collegeItems.length;
  const pending = save.isPending || submit.isPending;

  function handleBackNavigation(event: MouseEvent<HTMLAnchorElement>) {
    if (isDirty && !window.confirm("Leave this Exit Interview? Your unsaved changes will be discarded.")) {
      event.preventDefault();
    }
  }

  return (
    <section className="space-y-2" aria-labelledby="exit-interview-form-heading">
      <Link
        href="/portal/exit-interviews"
        onClick={handleBackNavigation}
        className="inline-flex min-h-9 items-center text-sm font-semibold text-brand underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        Back to Exit Interviews
      </Link>
      <ExitInterviewHeading
        id="exit-interview-form-heading"
        title="Exit Interview"
        description={`${detail.academic_year.label} · Draft response`}
      />

      <ExitInterviewCorrectionHistory events={detail.reopen_events} emphasizeLatest />

      <form onSubmit={handleSubmit} aria-busy={pending}>
        <ExitInterviewFormSections
          form={form}
          disabled={pending || submissionUncertain}
          onTextChange={updateText}
          onProgramCompletionChange={changeCompletion}
          onToggleDelayReason={toggleDelayReason}
          onToggleLearning={toggleLearning}
          onToggleCareerMode={toggleCareerMode}
          onToggleWorkChoice={(value) => {
            setForm((current) => ({ ...current, workChoices: toggle(current.workChoices, value) }));
            setSaveMessage("");
          }}
          onToggleStudyChoice={(value) => {
            setForm((current) => ({ ...current, studyChoices: toggle(current.studyChoices, value) }));
            setSaveMessage("");
          }}
          onRatingChange={updateRating}
        />

        <div className="border-t border-border py-6">
          <div aria-live="polite" className="space-y-1 text-sm text-muted">
            <p>Self-Assessment: {selfAnswered} of {SELF_ASSESSMENT_ITEMS.length} answered</p>
            <p>College Feedback: {collegeAnswered} of {collegeItems.length} answered</p>
          </div>
          {isDirty ? <p className="mt-3 text-sm text-warning">Unsaved changes. Save your draft before submitting.</p> : null}
          {saveMessage ? <p role="status" className="mt-3 text-sm text-success">{saveMessage}</p> : null}
          {saveError ? (
            <div className="mt-4 max-w-2xl">
              <ExitInterviewError error={saveError} fallback="The draft could not be saved. Your entries are still on this page." />
            </div>
          ) : null}
          {submitError && !confirmSubmit ? (
            <div className="mt-4 max-w-2xl" role="alert">
              <p className="text-sm leading-6 text-danger">
                {submissionUncertain
                  ? "We could not confirm whether submission completed. Refresh the Exit Interview before trying again."
                  : exitInterviewErrorMessage(submitError, "The Exit Interview could not be submitted. Your saved draft remains available.")}
              </p>
              {submissionUncertain ? (
                <div className="mt-3">
                  <Button type="button" variant="secondary" onClick={() => void refreshCanonicalRecord()}>
                    Refresh Exit Interview
                  </Button>
                  {refreshError ? <p className="mt-2 text-sm text-danger">The Exit Interview could not be refreshed. Retry before submitting again.</p> : null}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="mt-5 flex flex-wrap gap-3">
            <Button type="button" variant="secondary" onClick={() => void saveDraft()} disabled={pending || submissionUncertain}>
              {save.isPending ? "Saving…" : "Save draft"}
            </Button>
            <Button type="submit" disabled={!allRatingsComplete || isDirty || pending || submissionUncertain}>
              Submit Exit Interview
            </Button>
          </div>
        </div>
      </form>

      <Dialog open={confirmSubmit} onOpenChange={(open) => {
        if (!submit.isPending) setConfirmSubmit(open);
      }}>
        <DialogContent aria-describedby="exit-interview-submit-description">
          <DialogTitle>Submit Exit Interview?</DialogTitle>
          <DialogDescription id="exit-interview-submit-description">
            Your response will be available to Head Guidance for review. You will not be able to edit it after submission unless it is reopened for correction.
          </DialogDescription>
          {submitError ? (
            <p role="alert" className="mt-4 text-sm leading-6 text-danger">
              {exitInterviewErrorMessage(submitError, "The Exit Interview could not be submitted.")}
            </p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <Button type="button" variant="secondary" onClick={() => setConfirmSubmit(false)} disabled={submit.isPending}>
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void submitDraft()}
              disabled={submit.isPending || submissionUncertain}
            >
              {submit.isPending ? "Submitting…" : "Submit Exit Interview"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
