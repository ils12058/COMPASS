"use client";

import { invalidateGuidanceWork } from "@/features/freshness/guidance-work-invalidation";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { FormSaveStatus } from "@/components/ui/form-experience";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import {
  Panel,
  PanelFooter,
  PanelHeader,
  PanelMessage,
  PanelSection,
} from "@/components/ui/panel";
import { useUnsavedChangesGuard } from "@/features/form-safety/use-unsaved-changes-guard";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  formatRoutineDateTime,
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorCode,
  routineErrorMessage,
} from "@/features/routine-interviews/routine-interviews-shared";
import { CompassApiError } from "@/lib/api/errors";
import {
  RoutineEntryMode,
  type RoutineEncounterCandidate,
  type RoutineEncounterSummary,
  type RoutineEvaluationPayload,
} from "@/lib/api/generated/model";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryOptions,
  getRoutineInterviewsFinalizeAssignedEvaluationMutationKey,
  getRoutineInterviewsReplaceAssignedEvaluationMutationKey,
  routineInterviewsFinalizeAssignedEvaluation,
  routineInterviewsGetAssigned,
  routineInterviewsReplaceAssignedEvaluation,
  useRoutineInterviewsListEncounterCandidates,
} from "@/lib/api/generated/routine-interviews/routine-interviews";

type RatingKey =
  | "academic_adjustment_rating"
  | "physical_adjustment_rating"
  | "social_adjustment_rating"
  | "spiritual_adjustment_rating"
  | "financial_adjustment_rating"
  | "emotional_adjustment_rating";

type EvaluationTextKey =
  | "other_adjustment"
  | "special_concern"
  | "recommendations";

type EvaluationDraft = Record<RatingKey, number | null> & Record<EvaluationTextKey, string>;

const ratings: { key: RatingKey; label: string }[] = [
  { key: "academic_adjustment_rating", label: "Academically" },
  { key: "physical_adjustment_rating", label: "Physically" },
  { key: "social_adjustment_rating", label: "Socially" },
  { key: "spiritual_adjustment_rating", label: "Spiritually" },
  { key: "financial_adjustment_rating", label: "Financially" },
  { key: "emotional_adjustment_rating", label: "Emotionally" },
];

const evaluationText: { key: EvaluationTextKey; label: string }[] = [
  { key: "other_adjustment", label: "Other adjustment" },
  { key: "special_concern", label: "Special concern that needs attention" },
  { key: "recommendations", label: "Recommendations" },
];

function normalizeEvaluation(
  evaluation: RoutineEvaluationPayload,
): EvaluationDraft {
  return {
    academic_adjustment_rating: evaluation.academic_adjustment_rating ?? null,
    physical_adjustment_rating: evaluation.physical_adjustment_rating ?? null,
    social_adjustment_rating: evaluation.social_adjustment_rating ?? null,
    spiritual_adjustment_rating: evaluation.spiritual_adjustment_rating ?? null,
    financial_adjustment_rating: evaluation.financial_adjustment_rating ?? null,
    emotional_adjustment_rating: evaluation.emotional_adjustment_rating ?? null,
    other_adjustment: evaluation.other_adjustment ?? "",
    special_concern: evaluation.special_concern ?? "",
    recommendations: evaluation.recommendations ?? "",
  };
}

function asPayload(draft: EvaluationDraft): RoutineEvaluationPayload {
  return { ...draft };
}

function ratingLabel(value: number | null | undefined): string {
  return value == null ? "Not rated" : String(value);
}

