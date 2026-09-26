"use client";

import { civilStatusOptions, religionOptions, sexOptions } from "@/features/inventory/inventory-presentation";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import { SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import { PSGCLocationSelector } from "@/features/inventory/editor/psgc-location-selector";
import {
  CivilStatusCategoryValue,
  CurrentReligionCategoryValue,
  GeographicLocationKindValue,
} from "@/lib/api/generated/model";
import { FieldGroup } from "@/features/inventory/inventory-shared";

export function PersonalSection({ draft, onChange }: InventorySectionProps) {
  const currentLocation = draft.geographic_locations?.find(
    (location) => location.kind === GeographicLocationKindValue.CURRENT,
  );
  const permanentLocation = draft.geographic_locations?.find(
    (location) => location.kind === GeographicLocationKindValue.PERMANENT,
  );

  function updateLocation(
    kind: GeographicLocationKindValue,
    value: Parameters<typeof PSGCLocationSelector>[0]["location"],
  ) {
    const rest = (draft.geographic_locations ?? []).filter((item) => item.kind !== kind);
    onChange({ geographic_locations: value ? [...rest, value] : rest });
  }

  return (
    <div className="space-y-7">
      <FieldGroup
        legend="Personal data"
        className="border-t-0 pt-0"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id="inventory-full-name"
            label="Full name"
            value={draft.full_name}
            onChange={(value) => onChange({ full_name: value })}
            hint="This is the name snapshot for this annual Individual Inventory."
          />
          <TextField
            id="inventory-nickname"
            label="Nickname"
            value={draft.nickname}
            onChange={(value) => onChange({ nickname: value })}
          />
          <TextField
            id="inventory-student-number"
            label="Institutional ID"
            value={draft.student_number}
            onChange={() => undefined}
            readOnly
            hint="From your COMPASS account. It cannot be changed here."
          />
          <TextField
            id="inventory-date-of-birth"
            label="Date of birth"
            type="date"
            value={draft.date_of_birth}
            onChange={(value) => onChange({ date_of_birth: value || null })}
            required
          />
          <TextField
            id="inventory-place-of-birth"
            label="Place of birth"
            value={draft.place_of_birth}
            onChange={(value) => onChange({ place_of_birth: value })}
          />
          <TextField
            id="inventory-nationality"
            label="Nationality"
            value={draft.nationality}
            onChange={(value) => onChange({ nationality: value })}
          />
          <SelectField
            id="inventory-sex"
            label="Sex"
            value={draft.sex}
            options={sexOptions}
            onChange={(value) => onChange({ sex: value })}
            required
          />
          <TextField
            id="inventory-birth-order"
            label="Birth order among siblings"
            value={draft.birth_order_among_siblings}
            onChange={(value) => onChange({ birth_order_among_siblings: value })}
          />
          <SelectField
            id="inventory-civil-status"
            label="Civil status"
            value={draft.civil_status_category}
            options={civilStatusOptions}
            onChange={(value) =>
              onChange({
                civil_status_category: value,
                ...(value === CivilStatusCategoryValue.OTHER ? {} : { civil_status: "" }),
              })
            }
            required
          />
          {draft.civil_status_category === CivilStatusCategoryValue.OTHER ? (
            <TextField
              id="inventory-civil-status-other"
              label="Other civil status"
              value={draft.civil_status}
              onChange={(value) => onChange({ civil_status: value })}
              required
              hint="Choosing another civil-status category clears this detail."
            />
          ) : null}
        </div>
      </FieldGroup>

      <FieldGroup legend="Contact and addresses">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextAreaField
            id="inventory-current-address"
            label="Current address"
            value={draft.current_address}
            onChange={(value) => onChange({ current_address: value })}
          />
          <TextAreaField
            id="inventory-permanent-address"
            label="Permanent address"
            value={draft.permanent_address}
            onChange={(value) => onChange({ permanent_address: value })}
          />
          <TextField
            id="inventory-contact-number"
            label="Contact number"
            type="tel"
            value={draft.contact_number}
            onChange={(value) => onChange({ contact_number: value })}
            autoComplete="tel"
          />
          <TextField
            id="inventory-email"
            label="Email address"
            type="email"
            value={draft.email_address}
            onChange={(value) => onChange({ email_address: value })}
            autoComplete="email"
          />
          <TextAreaField
            id="inventory-languages-home"
            label="Languages spoken at home"
            value={draft.languages_spoken_at_home}
            onChange={(value) => onChange({ languages_spoken_at_home: value })}
          />
          <TextAreaField
            id="inventory-languages-fluent"
            label="Languages most fluent in"
            value={draft.languages_most_fluent}
            onChange={(value) => onChange({ languages_most_fluent: value })}
          />
          <TextField
            id="inventory-religion-birth"
            label="Religion from birth"
            value={draft.religion_from_birth}
            onChange={(value) => onChange({ religion_from_birth: value })}
          />
          <SelectField
            id="inventory-current-religion-category"
            label="Current religion"
            value={draft.current_religion_category}
            options={religionOptions}
            onChange={(value) =>
              onChange({
                current_religion_category: value,
                ...(value === CurrentReligionCategoryValue.OTHER
                  ? {}
                  : { current_religion: "" }),
              })
            }
            required
          />
          {draft.current_religion_category === CurrentReligionCategoryValue.OTHER ? (
            <TextField
              id="inventory-current-religion-other"
              label="Other current religion"
              value={draft.current_religion}
              onChange={(value) => onChange({ current_religion: value })}
              required
              hint="Choosing another religion category clears this detail."
            />
          ) : null}
        </div>
      </FieldGroup>

      <FieldGroup legend="Structured location">
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          The official location choices are separate from your address text. A province is not required in every area, and barangay is optional.
        </p>
        <div className="space-y-7">
          <PSGCLocationSelector
            kind={GeographicLocationKindValue.CURRENT}
            location={currentLocation}
            onChange={(value) => updateLocation(GeographicLocationKindValue.CURRENT, value)}
          />
          <div className="border-t border-border pt-6">
            <PSGCLocationSelector
              kind={GeographicLocationKindValue.PERMANENT}
              location={permanentLocation}
              onChange={(value) => updateLocation(GeographicLocationKindValue.PERMANENT, value)}
            />
          </div>
        </div>
      </FieldGroup>
    </div>
  );
}
