"use client";

import Link from "next/link";
import { Pencil } from "lucide-react";
import { PageActionLink } from "@/components/ui/page-action";
import { PageHeader, pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection, RecordSummary } from "@/components/ui/panel";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { usePortalSession } from "@/features/portal/components/portal-session";
import { useAssessmentRecordsGet } from "@/lib/api/generated/assessment-records/assessment-records";
import {
  formatDateOnly,
  formatInstitutionalDateTime,
} from "@/lib/institutional-time";
import { getAssessmentRecordsAccess } from "./assessment-records-access";
import {
  assessmentContentFields,
  AssessmentError,
  AssessmentLoading,
  safeAssessmentDetail,
} from "./assessment-records-shared";

export function AssessmentRecordDetailPage({ recordId }: { recordId: string }) {
  const { user } = usePortalSession();
  const access = getAssessmentRecordsAccess(user);
  const query = useAssessmentRecordsGet(recordId, {
    query: { enabled: access.canView, retry: false },
  });
  const record = safeAssessmentDetail(query)?.data;
  return (
    <>
      <PageHeader
        title="Assessment Record"
        back={
          <Link href="/portal/assessment-records" className={pageBackLinkClass}>
            Back to Assessment Records
          </Link>
        }
        actions={
          record && access.canManage ? (
            <PageActionLink
              href={`/portal/assessment-records/${record.id}/edit`}
              icon={Pencil}
              label="Edit record"
              labelDetail="assessment"
            />
          ) : undefined
        }
      />
      {!record ? (
        query.isPending ? (
          <AssessmentLoading />
        ) : (
          <AssessmentError
            error={query.error}
            retry={() => void query.refetch()}
            pending={query.isFetching}
          />
        )
      ) : (
        <>
          {query.isError ? (
            <RefreshFailureNotice
              onRetry={() => void query.refetch()}
              retrying={query.isFetching}
            />
          ) : null}
          <Panel aria-labelledby="assessment-student">
            <RecordSummary
              label="Student"
              title={record.student.display_name}
              titleId="assessment-student"
              facts={[
                {
                  label: "Institutional ID",
                  value: record.student.institutional_id ?? "Not available",
                },
                {
                  label: "Assessment Type",
                  value: (
                    <>
                      {record.assessment_type.name}
                      {!record.assessment_type.is_active ? (
                        <span className="block text-xs text-muted">
                          Inactive type · historical record
                        </span>
                      ) : null}
                    </>
                  ),
                },
                {
                  label: "Administered on",
                  value: formatDateOnly(record.administered_on),
                },
                {
                  label: "Recorded by",
                  value: record.recorded_by.display_name,
                },
              ]}
            />
            <PanelSection
              title="Assessment result"
              titleId="assessment-content"
              description="Confidential institutional record. Score and interpretation are recorded as supplied by the Guidance Office."
            >
              <dl className="space-y-5">
                {assessmentContentFields.map((field) => (
                  <div key={field.key}>
                    <dt className="text-sm font-semibold text-ink">
                      {field.label}
                    </dt>
                    <dd className="mt-1 whitespace-pre-wrap [overflow-wrap:anywhere] text-sm leading-6 text-ink">
                      {record[field.key].trim() ? (
                        record[field.key]
                      ) : (
                        <span className="text-muted">Not recorded</span>
                      )}
                    </dd>
                  </div>
                ))}
              </dl>
            </PanelSection>
            <PanelSection title="Record history" titleId="assessment-history">
              <dl className="grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-semibold text-muted">Recorded</dt>
                  <dd className="mt-1 text-sm">
                    {formatInstitutionalDateTime(record.created_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-semibold text-muted">
                    Last corrected
                  </dt>
                  <dd className="mt-1 text-sm">
                    {formatInstitutionalDateTime(record.updated_at)}
                  </dd>
                </div>
              </dl>
            </PanelSection>
          </Panel>
        </>
      )}
    </>
  );
}
