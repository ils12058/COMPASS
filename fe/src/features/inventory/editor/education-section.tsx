"use client";

import { Select } from "@/components/ui/select";
import { BooleanField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import { InventoryReviewHintText, useInventoryReview } from "@/features/inventory/editor/inventory-review-context";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { educationTextLimits, inventoryTextLimits } from "@/features/inventory/inventory-field-limits";
import { educationLevelOptions } from "@/features/inventory/inventory-presentation";
import { FieldGroup, InventoryNotice } from "@/features/inventory/inventory-shared";
import type { EducationEntryPayload } from "@/lib/api/generated/model";
import { EducationLevelValue } from "@/lib/api/generated/model";
import { RECORDED_YEAR_LEVELS, retainYearLevelIfApplicable, yearLevelLabel } from "@/lib/year-level";

export function EducationSection({
  draft,
  onChange,
  programSnapshot,
  activePrograms = [],
  programLookupPending = false,
  programLookupError = false,
  programDiscoveryAllowed = true,
  validationIssues = [],
}: InventorySectionProps) {
  const errorFor = (targetId: string) =>
    validationIssues.find((issue) => issue.targetId === targetId)?.message;
  const programError = errorFor("inventory-program");
  const yearLevelError = errorFor("inventory-year-level");
  const programReview = useInventoryReview("inventory-program");
  const yearLevelReview = useInventoryReview("inventory-year-level");
  const activeSelection = activePrograms.find((program) => program.id === draft.program_id);
  const configuredYearLevels = activeSelection?.applicable_year_levels ?? null;
  const selectableYearLevels: readonly number[] = activeSelection
    ? configuredYearLevels ?? RECORDED_YEAR_LEVELS
    : [];
  const selectedYearIsUnavailable =
    draft.year_level !== null &&
    draft.year_level !== undefined &&
    !selectableYearLevels.includes(draft.year_level);
  const shownYearLevels = selectedYearIsUnavailable
    ? [...selectableYearLevels, draft.year_level as number].sort((left, right) => left - right)
    : selectableYearLevels;
  const savedYearOptionSuffix = activeSelection
    ? " (saved value; choose a supported level)"
    : !draft.program_id
      ? " (saved value; Program not selected)"
      : !programDiscoveryAllowed
        ? " (saved value; Program options unavailable)"
        : programLookupPending
          ? " (saved value; Program options loading)"
          : programLookupError
            ? " (saved value; Program policy unavailable)"
            : " (saved value; Program inactive)";
  const preserveSnapshot =
    Boolean(draft.program_id) &&
    !activeSelection &&
    Boolean(programSnapshot || programLookupPending || programLookupError);

  function updateEducation(level: EducationLevelValue, patch: Partial<EducationEntryPayload>) {
    const entries = draft.education_entries ?? [];
    const current = entries.find((entry) => entry.level === level);
    const next = entries.filter((entry) => entry.level !== level);
    next.push({ level, ...current, ...patch });
    next.sort((a, b) => educationLevelOptions.findIndex(([candidate]) => candidate === a.level) - educationLevelOptions.findIndex(([candidate]) => candidate === b.level));
    onChange({ education_entries: next });
  }

  return (
    <div className="space-y-7">
      <FieldGroup legend="Educational history">
        <p className="mb-5 text-sm leading-6 text-muted">
          Add the school and years attended for each level, such as 2016–2022. You can leave levels that do not apply blank.
        </p>
        <div className="divide-y divide-border rounded-sm border border-border">
          {educationLevelOptions.map(([level, label]) => (
            <EducationLevelRow
              key={level}
              level={level}
              label={label}
              entry={(draft.education_entries ?? []).find((item) => item.level === level)}
              onChange={(patch) => updateEducation(level, patch)}
            />
          ))}
        </div>
      </FieldGroup>

      <FieldGroup legend="Current Program and course choices">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="inventory-program" className="text-sm font-semibold text-ink">
              Current Program <span aria-hidden="true" className="ml-1 text-danger">*</span>
            </label>
            <Select
              id="inventory-program"
              className="mt-2"
              value={draft.program_id ?? ""}
              disabled={programLookupPending || programLookupError || !programDiscoveryAllowed}
              aria-required="true"
              aria-invalid={programError ? true : undefined}
              aria-describedby={[programReview.describedBy, programError ? "inventory-program-error" : undefined].filter(Boolean).join(" ") || undefined}
              onChange={(event) => {
                const selected = activePrograms.find((program) => program.id === event.target.value);
                const supportedYearLevels = selected
                  ? selected.applicable_year_levels ?? RECORDED_YEAR_LEVELS
                  : [];
                onChange({
                  program_id: selected?.id ?? null,
                  course_currently_enrolled: selected?.name ?? "",
                  year_level: retainYearLevelIfApplicable(draft.year_level, supportedYearLevels),
                });
              }}
            >
              <option value="">Select an active program</option>
              {preserveSnapshot && draft.program_id ? (
                <option value={draft.program_id}>
                  {programSnapshot
                    ? `${programSnapshot.code} · ${programSnapshot.name} (no longer active for new selection)`
                    : "Previously selected Program (not available for new selection)"}
                </option>
              ) : null}
              {activePrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.code} · {program.name} — {program.college.name}
                </option>
              ))}
            </Select>
            <InventoryReviewHintText hint={programReview.hint} />
            {programError ? <p id="inventory-program-error" role="alert" className="mt-1.5 text-xs leading-5 text-danger">{programError}</p> : null}
            {programLookupPending ? <p role="status" className="mt-1.5 text-xs text-muted">Loading active programs…</p> : null}
          </div>
          <TextField
            id="inventory-course-currently-enrolled"
            label="Course currently enrolled"
            value={draft.course_currently_enrolled}
            onChange={() => undefined}
            readOnly
            hint="Filled from the selected Program."
          />
          <div>
            <label htmlFor="inventory-year-level" className="text-sm font-semibold text-ink">
              Year Level <span aria-hidden="true" className="ml-1 text-danger">*</span>
            </label>
            <Select
              id="inventory-year-level"
              className="mt-2"
              value={draft.year_level ?? ""}
              disabled={
                !draft.program_id ||
                !activeSelection ||
                programLookupPending ||
                programLookupError ||
                !programDiscoveryAllowed
              }
              aria-required="true"
              aria-invalid={yearLevelError ? true : undefined}
              aria-describedby={[yearLevelReview.describedBy, yearLevelError ? "inventory-year-level-error" : undefined].filter(Boolean).join(" ") || undefined}
              onChange={(event) => onChange({ year_level: event.target.value ? Number(event.target.value) : null })}
            >
              <option value="">
                {activeSelection ? "Select a Year Level" : "Select an active Program first"}
              </option>
              {shownYearLevels.map((year) => (
                <option key={year} value={year}>
                  {yearLevelLabel(year)}
                  {selectedYearIsUnavailable && year === draft.year_level
                    ? savedYearOptionSuffix
                    : ""}
                </option>
              ))}
            </Select>
            <InventoryReviewHintText hint={yearLevelReview.hint} />
            {activeSelection?.year_level_policy_status === "PENDING_POLICY" ? (
              <p className="mt-1.5 text-xs leading-5 text-muted">
                Year Level policy for this Program has not been confirmed. The existing recorded range remains available for compatibility; it does not establish an institutional limit.
              </p>
            ) : null}
            {draft.program_id &&
            !activeSelection &&
            programDiscoveryAllowed &&
            !programLookupPending &&
            !programLookupError ? (
              <p className="mt-1.5 text-xs leading-5 text-muted">
                This saved Program is no longer active for new selection. Choose an active Program to change its Year Level.
              </p>
            ) : null}
            {yearLevelError ? <p id="inventory-year-level-error" role="alert" className="mt-1.5 text-xs leading-5 text-danger">{yearLevelError}</p> : null}
          </div>
          <TextField
            id="inventory-major"
            maxLength={inventoryTextLimits.major}
            label="Major"
            value={draft.major}
            onChange={(value) => onChange({ major: value })}
          />
        </div>
        {programLookupError ? (
          <InventoryNotice tone="warning" role="status" >
            Active Program choices are temporarily unavailable. Saved Program data is preserved; you can continue editing and save progress.
          </InventoryNotice>
        ) : null}
        {!programDiscoveryAllowed ? (
          <InventoryNotice tone="warning" role="status">
            Program choices are unavailable. Your saved program information remains, and you can continue editing.
          </InventoryNotice>
        ) : null}
        {preserveSnapshot && programSnapshot ? (
          <p className="mt-3 text-sm text-warning">
            The saved program {programSnapshot.code} · {programSnapshot.name} is no longer available for new selection. Choose an active program before submission.
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <BooleanField
            id="inventory-schedule-satisfied"
            legend="Are you satisfied with your present schedule?"
            value={draft.schedule_satisfied}
            onChange={(value) => onChange({
              schedule_satisfied: value,
              ...(value === false ? {} : { schedule_satisfaction_reason: "" }),
            })}
          />
          {draft.schedule_satisfied === false ? (
            <TextAreaField
              id="inventory-schedule-reason"
              label="Reason (optional)"
              value={draft.schedule_satisfaction_reason}
              onChange={(value) => onChange({ schedule_satisfaction_reason: value })}
              hint="Changing the schedule response to Yes or no response clears this detail."
            />
          ) : null}
        </div>
      </FieldGroup>
    </div>
  );
}

