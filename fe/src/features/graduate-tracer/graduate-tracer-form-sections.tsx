"use client";

import { Button } from "@/components/ui/button";
import {
  ADVANCED_STUDY_REASON_CHOICES,
  CIVIL_STATUS_CHOICES,
  DEGREE_REASON_CHOICES,
  REGION_CHOICES,
  RESIDENCE_LOCATION_CHOICES,
  SEX_CHOICES,
  type GraduateTracerFormDraft,
} from "@/features/graduate-tracer/graduate-tracer-presentation";
import {
  CheckboxField,
  SelectField,
  TextAreaField,
  TextField,
} from "@/features/graduate-tracer/graduate-tracer-form-fields";
import { GraduateTracerSection } from "@/features/graduate-tracer/graduate-tracer-shared";

export type GraduateTracerDraftChange = <K extends keyof GraduateTracerFormDraft>(
  field: K,
  value: GraduateTracerFormDraft[K],
) => void;

function toggle<T extends string>(values: readonly T[] | undefined, value: T): T[] {
  const current = values ?? [];
  return current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
}

export function GraduateTracerGeneralSection({
  draft,
  onChange,
}: {
  draft: GraduateTracerFormDraft;
  onChange: GraduateTracerDraftChange;
}) {
  return (
    <GraduateTracerSection id="graduate-tracer-general" title="A. General Information">
      <p className="max-w-3xl text-sm leading-6 text-muted">
        Changes here apply only to this Graduate Tracer response and do not update your COMPASS account profile.
      </p>
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField id="gts-name" label="Name" value={draft.name} onChange={(value) => onChange("name", value)} />
        <TextField id="gts-email" label="E-mail Address" type="email" inputMode="email" value={draft.email} onChange={(value) => onChange("email", value)} />
        <TextField id="gts-birth-date" label="Birthday" type="date" max={new Date().toISOString().slice(0, 10)} value={draft.birth_date ?? undefined} onChange={(value) => onChange("birth_date", value || null)} />
        <TextField id="gts-province" label="Province" value={draft.province} onChange={(value) => onChange("province", value)} />
      </div>
      <TextAreaField id="gts-permanent-address" label="Permanent Address" value={draft.permanent_address} onChange={(value) => onChange("permanent_address", value)} />
      <div className="grid gap-5 sm:grid-cols-2">
        <TextField id="gts-telephone" label="Telephone or Contact Number(s)" type="tel" inputMode="tel" value={draft.telephone_contact_numbers} onChange={(value) => onChange("telephone_contact_numbers", value)} />
        <TextField id="gts-mobile" label="Mobile Number" type="tel" inputMode="tel" value={draft.mobile_number} onChange={(value) => onChange("mobile_number", value)} />
      </div>
      <div className="grid gap-5 sm:grid-cols-2">
        <SelectField id="gts-civil-status" label="Civil Status" value={draft.civil_status} options={CIVIL_STATUS_CHOICES} onChange={(value) => onChange("civil_status", value)} />
        <SelectField id="gts-sex" label="Sex" value={draft.sex} options={SEX_CHOICES} onChange={(value) => onChange("sex", value)} />
        <SelectField id="gts-region" label="Region of Origin" value={draft.region_of_origin} options={REGION_CHOICES} onChange={(value) => onChange("region_of_origin", value)} />
        <SelectField id="gts-residence-location" label="Location of Residence" value={draft.residence_location} options={RESIDENCE_LOCATION_CHOICES} onChange={(value) => onChange("residence_location", value)} />
      </div>
    </GraduateTracerSection>
  );
}

