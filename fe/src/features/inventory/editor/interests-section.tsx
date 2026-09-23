"use client";

import { BooleanField, CheckboxGroupField, SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import {
  courseChoiceReasonOptions,
  handednessOptions,
  interestOptions,
} from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import { CourseChoiceReasonValue } from "@/lib/api/generated/model";

const hours = [
  ["daily_hours_class", "Class"],
  ["daily_hours_library", "Library work"],
  ["daily_hours_studying", "Studying lessons"],
  ["daily_hours_rest", "Rest"],
  ["daily_hours_recreation", "Recreation"],
  ["daily_hours_other", "Other"],
] as const;

export function InterestsSection({ draft, onChange }: InventorySectionProps) {
  return (
    <div className="space-y-7">
      <FieldGroup legend="Course choice and educational perception">
        <div className="space-y-6">
          <BooleanField
            legend="Was your enrolled course your first choice?"
            value={draft.course_first_choice}
            onChange={(value) => onChange({ course_first_choice: value })}
          />
          <CheckboxGroupField
            legend="Reasons for your course choice"
            value={draft.course_choice_reasons}
            options={courseChoiceReasonOptions}
            onChange={(values) => onChange({
              course_choice_reasons: values,
              ...(values.includes(CourseChoiceReasonValue.OTHER) ? {} : { course_choice_other: "" }),
            })}
          />
          {(draft.course_choice_reasons ?? []).includes(CourseChoiceReasonValue.OTHER) ? (
            <TextField
              id="inventory-course-choice-other"
              label="Other course-choice reason"
              value={draft.course_choice_other}
              onChange={(value) => onChange({ course_choice_other: value })}
              required
              hint="Removing Other reason clears this detail."
            />
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            <TextAreaField
              id="inventory-lowest-subjects"
              label="Subjects with lowest grades and grades received"
              value={draft.lowest_subjects_grades}
              onChange={(value) => onChange({ lowest_subjects_grades: value })}
            />
            <TextAreaField
              id="inventory-highest-subjects"
              label="Subjects with highest grades and grades received"
              value={draft.highest_subjects_grades}
              onChange={(value) => onChange({ highest_subjects_grades: value })}
            />
            <TextAreaField
              id="inventory-inclination-performing-arts"
              label="Inclinations: performing arts"
              value={draft.inclination_performing_arts}
              onChange={(value) => onChange({ inclination_performing_arts: value })}
            />
            <TextAreaField
              id="inventory-inclination-sports"
              label="Inclinations: sports"
              value={draft.inclination_sports}
              onChange={(value) => onChange({ inclination_sports: value })}
            />
            <TextAreaField
              id="inventory-inclination-leadership"
              label="Inclinations: leadership"
              value={draft.inclination_leadership}
              onChange={(value) => onChange({ inclination_leadership: value })}
            />
          </div>
        </div>
      </FieldGroup>

      <FieldGroup legend="Interests and daily routine">
        <div className="space-y-6">
          <CheckboxGroupField
            legend="Interests"
            value={draft.interests}
            options={interestOptions}
            onChange={(values) => onChange({ interests: values })}
            columns={3}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextAreaField
              id="inventory-other-skills-hobbies"
              label="Other skills and hobbies"
              value={draft.other_skills_hobbies}
              onChange={(value) => onChange({ other_skills_hobbies: value })}
            />
            <TextAreaField
              id="inventory-desired-extracurricular"
              label="Extracurricular activities you would like to join"
              value={draft.desired_extracurricular_activities}
              onChange={(value) => onChange({ desired_extracurricular_activities: value })}
            />
            <TextAreaField
              id="inventory-reading-preferences"
              label="Books and magazines you enjoy reading"
              value={draft.reading_preferences}
              onChange={(value) => onChange({ reading_preferences: value })}
            />
            <SelectField
              id="inventory-handedness"
              label="Handedness"
              value={draft.handedness}
              options={handednessOptions}
              onChange={(value) => onChange({ handedness: value })}
              placeholder="No response"
            />
          </div>

          <div className="border-t border-border pt-5">
            <h3 className="text-sm font-semibold text-ink">Hours devoted daily</h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              Each value may be entered independently. The combined values do not need to total 24.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {hours.map(([key, label]) => (
                <TextField
                  key={key}
                  id={`inventory-${key.replaceAll("_", "-")}`}
                  label={label}
                  type="number"
                  min={0}
                  max={24}
                  step="any"
                  value={draft[key]}
                  onChange={(value) => onChange({ [key]: value || null })}
                  hint="0 to 24 hours; decimals are accepted."
                />
              ))}
            </div>
          </div>
        </div>
      </FieldGroup>
    </div>
  );
}
