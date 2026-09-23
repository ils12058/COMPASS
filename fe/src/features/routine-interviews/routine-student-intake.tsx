"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CompassApiError, readApiErrorCode } from "@/lib/api/errors";
import {
  RoutineConcernValue,
  type RoutineIntakePayload,
} from "@/lib/api/generated/model";
import {
  getRoutineInterviewsGetMineQueryKey,
  getRoutineInterviewsListMineQueryKey,
  getRoutineInterviewsReplaceMyIntakeMutationKey,
  getRoutineInterviewsSubmitMyIntakeMutationKey,
  routineInterviewsReplaceMyIntake,
  routineInterviewsSubmitMyIntake,
} from "@/lib/api/generated/routine-interviews/routine-interviews";
import { routineErrorMessage } from "@/features/routine-interviews/routine-interviews-shared";

const concernOptions: {
  value: RoutineConcernValue;
  label: string;
}[] = [
  { value: RoutineConcernValue.FAMILY, label: "Family" },
  { value: RoutineConcernValue.FINANCIAL, label: "Financial" },
  { value: RoutineConcernValue.ACADEMIC, label: "Academic" },
  { value: RoutineConcernValue.FRIENDS, label: "Friends" },
  { value: RoutineConcernValue.CLASSMATES, label: "Classmates" },
  { value: RoutineConcernValue.VICES, label: "Vices" },
  { value: RoutineConcernValue.LOVE_LIFE, label: "Love life" },
  { value: RoutineConcernValue.SLEEPING_PROBLEMS, label: "Sleeping problems" },
  {
    value: RoutineConcernValue.SUICIDAL_THOUGHT_TENDENCY,
    label: "Suicidal thought/tendency",
  },
  {
    value: RoutineConcernValue.DORM_BOARDING_HOUSE,
    label: "Dorm / boarding house",
  },
  {
    value: RoutineConcernValue.PAST_PAINFUL_EXPERIENCE,
    label: "Past painful experience",
  },
  { value: RoutineConcernValue.OTHER, label: "Other" },
];

type RoutineIntakeTextKey =
  | "coping_with_college_challenges"
  | "coping_remarks"
  | "college_experience"
  | "reason_for_choosing_institution"
  | "difficulties_encountered"
  | "stress_anxiety_causes"
  | "stress_anxiety_management"
  | "family_description"
  | "concerns_explanation"
  | "college_adjustment_and_peer_group"
  | "academic_goals"
  | "career_goals"
  | "other_concern_specification";

const intentionalResponseKeys: RoutineIntakeTextKey[] = [
  "coping_with_college_challenges",
  "coping_remarks",
  "college_experience",
  "reason_for_choosing_institution",
  "difficulties_encountered",
  "stress_anxiety_causes",
  "stress_anxiety_management",
  "family_description",
  "concerns_explanation",
  "college_adjustment_and_peer_group",
  "academic_goals",
  "career_goals",
];

export function normalizeRoutineIntake(
  intake: RoutineIntakePayload,
): RoutineIntakePayload {
  return {
    coping_with_college_challenges: intake.coping_with_college_challenges ?? "",
    coping_remarks: intake.coping_remarks ?? "",
    college_experience: intake.college_experience ?? "",
    reason_for_choosing_institution:
      intake.reason_for_choosing_institution ?? "",
    difficulties_encountered: intake.difficulties_encountered ?? "",
    stress_anxiety_causes: intake.stress_anxiety_causes ?? "",
    stress_anxiety_management: intake.stress_anxiety_management ?? "",
    family_description: intake.family_description ?? "",
    concerns: [...(intake.concerns ?? [])],
    other_concern_specification: intake.other_concern_specification ?? "",
    concerns_explanation: intake.concerns_explanation ?? "",
    college_adjustment_and_peer_group:
      intake.college_adjustment_and_peer_group ?? "",
    academic_goals: intake.academic_goals ?? "",
    career_goals: intake.career_goals ?? "",
  };
}

