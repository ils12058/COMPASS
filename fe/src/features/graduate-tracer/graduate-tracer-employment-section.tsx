"use client";

import { GTSFirstJobDurationValue, GTSFirstJobSourceValue } from "@/lib/api/generated/model";
import {
  BUSINESS_LINE_CHOICES,
  EARNING_BRACKET_CHOICES,
  EMPLOYMENT_STATE_CHOICES,
  FIRST_JOB_DURATION_CHOICES,
  FIRST_JOB_SOURCE_CHOICES,
  JOB_LEVEL_CHOICES,
  JOB_REASON_CHOICES,
  PLACE_OF_WORK_CHOICES,
  PRESENT_EMPLOYMENT_STATUS_CHOICES,
  STAYING_REASON_CHOICES,
  UNEMPLOYMENT_REASON_CHOICES,
  USEFUL_COMPETENCY_CHOICES,
  type GraduateTracerFormDraft,
} from "@/features/graduate-tracer/graduate-tracer-presentation";
import {
  BooleanField,
  CheckboxField,
  SelectField,
  TextAreaField,
  TextField,
  RadioField,
} from "@/features/graduate-tracer/graduate-tracer-form-fields";
import { GraduateTracerSection } from "@/features/graduate-tracer/graduate-tracer-shared";
import type { GraduateTracerDraftChange } from "@/features/graduate-tracer/graduate-tracer-form-sections";