function RatingGroup({
  id,
  label,
  value,
  scaleDescriptionId,
  disabled = false,
  onChange,
}: {
  id: string;
  label: string;
  value: number | null;
  scaleDescriptionId: string;
  disabled?: boolean;
  onChange?: (value: number | null) => void;
}) {
  return (
    <fieldset
      className="min-w-0 py-3"
      disabled={disabled}
      aria-describedby={scaleDescriptionId}
    >
      <legend className="font-medium text-ink">{label}</legend>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-sm text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash">
          <input
            type="radio"
            name={id}
            value="null"
            checked={value === null}
            onChange={() => onChange?.(null)}
            aria-describedby={scaleDescriptionId}
            className="accent-brand"
          />
          Not rated
        </label>
        {Array.from({ length: 10 }, (_, index) => index + 1).map((rating) => (
          <label key={rating} className="inline-flex size-11 cursor-pointer items-center justify-center gap-1 rounded-md border border-border-strong text-sm font-semibold text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:checked]:text-brand">
            <input
              type="radio"
              name={id}
              value={rating}
              checked={value === rating}
              onChange={() => onChange?.(rating)}
              aria-label={`${label}: ${rating}`}
              aria-describedby={scaleDescriptionId}
              className="sr-only"
            />
            {rating}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function RoutineCounselorEvaluationReadOnly({
  evaluation,
}: {
  evaluation: RoutineEvaluationPayload;
}) {
  const values = normalizeEvaluation(evaluation);
  return (
    <div className="divide-y divide-border">
      <p className="py-4 text-sm text-muted">
        Source evaluation scale: 1 = Poor · 5 = Average · 10 = Excellent.
      </p>
      {ratings.map((rating) => (
        <div key={rating.key} className="flex flex-wrap items-center justify-between gap-2 py-3">
          <p className="text-sm text-ink">{rating.label}</p>
          <p className="text-sm font-semibold text-ink">{ratingLabel(values[rating.key])}</p>
        </div>
      ))}
      {evaluationText.map((field) => (
        <div key={field.key} className="py-4">
          <p className="text-sm font-medium text-muted">{field.label}</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-ink">
            {values[field.key].trim() || "Not provided"}
          </p>
        </div>
      ))}
    </div>
  );
}

export function RoutineCounselorEvaluationWorkspace({
  routineInterviewId,
  entryMode,
  linkedEncounter,
  workspaceHref,
  initialEvaluation,
  evaluationFinalized,
}: {
  routineInterviewId: string;
  entryMode: RoutineEntryMode;
  // The Counseling Encounter COMPASS has linked to this Routine Interview, if any.
  linkedEncounter: RoutineEncounterSummary | null;
  // Where the completed interaction is recorded, when this page is not already that workspace.
  workspaceHref?: string | null;
  initialEvaluation: RoutineEvaluationPayload;
  evaluationFinalized: boolean;
}) {
  const queryClient = useQueryClient();
  const canonical = normalizeEvaluation(initialEvaluation);
  const [draft, setDraft] = useState(() => canonical);
  const [saved, setSaved] = useState(() => canonical);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  useUnsavedChangesGuard({
    dirty: dirty && !evaluationFinalized,
    message: "Discard your unsaved Counselor Evaluation changes?",
  });
  const save = useMutation({
    mutationKey: getRoutineInterviewsReplaceAssignedEvaluationMutationKey(),
    mutationFn: (data: RoutineEvaluationPayload) =>
      routineInterviewsReplaceAssignedEvaluation(routineInterviewId, data),
  });

  async function saveProgress() {
    if (save.isPending || !dirty) return;
    setSaveError(null);
    setNotice(null);
    try {
      const response = await save.mutateAsync(asPayload(draft));
      const nextDraft = normalizeEvaluation(response.data.evaluation);
      setDraft(nextDraft);
      setSaved(nextDraft);
      queryClient.setQueryData(getRoutineInterviewsGetAssignedQueryKey(routineInterviewId), response);
      await queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() });
      setNotice("Evaluation progress saved.");
    } catch (caught) {
      setSaveError(routineErrorMessage(caught, "The Counselor Evaluation could not be saved."));
      if (routineErrorCode(caught)) {
        void queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) });
        void queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() });
      }
    }
  }

  function updateRating(key: RatingKey, value: number | null) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaveError(null);
    setNotice(null);
  }

  function updateText(key: EvaluationTextKey, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaveError(null);
    setNotice(null);
  }

  function acceptCanonicalEvaluation(evaluation: RoutineEvaluationPayload) {
    const current = normalizeEvaluation(evaluation);
    setDraft(current);
    setSaved(current);
    setSaveError(null);
    setNotice(null);
  }

  if (evaluationFinalized) {
    return (
      <Panel aria-labelledby="routine-evaluation-heading">
        <PanelHeader title="Counselor Evaluation" titleId="routine-evaluation-heading" description="This finalized evaluation is read-only." />
        <div className="px-4 sm:px-5">
          <RoutineCounselorEvaluationReadOnly evaluation={initialEvaluation} />
        </div>
      </Panel>
    );
  }

  return (
    <Panel aria-labelledby="routine-evaluation-heading">
      <PanelHeader
        title="Counselor Evaluation"
        titleId="routine-evaluation-heading"
        description={
          "Counselor-authored professional documentation, separate from the Student Intake."
        }
      />

      {saveError ? (
        <PanelMessage role="alert" tone="danger">
          {saveError}
        </PanelMessage>
      ) : null}

      <form
        className="min-w-0"
        onSubmit={(event) => {
          event.preventDefault();
          void saveProgress();
        }}
      >
        <PanelSection
          title="Adjustment ratings"
          titleId="routine-evaluation-ratings-heading"
          description="Choose a value from 1 to 10, or Not rated. The source scale anchors are 1 = Poor, 5 = Average, and 10 = Excellent."
        >
          <div className="max-w-5xl @container/evaluation">
            <div className="divide-y divide-border @3xl/evaluation:grid @3xl/evaluation:grid-cols-2 @3xl/evaluation:divide-y-0 @3xl/evaluation:gap-x-8">
              {ratings.map((rating) => (
                <RatingGroup
                  key={rating.key}
                  id={`routine-evaluation-${rating.key}`}
                  label={rating.label}
                  value={draft[rating.key]}
                  scaleDescriptionId="routine-evaluation-scale-description"
                  disabled={save.isPending}
                  onChange={(value) => updateRating(rating.key, value)}
                />
              ))}
            </div>
          </div>
          <span id="routine-evaluation-scale-description" className="sr-only">
            Rating options are Not rated and integers from 1 through 10. Source scale anchors: 1 = Poor, 5 = Average, and 10 = Excellent.
          </span>
        </PanelSection>

        <PanelSection
          title="Narrative observations"
          titleId="routine-evaluation-narrative-heading"
          description="Complete the existing narrative fields in the Counselor's own words."
        >
          <div className="max-w-3xl space-y-5">
            {evaluationText.map((field) => (
              <div key={field.key} className="min-w-0">
                <Label
                  htmlFor={`routine-evaluation-${field.key}`}
                  className="block max-w-full break-words"
                >
                  {field.label}
                </Label>
                <Textarea
                  id={`routine-evaluation-${field.key}`}
                  className="mt-2 min-h-36"
                  rows={5}
                  value={draft[field.key]}
                  onChange={(event) => updateText(field.key, event.target.value)}
                  disabled={save.isPending}
                />
              </div>
            ))}
          </div>
        </PanelSection>

        <PanelFooter>
          <Button type="submit" variant="secondary" disabled={save.isPending || !dirty}>
            Save Evaluation
          </Button>
          <div className="min-w-0">
            <FormSaveStatus
              dirty={dirty}
              saving={save.isPending}
              savedMessage={notice}
            />
            <p className="mt-1 text-xs text-muted">
              Saving keeps this draft editable. Finalization is a separate action.
            </p>
          </div>
        </PanelFooter>
      </form>

      <RoutineEncounterFinalization
        routineInterviewId={routineInterviewId}
        entryMode={entryMode}
        linkedEncounter={linkedEncounter}
        workspaceHref={workspaceHref ?? null}
        disabled={dirty || save.isPending}
        onCanonicalEvaluation={acceptCanonicalEvaluation}
      />
    </Panel>
  );
}

