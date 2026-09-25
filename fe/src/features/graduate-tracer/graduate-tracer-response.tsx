import {
  ADVANCED_STUDY_REASON_CHOICES,
  BUSINESS_LINE_CHOICES,
  CIVIL_STATUS_CHOICES,
  DEGREE_REASON_CHOICES,
  EARNING_BRACKET_CHOICES,
  EMPLOYMENT_STATE_CHOICES,
  FIRST_JOB_DURATION_CHOICES,
  FIRST_JOB_SOURCE_CHOICES,
  JOB_LEVEL_CHOICES,
  JOB_REASON_CHOICES,
  PLACE_OF_WORK_CHOICES,
  PRESENT_EMPLOYMENT_STATUS_CHOICES,
  REGION_CHOICES,
  RESIDENCE_LOCATION_CHOICES,
  SEX_CHOICES,
  STAYING_REASON_CHOICES,
  UNEMPLOYMENT_REASON_CHOICES,
  USEFUL_COMPETENCY_CHOICES,
  choiceLabel,
  choiceListLabel,
  formatGraduateTracerDate,
  yesNoLabel,
} from "@/features/graduate-tracer/graduate-tracer-presentation";
import { GraduateTracerAnswer, GraduateTracerSection } from "@/features/graduate-tracer/graduate-tracer-shared";
import type { GraduateTracerDetailResponse } from "@/lib/api/generated/model";

function Answers({ children }: { children: React.ReactNode }) {
  return <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">{children}</dl>;
}

