import type { ReactNode } from "react";

import { enumLabel, educationLevelOptions, inventorySections } from "@/features/inventory/inventory-presentation";
import { DefinitionValue, formatInventoryDate, formatInventoryDateOnly } from "@/features/inventory/inventory-shared";
import type {
  CounselorInventoryDetailResponse,
  InventoryResponse,
} from "@/lib/api/generated/model";
import {
  CivilStatusCategoryValue,
  CurrentReligionCategoryValue,
  GeographicLocationKindValue,
  OrganizationScopeValue,
} from "@/lib/api/generated/model";

type ReadableInventory = InventoryResponse | CounselorInventoryDetailResponse;

function shown(value: string | number | null | undefined): string {
  if (typeof value === "number") return String(value);
  return value?.trim() ? value : "Not provided";
}

function yesNo(value: boolean | null | undefined): string {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "Not provided";
}

function ValueGrid({ children }: { children: ReactNode }) {
  return <dl className="grid gap-x-6 sm:grid-cols-2">{children}</dl>;
}

function RecordSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-border pt-6">
      <h2 className="font-heading text-xl font-semibold text-ink">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function StructuredLocation({
  location,
}: {
  location: NonNullable<ReadableInventory["geographic_locations"]>[number];
}) {
  const text = location.not_specified
    ? "Prefer not to specify"
    : [
        location.barangay_name_snapshot,
        location.city_municipality_name_snapshot,
        location.province_name_snapshot,
        location.region_name_snapshot,
      ]
        .filter(Boolean)
        .join(", ") || "Not provided";
  return (
    <div className="border-b border-border/70 py-3">
      <dt className="text-xs font-semibold text-muted">
        {location.kind === GeographicLocationKindValue.CURRENT ? "Current structured location" : "Permanent structured location"}
      </dt>
      <dd className="mt-1 text-sm leading-6 text-ink">{text}</dd>
    </div>
  );
}

