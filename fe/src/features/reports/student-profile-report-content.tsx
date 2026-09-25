import type { StudentProfilingReportResponse } from "@/lib/api/generated/model";
import { StudentProfileContext } from "@/features/reports/student-profile-context";
import { StudentProfileCoverage } from "@/features/reports/student-profile-coverage";
import { StudentProfileGeographySection } from "@/features/reports/student-profile-geography-section";
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
    <div aria-busy={isFetching}>
      <StudentProfileContext report={report} isGlobal={isGlobal} />
      {report.report_context.submitted_inventory_count === 0 ? (
        <p className="mt-5 border-l-2 border-border pl-3 text-sm leading-6 text-muted">
          No submitted Individual Inventories match the selected report context.
        </p>
      ) : null}
      <StudentProfileCoverage
        coverage={report.inventory_coverage}
        methodology={report.methodology}
      />
      <StudentProfileProgramLegend columns={report.program_columns} />

      {PROFILE_SECTION_GROUPS.map((group) => (
        <section
          key={group.title}
          aria-labelledby={groupId(group.title)}
          className="mt-9"
        >
          <h2
            id={groupId(group.title)}
            className="font-heading text-xl font-semibold text-ink"
          >
            {group.title}
          </h2>
          {group.keys.map((key) => (
            <StudentProfileSection
              key={key}
              section={report.sections[key]}
              programColumns={report.program_columns}
            />
          ))}
        </section>
      ))}

      <section
        aria-labelledby="student-profile-residence-heading"
        className="mt-9"
      >
        <h2
          id="student-profile-residence-heading"
          className="font-heading text-xl font-semibold text-ink"
        >
          Residence
        </h2>
        <StudentProfileGeographySection
          section={report.sections.city_municipality}
          programColumns={report.program_columns}
        />
      </section>

      <details className="mt-9 border-y border-border py-4">
        <summary className="cursor-pointer font-semibold text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
          How this report is calculated
        </summary>
        <dl className="mt-4 space-y-4 text-sm leading-6">
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
      <p className="mt-4 text-xs leading-5 text-muted">
        Exports are regenerated on demand using this displayed filter context;
        they are not immutable snapshots.
      </p>
    </div>
  );
}
