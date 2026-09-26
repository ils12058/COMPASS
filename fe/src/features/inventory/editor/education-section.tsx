"use client";

import { BooleanField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { educationLevelOptions } from "@/features/inventory/inventory-presentation";
import { FieldGroup, InventoryNotice, inventorySelectClass } from "@/features/inventory/inventory-shared";
import type { EducationEntryPayload } from "@/lib/api/generated/model";
import { EducationLevelValue } from "@/lib/api/generated/model";

export function EducationSection({
  draft,
  onChange,
  programSnapshot,
  activePrograms = [],
  programLookupPending = false,
  programLookupError = false,
  programDiscoveryAllowed = true,
}: InventorySectionProps) {
  const activeSelection = activePrograms.find((program) => program.id === draft.program_id);
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
          Add the school and years attended for each level. You can leave levels that do not apply blank.
        </p>
        <div className="divide-y divide-border border-y border-border">
          {educationLevelOptions.map(([level, label]) => {
            const entry = (draft.education_entries ?? []).find((item) => item.level === level);
            return (
              <section key={level} className="grid gap-4 py-5 lg:grid-cols-[12rem_minmax(0,1fr)_11rem_12rem] lg:items-start">
                <h3 className="pt-2 text-sm font-semibold text-ink">{label}</h3>
                <TextField
                  id={`inventory-education-${level.toLowerCase()}-school`}
                  label="School attended and address"
                  value={entry?.school_attended_address}
                  onChange={(value) => updateEducation(level, { school_attended_address: value })}
                />
                <TextField
                  id={`inventory-education-${level.toLowerCase()}-years`}
                  label="Inclusive years"
                  value={entry?.inclusive_years}
                  onChange={(value) => updateEducation(level, { inclusive_years: value })}
                />
                <TextField
                  id={`inventory-education-${level.toLowerCase()}-awards`}
                  label="Awards received"
                  value={entry?.awards_received}
                  onChange={(value) => updateEducation(level, { awards_received: value })}
                />
              </section>
            );
          })}
        </div>
      </FieldGroup>

      <FieldGroup legend="Current Program and course choices">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="inventory-program" className="text-sm font-semibold text-ink">
              Current Program <span aria-hidden="true" className="ml-1 text-danger">*</span>
            </label>
            <select
              id="inventory-program"
              className={`mt-2 ${inventorySelectClass}`}
              value={draft.program_id ?? ""}
              disabled={programLookupPending || programLookupError || !programDiscoveryAllowed}
              aria-required="true"
              onChange={(event) => {
                const selected = activePrograms.find((program) => program.id === event.target.value);
                onChange({
                  program_id: selected?.id ?? null,
                  course_currently_enrolled: selected?.name ?? "",
                });
              }}
            >
              <option value="">Select an active Program</option>
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
            </select>
            {programLookupPending ? <p role="status" className="mt-1.5 text-xs text-muted">Loading active Programs…</p> : null}
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
            <select
              id="inventory-year-level"
              className={`mt-2 ${inventorySelectClass}`}
              value={draft.year_level ?? ""}
              aria-required="true"
              onChange={(event) => onChange({ year_level: event.target.value ? Number(event.target.value) : null })}
            >
              <option value="">Select a Year Level</option>
              {Array.from({ length: 10 }, (_, index) => index + 1).map((year) => (
                <option key={year} value={year}>{year}{year === 1 ? "st" : year === 2 ? "nd" : year === 3 ? "rd" : "th"} year</option>
              ))}
            </select>
          </div>
          <TextField
            id="inventory-major"
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
            Program choices are not available with your current access. Saved Program data is preserved; you can continue editing and save progress.
          </InventoryNotice>
        ) : null}
        {preserveSnapshot && programSnapshot ? (
          <p className="mt-3 text-sm text-warning">
            The saved Program {programSnapshot.code} · {programSnapshot.name} is no longer available for new selection. Choose an active Program before submission.
          </p>
        ) : null}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <BooleanField
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