function RoutineEncounterFinalization({
  routineInterviewId,
  entryMode,
  linkedEncounter,
  workspaceHref,
  disabled,
  onCanonicalEvaluation,
}: {
  routineInterviewId: string;
  entryMode: RoutineEntryMode;
  linkedEncounter: RoutineEncounterSummary | null;
  workspaceHref: string | null;
  disabled: boolean;
  onCanonicalEvaluation: (evaluation: RoutineEvaluationPayload) => void;
}) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [selectedEncounterId, setSelectedEncounterId] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [requiresStatusCheck, setRequiresStatusCheck] = useState(false);
  const [checkingCurrentStatus, setCheckingCurrentStatus] = useState(false);
  const [reconciliationMessage, setReconciliationMessage] = useState<string | null>(null);
  const appointmentBacked = entryMode === RoutineEntryMode.APPOINTMENT;
  const linked = linkedEncounter !== null;
  // Only an unlinked direct Routine Interview needs the Counselor to name an Encounter: one
  // recorded outside its Counseling workspace. An Appointment-backed one resolves its single
  // Appointment Encounter on the server.
  const recovery = !linked && !appointmentBacked;
  const params = { page, page_size: 20 };
  const candidates = useRoutineInterviewsListEncounterCandidates(
    routineInterviewId,
    params,
    { query: { enabled: !linked, retry: false } },
  );
  const pageData = candidates.data?.data;
  const items = pageData?.items ?? [];
  const finalize = useMutation({
    mutationKey: getRoutineInterviewsFinalizeAssignedEvaluationMutationKey(),
    mutationFn: () =>
      routineInterviewsFinalizeAssignedEvaluation(routineInterviewId, {
        encounter_id: recovery ? selectedEncounterId : null,
      }),
  });
  const pending = finalize.isPending;
  const ready = linked || (!candidates.isPending && !candidates.isError && items.length > 0 && (!recovery || Boolean(selectedEncounterId)));

  async function checkCurrentStatus() {
    setCheckingCurrentStatus(true);
    setError(null);
    setReconciliationMessage(null);
    try {
      const current = await routineInterviewsGetAssigned(routineInterviewId);
      queryClient.setQueryData(
        getRoutineInterviewsGetAssignedQueryKey(routineInterviewId),
        current,
      );
      if (current.data.evaluation_status === "FINALIZED") {
        setRequiresStatusCheck(false);
        return;
      }
      if (current.data.evaluation_status !== "DRAFT") {
        throw new Error("The current Evaluation status is unavailable.");
      }
      onCanonicalEvaluation(current.data.evaluation);
      if (!current.data.counseling_encounter) {
        await queryClient.fetchQuery({
          ...getRoutineInterviewsListEncounterCandidatesQueryOptions(
            routineInterviewId,
            params,
            { query: { retry: false, staleTime: 0 } },
          ),
          retry: false,
          staleTime: 0,
        });
      }
      setRequiresStatusCheck(false);
      setReconciliationMessage(
        "The latest Evaluation is still a draft. Review the current Counseling Encounter details before finalizing again.",
      );
    } catch {
      setRequiresStatusCheck(true);
      setError(
        "The current Evaluation status could not be confirmed. Check it before trying to finalize again.",
      );
    } finally {
      setCheckingCurrentStatus(false);
    }
  }

  async function confirmFinalize() {
    if (disabled || pending || !ready || requiresStatusCheck) return;
    setError(null);
    setReconciliationMessage(null);
    let response;
    try {
      response = await finalize.mutateAsync();
    } catch (caught) {
      const code = routineErrorCode(caught);
      const changed =
        code === "routine_interview_encounter_mismatch" ||
        code === "routine_interview_encounter_required" ||
        code === "routine_interview_encounter_conflict" ||
        code === "routine_interview_evaluation_finalized";
      const uncertain =
        !(caught instanceof CompassApiError) ||
        caught.status === 408 ||
        caught.status >= 500;
      if (changed || uncertain) {
        setSelectedEncounterId("");
        setConfirmOpen(false);
        setRequiresStatusCheck(true);
        setError(
          uncertain
            ? "Finalization could not be confirmed. Checking the current record before another attempt."
            : "The Counseling interaction changed. Checking the latest Evaluation and Encounter details before another attempt.",
        );
        await checkCurrentStatus();
      } else {
        setError(routineErrorMessage(caught, "The Counselor Evaluation could not be finalized."));
        if (routineErrorCode(caught)) {
          void queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) });
        }
      }
      return;
    }

    queryClient.setQueryData(getRoutineInterviewsGetAssignedQueryKey(routineInterviewId), response);
    setConfirmOpen(false);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) }),
      queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() }),
      invalidateGuidanceWork(queryClient),
      queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(routineInterviewId) }),
    ]);
  }

  const recordLink = workspaceHref ? (
    <Link href={workspaceHref} className="font-semibold text-brand underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
      Open Counseling workspace
    </Link>
  ) : null;

  return (
    <PanelSection
      title="Finalize evaluation"
      titleId="routine-encounter-finalization"
      level={3}
      description="Finalization links a completed Counseling Encounter and makes this Evaluation read-only in this workflow."
    >
      {disabled ? (
        <PanelMessage role="status">
          Save the Evaluation before finalizing it.
        </PanelMessage>
      ) : null}

      {linkedEncounter ? (
        <dl className="mt-4 max-w-3xl">
          <dt className="text-sm font-medium text-ink">Encounter already linked</dt>
          <dd className="mt-1 text-sm text-ink">
            {formatRoutineDateTime(linkedEncounter.started_at)}
            <span className="block text-muted">Ended {formatRoutineDateTime(linkedEncounter.ended_at)}</span>
          </dd>
        </dl>
      ) : candidates.isPending ? (
        <div aria-busy="true" className="mt-4 space-y-3"><span className="sr-only">Loading completed Counseling interactions…</span>
          <Skeleton className="h-14 w-full" />
        </div>
      ) : candidates.isError ? (
        <PanelMessage
          className="mt-4 px-0 sm:px-0"
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" onClick={() => void candidates.refetch()}>
              Retry
            </Button>
          }
        >
          {routineErrorMessage(candidates.error, "Completed Counseling interactions could not be loaded.")}
        </PanelMessage>
      ) : appointmentBacked ? (
        <p className="mt-4 max-w-3xl text-sm leading-6 text-ink">
          {items.length > 0
            ? "The completed Counseling Encounter for this Appointment is available. Finalization will link it to this Routine Interview."
            : "A completed, matching Counseling Encounter for this Appointment is required before finalization."}
        </p>
      ) : (
        <div className="mt-4 max-w-3xl">
          <p className="font-medium text-ink">No eligible completed Encounter is available yet.</p>
          <p className="mt-1 text-sm leading-6 text-muted">
            Record this interaction in its Counseling workspace or wait until a matching Encounter is available.{recordLink ? <> {recordLink}</> : null}
          </p>
        </div>
      )}

      {recovery && !candidates.isPending && !candidates.isError && items.length > 0 ? (
        <fieldset className="mt-4 min-w-0">
          <legend className="text-sm font-medium text-ink">Select the completed Encounter for this interaction</legend>
          <p className="mb-2 mt-1 max-w-3xl text-sm leading-6 text-muted">
            These recorded Encounters match the existing Student, Counselor, Counseling Service, visit type, and delivery rules. Select the one linked to this Routine Interview.
          </p>
          <div className="divide-y divide-border rounded-sm border border-border">
            {items.map((candidate: RoutineEncounterCandidate) => (
              <label key={candidate.id} className="flex min-h-14 cursor-pointer items-start gap-3 px-3 py-3 focus-within:relative focus-within:z-10 focus-within:ring-2 focus-within:ring-focus has-[:checked]:bg-brand-wash">
                <input
                  type="radio"
                  name="routine-finalize-encounter"
                  value={candidate.id}
                  checked={candidate.id === selectedEncounterId}
                  onChange={() => {
                    setSelectedEncounterId(candidate.id);
                    setReconciliationMessage(null);
                  }}
                  className="mt-1 size-4 accent-brand"
                />
                <span className="min-w-0 break-words">
                  <span className="block font-medium text-ink">{formatRoutineDateTime(candidate.started_at)}</span>
                  <span className="mt-1 block text-sm text-muted">Ended {formatRoutineDateTime(candidate.ended_at)} · {routineEntryModeLabel(candidate.entry_mode)} · {routineDeliveryModeLabel(candidate.delivery_mode)}</span>
                </span>
              </label>
            ))}
          </div>
          {pageData ? (
            <CanonicalPagination
              className="mt-3"
              page={pageData.page}
              hasNext={pageData.has_next}
              disabled={candidates.isFetching}
              label="Counseling Encounter candidate pages"
              onPageChange={setPage}
            />
          ) : null}
        </fieldset>
      ) : null}

      {checkingCurrentStatus ? (
        <PanelMessage role="status" className="mt-4 px-0 sm:px-0">
          Checking the current Evaluation and Encounter details…
        </PanelMessage>
      ) : null}
      {requiresStatusCheck && !checkingCurrentStatus ? (
        <PanelMessage
          className="mt-4 px-0 sm:px-0"
          role="alert"
          tone="danger"
          action={
            <Button variant="secondary" onClick={() => void checkCurrentStatus()}>
              Check current status
            </Button>
          }
        >
          {error}
        </PanelMessage>
      ) : null}
      {reconciliationMessage ? (
        <PanelMessage role="status" className="mt-4 px-0 sm:px-0">
          {reconciliationMessage}
        </PanelMessage>
      ) : null}
      {error && !confirmOpen && !requiresStatusCheck && !checkingCurrentStatus ? (
        <PanelMessage role="alert" tone="danger" className="mt-4 px-0 sm:px-0">
          {error}
        </PanelMessage>
      ) : null}
      <Button
        className="mt-5"
        disabled={disabled || pending || !ready || requiresStatusCheck || checkingCurrentStatus}
        onClick={() => {
          setError(null);
          setReconciliationMessage(null);
          setConfirmOpen(true);
        }}
      >
        Finalize Counselor Evaluation
      </Button>

      <ConsequentialActionDialog
        open={confirmOpen}
        title="Finalize Counselor Evaluation?"
        confirmLabel="Finalize evaluation"
        pendingLabel="Finalizing…"
        pending={pending}
        confirmDisabled={disabled || requiresStatusCheck || checkingCurrentStatus}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void confirmFinalize()}
      >
        <p>
          Finalizing links the completed Counseling Encounter to this Routine Interview and makes the Evaluation read-only. You cannot edit it afterward in this workflow.
        </p>
      </ConsequentialActionDialog>
    </PanelSection>
  );
}