export function GraduateTracerEducationSection({
  draft,
  onChange,
}: {
  draft: GraduateTracerFormDraft;
  onChange: GraduateTracerDraftChange;
}) {
  return (
    <GraduateTracerSection id="graduate-tracer-education" title="B. Educational Background">
      <div>
        <h3 className="font-semibold text-ink">Q12. Educational Attainment (Baccalaureate Degree only)</h3>
        <p className="mt-1 text-sm leading-6 text-muted">Add each baccalaureate degree you completed. At least one is required before submission.</p>
        {draft.education.length ? (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {draft.education.map((row, index) => (
              <fieldset key={row.formKey} className="space-y-4 py-5">
                <legend className="font-semibold text-ink">Degree {index + 1}</legend>
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField id={`degree-${index}-name`} label="Degree(s) & Specialization(s)" value={row.degree_and_specialization} onChange={(value) => onChange("education", draft.education.map((item, itemIndex) => itemIndex === index ? { ...item, degree_and_specialization: value } : item))} />
                  <TextField id={`degree-${index}-institution`} label="College or University" value={row.college_or_university} onChange={(value) => onChange("education", draft.education.map((item, itemIndex) => itemIndex === index ? { ...item, college_or_university: value } : item))} />
                  <TextField id={`degree-${index}-year`} label="Year Graduated" type="number" inputMode="numeric" min={1900} max={new Date().getFullYear()} step={1} value={row.year_graduated} onChange={(value) => onChange("education", draft.education.map((item, itemIndex) => itemIndex === index ? { ...item, year_graduated: value } : item))} />
                  <TextField id={`degree-${index}-honors`} label="Honor(s) or Award(s) Received" value={row.honors_or_awards} onChange={(value) => onChange("education", draft.education.map((item, itemIndex) => itemIndex === index ? { ...item, honors_or_awards: value } : item))} />
                </div>
                <Button type="button" variant="secondary" onClick={() => onChange("education", draft.education.filter((_, itemIndex) => itemIndex !== index))}>Remove degree {index + 1}</Button>
              </fieldset>
            ))}
          </div>
        ) : <p className="mt-3 text-sm text-muted">No baccalaureate degree has been added.</p>}
        <Button type="button" variant="secondary" className="mt-4" onClick={() => onChange("education", [...draft.education, { degree_and_specialization: "", college_or_university: "", year_graduated: "", honors_or_awards: "", formKey: globalThis.crypto.randomUUID() }])}>Add another degree</Button>
      </div>

      <div className="border-t border-border pt-6">
        <h3 className="font-semibold text-ink">Q13. Professional Examinations</h3>
        <p className="mt-1 text-sm leading-6 text-muted">Optional. Add an examination name; date taken and rating may be left blank.</p>
        {draft.professional_exams.length ? (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {draft.professional_exams.map((row, index) => (
              <fieldset key={row.formKey} className="space-y-4 py-5">
                <legend className="font-semibold text-ink">Examination {index + 1}</legend>
                <div className="grid gap-4 sm:grid-cols-3">
                  <TextField id={`exam-${index}-name`} label="Name of Examination" value={row.examination_name} onChange={(value) => onChange("professional_exams", draft.professional_exams.map((item, itemIndex) => itemIndex === index ? { ...item, examination_name: value } : item))} />
                  <TextField id={`exam-${index}-date`} label="Date Taken" type="date" max={new Date().toISOString().slice(0, 10)} value={row.date_taken ?? ""} onChange={(value) => onChange("professional_exams", draft.professional_exams.map((item, itemIndex) => itemIndex === index ? { ...item, date_taken: value || null } : item))} />
                  <TextField id={`exam-${index}-rating`} label="Rating" value={row.rating} onChange={(value) => onChange("professional_exams", draft.professional_exams.map((item, itemIndex) => itemIndex === index ? { ...item, rating: value } : item))} />
                </div>
                <Button type="button" variant="secondary" onClick={() => onChange("professional_exams", draft.professional_exams.filter((_, itemIndex) => itemIndex !== index))}>Remove examination {index + 1}</Button>
              </fieldset>
            ))}
          </div>
        ) : <p className="mt-3 text-sm text-muted">No professional examinations added.</p>}
        <Button type="button" variant="secondary" className="mt-4" onClick={() => onChange("professional_exams", [...draft.professional_exams, { examination_name: "", date_taken: null, rating: "", formKey: globalThis.crypto.randomUUID() }])}>Add examination</Button>
      </div>

      <div className="border-t border-border pt-6">
        <h3 className="font-semibold text-ink">Q14. Reasons for taking degree(s)</h3>
        <p id="gts-degree-reasons-help" className="mt-1 text-sm leading-6 text-muted">Select any reasons that apply. The two columns are independent; the shared “Others, please specify” line is below the comparison.</p>
        <div className="mt-4 overflow-x-auto rounded-md border border-border">
          <table className="min-w-[42rem] w-full border-collapse text-sm">
            <caption className="sr-only">Reasons for taking undergraduate and graduate degree programs</caption>
            <thead className="bg-surface-muted text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="sticky left-0 z-10 min-w-[20rem] bg-surface-muted px-3 py-3 font-semibold">Reason</th>
                <th scope="col" className="min-w-44 px-3 py-3 font-semibold">Undergraduate / AB / BS</th>
                <th scope="col" className="min-w-44 px-3 py-3 font-semibold">Graduate / MS / MA / PhD</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {DEGREE_REASON_CHOICES.map((choice) => (
                <tr key={choice.value}>
                  <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-3 py-3 text-left font-medium text-ink">{choice.label}</th>
                  <td className="px-3 py-3">
                    <input type="checkbox" aria-label={`${choice.label} — Undergraduate / AB / BS`} checked={draft.undergraduate_degree_reasons?.includes(choice.value) ?? false} onChange={() => onChange("undergraduate_degree_reasons", toggle(draft.undergraduate_degree_reasons, choice.value))} className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" />
                  </td>
                  <td className="px-3 py-3">
                    <input type="checkbox" aria-label={`${choice.label} — Graduate / MS / MA / PhD`} checked={draft.graduate_study_reasons?.includes(choice.value) ?? false} onChange={() => onChange("graduate_study_reasons", toggle(draft.graduate_study_reasons, choice.value))} className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 max-w-2xl">
          <TextAreaField id="gts-degree-other-reason" label="Others, please specify" value={draft.degree_other_reason} onChange={(value) => onChange("degree_other_reason", value)} />
        </div>
      </div>
    </GraduateTracerSection>
  );
}

export function GraduateTracerTrainingSection({
  draft,
  onChange,
}: {
  draft: GraduateTracerFormDraft;
  onChange: GraduateTracerDraftChange;
}) {
  return (
    <GraduateTracerSection id="graduate-tracer-training" title="C. Training(s) / Advance Studies Attended After College">
      <div>
        <h3 className="font-semibold text-ink">Q15a. Training(s) / Advance Studies Attended After College</h3>
        <p className="mt-1 text-sm leading-6 text-muted">Optional. Add each training or advance study attended after college.</p>
        {draft.trainings.length ? (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {draft.trainings.map((row, index) => (
              <fieldset key={row.formKey} className="space-y-4 py-5">
                <legend className="font-semibold text-ink">Training / advance study {index + 1}</legend>
                <div className="grid gap-4 sm:grid-cols-2">
                  <TextField id={`training-${index}-title`} label="Title of Training or Advance Study" value={row.title} onChange={(value) => onChange("trainings", draft.trainings.map((item, itemIndex) => itemIndex === index ? { ...item, title: value } : item))} />
                  <TextField id={`training-${index}-duration`} label="Duration and Credits Earned" value={row.duration_and_credits} onChange={(value) => onChange("trainings", draft.trainings.map((item, itemIndex) => itemIndex === index ? { ...item, duration_and_credits: value } : item))} />
                  <TextField id={`training-${index}-institution`} label="Name of Training Institution / College / University" value={row.institution} onChange={(value) => onChange("trainings", draft.trainings.map((item, itemIndex) => itemIndex === index ? { ...item, institution: value } : item))} />
                </div>
                <Button type="button" variant="secondary" onClick={() => onChange("trainings", draft.trainings.filter((_, itemIndex) => itemIndex !== index))}>Remove training / advance study {index + 1}</Button>
              </fieldset>
            ))}
          </div>
        ) : <p className="mt-3 text-sm text-muted">No training or advance study has been added.</p>}
        <Button type="button" variant="secondary" className="mt-4" onClick={() => onChange("trainings", [...draft.trainings, { title: "", duration_and_credits: "", institution: "", formKey: globalThis.crypto.randomUUID() }])}>Add training / advance study</Button>
      </div>
      <div className="border-t border-border pt-6">
        <CheckboxField
          id="gts-advanced-study-reasons"
          legend="Q15b. Reasons for attending advance study"
          values={draft.advanced_study_reasons}
          options={ADVANCED_STUDY_REASON_CHOICES}
          onChange={(values) => onChange("advanced_study_reasons", values)}
        />
        {draft.advanced_study_reasons?.includes("OTHER") ? (
          <div className="mt-4 max-w-2xl">
            <TextAreaField id="gts-advanced-study-other" label="Please specify" value={draft.advanced_study_other_reason} onChange={(value) => onChange("advanced_study_other_reason", value)} />
          </div>
        ) : null}
      </div>
    </GraduateTracerSection>
  );
}
