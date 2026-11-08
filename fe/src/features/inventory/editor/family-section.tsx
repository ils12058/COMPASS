"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { CheckboxGroupField, SelectField, TextAreaField, TextField } from "@/features/inventory/editor/fields";
import { InventoryReviewHintText, useInventoryReview, useInventoryReviewDetailsOpen } from "@/features/inventory/editor/inventory-review-context";
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
import { familyMemberTextLimits, inventoryTextLimits } from "@/features/inventory/inventory-field-limits";
import { FieldGroup } from "@/features/inventory/inventory-shared";
import { institutionalDateInputValue } from "@/lib/institutional-time";
import {
  AnnualIncomeStatusValue,
  CivilStatusCategoryValue,
  FamilyMemberKindValue,
  OccupationCategoryValue,
  type FamilyMemberPayload,
} from "@/lib/api/generated/model";

const requiredKinds = [FamilyMemberKindValue.FATHER, FamilyMemberKindValue.MOTHER] as const;
const emptyFamilyMembers: FamilyMemberPayload[] = [];
const absentLifeStatuses = new Set<string>(["DECEASED", "UNKNOWN"]);

export function FamilySection({ draft, onChange, validationIssues = [] }: InventorySectionProps) {
  const errorFor = (targetId: string) =>
    validationIssues.find((issue) => issue.targetId === targetId)?.message;
  const members = draft.family_members ?? emptyFamilyMembers;
  const hasSpouse = members.some((member) => member.kind === FamilyMemberKindValue.SPOUSE);
  const spouseRequired = draft.civil_status_category === CivilStatusCategoryValue.MARRIED;
  const spouseAddReview = useInventoryReview("inventory-spouse-add");
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
          Complete the details for each parent who is living. If a parent is deceased or their life
          status is unknown, that parent’s details are not required. Spouse details are required only
          when your civil status is Married.
        </p>
        <div className="space-y-8">
          {requiredKinds.map((kind) => {
            const lifeStatus =
              kind === FamilyMemberKindValue.FATHER
                ? draft.support_profile?.father_life_status
                : draft.support_profile?.mother_life_status;
            return (
              <FamilyMemberFields
                key={kind}
                kind={kind}
                member={members.find((item) => item.kind === kind) ?? { kind }}
                required={!lifeStatus || !absentLifeStatuses.has(lifeStatus)}
                onChange={(patch) => updateMember(kind, patch)}
                errorFor={errorFor}
              />
            );
          })}
          {hasSpouse ? (
            <FamilyMemberFields
              kind={FamilyMemberKindValue.SPOUSE}
              member={members.find((item) => item.kind === FamilyMemberKindValue.SPOUSE) ?? {
                kind: FamilyMemberKindValue.SPOUSE,
              }}
              required={spouseRequired}
              onChange={(patch) => updateMember(FamilyMemberKindValue.SPOUSE, patch)}
              errorFor={errorFor}
              onRemove={() => {
                focusAfterUpdate.current = "inventory-spouse-add";
                removeSpouse();
              }}
            />
          ) : (
            <div>
              <Button
                id="inventory-spouse-add"
                variant="secondary"
                aria-describedby={spouseAddReview.describedBy}
                onClick={() => {
                  focusAfterUpdate.current = "inventory-family-spouse-name";
                  updateMember(FamilyMemberKindValue.SPOUSE, {});
                }}
              >
                {spouseRequired ? "Add Spouse details" : "Add optional Spouse details"}
              </Button>
              {errorFor("inventory-spouse-add") ? (
                <p role="alert" className="mt-1.5 text-xs leading-5 text-danger">
                  {errorFor("inventory-spouse-add")}
                </p>
              ) : null}
              <InventoryReviewHintText hint={spouseAddReview.hint} />
            </div>
          )}
        </div>
      </FieldGroup>

      <FieldGroup legend="Parent status">
        <div className="grid gap-5 @2xl/inventory:grid-cols-2">
          <SelectField
            id="inventory-parent-status-category"
            error={errorFor("inventory-parent-status-category")}
            label="Current parent-status category"
            value={draft.parent_status_category}
            options={parentStatusCategoryOptions}
            onChange={(value) => onChange({ parent_status_category: value })}
            required
            hint="This answer describes your current situation."
          />
          <CheckboxGroupField
            id="inventory-parent-statuses"
            legend="Additional parent circumstances"
            value={draft.parent_statuses}
            options={parentStatusOptions}
            onChange={(values) => onChange({ parent_statuses: values })}
            required
            error={errorFor("inventory-parent-statuses")}
          />
        </div>
      </FieldGroup>

      <FieldGroup legend="Guardian and emergency contact">
        <div className="grid gap-4 @md/inventory:grid-cols-2">
          <TextField
            id="inventory-guardian-name"
            maxLength={inventoryTextLimits.guardian_name}
            error={errorFor("inventory-guardian-name")}
            label="Guardian name"
            value={draft.guardian_name}
            onChange={(value) => onChange({ guardian_name: value })}
            required
          />
          <TextField
            id="inventory-guardian-relationship"
            maxLength={inventoryTextLimits.guardian_relationship}
            error={errorFor("inventory-guardian-relationship")}
            label="Relationship with guardian"
            value={draft.guardian_relationship}
            onChange={(value) => onChange({ guardian_relationship: value })}
            required
          />
          <TextAreaField
            id="inventory-guardian-address"
            error={errorFor("inventory-guardian-address")}
            label="Guardian address"
            value={draft.guardian_address}
            onChange={(value) => onChange({ guardian_address: value })}
            required
          />
          <TextField
            id="inventory-guardian-contact"
            maxLength={inventoryTextLimits.guardian_contact_number}
            hint="For example, 0917 123 4567."
            error={errorFor("inventory-guardian-contact")}
            label="Guardian contact number"
            type="tel"
            value={draft.guardian_contact_number}
            onChange={(value) => onChange({ guardian_contact_number: value })}
            required
          />
          <TextField
            id="inventory-emergency-name"
            maxLength={inventoryTextLimits.emergency_contact_name}
            error={errorFor("inventory-emergency-name")}
            label="Emergency contact name"
            value={draft.emergency_contact_name}
            onChange={(value) => onChange({ emergency_contact_name: value })}
            required
          />
          <TextField
            id="inventory-emergency-number"
            maxLength={inventoryTextLimits.emergency_contact_number}
            hint="For example, 0917 123 4567."
            error={errorFor("inventory-emergency-number")}
            label="Emergency contact number"
            type="tel"
            value={draft.emergency_contact_number}
            onChange={(value) => onChange({ emergency_contact_number: value })}
            required
          />
        </div>
      </FieldGroup>

      <FieldGroup legend="Student support information">
        <p className="mb-5 max-w-3xl text-sm leading-6 text-muted">
          These responses are confidential support information. They are not shown in the Counselor roster.
        </p>
        <div className="grid gap-4 @md/inventory:grid-cols-2">
          <SelectField
            id="inventory-four-ps"
            error={errorFor("inventory-four-ps")}
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
            error={errorFor("inventory-indigenous-peoples")}
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
            error={errorFor("inventory-mother-life-status")}
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
            error={errorFor("inventory-father-life-status")}
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
  required,
  onChange,
  onRemove,
  errorFor,
}: {
  kind: FamilyMemberKindValue;
  member: FamilyMemberPayload;
  required: boolean;
  onChange: (patch: Partial<FamilyMemberPayload>) => void;
  onRemove?: () => void;
  errorFor: (targetId: string) => string | undefined;
}) {
  const label =
    kind === FamilyMemberKindValue.FATHER
      ? "Father"
      : kind === FamilyMemberKindValue.MOTHER
        ? "Mother"
        : "Spouse";
  const prefix = `inventory-family-${kind.toLowerCase()}`;
  const birthDateError = errorFor(`${prefix}-date-of-birth`);
  const detailsId = `${prefix}-details`;
  const detailsUnderReview = useInventoryReviewDetailsOpen(detailsId);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const detailsError = [
    "date-of-birth",
    "place-of-birth",
    "current-address",
    "permanent-address",
    "contact",
    "email",
    "education",
    "business-address",
    "business-telephone",
    "languages",
    "religion-raised",
    "current-religion",
  ].some((suffix) => errorFor(`${prefix}-${suffix}`));

  // The birth date and the other details sit in the collapsed details; reveal them when one needs
  // attention or was named in a correction request.
  useEffect(() => {
    if ((detailsError || detailsUnderReview) && detailsRef.current) detailsRef.current.open = true;
  }, [detailsError, detailsUnderReview]);

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
        </h3>
        {onRemove ? (
          <Button variant="quiet" onClick={onRemove} aria-label="Remove optional Spouse information">
            Remove Spouse
          </Button>
        ) : null}
      </div>
      <div className="mt-4 grid gap-4 @md/inventory:grid-cols-2">
        <TextField
          id={`${prefix}-name`}
          label="Name"
          maxLength={familyMemberTextLimits.name}
          error={errorFor(`${prefix}-name`)}
          value={member.name}
          onChange={(value) => onChange({ name: value })}
          required={required}
        />
        <SelectField
          id={`${prefix}-occupation-category`}
          label="Occupation category"
          error={errorFor(`${prefix}-occupation-category`)}
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
            maxLength={familyMemberTextLimits.occupation}
            error={errorFor(`${prefix}-occupation`)}
            value={member.occupation}
            onChange={(value) => onChange({ occupation: value })}
            hint="If you chose Other, describe the occupation here."
            required={member.occupation_category === OccupationCategoryValue.OTHER}
          />
        ) : null}
        <SelectField
          id={`${prefix}-income-status`}
          label="Annual income from previous year"
          error={errorFor(`${prefix}-income-status`)}
          value={member.annual_income_status}
          options={annualIncomeOptions}
          onChange={changeIncomeStatus}
          required={required}
        />
        {member.annual_income_status === AnnualIncomeStatusValue.REPORTED ? (
          <TextField
            id={`${prefix}-income-amount`}
            label="Reported amount"
            error={errorFor(`${prefix}-income-amount`)}
            type="number"
            min={0}
            step={0.01}
            value={member.annual_income_previous_year}
            onChange={(value) => onChange({ annual_income_previous_year: value || null })}
            hint="Total for the whole previous year, in pesos (₱)."
            required
          />
        ) : null}
      </div>

      <details id={detailsId} ref={detailsRef} className="mt-5 border-t border-border/70 pt-4">
        <summary className="min-h-9 cursor-pointer text-sm font-semibold text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          Additional {label.toLowerCase()} information
        </summary>
        <div className="mt-4 grid gap-4 @md/inventory:grid-cols-2">
          <TextField id={`${prefix}-date-of-birth`} label="Date of birth" type="date" max={institutionalDateInputValue()} error={birthDateError} value={member.date_of_birth} onChange={(value) => onChange({ date_of_birth: value || null })} required={required} />
          <TextField id={`${prefix}-place-of-birth`} label="Place of birth" maxLength={familyMemberTextLimits.place_of_birth} error={errorFor(`${prefix}-place-of-birth`)} value={member.place_of_birth} onChange={(value) => onChange({ place_of_birth: value })} required={required} />
          <TextAreaField id={`${prefix}-current-address`} label="Current address" error={errorFor(`${prefix}-current-address`)} value={member.current_address} onChange={(value) => onChange({ current_address: value })} required={required} />
          <TextAreaField id={`${prefix}-permanent-address`} label="Permanent address" error={errorFor(`${prefix}-permanent-address`)} value={member.permanent_address} onChange={(value) => onChange({ permanent_address: value })} required={required} />
          <TextField id={`${prefix}-contact`} label="Contact number" type="tel" maxLength={familyMemberTextLimits.contact_number} hint="For example, 0917 123 4567." error={errorFor(`${prefix}-contact`)} value={member.contact_number} onChange={(value) => onChange({ contact_number: value })} required={required} />
          <TextField id={`${prefix}-email`} label="Email address" type="email" maxLength={familyMemberTextLimits.email_address} error={errorFor(`${prefix}-email`)} value={member.email_address} onChange={(value) => onChange({ email_address: value })} required={required} />
          <TextField id={`${prefix}-education`} label="Educational attainment" maxLength={familyMemberTextLimits.educational_attainment} error={errorFor(`${prefix}-education`)} value={member.educational_attainment} onChange={(value) => onChange({ educational_attainment: value })} required={required} />
          <TextAreaField id={`${prefix}-business-address`} label="Business address" error={errorFor(`${prefix}-business-address`)} value={member.business_address} onChange={(value) => onChange({ business_address: value })} required={required} />
          <TextField id={`${prefix}-business-telephone`} label="Business telephone" type="tel" maxLength={familyMemberTextLimits.business_telephone} hint="Include the area code for a landline." error={errorFor(`${prefix}-business-telephone`)} value={member.business_telephone} onChange={(value) => onChange({ business_telephone: value })} required={required} />
          <TextField id={`${prefix}-languages`} label="Languages spoken" error={errorFor(`${prefix}-languages`)} value={member.languages_spoken} onChange={(value) => onChange({ languages_spoken: value })} required={required} />
          <TextField id={`${prefix}-religion-raised`} label="Religion raised with" maxLength={familyMemberTextLimits.religion_raised_with} error={errorFor(`${prefix}-religion-raised`)} value={member.religion_raised_with} onChange={(value) => onChange({ religion_raised_with: value })} required={required} />
          <TextField id={`${prefix}-current-religion`} label="Current religion" maxLength={familyMemberTextLimits.current_religion} error={errorFor(`${prefix}-current-religion`)} value={member.current_religion} onChange={(value) => onChange({ current_religion: value })} required={required} />
        </div>
      </details>
    </section>
  );
}
