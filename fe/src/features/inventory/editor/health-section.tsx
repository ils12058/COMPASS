"use client";

import { BooleanField, CheckboxGroupField, SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { immunizationOptions, livingArrangementOptions, pwdOptions } from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import {
  ImmunizationValue,
  LivingArrangementValue,
  PWDStatusValue,
} from "@/lib/api/generated/model";

function nullableCount(value: string): number | null {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function HealthSection({ draft, onChange }: InventorySectionProps) {
  const boarding = draft.living_arrangement === LivingArrangementValue.BOARDING_HOUSE;
  const immunizations = draft.immunizations ?? [];

  return (
    <div className="space-y-7">
      <FieldGroup legend="Living conditions">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            id="inventory-living-arrangement"
            label="Where do you live now?"
            value={draft.living_arrangement}
            options={livingArrangementOptions}
            onChange={(value) => onChange({
              living_arrangement: value,
              ...(value === LivingArrangementValue.BOARDING_HOUSE
                ? {}
                : {
                    boarding_exclusive: null,
                    boarding_landlord_name: "",
                    boarding_address: "",
                  }),
            })}
            required
          />
          <TextField
            id="inventory-present-place-people"
            label="People in your present living place"
            type="number"
            min={0}
            value={draft.present_place_people_count}
            onChange={(value) => onChange({ present_place_people_count: nullableCount(value) })}
          />
          <TextField
            id="inventory-room-sharing-people"
            label="People sharing your room"
            type="number"
            min={0}
            value={draft.room_sharing_people_count}
            onChange={(value) => onChange({ room_sharing_people_count: nullableCount(value) })}
          />
        </div>
        {boarding ? (
          <div className="mt-5 grid gap-4 border-l-2 border-border pl-4 sm:grid-cols-2">
            <BooleanField
              legend="Is the boarding house exclusive to one sex?"
              value={draft.boarding_exclusive}
              onChange={(value) => onChange({ boarding_exclusive: value })}
            />
            <TextField
              id="inventory-boarding-landlord"
              label="Landlord or landlady name"
              value={draft.boarding_landlord_name}
              onChange={(value) => onChange({ boarding_landlord_name: value })}
            />
            <TextAreaField
              id="inventory-boarding-address"
              label="Boarding-house address"
              value={draft.boarding_address}
              onChange={(value) => onChange({ boarding_address: value })}
            />
            <p className="self-end text-xs leading-5 text-muted">
              Choosing another living arrangement clears boarding-house details.
            </p>
          </div>
        ) : null}
      </FieldGroup>

      <FieldGroup legend="Health conditions">
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          Share only what you are comfortable providing. These responses are confidential Student information and are not medical advice.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextAreaField
            id="inventory-accidents"
            label="Accidents experienced"
            value={draft.accidents_experienced}
            onChange={(value) => onChange({ accidents_experienced: value })}
          />
          <TextAreaField
            id="inventory-accidents-effect"
            label="Effect of accidents"
            value={draft.accidents_effect}
            onChange={(value) => onChange({ accidents_effect: value })}
          />
          <TextAreaField
            id="inventory-operations"
            label="Operations experienced"
            value={draft.operations_experienced}
            onChange={(value) => onChange({ operations_experienced: value })}
          />
          <TextAreaField
            id="inventory-operations-effect"
            label="Effect of operations"
            value={draft.operations_effect}
            onChange={(value) => onChange({ operations_effect: value })}
          />
          <div className="sm:col-span-2">
            <CheckboxGroupField
              legend="Immunizations you have had"
              value={immunizations}
              options={immunizationOptions}
              onChange={(values) => onChange({
                immunizations: values,
                ...(values.includes(ImmunizationValue.OTHER) ? {} : { immunization_other: "" }),
              })}
            />
          </div>
          {immunizations.includes(ImmunizationValue.OTHER) ? (
            <TextField
              id="inventory-immunization-other"
              label="Other immunization"
              value={draft.immunization_other}
              onChange={(value) => onChange({ immunization_other: value })}
              required
              hint="Removing Other clears this detail."
            />
          ) : null}
          <TextField
            id="inventory-height"
            label="Height"
            value={draft.height}
            onChange={(value) => onChange({ height: value })}
          />
          <TextField
            id="inventory-weight"
            label="Weight"
            value={draft.weight}
            onChange={(value) => onChange({ weight: value })}
          />
          <SelectField
            id="inventory-pwd-status"
            label="Disability status"
            value={draft.pwd_status}
            options={pwdOptions}
            onChange={(value) => onChange({
              pwd_status: value,
              ...(value === PWDStatusValue.PWD ? {} : { physical_disadvantage: "" }),
            })}
            required
          />
          {draft.pwd_status === PWDStatusValue.PWD ? (
            <TextAreaField
              id="inventory-physical-disadvantage"
              label="Physical disadvantage or support context"
              value={draft.physical_disadvantage}
              onChange={(value) => onChange({ physical_disadvantage: value })}
              required
              hint="Changing the response to a different option clears this detail."
            />
          ) : null}
          <TextAreaField
            id="inventory-illness-this-year"
            label="Illness this year"
            value={draft.illness_this_year}
            onChange={(value) => onChange({ illness_this_year: value })}
          />
          <TextAreaField
            id="inventory-previous-illness"
            label="Previous illness"
            value={draft.previous_illness}
            onChange={(value) => onChange({ previous_illness: value })}
          />
        </div>
      </FieldGroup>
    </div>
  );
}
