"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { CheckboxGroupField, SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import type { InventorySectionProps } from "@/features/inventory/editor/types";
import {
  annualIncomeOptions,
  fourPsOptions,
  indigenousOptions,
  occupationOptions,
  parentLifeOptions,
  parentStatusCategoryOptions,
  parentStatusOptions,
} from "@/features/inventory/inventory-presentation";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import {
  AnnualIncomeStatusValue,
  FamilyMemberKindValue,
  OccupationCategoryValue,
  type FamilyMemberPayload,
} from "@/lib/api/generated/model";

const requiredKinds = [FamilyMemberKindValue.FATHER, FamilyMemberKindValue.MOTHER] as const;
const emptyFamilyMembers: FamilyMemberPayload[] = [];

export function FamilySection({ draft, onChange }: InventorySectionProps) {
  const members = draft.family_members ?? emptyFamilyMembers;
  const hasSpouse = members.some((member) => member.kind === FamilyMemberKindValue.SPOUSE);
  const focusAfterUpdate = useRef<string | null>(null);

  useEffect(() => {
    const target = focusAfterUpdate.current;
    if (!target) return;
    document.getElementById(target)?.focus();
    focusAfterUpdate.current = null;
  }, [members]);

  function updateMember(kind: FamilyMemberKindValue, patch: Partial<FamilyMemberPayload>) {
    const existing = members.find((member) => member.kind === kind);
    const next = members.filter((member) => member.kind !== kind);
    next.push({ kind, ...existing, ...patch });
    onChange({ family_members: next });
  }

  function removeSpouse() {
    onChange({
      family_members: members.filter((member) => member.kind !== FamilyMemberKindValue.SPOUSE),
    });
  }

  return (
    <div className="space-y-7">
      <FieldGroup legend="Family data">
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          Father and Mother responses are required for submission. Spouse information is optional.
        </p>
        <div className="space-y-8">
          {requiredKinds.map((kind) => (
            <FamilyMemberFields
              key={kind}
              kind={kind}
              member={members.find((item) => item.kind === kind) ?? { kind }}
              onChange={(patch) => updateMember(kind, patch)}
            />
          ))}
          {hasSpouse ? (
            <FamilyMemberFields
              kind={FamilyMemberKindValue.SPOUSE}
              member={members.find((item) => item.kind === FamilyMemberKindValue.SPOUSE) ?? {
                kind: FamilyMemberKindValue.SPOUSE,
              }}
              onChange={(patch) => updateMember(FamilyMemberKindValue.SPOUSE, patch)}
              onRemove={() => {
                focusAfterUpdate.current = "inventory-spouse-add";
                removeSpouse();
              }}
            />
          ) : (
            <Button
              id="inventory-spouse-add"
              variant="secondary"
              onClick={() => {
                focusAfterUpdate.current = "inventory-family-spouse-name";
                updateMember(FamilyMemberKindValue.SPOUSE, {});
              }}
            >
              Add optional Spouse details
            </Button>
          )}
        </div>
      </FieldGroup>

      <FieldGroup legend="Parent status">
        <div className="grid gap-5 lg:grid-cols-2">
          <SelectField
            id="inventory-parent-status-category"
            label="Current parent-status category"
            value={draft.parent_status_category}
            options={parentStatusCategoryOptions}
            onChange={(value) => onChange({ parent_status_category: value })}
            required
            hint="This normalized response is used as the primary current condition."
          />
          <CheckboxGroupField
            legend="Additional parent circumstances"
            value={draft.parent_statuses}
            options={parentStatusOptions}
            onChange={(values) => onChange({ parent_statuses: values })}
          />
        </div>
      </FieldGroup>

      <FieldGroup legend="Guardian and emergency contact">
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id="inventory-guardian-name"
            label="Guardian name"
            value={draft.guardian_name}
            onChange={(value) => onChange({ guardian_name: value })}
          />
          <TextField
            id="inventory-guardian-relationship"
            label="Relationship with guardian"
            value={draft.guardian_relationship}
            onChange={(value) => onChange({ guardian_relationship: value })}
          />
          <TextAreaField
            id="inventory-guardian-address"
            label="Guardian address"
            value={draft.guardian_address}
            onChange={(value) => onChange({ guardian_address: value })}
          />
          <TextField
            id="inventory-guardian-contact"
            label="Guardian contact number"
            type="tel"
            value={draft.guardian_contact_number}
            onChange={(value) => onChange({ guardian_contact_number: value })}
          />
          <TextField
            id="inventory-emergency-name"
            label="Emergency contact name"
            value={draft.emergency_contact_name}
            onChange={(value) => onChange({ emergency_contact_name: value })}
          />
          <TextField
            id="inventory-emergency-number"
            label="Emergency contact number"
            type="tel"
            value={draft.emergency_contact_number}
            onChange={(value) => onChange({ emergency_contact_number: value })}
          />
        </div>
      </FieldGroup>

      <FieldGroup legend="Student support information">
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          These responses are confidential support information. They are not shown in the Counselor roster.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            id="inventory-four-ps"
            label="4Ps status"
            value={draft.support_profile?.four_ps_status}
            options={fourPsOptions}
            onChange={(value) => onChange({
              support_profile: { ...draft.support_profile, four_ps_status: value },
            })}
            required
          />
          <SelectField
            id="inventory-indigenous-peoples"
            label="Indigenous Peoples status"
            value={draft.support_profile?.indigenous_peoples_status}
            options={indigenousOptions}
            onChange={(value) => onChange({
              support_profile: { ...draft.support_profile, indigenous_peoples_status: value },
            })}
            required
          />
          <SelectField
            id="inventory-mother-life-status"
            label="Mother's life status"
            value={draft.support_profile?.mother_life_status}
            options={parentLifeOptions}
            onChange={(value) => onChange({
              support_profile: { ...draft.support_profile, mother_life_status: value },
            })}
            required
          />
          <SelectField
            id="inventory-father-life-status"
            label="Father's life status"
            value={draft.support_profile?.father_life_status}
            options={parentLifeOptions}
            onChange={(value) => onChange({
              support_profile: { ...draft.support_profile, father_life_status: value },
            })}
            required
          />
        </div>
      </FieldGroup>
    </div>
  );
}