// One school level. A level is a stable key, so a review request can name the row even before it
// has answers.
function EducationLevelRow({
  level,
  label,
  entry,
  onChange,
}: {
  level: EducationLevelValue;
  label: string;
  entry: EducationEntryPayload | undefined;
  onChange: (patch: Partial<EducationEntryPayload>) => void;
}) {
  const key = level.toLowerCase();
  const review = useInventoryReview(`inventory-education-${key}`);
  return (
    <section className="grid gap-4 px-4 py-5 lg:grid-cols-[12rem_minmax(0,1fr)_11rem_12rem] lg:items-start">
      <div className="pt-2">
        <h3 className="text-sm font-semibold text-ink">{label}</h3>
        <InventoryReviewHintText hint={review.hint} className="mt-1" />
      </div>
      <TextField
        id={`inventory-education-${key}-school`}
        label="School attended and address"
        value={entry?.school_attended_address}
        onChange={(value) => onChange({ school_attended_address: value })}
      />
      <TextField
        id={`inventory-education-${key}-years`}
        label="Inclusive years"
        maxLength={educationTextLimits.inclusive_years}
        value={entry?.inclusive_years}
        onChange={(value) => onChange({ inclusive_years: value })}
      />
      <TextField
        id={`inventory-education-${key}-awards`}
        label="Awards received"
        value={entry?.awards_received}
        onChange={(value) => onChange({ awards_received: value })}
      />
    </section>
  );
}