export function RoutineStudentIntakeReadOnly({
  intake,
}: {
  intake: RoutineIntakePayload;
}) {
  const concerns = intake.concerns ?? [];
  const selectedConcerns = concernOptions.filter((option) =>
    concerns.includes(option.value),
  );

  return (
    <div className="divide-y divide-border">
      <section className="py-5" aria-labelledby="routine-intake-q1">
        <h3 id="routine-intake-q1" className="font-heading text-lg font-semibold text-ink">
          1. Coping with college
        </h3>
        <ReadOnlyAnswer
          label="How are you? How are you coping with the challenges in college?"
          value={intake.coping_with_college_challenges}
        />
        <ReadOnlyAnswer label="Remarks" value={intake.coping_remarks} />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q2">
        <h3 id="routine-intake-q2" className="font-heading text-lg font-semibold text-ink">
          2. College experience
        </h3>
        <ReadOnlyAnswer
          label="How has your UCN experience been so far?"
          value={intake.college_experience}
        />
        <ReadOnlyAnswer
          label="What influenced your decision to come to UCN?"
          value={intake.reason_for_choosing_institution}
        />
        <ReadOnlyAnswer
          label="What difficulties have you encountered at UCN?"
          value={intake.difficulties_encountered}
        />
        <ReadOnlyAnswer
          label="What causes you stress or anxiety?"
          value={intake.stress_anxiety_causes}
        />
        <ReadOnlyAnswer
          label="How do you manage stress or anxiety?"
          value={intake.stress_anxiety_management}
        />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q3">
        <h3 id="routine-intake-q3" className="font-heading text-lg font-semibold text-ink">
          3. Family
        </h3>
        <ReadOnlyAnswer
          label="Please tell us something about your family."
          value={intake.family_description}
        />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q4">
        <h3 id="routine-intake-q4" className="font-heading text-lg font-semibold text-ink">
          4. Current concerns
        </h3>
        <div className="mt-4">
          <p className="text-sm font-semibold text-ink">
            What concerns do you have right now?
          </p>
          {selectedConcerns.length ? (
            <ul className="mt-2 flex flex-wrap gap-2">
              {selectedConcerns.map((option) => (
                <li
                  key={option.value}
                  className="rounded-md border border-border bg-surface-muted px-2.5 py-1 text-sm text-ink"
                >
                  {option.label}
                  {option.value === RoutineConcernValue.OTHER &&
                  intake.other_concern_specification?.trim()
                    ? ": " + intake.other_concern_specification
                    : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">Not provided</p>
          )}
        </div>
        <ReadOnlyAnswer
          label="Please tell us more about your concerns."
          value={intake.concerns_explanation}
        />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q5">
        <h3 id="routine-intake-q5" className="font-heading text-lg font-semibold text-ink">
          5. College adjustment
        </h3>
        <ReadOnlyAnswer
          label="How are you adjusting to college life? How about your peer group or barkada?"
          value={intake.college_adjustment_and_peer_group}
        />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q6">
        <h3 id="routine-intake-q6" className="font-heading text-lg font-semibold text-ink">
          6. Academic goals
        </h3>
        <ReadOnlyAnswer
          label="What are your academic goals?"
          value={intake.academic_goals}
        />
      </section>

      <section className="py-5" aria-labelledby="routine-intake-q7">
        <h3 id="routine-intake-q7" className="font-heading text-lg font-semibold text-ink">
          7. Career goals
        </h3>
        <ReadOnlyAnswer
          label="What are your career goals?"
          value={intake.career_goals}
        />
      </section>
    </div>
  );
}

function ReadOnlyAnswer({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  return (
    <div className="mt-4">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-ink">
        {value?.trim() ? value : "Not provided"}
      </p>
    </div>
  );
}

export function RoutineStudentIntakeEditor({
  routineInterviewId,
  initialIntake,
}: {
  routineInterviewId: string;
  initialIntake: RoutineIntakePayload;
}) {
  const queryClient = useQueryClient();
  const canonical = normalizeRoutineIntake(initialIntake);
  const [draft, setDraft] = useState(() => canonical);
  const [saved, setSaved] = useState(() => canonical);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const save = useMutation({
    mutationKey: getRoutineInterviewsReplaceMyIntakeMutationKey(),
    mutationFn: (data: RoutineIntakePayload) =>
      routineInterviewsReplaceMyIntake(routineInterviewId, data),
  });
  const submit = useMutation({
    mutationKey: getRoutineInterviewsSubmitMyIntakeMutationKey(),
    mutationFn: () => routineInterviewsSubmitMyIntake(routineInterviewId),
  });
  const pending = save.isPending || submit.isPending;
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const selectedOther =
    draft.concerns?.includes(RoutineConcernValue.OTHER) ?? false;

  useEffect(() => {
    if (!dirty) return;
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const confirmLinkNavigation = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return;
      const anchor = event.target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) return;
      if (
        anchor.origin === window.location.origin &&
        anchor.pathname === window.location.pathname
      ) {
        return;
      }
      if (
        !window.confirm(
          "Discard your unsaved Routine Interview Intake changes?",
        )
      ) {
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

  function updateText(key: RoutineIntakeTextKey, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
    setSaveError(null);
    setSubmitError(null);
    setNotice(null);
  }

  function toggleConcern(value: RoutineConcernValue) {
    setDraft((current) => {
      const currentConcerns = current.concerns ?? [];
      const isSelected = currentConcerns.includes(value);
      const concerns = isSelected
        ? currentConcerns.filter((item) => item !== value)
        : [...currentConcerns, value];
      return {
        ...current,
        concerns,
        ...(value === RoutineConcernValue.OTHER && isSelected
          ? { other_concern_specification: "" }
          : {}),
      };
    });
    setSaveError(null);
    setSubmitError(null);
    setNotice(null);
  }

  async function saveProgress(): Promise<boolean> {
    if (pending || !dirty) return !dirty;
    setSaveError(null);
    setSubmitError(null);
    setNotice(null);
    try {
      const response = await save.mutateAsync(draft);
      const nextDraft = normalizeRoutineIntake(response.data.intake);
      setDraft(nextDraft);
      setSaved(nextDraft);
      queryClient.setQueryData(
        getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        response,
      );
      setNotice("Progress saved.");
      return true;
    } catch (error) {
      const code =
        error instanceof CompassApiError
          ? readApiErrorCode(error.body)
          : undefined;
      if (
        code === "routine_interview_intake_already_submitted" ||
        code === "routine_interview_not_found"
      ) {
        void queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        });
        void queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsListMineQueryKey(),
        });
      }
      setSaveError(
        routineErrorMessage(
          error,
          "Your Routine Interview progress could not be saved.",
        ),
      );
      return false;
    }
  }

  function requestSubmit() {
    setSubmitError(null);
    if (dirty) {
      setSubmitError("Save your changes before submitting the Intake.");
      return;
    }
    if (
      !draft.concerns?.length &&
      !intentionalResponseKeys.some((key) => Boolean(draft[key]?.trim()))
    ) {
      setSubmitError(
        "Add at least one response or select a concern before submitting.",
      );
      return;
    }
    if (selectedOther && !draft.other_concern_specification?.trim()) {
      setSubmitError("Please specify the other concern before submitting.");
      document.getElementById("routine-other-concern-specification")?.focus();
      return;
    }
    setConfirmSubmit(true);
  }

  async function submitIntake() {
    if (pending) return;
    setSubmitError(null);
    setNotice(null);
    try {
      const response = await submit.mutateAsync();
      const nextDraft = normalizeRoutineIntake(response.data.intake);
      setDraft(nextDraft);
      setSaved(nextDraft);
      queryClient.setQueryData(
        getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        response,
      );
      setConfirmSubmit(false);
      setNotice("Intake submitted. Your responses are now read-only.");
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        }),
        queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsListMineQueryKey(),
        }),
      ]);
    } catch (error) {
      const code =
        error instanceof CompassApiError
          ? readApiErrorCode(error.body)
          : undefined;
      if (code === "routine_interview_intake_already_submitted") {
        void queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsGetMineQueryKey(routineInterviewId),
        });
        void queryClient.invalidateQueries({
          queryKey: getRoutineInterviewsListMineQueryKey(),
        });
      }
      setSubmitError(
        routineErrorMessage(
          error,
          "Your Routine Interview Intake could not be submitted.",
        ),
      );
    }
  }

  return (
    <section aria-labelledby="routine-student-intake-heading">
      <header className="border-b border-border pb-4">
        <h2
          id="routine-student-intake-heading"
          className="font-heading text-2xl font-semibold text-ink"
        >
          Student Intake
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          Answer what you would like to share. You may save a draft and return
          before submitting.
        </p>
      </header>

      {saveError ? (
        <p role="alert" className="mt-4 border-l-4 border-danger px-3 py-2 text-sm text-danger">
          {saveError}
        </p>
      ) : null}
      {submitError ? (
        <p role="alert" className="mt-4 border-l-4 border-danger px-3 py-2 text-sm text-danger">
          {submitError}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="mt-4 text-sm text-success">
          {notice}
        </p>
      ) : null}

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void saveProgress();
        }}
      >
        <div className="divide-y divide-border">
          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              1. Coping with college
            </legend>
            <TextField
              id="routine-coping"
              label="How are you? How are you coping with the challenges in college?"
              value={draft.coping_with_college_challenges ?? ""}
              onChange={(value) =>
                updateText("coping_with_college_challenges", value)
              }
            />
            <TextField
              id="routine-coping-remarks"
              label="Remarks"
              value={draft.coping_remarks ?? ""}
              onChange={(value) => updateText("coping_remarks", value)}
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              2. College experience
            </legend>
            <TextField
              id="routine-college-experience"
              label="How has your UCN experience been so far?"
              value={draft.college_experience ?? ""}
              onChange={(value) => updateText("college_experience", value)}
            />
            <TextField
              id="routine-reason-for-choosing"
              label="What influenced your decision to come to UCN?"
              value={draft.reason_for_choosing_institution ?? ""}
              onChange={(value) =>
                updateText("reason_for_choosing_institution", value)
              }
            />
            <TextField
              id="routine-difficulties"
              label="What difficulties have you encountered at UCN?"
              value={draft.difficulties_encountered ?? ""}
              onChange={(value) => updateText("difficulties_encountered", value)}
            />
            <TextField
              id="routine-stress-causes"
              label="What causes you stress or anxiety?"
              value={draft.stress_anxiety_causes ?? ""}
              onChange={(value) => updateText("stress_anxiety_causes", value)}
            />
            <TextField
              id="routine-stress-management"
              label="How do you manage stress or anxiety?"
              value={draft.stress_anxiety_management ?? ""}
              onChange={(value) =>
                updateText("stress_anxiety_management", value)
              }
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              3. Family
            </legend>
            <TextField
              id="routine-family"
              label="Please tell us something about your family."
              value={draft.family_description ?? ""}
              onChange={(value) => updateText("family_description", value)}
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              4. Current concerns
            </legend>
            <p className="mt-2 text-sm font-medium text-ink">
              What concerns do you have right now?
            </p>
            <div className="mt-3 grid gap-x-5 gap-y-2 sm:grid-cols-2">
              {concernOptions.map((option) => {
                const checked =
                  draft.concerns?.includes(option.value) ?? false;
                return (
                  <label
                    key={option.value}
                    className="inline-flex min-h-10 items-start gap-3 py-2 text-sm text-ink"
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 h-4 w-4 shrink-0 accent-brand"
                      checked={checked}
                      onChange={() => toggleConcern(option.value)}
                      aria-controls={
                        option.value === RoutineConcernValue.OTHER
                          ? "routine-other-concern-specification"
                          : undefined
                      }
                      aria-expanded={
                        option.value === RoutineConcernValue.OTHER
                          ? selectedOther
                          : undefined
                      }
                    />
                    <span>{option.label}</span>
                  </label>
                );
              })}
            </div>
            {selectedOther ? (
              <div className="mt-4 max-w-2xl">
                <Label htmlFor="routine-other-concern-specification">
                  Please specify the other concern
                </Label>
                <Textarea
                  id="routine-other-concern-specification"
                  className="mt-2"
                  value={draft.other_concern_specification ?? ""}
                  onChange={(event) =>
                    updateText(
                      "other_concern_specification",
                      event.target.value,
                    )
                  }
                />
              </div>
            ) : null}
            <TextField
              id="routine-concerns-explanation"
              label="Please tell us more about your concerns."
              value={draft.concerns_explanation ?? ""}
              onChange={(value) => updateText("concerns_explanation", value)}
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              5. College adjustment
            </legend>
            <TextField
              id="routine-adjustment"
              label="How are you adjusting to college life? How about your peer group or barkada?"
              value={draft.college_adjustment_and_peer_group ?? ""}
              onChange={(value) =>
                updateText("college_adjustment_and_peer_group", value)
              }
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              6. Academic goals
            </legend>
            <TextField
              id="routine-academic-goals"
              label="What are your academic goals?"
              value={draft.academic_goals ?? ""}
              onChange={(value) => updateText("academic_goals", value)}
            />
          </fieldset>

          <fieldset disabled={pending} className="min-w-0 py-5">
            <legend className="font-heading text-lg font-semibold text-ink">
              7. Career goals
            </legend>
            <TextField
              id="routine-career-goals"
              label="What are your career goals?"
              value={draft.career_goals ?? ""}
              onChange={(value) => updateText("career_goals", value)}
            />
          </fieldset>
        </div>

        <div className="border-t border-border py-5">
          <h3 className="font-semibold text-ink">Review before submitting</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Your answers will become read-only after submission and will be
            available to your assigned Counselor. You can save a draft and
            return before submitting.
          </p>
          {dirty ? (
            <p role="status" className="mt-4 text-sm font-semibold text-warning">
              Unsaved changes
            </p>
          ) : (
            <p role="status" className="mt-4 text-sm text-muted">Saved</p>
          )}
          <div className="mt-4 flex flex-wrap gap-3">
            <Button
              type="submit"
              variant="secondary"
              disabled={pending || !dirty}
            >
              {save.isPending ? "Saving…" : "Save progress"}
            </Button>
            <Button
              type="button"
              disabled={pending || dirty}
              onClick={requestSubmit}
            >
              {submit.isPending ? "Submitting…" : "Submit Intake"}
            </Button>
          </div>
          {dirty ? (
            <p className="mt-3 text-sm text-muted">
              Save your changes before submitting.
            </p>
          ) : null}
        </div>
      </form>

      <AlertDialog
        open={confirmSubmit}
        onOpenChange={(open) => {
          if (!pending) setConfirmSubmit(open);
        }}
      >
        <AlertDialogContent>
          <AlertDialogTitle>
            Submit your Routine Interview responses?
          </AlertDialogTitle>
          <AlertDialogDescription>
            After submission, your Intake becomes read-only and will be
            available to your assigned Counselor.
          </AlertDialogDescription>
          {submitError ? (
            <p role="alert" className="mt-3 text-sm text-danger">{submitError}</p>
          ) : null}
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <AlertDialogCancel asChild>
              <Button variant="secondary" disabled={submit.isPending}>
                Cancel
              </Button>
            </AlertDialogCancel>
            <AlertDialogAction asChild>
              <Button
                onClick={(event) => {
                  event.preventDefault();
                  void submitIntake();
                }}
                disabled={pending}
              >
                {submit.isPending ? "Submitting…" : "Submit Intake"}
              </Button>
            </AlertDialogAction>
          </div>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function TextField({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="mt-4 max-w-3xl">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        className="mt-2"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
