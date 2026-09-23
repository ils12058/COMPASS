"use client";

import { BooleanField, SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { allowanceOptions, workFieldOptions } from "@/features/inventory/inventory-presentation";
import { FieldGroup, InventoryNotice } from "@/features/inventory/inventory-shared";
import { PostGraduationFieldValue } from "@/lib/api/generated/model";

export function PlansSection({ draft, onChange }: InventorySectionProps) {
  return (
    <div className="space-y-7">
      <FieldGroup legend="Plans after graduation">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            id="inventory-ideal-allowance"
            label="Ideal monthly allowance"
            value={draft.ideal_monthly_allowance}
            options={allowanceOptions}
            onChange={(value) => onChange({ ideal_monthly_allowance: value })}
          />
          <SelectField
            id="inventory-intended-work-field"
            label="Field you intend to work in after graduation"
            value={draft.intended_work_field}
            options={workFieldOptions}
            onChange={(value) => onChange({
              intended_work_field: value,
              ...(value === PostGraduationFieldValue.OTHER ? {} : { intended_work_other: "" }),
            })}
          />
          {draft.intended_work_field === PostGraduationFieldValue.OTHER ? (
            <TextField
              id="inventory-intended-work-other"
              label="Other intended work field"
              value={draft.intended_work_other}
              onChange={(value) => onChange({ intended_work_other: value })}
              required
              hint="Choosing another field clears this detail."
            />
          ) : null}
        </div>
      </FieldGroup>

      <FieldGroup legend="Prior counseling experience">
        <div className="space-y-5">
          <BooleanField
            legend="Have you had a counseling experience before?"
            value={draft.prior_counseling_experience}
            onChange={(value) => onChange({
              prior_counseling_experience: value,
              ...(value === true
                ? {}
                : {
                    prior_counselor_name: "",
                    prior_counseling_when: "",
                    prior_counseling_where: "",
                  }),
            })}
          />
          {draft.prior_counseling_experience === true ? (
            <div className="grid gap-4 border-l-2 border-border pl-4 sm:grid-cols-2">
              <TextField
                id="inventory-prior-counselor"
                label="Counselor name"
                value={draft.prior_counselor_name}
                onChange={(value) => onChange({ prior_counselor_name: value })}
              />
              <TextField
                id="inventory-prior-counseling-when"
                label="When"
                value={draft.prior_counseling_when}
                onChange={(value) => onChange({ prior_counseling_when: value })}
              />
              <TextField
                id="inventory-prior-counseling-where"
                label="Where"
                value={draft.prior_counseling_where}
                onChange={(value) => onChange({ prior_counseling_where: value })}
              />
            </div>
          ) : null}
        </div>
      </FieldGroup>

      <FieldGroup legend="Current concerns and fears">
        <InventoryNotice tone="neutral">
          These are sensitive counseling-context responses. Share what you would like the Guidance and Counseling Office to understand.
        </InventoryNotice>
        <div className="mt-4 grid gap-4">
          <TextAreaField
            id="inventory-current-concerns"
            label="Current concerns"
            value={draft.current_concerns}
            onChange={(value) => onChange({ current_concerns: value })}
            rows={5}
          />
          <TextAreaField
            id="inventory-current-fears"
            label="Current fears"
            value={draft.current_fears}
            onChange={(value) => onChange({ current_fears: value })}
            rows={5}
          />
        </div>
      </FieldGroup>
    </div>
  );
}
