"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ConsequentialActionDialog } from "@/components/ui/consequential-action-dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { CanonicalPagination } from "@/features/portal/components/canonical-pagination";
import {
  formatRoutineDateTime,
  routineDeliveryModeLabel,
  routineEntryModeLabel,
  routineErrorCode,
  routineErrorMessage,
} from "@/features/routine-interviews/routine-interviews-shared";
import {
  RoutineEntryMode,
  type RoutineEncounterCandidate,
  type RoutineEvaluationPayload,
} from "@/lib/api/generated/model";
import {
  getRoutineInterviewsGetAssignedQueryKey,
  getRoutineInterviewsListAssignedQueryKey,
  getRoutineInterviewsListEncounterCandidatesQueryKey,
  getRoutineInterviewsFinalizeAssignedEvaluationMutationKey,
  getRoutineInterviewsReplaceAssignedEvaluationMutationKey,
  routineInterviewsFinalizeAssignedEvaluation,
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
  disabled = false,
  onChange,
}: {
  id: string;
  label: string;
  value: number | null;
  disabled?: boolean;
  onChange?: (value: number | null) => void;
}) {
  const describedBy = `${id}-anchors`;
  return (
    <fieldset className="min-w-0 py-4" disabled={disabled}>
      <legend className="font-medium text-ink">{label}</legend>
      <p id={describedBy} className="mt-1 text-xs text-muted">
        Scale anchors: 1 = Poor · 5 = Average · 10 = Excellent
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <label className="inline-flex min-h-10 cursor-pointer items-center gap-1.5 rounded-md border border-border-strong px-2.5 text-sm text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash">
          <input
            type="radio"
            name={id}
            value="null"
            checked={value === null}
            onChange={() => onChange?.(null)}
            aria-describedby={describedBy}
            className="accent-brand"
          />
          Not rated
        </label>
        {Array.from({ length: 10 }, (_, index) => index + 1).map((rating) => (
          <label key={rating} className="inline-flex size-10 cursor-pointer items-center justify-center gap-1 rounded-md border border-border-strong text-sm font-semibold text-ink focus-within:ring-2 focus-within:ring-focus has-[:checked]:border-brand has-[:checked]:bg-brand-wash has-[:checked]:text-brand">
            <input
              type="radio"
              name={id}
              value={rating}
              checked={value === rating}
              onChange={() => onChange?.(rating)}
              aria-label={`${label}: ${rating}`}
              aria-describedby={describedBy}
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
  initialEvaluation,
  evaluationFinalized,
}: {
  routineInterviewId: string;
  entryMode: RoutineEntryMode;
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
          <>
            <span className="block max-w-3xl">Guidance Counselor / Coordinator section. This is separate from the Student-authored Intake.</span>
            <span className="mt-1 block text-xs">Source evaluation scale: 1 = Poor · 5 = Average · 10 = Excellent.</span>
          </>
        }
      />

      {saveError ? <p role="alert" className="border-b border-border px-4 py-3 text-sm text-danger sm:px-5">{saveError}</p> : null}
      {notice ? <p role="status" className="border-b border-border px-4 py-3 text-sm text-success sm:px-5">{notice}</p> : null}

      <form
        className="px-4 sm:px-5"
        onSubmit={(event) => {
          event.preventDefault();
          void saveProgress();
        }}
      >
        <div className="divide-y divide-border">
          {ratings.map((rating) => (
            <RatingGroup
              key={rating.key}
              id={`routine-evaluation-${rating.key}`}
              label={rating.label}
              value={draft[rating.key]}
              disabled={save.isPending}
              onChange={(value) => updateRating(rating.key, value)}
            />
          ))}
        </div>
        {evaluationText.map((field) => (
          <div key={field.key} className="mt-5 max-w-3xl">
            <Label htmlFor={`routine-evaluation-${field.key}`}>{field.label}</Label>
            <Textarea
              id={`routine-evaluation-${field.key}`}
              className="mt-2"
              value={draft[field.key]}
              onChange={(event) => updateText(field.key, event.target.value)}
              disabled={save.isPending}
            />
          </div>
        ))}
        <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border py-4">
          <Button type="submit" variant="secondary" disabled={save.isPending || !dirty}>
            {save.isPending ? "Saving…" : "Save evaluation"}
          </Button>
          <p role="status" className="text-sm text-muted">
            {dirty ? "Unsaved changes. Save before finalizing." : "Saved"}
          </p>
        </div>
      </form>

      <RoutineEncounterFinalization
        routineInterviewId={routineInterviewId}
        entryMode={entryMode}
        disabled={dirty || save.isPending}
      />
    </Panel>
  );
}

function RoutineEncounterFinalization({
  routineInterviewId,
  entryMode,
  disabled,
}: {
  routineInterviewId: string;
  entryMode: RoutineEntryMode;
  disabled: boolean;
}) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [selectedEncounterId, setSelectedEncounterId] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const appointmentBacked = entryMode === RoutineEntryMode.APPOINTMENT;
  const params = { page, page_size: 20 };
  const candidates = useRoutineInterviewsListEncounterCandidates(
    routineInterviewId,
    params,
    { query: { retry: false } },
  );
  const pageData = candidates.data?.data;
  const items = pageData?.items ?? [];
  const finalize = useMutation({
    mutationKey: getRoutineInterviewsFinalizeAssignedEvaluationMutationKey(),
    mutationFn: () =>
      routineInterviewsFinalizeAssignedEvaluation(routineInterviewId, {
        encounter_id: appointmentBacked ? null : selectedEncounterId,
      }),
  });
  const pending = finalize.isPending;

  async function confirmFinalize() {
    if (disabled || pending || (!appointmentBacked && !selectedEncounterId)) return;
    setError(null);
    try {
      const response = await finalize.mutateAsync();
      queryClient.setQueryData(getRoutineInterviewsGetAssignedQueryKey(routineInterviewId), response);
      setConfirmOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) }),
        queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListAssignedQueryKey() }),
        queryClient.invalidateQueries({ queryKey: getRoutineInterviewsListEncounterCandidatesQueryKey(routineInterviewId) }),
      ]);
    } catch (caught) {
      const code = routineErrorCode(caught);
      setError(code === "routine_interview_encounter_mismatch" || code === "routine_interview_encounter_required"
        ? "The Counseling interaction changed while this page was open. Available completed Encounters have been refreshed; review the current options before trying again."
        : routineErrorMessage(caught, "The Counselor Evaluation could not be finalized."));
      if (code === "routine_interview_encounter_mismatch" || code === "routine_interview_encounter_required") {
        setSelectedEncounterId("");
        void candidates.refetch();
      }
      void queryClient.invalidateQueries({ queryKey: getRoutineInterviewsGetAssignedQueryKey(routineInterviewId) });
    }
  }

  return (
    <section aria-labelledby="routine-encounter-finalization" className="border-t border-brand-line px-4 py-5 sm:px-5">
      <h3 id="routine-encounter-finalization" className="font-heading text-sm font-semibold uppercase tracking-[0.08em] text-brand">Finalize against a completed Counseling interaction</h3>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
        Finalizing is separate from saving. COMPASS verifies the completed Counseling Encounter and permanently locks this Evaluation.
      </p>

      {candidates.isPending ? (
        <div aria-busy="true" className="mt-4 space-y-3"><span className="sr-only">Loading completed Counseling interactions…</span>
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : candidates.isError ? (
        <div role="alert" className="mt-4">
          <p className="text-sm text-danger">{routineErrorMessage(candidates.error, "Matching completed Counseling interactions could not be loaded.")}</p>
          <Button className="mt-3" variant="secondary" onClick={() => void candidates.refetch()}>Retry</Button>
        </div>
      ) : items.length === 0 ? (
        <div className="mt-4 rounded-sm bg-surface-subtle px-4 py-3">
          <p className="font-medium text-ink">{appointmentBacked ? "Counseling interaction not yet recorded" : "No matching completed Counseling Encounter is available yet."}</p>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            {appointmentBacked
              ? "A completed Counseling Encounter for this Appointment is required before the Evaluation can be finalized."
              : "Record the completed Counseling interaction in the Counseling workspace before finalizing this Evaluation."}
          </p>
        </div>
      ) : (
        <>
          {appointmentBacked ? (
            <p className="mt-4 rounded-sm bg-surface-subtle px-4 py-3 text-sm text-ink">
              A completed Counseling Encounter for this Appointment is available. COMPASS will resolve and link it automatically during finalization.
            </p>
          ) : (
            <fieldset className="mt-4 min-w-0">
              <legend className="mb-2 text-sm font-medium text-ink">Select the completed Counseling Encounter</legend>
              <div className="divide-y divide-border rounded-sm border border-border">
                {items.map((candidate: RoutineEncounterCandidate) => (
                  <label key={candidate.id} className="flex cursor-pointer items-start gap-3 px-3 py-3 has-[:checked]:bg-brand-wash">
                    <input
                      type="radio"
                      name="routine-finalize-encounter"
                      value={candidate.id}
                      checked={candidate.id === selectedEncounterId}
                      onChange={() => setSelectedEncounterId(candidate.id)}
                      className="mt-1 size-4 accent-brand"
                    />
                    <span>
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
          )}
        </>
      )}

      {error && !confirmOpen ? <p role="alert" className="mt-4 text-sm text-danger">{error}</p> : null}
      <Button
        className="mt-5"
        disabled={disabled || pending || candidates.isPending || candidates.isError || items.length === 0 || (!appointmentBacked && !selectedEncounterId)}
        onClick={() => setConfirmOpen(true)}
      >
        Finalize Counselor Evaluation
      </Button>

      <ConsequentialActionDialog
        open={confirmOpen}
        title="Finalize Counselor Evaluation?"
        confirmLabel="Finalize evaluation"
        pendingLabel="Finalizing…"
        pending={pending}
        confirmDisabled={disabled}
        error={error}
        onOpenChange={setConfirmOpen}
        onConfirm={() => void confirmFinalize()}
      >
        <p>
          After finalization, this Evaluation becomes read-only and remains
          linked to the completed Counseling interaction used for finalization.
        </p>
      </ConsequentialActionDialog>
    </section>
  );
}
