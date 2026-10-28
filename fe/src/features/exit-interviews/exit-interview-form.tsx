"use client";

import { studentActionsQueryFamily } from "@/features/student-actions/student-actions-data";

import { useMemo, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button, buttonVariants } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelSection, PanelMessage } from "@/components/ui/panel";
import { FormErrorSummary, FormSaveStatus, FormSectionLinks } from "@/components/ui/form-experience";
import { GuardedPortalLink } from "@/features/form-safety/guarded-portal-link";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import type { ExitInterviewCorrectionTarget, ExitInterviewDetailResponse } from "@/lib/api/generated/model";
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
  collegeFeedbackCategories,
  SELF_ASSESSMENT_ITEMS,
} from "@/features/exit-interviews/exit-interview-presentation";
import {
  ExitInterviewFormSections,
  exitRatingRowId,
  type ExitInterviewTextFieldKey,
} from "@/features/exit-interviews/exit-interview-form-sections";
import {
  ExitInterviewHeading,
  exitInterviewErrorMessage,
  isUncertainExitInterviewMutation,
} from "@/features/exit-interviews/exit-interview-shared";
import { ExitInterviewCorrectionHistory } from "@/features/exit-interviews/exit-interview-correction-history";
import {
  exitInterviewCorrectionSections,
  exitInterviewCorrectionFocusOrder,
  exitInterviewReviewHints,
  focusExitInterviewCorrectionTarget,
  readExitInterviewCorrectionTargets,
} from "@/features/exit-interviews/exit-interview-correction-targets";
import { ExitInterviewReviewProvider } from "@/features/exit-interviews/exit-interview-review-context";
import {
  exitInterviewsSubmitMine,
  exitInterviewsUpdateMine,
  getExitInterviewsGetMineQueryKey,
  getExitInterviewsGetMyCurrentQueryKey,
  getExitInterviewsGetMyStatusQueryKey,
  getExitInterviewsListMineQueryKey,
} from "@/lib/api/generated/exit-interviews/exit-interviews";

