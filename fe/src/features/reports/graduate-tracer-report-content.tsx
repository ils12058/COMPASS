import { Notice } from "@/components/ui/notice";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import type { GraduateTracerReportResponse } from "@/lib/api/generated/model";
import { GraduateTracerSection } from "@/features/reports/graduate-tracer-section";
import {
  ReportDisclosureNotice,
  reportDetails,
  reportStack,
} from "@/features/reports/reports-shared";
import { formatDateOnly, formatInstitutionalDateTime } from "@/lib/institutional-time";

type GraduateTracerSectionKey = keyof GraduateTracerReportResponse["sections"];

const GRADUATE_TRACER_GROUPS: {
  title: string;
  keys: GraduateTracerSectionKey[];
}[] = [
  {
    title: "Respondent Profile",
    keys: ["sex", "civil_status", "region_of_origin", "residence_location"],
  },
  {
    title: "Employment",
    keys: [
      "current_employment_state",
      "present_employment_status",
      "current_job_level",
      "place_of_work",
      "employer_business_line",
    ],
  },
  {
    title: "First Job",
    keys: [
      "first_job_after_college",
      "first_job_duration",
      "time_to_first_job",
      "first_job_level",
      "first_job_related_to_course",
      "first_job_source",
      "initial_gross_monthly_earning",
      "curriculum_relevant_to_first_job",
    ],
  },
  {
    title: "Reasons & Skills",
    keys: [
      "unemployment_reasons",
      "reasons_for_staying_on_job",
      "useful_competencies",
    ],
  },
];

function submittedPeriod(from: string | null, to: string | null): string {
  if (!from && !to) return "All submissions";
  if (from && to) {
    return formatDateOnly(from) + " to " + formatDateOnly(to);
  }
  return from
    ? "From " + formatDateOnly(from)
    : "Through " + formatDateOnly(to);
}

function groupId(title: string): string {
  return (
    "graduate-tracer-group-" +
    title.toLowerCase().replaceAll(" ", "-").replaceAll("&", "and")
  );
}

export function GraduateTracerReportContent({
  report,
  isFetching,
}: {
  report: GraduateTracerReportResponse;
  isFetching: boolean;
}) {
  return (
    <div aria-busy={isFetching} className={reportStack}>
      <Panel aria-labelledby="graduate-tracer-context-heading">
        <PanelHeader title="Report context" titleId="graduate-tracer-context-heading" />
        <PanelBody>
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
              Submitted Response Count
            </dt>
            <dd className="mt-1 text-sm font-medium text-ink">
              {report.report_context.submitted_response_count}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
              Submission Period
            </dt>
            <dd className="mt-1 text-sm font-medium text-ink">
              {submittedPeriod(
                report.report_context.submitted_from,
                report.report_context.submitted_to,
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
              Generated At
            </dt>
            <dd className="mt-1 text-sm font-medium text-ink">
              {formatInstitutionalDateTime(report.report_context.generated_at)}
            </dd>
          </div>
        </dl>
        </PanelBody>
      </Panel>
      <ReportDisclosureNotice warnings={report.disclosure_warnings} />
      {report.report_context.submitted_response_count === 0 ? (
        <Notice>
          No submitted Graduate Tracer responses match the selected submission period.
        </Notice>
      ) : null}

      {GRADUATE_TRACER_GROUPS.map((group) => (
        <Panel key={group.title} aria-labelledby={groupId(group.title)}>
          <PanelHeader title={group.title} titleId={groupId(group.title)} />
          {group.keys.map((key) => (
            <GraduateTracerSection
              key={key}
              section={report.sections[key]}
            />
          ))}
        </Panel>
      ))}

      <details className={reportDetails.root}>
        <summary className={reportDetails.summary}>
          How this report is calculated
        </summary>
        <dl className={reportDetails.body}>
          <div>
            <dt className="font-semibold text-ink">Population</dt>
            <dd className="mt-1 text-muted">{report.methodology.population}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Draft responses</dt>
            <dd className="mt-1 text-muted">{report.methodology.drafts}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Submission period</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.submission_period}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Response rate methodology</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.response_rate}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Academic grouping</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.academic_grouping}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Free-text fields</dt>
            <dd className="mt-1 text-muted">{report.methodology.free_text}</dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Multiple selections</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.multi_select}
            </dd>
          </div>
        </dl>
      </details>
    </div>
  );
}