function FamilyMemberFields({
  kind,
  member,
  onChange,
  onRemove,
}: {
  kind: FamilyMemberKindValue;
  member: FamilyMemberPayload;
  onChange: (patch: Partial<FamilyMemberPayload>) => void;
  onRemove?: () => void;
}) {
  const label =
    kind === FamilyMemberKindValue.FATHER
      ? "Father"
      : kind === FamilyMemberKindValue.MOTHER
        ? "Mother"
        : "Spouse";
  const required = kind !== FamilyMemberKindValue.SPOUSE;
  const prefix = `inventory-family-${kind.toLowerCase()}`;

  function changeOccupationCategory(value: OccupationCategoryValue | null) {
    onChange({
      occupation_category: value,
      ...(value === OccupationCategoryValue.NONE || value === OccupationCategoryValue.NOT_SPECIFIED
        ? { occupation: "" }
        : {}),
    });
  }

  function changeIncomeStatus(value: AnnualIncomeStatusValue | null) {
    onChange({
      annual_income_status: value,
      ...(value === AnnualIncomeStatusValue.REPORTED
        ? {}
        : { annual_income_previous_year: null }),
    });
  }

  return (
    <section className="min-w-0 border-t border-border pt-5" aria-labelledby={`${prefix}-heading`}>
      <div className="flex items-center justify-between gap-3">
        <h3 id={`${prefix}-heading`} className="font-semibold text-ink">
          {label}
          {required ? <span aria-hidden="true" className="ml-1 text-danger">*</span> : null}
        </h3>
        {onRemove ? (
          <Button variant="quiet" onClick={onRemove} aria-label="Remove optional Spouse information">
            Remove Spouse
          </Button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <TextField id={`${prefix}-name`} label="Name" value={member.name} onChange={(value) => onChange({ name: value })} />
        <SelectField
          id={`${prefix}-occupation-category`}
          label="Occupation category"
          value={member.occupation_category}
          options={occupationOptions}
          onChange={changeOccupationCategory}
          required={required}
        />
        {member.occupation_category &&
        member.occupation_category !== OccupationCategoryValue.NONE &&
        member.occupation_category !== OccupationCategoryValue.NOT_SPECIFIED ? (
          <TextField
            id={`${prefix}-occupation`}
            label="Occupation details"
            value={member.occupation}
            onChange={(value) => onChange({ occupation: value })}
            hint="If you chose Other, describe the occupation here."
          />
        ) : null}
        <SelectField
          id={`${prefix}-income-status`}
          label="Annual income from previous year"
          value={member.annual_income_status}
          options={annualIncomeOptions}
          onChange={changeIncomeStatus}
          required={required}
        />
        {member.annual_income_status === AnnualIncomeStatusValue.REPORTED ? (
          <TextField
            id={`${prefix}-income-amount`}
            label="Reported amount"
            type="number"
            min={0}
            step="any"
            value={member.annual_income_previous_year}
            onChange={(value) => onChange({ annual_income_previous_year: value || null })}
            required={required}
          />
        ) : null}
      </div>

      <details className="mt-5 border-t border-border/70 pt-4">
        <summary className="min-h-9 cursor-pointer text-sm font-semibold text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Additional {label.toLowerCase()} information
        </summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <TextField id={`${prefix}-date-of-birth`} label="Date of birth" type="date" value={member.date_of_birth} onChange={(value) => onChange({ date_of_birth: value || null })} />
          <TextField id={`${prefix}-place-of-birth`} label="Place of birth" value={member.place_of_birth} onChange={(value) => onChange({ place_of_birth: value })} />
          <TextAreaField id={`${prefix}-current-address`} label="Current address" value={member.current_address} onChange={(value) => onChange({ current_address: value })} />
          <TextAreaField id={`${prefix}-permanent-address`} label="Permanent address" value={member.permanent_address} onChange={(value) => onChange({ permanent_address: value })} />
          <TextField id={`${prefix}-contact`} label="Contact number" type="tel" value={member.contact_number} onChange={(value) => onChange({ contact_number: value })} />
          <TextField id={`${prefix}-email`} label="Email address" type="email" value={member.email_address} onChange={(value) => onChange({ email_address: value })} />
          <TextField id={`${prefix}-education`} label="Educational attainment" value={member.educational_attainment} onChange={(value) => onChange({ educational_attainment: value })} />
          <TextAreaField id={`${prefix}-business-address`} label="Business address" value={member.business_address} onChange={(value) => onChange({ business_address: value })} />
          <TextField id={`${prefix}-business-telephone`} label="Business telephone" type="tel" value={member.business_telephone} onChange={(value) => onChange({ business_telephone: value })} />
          <TextField id={`${prefix}-languages`} label="Languages spoken" value={member.languages_spoken} onChange={(value) => onChange({ languages_spoken: value })} />
          <TextField id={`${prefix}-religion-raised`} label="Religion raised with" value={member.religion_raised_with} onChange={(value) => onChange({ religion_raised_with: value })} />
          <TextField id={`${prefix}-current-religion`} label="Current religion" value={member.current_religion} onChange={(value) => onChange({ current_religion: value })} />
        </div>
      </details>
    </section>
  );
}