export function GraduateTracerEmploymentSection({
  draft,
  onChange,
}: {
  draft: GraduateTracerFormDraft;
  onChange: GraduateTracerDraftChange;
}) {
  const employed = draft.current_employment_state === "EMPLOYED";
  const unemployed = draft.current_employment_state === "NOT_EMPLOYED" || draft.current_employment_state === "NEVER_EMPLOYED";
  const firstJob = draft.first_job_after_college === true;

  return (
    <GraduateTracerSection id="graduate-tracer-employment" title="D. Employment Data">
      <RadioField
        id="gts-employment-state"
        legend="Q16. Are you presently employed?"
        value={draft.current_employment_state}
        options={EMPLOYMENT_STATE_CHOICES}
        onChange={(value) => onChange("current_employment_state", value)}
      />

      {unemployed ? (
        <div className="border-t border-border pt-6">
          <CheckboxField
            id="gts-unemployment-reasons"
            legend="Q17. Please state reason(s) why you are not yet employed."
            values={draft.unemployment_reasons}
            options={UNEMPLOYMENT_REASON_CHOICES}
            onChange={(values) => onChange("unemployment_reasons", values)}
          />
          {draft.unemployment_reasons?.includes("OTHER") ? (
            <div className="mt-4 max-w-2xl">
              <TextAreaField id="gts-unemployment-other" label="Please specify" value={draft.unemployment_other_reason} onChange={(value) => onChange("unemployment_other_reason", value)} />
            </div>
          ) : null}
        </div>
      ) : null}

      {employed ? (
        <>
          <div className="border-t border-border pt-6">
            <RadioField
              id="gts-present-employment-status"
              legend="Q18. Present Employment Status"
              value={draft.present_employment_status}
              options={PRESENT_EMPLOYMENT_STATUS_CHOICES}
              onChange={(value) => onChange("present_employment_status", value)}
            />
            {draft.present_employment_status === "SELF_EMPLOYED" ? (
              <div className="mt-4 max-w-3xl">
                <TextAreaField
                  id="gts-self-employed-skills"
                  label="If self-employed, what skills acquired in college were you able to apply in your work?"
                  value={draft.self_employed_college_skills}
                  onChange={(value) => onChange("self_employed_college_skills", value)}
                />
              </div>
            ) : null}
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              <TextField id="gts-present-occupation" label="Q19. Present Occupation" value={draft.present_occupation} onChange={(value) => onChange("present_occupation", value)} />
              <SelectField id="gts-business-line" label="Q20. Major Line of Business" value={draft.employer_business_line} options={BUSINESS_LINE_CHOICES} onChange={(value) => onChange("employer_business_line", value)} />
              <SelectField id="gts-place-of-work" label="Q21. Place of Work" value={draft.place_of_work} options={PLACE_OF_WORK_CHOICES} onChange={(value) => onChange("place_of_work", value)} />
            </div>
          </div>

          <div className="border-t border-border pt-6">
            <BooleanField
              id="gts-first-job-after-college"
              legend="Q22. Is this your first job after college?"
              value={draft.first_job_after_college}
              onChange={(value) => onChange("first_job_after_college", value)}
            />
            {firstJob ? (
              <div className="mt-6 space-y-6 border-l-2 border-support pl-4 sm:pl-6">
                <CheckboxField
                  id="gts-staying-reasons"
                  legend="What are your reason(s) for staying on the job?"
                  values={draft.reasons_for_staying_on_job}
                  options={STAYING_REASON_CHOICES}
                  onChange={(values) => onChange("reasons_for_staying_on_job", values)}
                />
                {draft.reasons_for_staying_on_job?.includes("OTHER") ? (
                  <div className="max-w-2xl">
                    <TextAreaField id="gts-staying-other" label="Please specify" value={draft.reasons_for_staying_other} onChange={(value) => onChange("reasons_for_staying_other", value)} />
                  </div>
                ) : null}
                <BooleanField
                  id="gts-first-job-related"
                  legend="Is your first job related to the course you took up in college?"
                  value={draft.first_job_related_to_course}
                  onChange={(value) => onChange("first_job_related_to_course", value)}
                />
              </div>
            ) : null}
          </div>

          <div className="border-t border-border pt-6">
            <h3 className="font-semibold text-ink">First-job and job-change context</h3>
            <p className="mt-1 text-sm leading-6 text-muted">The supplied survey has an inconsistent question-number sequence in this area. These fields use semantic labels and do not reconstruct a missing question.</p>
            {firstJob && draft.first_job_related_to_course !== false ? (
              <div className="mt-5 max-w-3xl">
                <CheckboxField
                  id="gts-accepting-reasons"
                  legend="Reasons for accepting the first job"
                  values={draft.reasons_for_accepting_first_job}
                  options={JOB_REASON_CHOICES}
                  onChange={(values) => onChange("reasons_for_accepting_first_job", values)}
                />
                {draft.reasons_for_accepting_first_job?.includes("OTHER") ? (
                  <div className="mt-4">
                    <TextAreaField id="gts-accepting-other" label="Please specify" value={draft.reasons_for_accepting_other} onChange={(value) => onChange("reasons_for_accepting_other", value)} />
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="mt-5 max-w-3xl">
              <CheckboxField
                id="gts-changing-reasons"
                legend="Reasons for changing job"
                values={draft.reasons_for_changing_job}
                options={JOB_REASON_CHOICES}
                onChange={(values) => onChange("reasons_for_changing_job", values)}
              />
              {draft.reasons_for_changing_job?.includes("OTHER") ? (
                <div className="mt-4">
                  <TextAreaField id="gts-changing-other" label="Please specify" value={draft.reasons_for_changing_other} onChange={(value) => onChange("reasons_for_changing_other", value)} />
                </div>
              ) : null}
            </div>
          </div>

          <div className="border-t border-border pt-6">
            <div className="grid gap-5 sm:grid-cols-2">
              <SelectField id="gts-first-job-duration" label="How long did you stay in your first job?" value={draft.first_job_duration} options={FIRST_JOB_DURATION_CHOICES} onChange={(value) => onChange("first_job_duration", value)} />
              <SelectField id="gts-first-job-source" label="How did you find your first job?" value={draft.first_job_source} options={FIRST_JOB_SOURCE_CHOICES} onChange={(value) => onChange("first_job_source", value)} />
              <SelectField id="gts-time-to-first-job" label="How long did it take you to land your first job?" value={draft.time_to_first_job} options={FIRST_JOB_DURATION_CHOICES} onChange={(value) => onChange("time_to_first_job", value)} />
            </div>
            {draft.first_job_duration === GTSFirstJobDurationValue.OTHER ? (
              <div className="mt-4 max-w-2xl"><TextField id="gts-first-job-duration-other" label="Please specify first-job duration" value={draft.first_job_duration_other} onChange={(value) => onChange("first_job_duration_other", value)} /></div>
            ) : null}
            {draft.first_job_source === GTSFirstJobSourceValue.OTHER ? (
              <div className="mt-4 max-w-2xl"><TextField id="gts-first-job-source-other" label="Please specify how you found your first job" value={draft.first_job_source_other} onChange={(value) => onChange("first_job_source_other", value)} /></div>
            ) : null}
            {draft.time_to_first_job === GTSFirstJobDurationValue.OTHER ? (
              <div className="mt-4 max-w-2xl"><TextField id="gts-time-to-first-job-other" label="Please specify time to first job" value={draft.time_to_first_job_other} onChange={(value) => onChange("time_to_first_job_other", value)} /></div>
            ) : null}
          </div>

          <div className="border-t border-border pt-6">
            <h3 className="font-semibold text-ink">Job level position</h3>
            <div className="mt-4 overflow-x-auto rounded-md border border-border">
              <table className="min-w-[38rem] w-full border-collapse text-sm">
                <caption className="sr-only">Compare job level in the first job and current or present job</caption>
                <thead className="bg-surface-muted text-left text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th scope="col" className="sticky left-0 z-10 min-w-[18rem] bg-surface-muted px-3 py-3 font-semibold">Job Level</th>
                    <th scope="col" className="min-w-36 px-3 py-3 font-semibold">First Job</th>
                    <th scope="col" className="min-w-36 px-3 py-3 font-semibold">Current or Present Job</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {JOB_LEVEL_CHOICES.map((choice) => (
                    <tr key={choice.value}>
                      <th scope="row" className="sticky left-0 z-10 bg-surface-raised px-3 py-3 text-left font-medium text-ink">{choice.label}</th>
                      <td className="px-3 py-3"><input type="radio" name="gts-first-job-level" aria-label={`${choice.label} — First Job`} checked={draft.first_job_level === choice.value} onChange={() => onChange("first_job_level", choice.value)} className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" /></td>
                      <td className="px-3 py-3"><input type="radio" name="gts-current-job-level" aria-label={`${choice.label} — Current or Present Job`} checked={draft.current_job_level === choice.value} onChange={() => onChange("current_job_level", choice.value)} className="h-4 w-4 accent-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-5 max-w-2xl">
              <SelectField id="gts-initial-earning" label="Initial gross monthly earning in your first job after college" value={draft.initial_gross_monthly_earning} options={EARNING_BRACKET_CHOICES} onChange={(value) => onChange("initial_gross_monthly_earning", value)} />
            </div>
          </div>

          <div className="border-t border-border pt-6">
            <BooleanField
              id="gts-curriculum-relevant"
              legend="Was the curriculum you had in college relevant to your first job?"
              value={draft.curriculum_relevant_to_first_job}
              onChange={(value) => onChange("curriculum_relevant_to_first_job", value)}
            />
            {draft.curriculum_relevant_to_first_job === true ? (
              <div className="mt-5 max-w-3xl">
                <CheckboxField
                  id="gts-useful-competencies"
                  legend="What competencies learned in college did you find very useful in your first job?"
                  values={draft.useful_competencies}
                  options={USEFUL_COMPETENCY_CHOICES}
                  onChange={(values) => onChange("useful_competencies", values)}
                />
                {draft.useful_competencies?.includes("OTHER") ? (
                  <div className="mt-4">
                    <TextAreaField id="gts-useful-competencies-other" label="Please specify other skills" value={draft.useful_competencies_other} onChange={(value) => onChange("useful_competencies_other", value)} />
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </GraduateTracerSection>
  );
}

export function GraduateTracerCurriculumSection({
  draft,
  onChange,
}: {
  draft: GraduateTracerFormDraft;
  onChange: GraduateTracerDraftChange;
}) {
  return (
    <GraduateTracerSection id="graduate-tracer-curriculum" title="Curriculum Suggestions">
      <TextAreaField
        id="gts-curriculum-suggestions"
        label="List down suggestions to further improve your course curriculum."
        value={draft.curriculum_improvement_suggestions}
        onChange={(value) => onChange("curriculum_improvement_suggestions", value)}
      />
    </GraduateTracerSection>
  );
}