function toggle<T extends string>(values: readonly T[], value: T): T[] {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function isValidExtraTerms(value: string): boolean {
  if (!value.trim()) return false;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1;
}

export function ExitInterviewForm({
  detail,
  onRefreshRecord,
  writesUnavailable = false,
  refreshNotice,
}: {
  detail: ExitInterviewDetailResponse;
  onRefreshRecord: () => Promise<ExitInterviewDetailResponse | undefined>;
  // Set while the record's status could not be confirmed; answers stay editable.
  writesUnavailable?: boolean;
  refreshNotice?: ReactNode;
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
  const [extraTermsError, setExtraTermsError] = useState<string>();
  const [invalidRatingTargetId, setInvalidRatingTargetId] = useState<string>();
  const isDirty = JSON.stringify(form) !== JSON.stringify(savedForm);
  // An editable draft with reopen events is answering the latest one; earlier events are history.
  const pendingTargetValues = detail.reopen_events.at(-1)?.targets;
  const pendingTargets = useMemo(
    () => readExitInterviewCorrectionTargets(pendingTargetValues).targets,
    [pendingTargetValues],
  );
  // Advisory only: a target never marks an answer invalid, changes it, or blocks saving or submitting.
  const reviewHints = useMemo(() => exitInterviewReviewHints(pendingTargets, form), [pendingTargets, form]);

  useUnsavedChangesGuard({
    dirty: isDirty,
    message: "Leave this Exit Interview? Your unsaved changes will be discarded.",
  });

  const save = useMutation({
    mutationFn: (payload: ReturnType<typeof exitInterviewDraftPayload>) =>
      exitInterviewsUpdateMine(detail.id, payload),
    retry: false,
  });
  const submit = useMutation({
    mutationFn: () => exitInterviewsSubmitMine(detail.id),
    retry: false,
  });


  function updateText(field: ExitInterviewTextFieldKey, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    if (field === "extraTermsCount" && isValidExtraTerms(value)) {
      setExtraTermsError(undefined);
    }
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
    const targetId = exitRatingRowId(section === "selfRatings" ? "self" : "college", code);
    if (invalidRatingTargetId === targetId) setInvalidRatingTargetId(undefined);
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
    if (value !== ProgramCompletionValue.WITH_SOME_DELAY) setExtraTermsError(undefined);
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
    if (
      form.programCompletion === ProgramCompletionValue.WITH_SOME_DELAY &&
      !isValidExtraTerms(form.extraTermsCount)
    ) {
      setExtraTermsError("Enter the number of extra terms as a positive whole number.");
      const target = document.getElementById("exit-extra-terms");
      target?.scrollIntoView({ block: "center" });
      target?.focus({ preventScroll: true });
      return;
    }
    setExtraTermsError(undefined);
    try {
      const result = await save.mutateAsync(exitInterviewDraftPayload(form));
      queryClient.setQueryData(getExitInterviewsGetMineQueryKey(detail.id), result);
      const canonical = exitInterviewFormFromDetail(result.data);
      setForm(canonical);
      setSavedForm(canonical);
      setSaveMessage("Draft saved.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyCurrentQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyStatusQueryKey() }),
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
        queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyCurrentQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getExitInterviewsGetMyStatusQueryKey() }),
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
    void queryClient.invalidateQueries({ queryKey: studentActionsQueryFamily() });
    setForm(nextForm);
    setSavedForm(nextForm);
    setSubmissionUncertain(false);
    setSubmitError(undefined);
    setSaveError(undefined);
    setSaveMessage("");
    setExtraTermsError(undefined);
    setInvalidRatingTargetId(undefined);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isDirty || submissionUncertain || writesUnavailable || !allRatingsComplete) return;
    setSubmitError(undefined);
    setConfirmSubmit(true);
  }

  const selfAnswered = answeredCount(SELF_ASSESSMENT_ITEMS, form.selfRatings);
  const collegeItems = collegeFeedbackCategories(form.collegeFeedbackItemCodes).flatMap((category) => category.items);
  const collegeAnswered = answeredCount(collegeItems, form.collegeRatings);
  const missingRatings = [
    ...SELF_ASSESSMENT_ITEMS
      .filter((item) => !form.selfRatings[item.code])
      .map((item) => ({
        sectionLabel: "Self-Assessment",
        label: item.label,
        targetId: exitRatingRowId("self", item.code),
      })),
    ...collegeFeedbackCategories(form.collegeFeedbackItemCodes).flatMap((category) =>
      category.items
        .filter((item) => !form.collegeRatings[item.code])
        .map((item) => ({
          sectionLabel: `College Feedback — ${category.label}`,
          label: item.label,
          targetId: exitRatingRowId("college", item.code),
        })),
    ),
  ];
  const allRatingsComplete =
    selfAnswered === SELF_ASSESSMENT_ITEMS.length &&
    collegeAnswered === collegeItems.length;

  function recoverMissingRating(targetId: string) {
    setInvalidRatingTargetId(targetId);
    const row = document.getElementById(targetId);
    row?.scrollIntoView({ block: "center" });
    row?.querySelector<HTMLInputElement>('input[type="radio"]')?.focus({ preventScroll: true });
  }

  const reviewIssues = [
    ...(extraTermsError ? [{ message: extraTermsError, targetId: "exit-extra-terms" }] : []),
    ...missingRatings.map((item) => ({ message: `${item.sectionLabel} — ${item.label}`, targetId: item.targetId })),
  ];

  function selectReviewIssue(issue: { targetId: string }) {
    if (issue.targetId.startsWith("exit-rating-")) recoverMissingRating(issue.targetId);
    else focusExitInterviewCorrectionTarget([issue.targetId]);
  }

  function selectSection(id: string) {
    const heading = document.getElementById(id);
    if (!heading) return;
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
    heading.scrollIntoView({ block: "start", inline: "nearest" });
  }

  const pending = save.isPending || submit.isPending;

  // Every section is on the page, so a requested answer is scrolled to and focused right away.
  function selectCorrectionTarget(target: ExitInterviewCorrectionTarget) {
    focusExitInterviewCorrectionTarget(exitInterviewCorrectionFocusOrder(target, form));
  }

  return (
    <section className="space-y-5" aria-labelledby="exit-interview-form-heading">
      <div>
      <GuardedPortalLink href="/portal/exit-interviews" className={pageBackLinkClass}>
        Back to Exit Interviews
      </GuardedPortalLink>
      <ExitInterviewHeading
        id="exit-interview-form-heading"
        title="Exit Interview"
        description={`${detail.academic_year.label} · Draft response`}
      />
      </div>

      {refreshNotice}

      <ExitInterviewCorrectionHistory events={detail.reopen_events} emphasizeLatest onSelectTarget={selectCorrectionTarget} />

      <p className="max-w-3xl text-sm leading-6 text-muted">
        Review your university experience and future plans. You can move freely through the sections. Save your draft before leaving.
      </p>
      <FormSectionLinks
        id="exit-interview-section-links"
        label="Exit Interview sections"
        sections={[
          ...exitInterviewCorrectionSections.map((section) => ({ id: section.headingId, label: section.title.replace(/^Section [IV]+ — /, "") })),
          { id: "exit-interview-review-submit", label: "Review and submit" },
        ]}
        onSelect={selectSection}
      />
      <form onSubmit={handleSubmit} aria-busy={pending} className="@container/exit min-w-0 [overflow-wrap:anywhere] [&_h2]:scroll-mt-24 [&_h2:focus]:outline-none [&_h2:focus]:ring-2 [&_h2:focus]:ring-focus">
        <Panel as="div">
        <ExitInterviewReviewProvider value={reviewHints}>
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
          extraTermsError={extraTermsError}
          invalidRatingTargetId={invalidRatingTargetId}
        />
        </ExitInterviewReviewProvider>

        <PanelSection title="Review and submit" titleId="exit-interview-review-submit">
          <div aria-live="polite" aria-atomic="true" className="space-y-1 text-sm text-muted">
            <p>Self-Assessment: {selfAnswered} of {SELF_ASSESSMENT_ITEMS.length} answered</p>
            <p>College Feedback: {collegeAnswered} of {collegeItems.length} answered</p>
          </div>
          {reviewIssues.length ? (
            <details open={extraTermsError ? true : undefined} className="mt-3 max-w-3xl">
              <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-ink">
                {extraTermsError ? "Review these answers before saving." : `${missingRatings.length} required ${missingRatings.length === 1 ? "rating still needs" : "ratings still need"} a response.`}
              </summary>
              <FormErrorSummary
                id="exit-interview-errors"
                title="Answers to review"
                instruction="Select an item to go to its question or rating."
                issues={reviewIssues}
                onSelect={selectReviewIssue}
              />
            </details>
          ) : <p className="mt-3 text-sm leading-6 text-ink">All required ratings have a response. Review your answers before submitting.</p>}
        </PanelSection>
        <PanelFooter className="block space-y-3">
          <FormSaveStatus dirty={isDirty} saving={save.isPending} savedMessage={submit.isPending ? "Submitting…" : submissionUncertain ? "Submission status unconfirmed" : writesUnavailable ? "Latest draft status unconfirmed" : saveMessage} />
          {isDirty ? <p className="text-sm text-muted">Save your draft before submitting.</p> : null}
          {saveError ? (
            <div className="mt-4 max-w-2xl">
              <PanelMessage role="alert" tone="danger" className="px-0 sm:px-0">{exitInterviewErrorMessage(saveError, "The draft could not be saved. Your entries are still on this page.")}</PanelMessage>
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
          <div className="flex flex-wrap gap-3 *:max-w-full">
            <Button type="button" variant="secondary" onClick={() => void saveDraft()} disabled={pending || submissionUncertain || writesUnavailable}>
              {save.isPending ? "Saving…" : "Save draft"}
            </Button>
            <Button type="submit" disabled={!allRatingsComplete || isDirty || pending || submissionUncertain || writesUnavailable}>
              Submit Exit Interview
            </Button>
            <a href="#exit-interview-section-links" className={buttonVariants({ variant: "quiet", className: "min-h-11" })} onClick={(event) => {
              event.preventDefault();
              selectSection("exit-interview-section-links");
            }}>Back to sections</a>
          </div>
        </PanelFooter>
        </Panel>
      </form>

      <ConsequentialActionDialog
        open={confirmSubmit}
        title="Submit Exit Interview?"
        confirmLabel="Submit Exit Interview"
        pendingLabel="Submitting…"
        pending={submit.isPending}
        confirmDisabled={submissionUncertain}
        error={submitError ? exitInterviewErrorMessage(submitError, "The Exit Interview could not be submitted.") : null}
        onOpenChange={setConfirmSubmit}
        onConfirm={() => void submitDraft()}
      >
        <p>
          Your response will be available only to authorized Guidance and Counseling Office reviewers. You will not be able to edit it after submission unless it is reopened for correction.
        </p>
      </ConsequentialActionDialog>
    </section>
  );
}