function RowTable({
  caption,
  headings,
  rows,
}: {
  caption: string;
  headings: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto border-y border-border">
      <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border bg-surface-muted">
            {headings.map((heading) => (
              <th key={heading} scope="col" className="px-3 py-2.5 font-semibold text-ink">{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`${caption}-${rowIndex}`} className="border-b border-border last:border-b-0">
              {row.map((value, cellIndex) => (
                <td key={`${caption}-${rowIndex}-${cellIndex}`} className="px-3 py-3 align-top whitespace-pre-wrap text-ink">{shown(value)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function InventoryReadOnly({
  inventory,
  studentIdentity,
}: {
  inventory: ReadableInventory;
  studentIdentity?: { display_name: string; institutional_id: string | null };
}) {
  const currentLocation = inventory.geographic_locations?.find((location) => location.kind === GeographicLocationKindValue.CURRENT);
  const permanentLocation = inventory.geographic_locations?.find((location) => location.kind === GeographicLocationKindValue.PERMANENT);
  const familyMembers = inventory.family_members ?? [];
  const educationEntries = inventory.education_entries ?? [];
  const memberships = inventory.organization_memberships ?? [];
  const transportation = inventory.transportation_entries ?? [];

  return (
    <div className="space-y-7">
      {studentIdentity ? (
        <section className="border-b border-border pb-5" aria-labelledby="inventory-record-student-heading">
          <h2 id="inventory-record-student-heading" className="font-heading text-xl font-semibold text-ink">
            {studentIdentity.display_name}
          </h2>
          <p className="mt-1 text-sm text-muted">Institutional ID: {studentIdentity.institutional_id ?? "Not provided"}</p>
        </section>
      ) : null}

      <dl className="grid gap-x-6 sm:grid-cols-2">
        <DefinitionValue label="Academic Year" value={inventory.academic_year.label} />
        <DefinitionValue
          label="Official Form Revision"
          value={`${inventory.form_revision.official_code} · Revision ${inventory.form_revision.official_revision}`}
        />
        <DefinitionValue label="Submitted" value={formatInventoryDate(inventory.submitted_at)} />
        <DefinitionValue label="Last submitted" value={formatInventoryDate(inventory.last_submitted_at)} />
      </dl>

      <RecordSection title={inventorySections[0].label}>
        <ValueGrid>
          <DefinitionValue label="Full name" value={shown(inventory.full_name)} />
          <DefinitionValue label="Nickname" value={shown(inventory.nickname)} />
          <DefinitionValue label="Institutional ID" value={shown(inventory.student_number)} />
          <DefinitionValue label="Date of birth" value={formatInventoryDateOnly(inventory.date_of_birth)} />
          <DefinitionValue label="Place of birth" value={shown(inventory.place_of_birth)} />
          <DefinitionValue label="Nationality" value={shown(inventory.nationality)} />
          <DefinitionValue label="Sex" value={enumLabel(inventory.sex)} />
          <DefinitionValue label="Birth order among siblings" value={shown(inventory.birth_order_among_siblings)} />
          <DefinitionValue
            label="Civil status"
            value={inventory.civil_status_category === CivilStatusCategoryValue.OTHER
              ? `Other · ${shown(inventory.civil_status)}`
              : enumLabel(inventory.civil_status_category)}
          />
          <DefinitionValue label="Contact number" value={shown(inventory.contact_number)} />
          <DefinitionValue label="Email address" value={shown(inventory.email_address)} />
          <DefinitionValue label="Languages spoken at home" value={shown(inventory.languages_spoken_at_home)} />
          <DefinitionValue label="Languages most fluent in" value={shown(inventory.languages_most_fluent)} />
          <DefinitionValue label="Religion from birth" value={shown(inventory.religion_from_birth)} />
          <DefinitionValue
            label="Current religion"
            value={inventory.current_religion_category === CurrentReligionCategoryValue.OTHER
              ? `Other · ${shown(inventory.current_religion)}`
              : enumLabel(inventory.current_religion_category)}
          />
        </ValueGrid>
        <div className="mt-4 grid gap-x-6 sm:grid-cols-2">
          <DefinitionValue label="Current address" value={shown(inventory.current_address)} />
          <DefinitionValue label="Permanent address" value={shown(inventory.permanent_address)} />
          {currentLocation ? <StructuredLocation location={currentLocation} /> : null}
          {permanentLocation ? <StructuredLocation location={permanentLocation} /> : null}
        </div>
      </RecordSection>

      <RecordSection title={inventorySections[1].label}>
        <div className="space-y-6">
          {familyMembers.map((member) => (
            <section key={member.kind} className="border-t border-border pt-4">
              <h3 className="font-semibold text-ink">{enumLabel(member.kind)}</h3>
              <ValueGrid>
                <DefinitionValue label="Name" value={shown(member.name)} />
                <DefinitionValue label="Date of birth" value={formatInventoryDateOnly(member.date_of_birth)} />
                <DefinitionValue label="Place of birth" value={shown(member.place_of_birth)} />
                <DefinitionValue label="Occupation category" value={enumLabel(member.occupation_category)} />
                <DefinitionValue label="Occupation" value={shown(member.occupation)} />
                <DefinitionValue label="Educational attainment" value={shown(member.educational_attainment)} />
                <DefinitionValue label="Annual income response" value={enumLabel(member.annual_income_status)} />
                <DefinitionValue label="Annual income, previous year" value={shown(member.annual_income_previous_year)} />
                <DefinitionValue label="Contact number" value={shown(member.contact_number)} />
                <DefinitionValue label="Email address" value={shown(member.email_address)} />
                <DefinitionValue label="Current address" value={shown(member.current_address)} />
                <DefinitionValue label="Permanent address" value={shown(member.permanent_address)} />
                <DefinitionValue label="Business address" value={shown(member.business_address)} />
                <DefinitionValue label="Business telephone" value={shown(member.business_telephone)} />
                <DefinitionValue label="Languages spoken" value={shown(member.languages_spoken)} />
                <DefinitionValue label="Religion raised with" value={shown(member.religion_raised_with)} />
                <DefinitionValue label="Current religion" value={shown(member.current_religion)} />
              </ValueGrid>
            </section>
          ))}
          <ValueGrid>
            <DefinitionValue label="Parent-status category" value={enumLabel(inventory.parent_status_category)} />
            <DefinitionValue label="Additional parent circumstances" value={(inventory.parent_statuses ?? []).map(enumLabel).join(", ") || "Not provided"} />
            <DefinitionValue label="Guardian" value={shown(inventory.guardian_name)} />
            <DefinitionValue label="Relationship with guardian" value={shown(inventory.guardian_relationship)} />
            <DefinitionValue label="Guardian address" value={shown(inventory.guardian_address)} />
            <DefinitionValue label="Guardian contact number" value={shown(inventory.guardian_contact_number)} />
            <DefinitionValue label="Emergency contact" value={shown(inventory.emergency_contact_name)} />
            <DefinitionValue label="Emergency contact number" value={shown(inventory.emergency_contact_number)} />
            <DefinitionValue label="4Ps status" value={enumLabel(inventory.support_profile?.four_ps_status)} />
            <DefinitionValue label="Indigenous Peoples status" value={enumLabel(inventory.support_profile?.indigenous_peoples_status)} />
            <DefinitionValue label="Mother's life status" value={enumLabel(inventory.support_profile?.mother_life_status)} />
            <DefinitionValue label="Father's life status" value={enumLabel(inventory.support_profile?.father_life_status)} />
          </ValueGrid>
        </div>
      </RecordSection>

      <RecordSection title={inventorySections[2].label}>
        {(inventory.siblings ?? []).length ? (
          <RowTable
            caption="Siblings listed from eldest to youngest"
            headings={["Name", "Sex", "Age", "Educational attainment", "Occupation", "Student"]}
            rows={(inventory.siblings ?? []).map((row) => [
              row.name ?? "",
              enumLabel(row.sex),
              row.age === null || row.age === undefined ? "Not provided" : String(row.age),
              row.educational_attainment ?? "",
              row.occupation ?? "",
              row.is_self ? "This is me" : "",
            ])}
          />
        ) : <p className="text-sm text-muted">No sibling information provided.</p>}
        <ValueGrid>
          <DefinitionValue label="Friends in school" value={shown(inventory.friends_in_school)} />
          <DefinitionValue label="Friends outside school" value={shown(inventory.friends_outside_school)} />
          <DefinitionValue label="Special interest" value={shown(inventory.special_interest)} />
          <DefinitionValue label="Special skills and talents" value={shown(inventory.special_skills_talents)} />
          <DefinitionValue label="Hobbies and recreation" value={shown(inventory.hobbies_recreation)} />
          <DefinitionValue label="Ambition or goal" value={shown(inventory.ambition_goal)} />
          <DefinitionValue label="Characteristics" value={shown(inventory.characteristics)} />
        </ValueGrid>
      </RecordSection>

      <RecordSection title={inventorySections[3].label}>
        <ValueGrid>
          <DefinitionValue label="Living arrangement" value={enumLabel(inventory.living_arrangement)} />
          <DefinitionValue label="Boarding house exclusive" value={yesNo(inventory.boarding_exclusive)} />
          <DefinitionValue label="Landlord or landlady" value={shown(inventory.boarding_landlord_name)} />
          <DefinitionValue label="Boarding-house address" value={shown(inventory.boarding_address)} />
          <DefinitionValue label="People in present living place" value={shown(inventory.present_place_people_count)} />
          <DefinitionValue label="People sharing room" value={shown(inventory.room_sharing_people_count)} />
          <DefinitionValue label="Accidents experienced" value={shown(inventory.accidents_experienced)} />
          <DefinitionValue label="Effect of accidents" value={shown(inventory.accidents_effect)} />
          <DefinitionValue label="Operations experienced" value={shown(inventory.operations_experienced)} />
          <DefinitionValue label="Effect of operations" value={shown(inventory.operations_effect)} />
          <DefinitionValue label="Immunizations" value={(inventory.immunizations ?? []).map(enumLabel).join(", ") || "Not provided"} />
          <DefinitionValue label="Other immunization" value={shown(inventory.immunization_other)} />
          <DefinitionValue label="Height" value={shown(inventory.height)} />
          <DefinitionValue label="Weight" value={shown(inventory.weight)} />
          <DefinitionValue label="Disability status" value={enumLabel(inventory.pwd_status)} />
          <DefinitionValue label="Physical disadvantage or support context" value={shown(inventory.physical_disadvantage)} />
          <DefinitionValue label="Illness this year" value={shown(inventory.illness_this_year)} />
          <DefinitionValue label="Previous illness" value={shown(inventory.previous_illness)} />
        </ValueGrid>
      </RecordSection>

      <RecordSection title={inventorySections[4].label}>
        {educationEntries.length ? (
          <RowTable
            caption="Educational history"
            headings={["Level", "School and address", "Inclusive years", "Awards received"]}
            rows={[...educationEntries]
              .sort((a, b) => educationLevelOptions.findIndex(([level]) => level === a.level) - educationLevelOptions.findIndex(([level]) => level === b.level))
              .map((entry) => [
                enumLabel(entry.level),
                entry.school_attended_address ?? "",
                entry.inclusive_years ?? "",
                entry.awards_received ?? "",
              ])}
          />
        ) : <p className="text-sm text-muted">No educational history provided.</p>}
        <ValueGrid>
          <DefinitionValue label="Program" value={inventory.program ? `${inventory.program.code} · ${inventory.program.name}` : "Not provided"} />
          <DefinitionValue label="Current course snapshot" value={shown(inventory.course_currently_enrolled)} />
          <DefinitionValue label="Year Level" value={shown(inventory.year_level)} />
          <DefinitionValue label="Major" value={shown(inventory.major)} />
          <DefinitionValue label="Satisfied with schedule" value={yesNo(inventory.schedule_satisfied)} />
          <DefinitionValue label="Schedule satisfaction reason" value={shown(inventory.schedule_satisfaction_reason)} />
        </ValueGrid>
      </RecordSection>

      <RecordSection title={inventorySections[5].label}>
        <ValueGrid>
          <DefinitionValue label="First-choice course" value={yesNo(inventory.course_first_choice)} />
          <DefinitionValue label="Course-choice reasons" value={(inventory.course_choice_reasons ?? []).map(enumLabel).join(", ") || "Not provided"} />
          <DefinitionValue label="Other course-choice reason" value={shown(inventory.course_choice_other)} />
          <DefinitionValue label="Subjects with lowest grades" value={shown(inventory.lowest_subjects_grades)} />
          <DefinitionValue label="Subjects with highest grades" value={shown(inventory.highest_subjects_grades)} />
          <DefinitionValue label="Inclination: performing arts" value={shown(inventory.inclination_performing_arts)} />
          <DefinitionValue label="Inclination: sports" value={shown(inventory.inclination_sports)} />
          <DefinitionValue label="Inclination: leadership" value={shown(inventory.inclination_leadership)} />
          <DefinitionValue label="Interests" value={(inventory.interests ?? []).map(enumLabel).join(", ") || "Not provided"} />
          <DefinitionValue label="Other skills and hobbies" value={shown(inventory.other_skills_hobbies)} />
          <DefinitionValue label="Desired extracurricular activities" value={shown(inventory.desired_extracurricular_activities)} />
          <DefinitionValue label="Reading preferences" value={shown(inventory.reading_preferences)} />
          <DefinitionValue label="Handedness" value={enumLabel(inventory.handedness)} />
          <DefinitionValue label="Daily hours: class" value={shown(inventory.daily_hours_class)} />
          <DefinitionValue label="Daily hours: library work" value={shown(inventory.daily_hours_library)} />
          <DefinitionValue label="Daily hours: studying" value={shown(inventory.daily_hours_studying)} />
          <DefinitionValue label="Daily hours: rest" value={shown(inventory.daily_hours_rest)} />
          <DefinitionValue label="Daily hours: recreation" value={shown(inventory.daily_hours_recreation)} />
          <DefinitionValue label="Daily hours: other" value={shown(inventory.daily_hours_other)} />
        </ValueGrid>
      </RecordSection>

      <RecordSection title={inventorySections[6].label}>
        {memberships.length ? (
          <div className="space-y-5">
            {([OrganizationScopeValue.INSIDE_SCHOOL, OrganizationScopeValue.OUTSIDE_SCHOOL] as const).map((scope) => {
              const rows = memberships.filter((item) => item.scope === scope);
              if (!rows.length) return null;
              return (
                <div key={scope}>
                  <h3 className="mb-2 font-semibold text-ink">{enumLabel(scope)}</h3>
                  <RowTable
                    caption={`${enumLabel(scope)} organizations`}
                    headings={["Organization", "Position or title"]}
                    rows={rows
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((item) => [item.organization_name ?? "", item.position_title ?? ""])}
                  />
                </div>
              );
            })}
          </div>
        ) : <p className="text-sm text-muted">No organization memberships provided.</p>}
        {transportation.length ? (
          <div className="mt-5">
            <RowTable
              caption="Transportation to and from the university"
              headings={["Mode", "Frequency", "Details", "Fare"]}
              rows={transportation.map((entry) => [
                enumLabel(entry.mode),
                enumLabel(entry.frequency_category),
                shown(entry.frequency),
                shown(entry.fare),
              ])}
            />
          </div>
        ) : <p className="mt-4 text-sm text-muted">No transportation modes provided.</p>}
      </RecordSection>

      <RecordSection title={inventorySections[7].label}>
        <ValueGrid>
          <DefinitionValue label="Ideal monthly allowance" value={enumLabel(inventory.ideal_monthly_allowance)} />
          <DefinitionValue label="Intended work field" value={enumLabel(inventory.intended_work_field)} />
          <DefinitionValue label="Other intended work field" value={shown(inventory.intended_work_other)} />
          <DefinitionValue label="Prior counseling experience" value={yesNo(inventory.prior_counseling_experience)} />
          <DefinitionValue label="Prior Counselor name" value={shown(inventory.prior_counselor_name)} />
          <DefinitionValue label="Prior counseling when" value={shown(inventory.prior_counseling_when)} />
          <DefinitionValue label="Prior counseling where" value={shown(inventory.prior_counseling_where)} />
          <DefinitionValue label="Current concerns" value={shown(inventory.current_concerns)} />
          <DefinitionValue label="Current fears" value={shown(inventory.current_fears)} />
        </ValueGrid>
      </RecordSection>
    </div>
  );
}
