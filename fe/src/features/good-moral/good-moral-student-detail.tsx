"use client";

import Link from "next/link";

import { Notice } from "@/components/ui/notice";
import { pageBackLinkClass } from "@/components/ui/page-header";
import { Panel, PanelSection, RecordSummary, type RecordFact } from "@/components/ui/panel";
import { safeQueryData } from "@/features/freshness/query-freshness";
import { RefreshFailureNotice } from "@/features/freshness/refresh-failure-notice";
import { GoodMoralCancelAction } from "@/features/good-moral/good-moral-cancellation-action";
import { GoodMoralPdfDownload } from "@/features/good-moral/good-moral-pdf";
import {
  GoodMoralDetailSkeleton,
  GoodMoralError,
  GoodMoralField,
  GoodMoralHeading,
  GoodMoralSection,
  GoodMoralStatus,
  formatGoodMoralAmount,
  formatGoodMoralDate,
  formatGoodMoralDateTime,
  goodMoralErrorCode,
  goodMoralVariantLabel,
} from "@/features/good-moral/good-moral-shared";
import { useGoodMoralGetMyRequest } from "@/lib/api/generated/good-moral/good-moral";

const factGrid = "grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3";

export function GoodMoralStudentDetail({
  requestId,
  canCancel,
}: {
  requestId: string;
  canCancel: boolean;
}) {
  const detail = useGoodMoralGetMyRequest(requestId, { query: { retry: false } });
  const confirmed = safeQueryData(detail);

  if (detail.isPending) {
    return <GoodMoralDetailSkeleton />;
  }
  if (!confirmed) {
    const notFound = goodMoralErrorCode(detail.error) === "good_moral_not_found";
    return (
      <section className="max-w-2xl space-y-5">
        <Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral</Link>
        {notFound ? <Notice role="alert" title={<h1 className="font-heading text-2xl font-semibold text-ink">Good Moral request not found</h1>} /> : <GoodMoralError error={detail.error} fallback="Your Good Moral request could not be loaded." onRetry={() => void detail.refetch()} />}
      </section>
    );
  }

  const item = confirmed.data;
  const refresh = async () => {
    const result = await detail.refetch();
    return result.isError ? undefined : result.data?.data;
  };
  const keyFacts: RecordFact[] = [
    { label: "Requested", value: formatGoodMoralDateTime(item.created_at) },
    ...(item.issued_at ? [{ label: "Issued", value: formatGoodMoralDateTime(item.issued_at) }] : []),
    ...(item.cancelled_at ? [{ label: "Cancelled", value: formatGoodMoralDateTime(item.cancelled_at) }] : []),
  ];
  const hasReceipt = Boolean(item.official_receipt_number || item.official_receipt_date || item.official_receipt_amount !== null);

  return (
    <section className="space-y-5" aria-labelledby="good-moral-student-detail-heading">
      {detail.isError ? <RefreshFailureNotice onRetry={() => void detail.refetch()} retrying={detail.isFetching} /> : null}
      <GoodMoralHeading
        headingId="good-moral-student-detail-heading"
        title="Good Moral request"
        description={item.status === "ISSUED" ? `${goodMoralVariantLabel(item.variant)} certificate` : `${goodMoralVariantLabel(item.variant)} request`}
        back={<Link href="/portal/good-moral" className={pageBackLinkClass}>Back to Good Moral</Link>}
      />

      <Panel aria-labelledby="good-moral-student-applicant">
        <RecordSummary
          label="Applicant name"
          title={item.applicant_name?.trim() || "Not provided"}
          titleId="good-moral-student-applicant"
          status={<GoodMoralStatus status={item.status} />}
          facts={keyFacts}
        />
        <PanelSection title="Request details" titleId="good-moral-student-request-details">
          <dl className={factGrid}>
            {item.variant === "CURRENT_STUDENT" ? (
              <>
                <GoodMoralField label="Year level" value={item.year_level} />
                <GoodMoralField label="College" value={item.college} />
                <GoodMoralField label="Course" value={item.course} />
                <GoodMoralField label="Major" value={item.major} />
                <GoodMoralField label="Semester" value={item.semester} />
                <GoodMoralField label="Academic Year" value={item.academic_year?.label} />
              </>
            ) : (
              <>
                <GoodMoralField label="Degree" value={item.degree} />
                <GoodMoralField label="Major" value={item.major} />
                <GoodMoralField label="Graduation date" value={formatGoodMoralDate(item.graduation_date)} />
              </>
            )}
          </dl>
        </PanelSection>
        {hasReceipt ? (
          <PanelSection title="Official Receipt" titleId="good-moral-student-receipt">
            <dl className={factGrid}>
              <GoodMoralField label="Receipt number" value={item.official_receipt_number} />
              <GoodMoralField label="Receipt date" value={formatGoodMoralDate(item.official_receipt_date)} />
              <GoodMoralField label="Receipt amount" value={formatGoodMoralAmount(item.official_receipt_amount)} />
            </dl>
          </PanelSection>
        ) : null}
      </Panel>

      {item.status === "ISSUED" ? (
        <GoodMoralSection title="Certificate issuance">
          <dl className={factGrid}>
            <GoodMoralField label="Issued by" value={item.issued_by_name_snapshot} />
            <GoodMoralField label="Official form code" value={item.form_revision?.official_code} />
            <GoodMoralField label="Official revision" value={item.form_revision?.official_revision ? `Revision ${item.form_revision.official_revision}` : null} />
          </dl>
          <div className="mt-5 border-t border-border pt-4">
            <GoodMoralPdfDownload requestId={item.id} studentFacing />
          </div>
        </GoodMoralSection>
      ) : null}

      {(item.status === "REQUESTED" || item.status === "READY_FOR_ISSUANCE") && canCancel && !detail.isError ? (
        <GoodMoralSection title="Request actions">
          <GoodMoralCancelAction requestId={item.id} studentFacing onRefresh={refresh} />
        </GoodMoralSection>
      ) : null}
    </section>
  );
}
