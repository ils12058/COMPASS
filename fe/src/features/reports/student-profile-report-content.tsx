import { Notice } from "@/components/ui/notice";
import { Panel, PanelHeader } from "@/components/ui/panel";
import type { StudentProfilingReportResponse } from "@/lib/api/generated/model";
import { StudentProfileContext } from "@/features/reports/student-profile-context";
import { StudentProfileCoverage } from "@/features/reports/student-profile-coverage";
import { StudentProfileGeographySection } from "@/features/reports/student-profile-geography-section";
import {
  ReportDisclosureNotice,
  reportDetails,
  reportStack,
} from "@/features/reports/reports-shared";
import {
  StudentProfileProgramLegend,
  StudentProfileSection,
} from "@/features/reports/student-profile-section";

type ProfileSectionKey =
  | "sex"
  | "age"
  | "civil_status"
  | "physical_disadvantage"
  | "current_religion"
  | "mother_life_status"
  | "father_life_status"
  | "parent_family_status"
  | "parent_annual_income"
  | "mother_occupation"
  | "father_occupation"
  | "living_condition";

const PROFILE_SECTION_GROUPS: {
  title: string;
  keys: ProfileSectionKey[];
}[] = [
  {
    title: "Demographics",
    keys: [
      "sex",
      "age",
      "civil_status",
      "physical_disadvantage",
      "current_religion",
    ],
  },
  {
    title: "Family & Household",
    keys: [
      "mother_life_status",
      "father_life_status",
      "parent_family_status",
      "parent_annual_income",
      "mother_occupation",
      "father_occupation",
      "living_condition",
    ],
  },
];

function groupId(title: string): string {
  return (
    "student-profile-group-" +
    title.toLowerCase().replaceAll(" ", "-").replaceAll("&", "and")
  );
}

export function StudentProfileReportContent({
  report,
  isGlobal,
  isFetching,
}: {
  report: StudentProfilingReportResponse;
  isGlobal: boolean;
  isFetching: boolean;
}) {
  return (
    <div aria-busy={isFetching} className={reportStack}>
      <StudentProfileContext report={report} isGlobal={isGlobal} />
      <ReportDisclosureNotice warnings={report.disclosure_warnings} />
      {report.report_context.submitted_inventory_count === 0 ? (
        <Notice>
          No submitted Individual Inventory records match the selected report filters.
        </Notice>
      ) : null}
      <StudentProfileCoverage
        coverage={report.inventory_coverage}
        methodology={report.methodology}
      />
      <StudentProfileProgramLegend columns={report.program_columns} />

      {PROFILE_SECTION_GROUPS.map((group) => (
        <Panel key={group.title} aria-labelledby={groupId(group.title)}>
          <PanelHeader title={group.title} titleId={groupId(group.title)} />
          {group.keys.map((key) => (
            <StudentProfileSection
              key={key}
              section={report.sections[key]}
              programColumns={report.program_columns}
            />
          ))}
        </Panel>
      ))}

      <Panel aria-labelledby="student-profile-residence-heading">
        <PanelHeader title="Residence" titleId="student-profile-residence-heading" />
        <StudentProfileGeographySection
          section={report.sections.city_municipality}
          programColumns={report.program_columns}
        />
      </Panel>

      <details className={reportDetails.root}>
        <summary className={reportDetails.summary}>
          How this report is calculated
        </summary>
        <dl className={reportDetails.body}>
          <div>
            <dt className="font-semibold text-ink">Profile population</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.profile_population_note}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-ink">Inventory Coverage</dt>
            <dd className="mt-1 text-muted">
              {report.methodology.coverage_note}
            </dd>
          </div>
        </dl>
      </details>
      <p className="text-xs leading-5 text-muted">
        Each export uses the selected filters and the records available when you download it.
      </p>
    </div>
  );
}