function DataTable({
  caption,
  headers,
  rows,
}: {
  caption: string;
  headers: string[];
  rows: string[][];
}) {
  if (!rows.length) return <p className="text-sm text-muted">No entries provided.</p>;
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="min-w-[36rem] w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-surface-muted text-xs uppercase tracking-wide text-muted">
          <tr>{headers.map((header) => <th key={header} scope="col" className="px-3 py-3 font-semibold">{header}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row, index) => (
            <tr key={`${caption}-${row.join("-")}-${index}`}>
              {row.map((cell, cellIndex) => cellIndex === 0 ? (
                <th key={`${cellIndex}-${cell}`} scope="row" className="px-3 py-3 text-left font-medium text-ink">{cell || "Not provided"}</th>
              ) : (
                <td key={`${cellIndex}-${cell}`} className="px-3 py-3 align-top whitespace-pre-wrap text-ink">{cell || "Not provided"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function GraduateTracerResponse({ detail }: { detail: GraduateTracerDetailResponse }) {
  const degreeRows = DEGREE_REASON_CHOICES.map((choice) => [
    choice.label,
    detail.undergraduate_degree_reasons?.includes(choice.value) ? "Selected" : "Not selected",
    detail.graduate_study_reasons?.includes(choice.value) ? "Selected" : "Not selected",
  ]);

  const jobLevelRows = JOB_LEVEL_CHOICES.map((choice) => [
    choice.label,
    detail.first_job_level === choice.value ? "Selected" : "Not selected",
    detail.current_job_level === choice.value ? "Selected" : "Not selected",
  ]);

  const employed = detail.current_employment_state === "EMPLOYED";
  const unemployed = detail.current_employment_state === "NOT_EMPLOYED" || detail.current_employment_state === "NEVER_EMPLOYED";

  return (
    <div className="space-y-1">
      <GraduateTracerSection id="graduate-tracer-general" title="A. General Information">
        <Answers>
          <GraduateTracerAnswer label="Name" value={detail.name} />
          <GraduateTracerAnswer label="Permanent Address" value={detail.permanent_address} />
          <GraduateTracerAnswer label="E-mail Address" value={detail.email} />
          <GraduateTracerAnswer label="Telephone or Contact Number(s)" value={detail.telephone_contact_numbers} />
          <GraduateTracerAnswer label="Mobile Number" value={detail.mobile_number} />
          <GraduateTracerAnswer label="Civil Status" value={choiceLabel(detail.civil_status, CIVIL_STATUS_CHOICES)} />
          <GraduateTracerAnswer label="Sex" value={choiceLabel(detail.sex, SEX_CHOICES)} />
          <GraduateTracerAnswer label="Birthday" value={formatGraduateTracerDate(detail.birth_date)} />
          <GraduateTracerAnswer label="Region of Origin" value={choiceLabel(detail.region_of_origin, REGION_CHOICES)} />
          <GraduateTracerAnswer label="Province" value={detail.province} />
          <GraduateTracerAnswer label="Location of Residence" value={choiceLabel(detail.residence_location, RESIDENCE_LOCATION_CHOICES)} />
        </Answers>
      </GraduateTracerSection>

      <GraduateTracerSection id="graduate-tracer-education" title="B. Educational Background">
        <div>
          <h3 className="font-semibold text-ink">Q12. Educational Attainment (Baccalaureate Degree only)</h3>
          <div className="mt-3">
            <DataTable
              caption="Baccalaureate education history"
              headers={["Degree(s) & Specialization(s)", "College or University", "Year Graduated", "Honor(s) or Award(s) Received"]}
              rows={(detail.education ?? []).map((row) => [row.degree_and_specialization, row.college_or_university, String(row.year_graduated), row.honors_or_awards ?? ""])}
            />
          </div>
        </div>
        <div className="border-t border-border pt-5">
          <h3 className="font-semibold text-ink">Q13. Professional Examinations</h3>
          <div className="mt-3">
            <DataTable
              caption="Professional examination history"
              headers={["Name of Examination", "Date Taken", "Rating"]}
              rows={(detail.professional_exams ?? []).map((row) => [row.examination_name, formatGraduateTracerDate(row.date_taken), row.rating ?? ""])}
            />
          </div>
        </div>
        <div className="border-t border-border pt-5">
          <h3 className="font-semibold text-ink">Q14. Reasons for taking degree(s)</h3>
          <div className="mt-3">
            <DataTable
              caption="Selected reasons for undergraduate and graduate degrees"
              headers={["Reason", "Undergraduate / AB / BS", "Graduate / MS / MA / PhD"]}
              rows={degreeRows}
            />
          </div>
          <dl className="mt-4 max-w-3xl"><GraduateTracerAnswer label="Others, please specify" value={detail.degree_other_reason} /></dl>
        </div>
      </GraduateTracerSection>

      <GraduateTracerSection id="graduate-tracer-training" title="C. Training(s) / Advance Studies Attended After College">
        <div>
          <h3 className="font-semibold text-ink">Q15a. Training(s) / Advance Studies Attended After College</h3>
          <div className="mt-3">
            <DataTable
              caption="Training and advance studies history"
              headers={["Title of Training or Advance Study", "Duration and Credits Earned", "Name of Training Institution / College / University"]}
              rows={(detail.trainings ?? []).map((row) => [row.title, row.duration_and_credits ?? "", row.institution ?? ""])}
            />
          </div>
        </div>
        <div className="border-t border-border pt-5">
          <Answers>
            <GraduateTracerAnswer label="Q15b. Reasons for attending advance study" value={choiceListLabel(detail.advanced_study_reasons, ADVANCED_STUDY_REASON_CHOICES)} />
            <GraduateTracerAnswer label="Please specify" value={detail.advanced_study_other_reason} />
          </Answers>
        </div>
      </GraduateTracerSection>

      <GraduateTracerSection id="graduate-tracer-employment" title="D. Employment Data">
        <Answers>
          <GraduateTracerAnswer label="Q16. Are you presently employed?" value={choiceLabel(detail.current_employment_state, EMPLOYMENT_STATE_CHOICES)} />
        </Answers>

        {unemployed ? (
          <div className="border-t border-border pt-5">
            <Answers>
              <GraduateTracerAnswer label="Q17. Reasons not yet employed" value={choiceListLabel(detail.unemployment_reasons, UNEMPLOYMENT_REASON_CHOICES)} />
              <GraduateTracerAnswer label="Other reason(s)" value={detail.unemployment_other_reason} />
            </Answers>
          </div>
        ) : null}

        {employed ? (
          <>
            <div className="border-t border-border pt-5">
              <Answers>
                <GraduateTracerAnswer label="Q18. Present Employment Status" value={choiceLabel(detail.present_employment_status, PRESENT_EMPLOYMENT_STATUS_CHOICES)} />
                {detail.present_employment_status === "SELF_EMPLOYED" ? <GraduateTracerAnswer label="Skills acquired in college applied in self-employed work" value={detail.self_employed_college_skills} /> : null}
                <GraduateTracerAnswer label="Q19. Present Occupation" value={detail.present_occupation} />
                <GraduateTracerAnswer label="Q20. Major Line of Business" value={choiceLabel(detail.employer_business_line, BUSINESS_LINE_CHOICES)} />
                <GraduateTracerAnswer label="Q21. Place of Work" value={choiceLabel(detail.place_of_work, PLACE_OF_WORK_CHOICES)} />
                <GraduateTracerAnswer label="Q22. Is this your first job after college?" value={yesNoLabel(detail.first_job_after_college)} />
              </Answers>
            </div>

            {detail.first_job_after_college === true ? (
              <div className="border-t border-border pt-5">
                <Answers>
                  <GraduateTracerAnswer label="Reasons for staying on the job" value={choiceListLabel(detail.reasons_for_staying_on_job, STAYING_REASON_CHOICES)} />
                  <GraduateTracerAnswer label="Other reason(s) for staying" value={detail.reasons_for_staying_other} />
                  <GraduateTracerAnswer label="Is your first job related to the course you took up in college?" value={yesNoLabel(detail.first_job_related_to_course)} />
                </Answers>
              </div>
            ) : null}

            <div className="border-t border-border pt-5">
              <h3 className="font-semibold text-ink">First-job and job-change context</h3>
              <p className="mt-1 text-sm text-muted">Semantic fields from the survey&apos;s inconsistently numbered source area.</p>
              <div className="mt-4">
                <Answers>
                  <GraduateTracerAnswer label="Reasons for accepting the first job" value={choiceListLabel(detail.reasons_for_accepting_first_job, JOB_REASON_CHOICES)} />
                  <GraduateTracerAnswer label="Other reason(s) for accepting" value={detail.reasons_for_accepting_other} />
                  <GraduateTracerAnswer label="Reasons for changing job" value={choiceListLabel(detail.reasons_for_changing_job, JOB_REASON_CHOICES)} />
                  <GraduateTracerAnswer label="Other reason(s) for changing job" value={detail.reasons_for_changing_other} />
                  <GraduateTracerAnswer label="How long did you stay in your first job?" value={`${choiceLabel(detail.first_job_duration, FIRST_JOB_DURATION_CHOICES)}${detail.first_job_duration === "OTHER" && detail.first_job_duration_other ? ` — ${detail.first_job_duration_other}` : ""}`} />
                  <GraduateTracerAnswer label="How did you find your first job?" value={`${choiceLabel(detail.first_job_source, FIRST_JOB_SOURCE_CHOICES)}${detail.first_job_source === "OTHER" && detail.first_job_source_other ? ` — ${detail.first_job_source_other}` : ""}`} />
                  <GraduateTracerAnswer label="How long did it take you to land your first job?" value={`${choiceLabel(detail.time_to_first_job, FIRST_JOB_DURATION_CHOICES)}${detail.time_to_first_job === "OTHER" && detail.time_to_first_job_other ? ` — ${detail.time_to_first_job_other}` : ""}`} />
                </Answers>
              </div>
            </div>

            <div className="border-t border-border pt-5">
              <h3 className="font-semibold text-ink">Job level position</h3>
              <div className="mt-3">
                <DataTable caption="First and current job levels" headers={["Job Level", "First Job", "Current or Present Job"]} rows={jobLevelRows} />
              </div>
              <dl className="mt-4 max-w-3xl">
                <GraduateTracerAnswer label="Initial gross monthly earning in your first job after college" value={choiceLabel(detail.initial_gross_monthly_earning, EARNING_BRACKET_CHOICES)} />
              </dl>
            </div>

            <div className="border-t border-border pt-5">
              <Answers>
                <GraduateTracerAnswer label="Was the curriculum you had in college relevant to your first job?" value={yesNoLabel(detail.curriculum_relevant_to_first_job)} />
                {detail.curriculum_relevant_to_first_job === true ? (
                  <>
                    <GraduateTracerAnswer label="Useful competencies learned in college" value={choiceListLabel(detail.useful_competencies, USEFUL_COMPETENCY_CHOICES)} />
                    <GraduateTracerAnswer label="Other useful skills" value={detail.useful_competencies_other} />
                  </>
                ) : null}
              </Answers>
            </div>
          </>
        ) : null}
      </GraduateTracerSection>

      <GraduateTracerSection id="graduate-tracer-curriculum" title="Curriculum Suggestions">
        <GraduateTracerAnswer label="List down suggestions to further improve your course curriculum." value={detail.curriculum_improvement_suggestions} />
      </GraduateTracerSection>
    </div>
  );
}
